#!/usr/bin/env python
"""
每日收盘数据采集 + 增量入库
交易日15:30运行，把当天收盘数据存进 data_cache
同时把新浪2:50拉过的实时数据存进 data_sina
"""
import sqlite3, os, sys, json, time, subprocess
from datetime import datetime, timedelta

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
sys.path.insert(0, SCRIPTS_DIR)
from db_config import get_config, get_path_config

def get_today_close_from_tencent(code):
    """从腾讯API获取当日收盘数据"""
    pref = 'sh' if code.startswith(('6','9')) else 'sz'
    url = f'http://qt.gtimg.cn/q={pref}{code}'
    try:
        r = subprocess.run(['curl', '-s', '--max-time', '5', url],
                          capture_output=True, timeout=8)
        text = r.stdout.decode('gbk', errors='ignore')
        if '=' not in text or '~' not in text:
            return None
        
        parts = text.split('~')
        if len(parts) < 40:
            return None
        
        return {
            'name': parts[1],
            'code': code,
            'price': float(parts[3]) if parts[3] else 0,
            'pre_close': float(parts[4]) if parts[4] else 0,
            'open': float(parts[5]) if parts[5] else 0,
            'high': float(parts[33]) if len(parts) > 33 and parts[33] else 0,
            'low': float(parts[34]) if len(parts) > 34 and parts[34] else 0,
            'volume': float(parts[6]) if parts[6] else 0,
            'amount': float(parts[37]) if len(parts) > 37 and parts[37] else 0,
            'pct': float(parts[39]) if len(parts) > 39 and parts[39] else 0,
            # ⭐ 新增：每天自动刷新HSL/PE/市值
            'hsl': float(parts[38]) if len(parts) > 38 and parts[38] else 0,
            'pe': float(parts[39]) if len(parts) > 39 and parts[39] else 0,
            'shizhi': float(parts[44]) if len(parts) > 44 and parts[44] else 0,
            'liangbi': float(parts[46]) if len(parts) > 46 and parts[46] else 0,
        }
    except:
        return None

def check_missing_and_backfill():
    """检查14:50漏拉的股票，在15:30收盘后补齐"""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 查14:50哪些股票已经拉到了
    c.execute('SELECT DISTINCT code FROM data_sina WHERE date=?', (today,))
    sina_codes = set(r[0] for r in c.fetchall())
    
    # 查data_cache今天已有的
    c.execute('SELECT DISTINCT code FROM data_cache WHERE date=?', (today,))
    cache_codes = set(r[0] for r in c.fetchall())
    
    # 缺了哪些股票
    missing = set()
    if sina_codes:
        missing = sina_codes - cache_codes
        print(f'  14:50拉到 {len(sina_codes)} 只, data_cache已有 {len(cache_codes)} 只')
        print(f'  需要补齐: {len(missing)} 只')
    
    # 还缺的技术指标（从big_cache补充）
    c.execute('SELECT DISTINCT code FROM data_cache WHERE date=? AND dif_val=0 AND wr_val=50', (today,))
    no_tech = set(r[0] for r in c.fetchall())
    print(f'  缺技术指标: {len(no_tech)} 只')
    
    conn.close()
    return len(missing), len(no_tech)

def save_today_close():
    """保存今天收盘数据到 data_cache + 补充14:50缺口"""
    today = datetime.now().strftime('%Y-%m-%d')
    now_str = datetime.now().strftime('%H:%M:%S')
    
    # 先检查14:50的缺口
    print('\n① 检查14:50数据缺口...')
    missing_count, no_tech_count = check_missing_and_backfill()
    
    # 加载股票池
    pool_file = get_config('path', 'stock_pool')
    if not pool_file or not os.path.exists(pool_file):
        print(f'⚠️ 未找到股票池文件')
        return 0, 0, 0
    
    with open(pool_file, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    
    codes = [s['code'] if isinstance(s, dict) else s for s in pool]
    codes = [c for c in codes if c.startswith(('600','601','603','605','000','001','002'))]
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 查今天已有数据（跳过已入库的）
    c.execute('SELECT code FROM data_cache WHERE date=?', (today,))
    existing = set(r[0] for r in c.fetchall())
    
    # 排除剔除清单
    try:
        exc = set(r[0] for r in c.execute('SELECT code FROM excluded_stocks WHERE active=1').fetchall())
    except:
        exc = set()
    # 只拉缺失的（跳过剔除清单）
    to_fetch = [c for c in codes if c not in existing and c not in exc]
    print(f'\n② 补缺 {len(to_fetch)} 只股票(已有{len(existing)}只, 剔除{len(exc)}只)...')
    
    if not to_fetch:
        print('  所有股票已有数据，无需补充')
    else:
        saved = 0
        total = len(to_fetch)
        t0 = time.time()
        
        BATCH = 50
        for i in range(0, len(to_fetch), BATCH):
            batch = to_fetch[i:i+BATCH]
            for code in batch:
                try:
                    data = get_today_close_from_tencent(code)
                    if not data or data['price'] <= 0:
                        continue
                    
                    p = data['pct']
                    close = data['price']
                    high = data['high'] or close
                    low = data['low'] or close
                    cl = round((close - low) / (high - low) * 100, 2) if (high - low) > 0 else 50
                    
                    c.execute('''
                        INSERT OR IGNORE INTO data_cache
                        (date, code, name, p, cl, vr, n,
                         dif_val, macd_golden, wr_val, j_val, k_val, d_val,
                         pos_in_day, above_ma5, kdj_golden,
                         close, volume, original_source, cache_version)
                        VALUES (?,?,?,?,?,?,0,
                                0,0,50,50,50,50,
                                50,0,0,
                                ?,?,?,?)
                    ''', (today, code, data['name'],
                          round(p, 2), cl, round(data.get('liangbi', 0) or 0, 2),
                          round(close, 2), round(data['volume'], 0),
                          'tencent:qt.gtimg.cn', today))
                    
                    # 同步刷新股票信息
                    c.execute('''
                        INSERT OR REPLACE INTO data_stock_info
                        (code, name, hsl, pe, shizhi, liangbi, price, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (code, data['name'],
                          data.get('hsl', 0), data.get('pe', 0),
                          data.get('shizhi', 0), data.get('liangbi', 0),
                          close, f'{today} {now_str}'))
                    saved += 1
                except:
                    pass
            
            conn.commit()
            pct = min(100, (i + BATCH) * 100 // len(to_fetch)) if to_fetch else 100
            print(f'  进度: {pct:>3}% | 已补: {saved}/{total}')
        
        print(f'  补充完成: {saved}/{total}')
    
    # ③ 对比2:50价格 vs 收盘价
    print('\n③ 比较14:50价格 vs 收盘价差...')
    c.execute('''
        SELECT ds.code, ds.pct as sina_pct, dc.p as close_pct
        FROM data_sina ds
        JOIN data_cache dc ON dc.date=ds.date AND dc.code=ds.code
        WHERE ds.date=? AND dc.p IS NOT NULL
        LIMIT 10
    ''', (today,))
    diffs = []
    for r in c.fetchall():
        if r[1] and r[2]:
            diffs.append(abs(r[1] - r[2]))
    
    if diffs:
        avg_diff = sum(diffs) / len(diffs)
        max_diff = max(diffs)
        print(f'  采样10只: 平均价差={avg_diff:.2f}% 最大价差={max_diff:.2f}%')
    
    conn.close()
    
    # 统计
    c2 = sqlite3.connect(DB_PATH)
    cnt = c2.execute('SELECT COUNT(*) FROM data_cache WHERE date=?', (today,)).fetchone()[0]
    c2.close()
    
    print(f'\n✅ {today} 收盘入库: data_cache共{cnt}只')
    return cnt, missing_count, no_tech_count

def save_sina_realtime(all_real):
    """把2:50新浪实时数据存进data_sina表（由V13_生产.py调用）"""
    today = datetime.now().strftime('%Y-%m-%d')
    now_str = datetime.now().strftime('%H:%M:%S')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    saved = 0
    for full_code, real in all_real.items():
        code = full_code[2:] if full_code.startswith(('sh','sz')) else full_code
        try:
            c.execute('''
                INSERT OR IGNORE INTO data_sina
                (date, time, code, name, price, pre_close, pct,
                 high, low, volume, amount, api_endpoint)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (today, now_str, code,
                  real.get('name', ''),
                  real.get('price', 0),
                  real.get('pre_close', 0),
                  real.get('pct', 0),
                  real.get('high', 0),
                  real.get('low', 0),
                  real.get('volume', 0),
                  real.get('amount', 0),
                  'hq.sinajs.cn'))
            saved += 1
        except:
            pass
    
    conn.commit()
    conn.close()
    return saved

if __name__ == '__main__':
    print(f'📡 每日数据采集 {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*55}')
    
    print()
    print('① 保存今天收盘数据...')
    save_today_close()

    # 刷新ST剔除清单
    print()
    print('② 刷新ST剔除清单...')
    try:
        from refresh_excluded import refresh_st_excluded
        n = refresh_st_excluded()
        print(f'  ST剔除清单: 更新{n}只' if n else '  ST剔除清单: 无变化')
    except Exception as e:
        print(f'  ST刷新跳过: {e}')
    
    # 查看数据库规模
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for tbl in ['data_cache', 'data_sina', 'selection_pool']:
        try:
            cnt = c.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]
            c.execute(f'SELECT MIN(date) FROM {tbl}')
            dr = c.fetchone()
            print(f'  {tbl:>20}: {cnt:>8}行  {dr[0] if dr else "-"}')
        except:
            pass
    conn.close()
    
    print(f'\n✅ 采集完成')
