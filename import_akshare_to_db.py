#!/usr/bin/env python
"""
高性能历史数据导入：akshare批量拉 + 直接写SQLite
特点：
- 边拉边写，不占用大量内存
- 分批入库，每批100只股票
- 断点续传（已存在的日期自动跳过）
- WAL模式提升写入速度
"""
import sqlite3, os, sys, time, json
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
POOL_FILE = os.path.join(SCRIPTS_DIR, '活跃股票池_3043.json')

def init_db():
    """确保表存在 + 开WAL模式加速"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')       # 读写不互斥
    conn.execute('PRAGMA synchronous=OFF')         # 导入时关同步加速
    conn.execute('PRAGMA cache_size=-80000')       # 80MB缓存
    conn.execute('PRAGMA temp_store=MEMORY')
    conn.commit()
    return conn

def load_pool():
    """加载股票池"""
    if os.path.exists(POOL_FILE):
        with open(POOL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    # 如果没有股票池文件，用V13的big_cache中的股票列表
    print('⚠️ 未找到活跃股票池文件')
    return None

def get_existing_dates(conn):
    """查询已有数据日期（断点续传用）"""
    c = conn.cursor()
    c.execute('SELECT DISTINCT date FROM data_cache ORDER BY date')
    return set(r[0] for r in c.fetchall())

def fetch_and_store(stock_codes, conn, batch_size=100):
    """批量拉取历史K线 + 直接写入SQLite"""
    try:
        import akshare as ak
    except ImportError:
        print('❌ akshare未安装，尝试 pip install akshare')
        os.system(f'{sys.executable} -m pip install akshare -q')
        import akshare as ak
    
    existing_dates = get_existing_dates(conn)
    c = conn.cursor()
    
    total_codes = len(stock_codes)
    total_rows = 0
    t_start = time.time()
    
    for batch_idx in range(0, total_codes, batch_size):
        batch = stock_codes[batch_idx:batch_idx + batch_size]
        t_batch = time.time()
        
        for code in batch:
            try:
                # 东方财富K线
                mkt = '1' if code.startswith(('6','9')) else '0'
                df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                         start_date="20250101", end_date="20260601",
                                         adjust="qfq")
                if df is None or df.empty:
                    continue
                
                rows = []
                for _, row in df.iterrows():
                    dt = str(row['日期'])[:10]
                    if dt in existing_dates:
                        continue  # 已有，跳过
                    
                    pct = float(row.get('涨跌幅', 0) or 0)
                    close = float(row.get('收盘', 0) or 0)
                    pre_close = close / (1 + pct/100) if pct != 0 else close
                    high = float(row.get('最高', 0) or 0)
                    low = float(row.get('最低', 0) or 0)
                    volume = float(row.get('成交量', 0) or 0)
                    amount = float(row.get('成交额', 0) or 0)
                    
                    # 计算CL（价格在当天区间的位置）
                    cl = round((close - low) / (high - low) * 100, 2) if (high - low) > 0 else 50
                    
                    rows.append((
                        dt, code, str(row.get('名称', '')),
                        round(pct, 2), cl,
                        round(float(row.get('换手率', 0) or 0), 2),
                        0,  # n（次日最高），后面再计算
                        round(float(row.get('量比', 1) or 1), 2),
                        0, 0, 50, 50, 50, 50,  # dif, macd, wr, j, k, d（跨日指标后面算）
                        50, 0, 0,  # pos_in_day, ma5, kdj
                        round(close, 2), round(volume, 0),
                        'eastmoney:akshare'
                    ))
                    existing_dates.add(dt)
                
                if rows:
                    c.executemany('''
                        INSERT OR IGNORE INTO data_cache
                        (date, code, name, p, cl, vr, n, vol_ratio,
                         dif_val, macd_golden, wr_val, j_val, k_val, d_val,
                         pos_in_day, above_ma5, kdj_golden,
                         close, volume, original_source)
                        VALUES (?,?,?,?,?,?,?,?,
                                ?,?,?,?,?,?,
                                ?,?,?,
                                ?,?,?)
                    ''', rows)
                    total_rows += len(rows)
                
            except Exception as e:
                print(f'  ⚠️ {code} 失败: {str(e)[:50]}')
                continue
        
        # 每批提交一次
        conn.commit()
        
        # 显示进度
        elapsed = time.time() - t_batch
        batch_pct = min(100, (batch_idx + batch_size) * 100 // total_codes)
        total_elapsed = time.time() - t_start
        rate = total_rows / total_elapsed if total_elapsed > 0 else 0
        print(f'  进度: {batch_pct}% | 本批: {len(batch)}只/{elapsed:.0f}s | 总计: {total_rows}行 | {rate:.0f}行/秒')
    
    return total_rows

def compute_n_values(conn):
    """计算n值（次日最高涨幅）"""
    print('\n计算次日最高涨幅(n值)...')
    c = conn.cursor()
    c.execute('SELECT DISTINCT date FROM data_cache ORDER BY date')
    dates = [r[0] for r in c.fetchall()]
    
    updated = 0
    for i, dt in enumerate(dates[:-1]):  # 最后一天没有次日数据
        next_dt = dates[i + 1]
        # 获取今日收盘/最高和明日最高
        c.execute('''
            SELECT dc.code, dc.close, dc_tr.close as next_close,
                   dc_tr.high as next_high
            FROM data_cache dc
            LEFT JOIN data_cache dc_tr ON dc_tr.date=? AND dc_tr.code=dc.code
            WHERE dc.date=?
        ''', (next_dt, dt))
        
        for row in c.fetchall():
            code, close, next_close, next_high = row
            if close and close > 0 and next_high and next_high > 0:
                n = round((next_high - close) / close * 100, 2)
                c.execute('UPDATE data_cache SET n=? WHERE date=? AND code=?',
                         (n, dt, code))
                updated += 1
    
    conn.commit()
    print(f'  ✅ 已计算 {updated} 条n值')

def compute_tech_indicators(conn):
    """计算技术指标(WMA/MACD/WR/KDJ)"""
    print('\n计算技术指标...')
    c = conn.cursor()
    c.execute('SELECT DISTINCT code FROM data_cache ORDER BY code')
    codes = [r[0] for r in c.fetchall()]
    
    for idx, code in enumerate(codes):
        c.execute('''
            SELECT date, close, high, low
            FROM data_cache WHERE code=? ORDER BY date
        ''', (code,))
        rows = c.fetchall()
        if len(rows) < 20:
            continue
        
        closes = [r[1] for r in rows]
        highs = [r[2] for r in rows]
        lows = [r[3] for r in rows]
        dates = [r[0] for r in rows]
        
        # 计算WMA
        wma_period = 5
        wmas = []
        for i in range(len(closes)):
            if i < wma_period - 1:
                wmas.append(None)
            else:
                weights = sum(j+1 for j in range(wma_period))
                wma = sum(closes[i-wma_period+1+j] * (j+1) for j in range(wma_period)) / weights
                wmas.append(round(wma, 2))
        
        # KDJ
        k_values = [50]
        d_values = [50]
        for i in range(1, len(closes)):
            if i < 8:
                k_values.append(50)
                d_values.append(50)
                continue
            h9 = max(highs[i-8:i+1])
            l9 = min(lows[i-8:i+1])
            rsv = (closes[i] - l9) / (h9 - l9) * 100 if (h9 - l9) > 0 else 50
            k = 2/3 * k_values[-1] + 1/3 * rsv
            d = 2/3 * d_values[-1] + 1/3 * k
            k_values.append(round(k, 2))
            d_values.append(round(d, 2))
        
        # WR
        wr_values = []
        for i in range(len(closes)):
            if i < 13:
                wr_values.append(50)
                continue
            h14 = max(highs[i-13:i+1])
            l14 = min(lows[i-13:i+1])
            wr = (h14 - closes[i]) / (h14 - l14) * 100 if (h14 - l14) > 0 else 50
            wr_values.append(round(wr, 2))
        
        # 批量写入
        updates = []
        for i, dt in enumerate(dates):
            wr = wr_values[i] if i < len(wr_values) else 50
            jv = k_values[i] if i < len(k_values) else 50
            kv = k_values[i] if i < len(k_values) else 50
            dv = d_values[i] if i < len(d_values) else 50
            
            updates.append((wr, jv, kv, dv, dt, code))
        
        c.executemany('''
            UPDATE data_cache SET 
            wr_val=?, j_val=?, k_val=?, d_val=?
            WHERE date=? AND code=?
        ''', updates)
        
        if (idx + 1) % 500 == 0:
            conn.commit()
            print(f'  技术指标: {idx+1}/{len(codes)}')
    
    conn.commit()
    print(f'  ✅ 已完成 {len(codes)} 只股票的技术指标')

def main():
    print(f'{"="*60}')
    print(f'  🚀 历史数据导入: akshare → SQLite')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*60}')
    
    conn = init_db()
    
    # 加载股票池
    pool = load_pool()
    if pool and isinstance(pool, list):
        stock_codes = [s.get('code', s) if isinstance(s, dict) else s for s in pool]
        stock_codes = [c for c in stock_codes if c.startswith(('600','601','603','605','000','001','002'))]
    else:
        # 手动生成
        stock_codes = []
        for prefix in ['600','601','603','605','000','001','002']:
            for suffix in range(1, 1000):
                stock_codes.append(f'{prefix}{suffix:03d}')
        stock_codes = stock_codes[:3043]
    
    print(f'股票池: {len(stock_codes)}只')
    
    t0 = time.time()
    
    # 1. 拉取数据
    print('\n① 开始拉取历史K线数据...')
    total = fetch_and_store(stock_codes, conn, batch_size=50)
    
    # 2. 计算n值
    print('\n② 计算次日最高涨幅...')
    compute_n_values(conn)
    
    # 3. 计算技术指标
    print('\n③ 计算技术指标...')
    compute_tech_indicators(conn)
    
    # 4. 统计
    c = conn.cursor()
    cnt = c.execute('SELECT COUNT(*) FROM data_cache').fetchone()[0]
    c.execute('SELECT MIN(date), MAX(date) FROM data_cache')
    dr = c.fetchone()
    
    print(f'\n{"="*60}')
    print(f'  ✅ 导入完成')
    print(f'  data_cache: {cnt}行')
    print(f'  日期范围: {dr[0]} ~ {dr[1]}')
    print(f'  耗时: {time.time()-t0:.0f}秒')
    print(f'{"="*60}')
    
    conn.close()

if __name__ == '__main__':
    main()
