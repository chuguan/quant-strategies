#!/usr/bin/env python3
"""
全面补全 data_cache + features_cache
1. 找出所有日期缺失的股票（对照活跃股票池_3043.json）
2. 从腾讯K线API拉历史数据补全
3. 计算动量特征（slope5/t4_shadow等）补到features_cache
"""
import sqlite3, os, json, subprocess, time, pickle
from datetime import datetime

SCRIPTS = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS, 'v13_quant.db')

def curl(url, timeout=10):
    try:
        r = subprocess.run(['curl', '-sL', '--max-time', str(timeout), url,
                          '-H', 'User-Agent: Mozilla/5.0'], capture_output=True, timeout=timeout+5)
        return r.stdout
    except: return b''

def prefix(code):
    return 'sh' if code.startswith(('6','9')) else 'sz'

def get_kline_day(code, days=60):
    """获取日K线数据"""
    pref = prefix(code)
    url = f'http://ifzq.gtimg.cn/appstock/app/kline/mkline?param={pref}{code},day,,,{days}'
    raw = curl(url, timeout=8)
    try:
        d = json.loads(raw)
        key = f'{pref}{code}'
        day_data = d.get('data', {}).get(key, {}).get('day', [])
        if not day_data and 'qt' in d.get('data', {}).get(key, {}):
            # 备选格式
            day_data = d['data'][key].get('qt', {}).get('day', [])
        return day_data
    except: return []

def get_daily_close(code, target_date):
    """从日K线中提取指定日期的收盘数据"""
    klines = get_kline_day(code, 30)
    for k in klines:
        if len(k) >= 6:
            k_date = k[0][:10]  # "2026-05-25"
            if k_date == target_date:
                return {
                    'close': float(k[2]),   # close
                    'high': float(k[3]),    # high
                    'low': float(k[4]),     # low
                    'open': float(k[1]),    # open
                    'volume': float(k[5]),  # volume
                }
    return None

def compute_p(cl, pre_close):
    return round((cl - pre_close) / pre_close * 100, 2) if pre_close > 0 else 0

def compute_cl(close, low, high):
    return round((close - low) / (high - low) * 100, 2) if (high - low) > 0 else 50

def get_prev_close(data_cache, code, dt):
    """获取前一个交易日的收盘价"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 找dt之前最近的交易日
    c.execute('SELECT DISTINCT date FROM data_cache WHERE date < ? ORDER BY date DESC LIMIT 1', (dt,))
    prev = c.fetchone()
    if prev:
        c.execute('SELECT close FROM data_cache WHERE date=? AND code=?', (prev[0], code))
        row = c.fetchone()
        if row and row[0] > 0:
            return row[0]
    conn.close()
    return 0

def get_next_high(data_cache, code, dt):
    """获取下一个交易日的最高价（用于n值）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT DISTINCT date FROM data_cache WHERE date > ? ORDER BY date LIMIT 1', (dt,))
    nxt = c.fetchone()
    if nxt:
        # 从data_cache查
        c.execute('SELECT close, p FROM data_cache WHERE date=? AND code=?', (nxt[0], code))
        row = c.fetchone()
        if row:
            return row[0], row[1]  # next_close, next_p
        # 查不到就试腾讯API
        k = get_daily_close(code, nxt[0])
        if k:
            return k['close'], compute_p(k['close'], get_prev_close(data_cache, code, nxt[0]))
    conn.close()
    return 0, 0

def get_momentum_features(data_cache, code, dt):
    """计算动量特征（d1-d3, slope5, t4_shadow等）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT DISTINCT date FROM data_cache WHERE date <= ? ORDER BY date DESC LIMIT 8', (dt,))
    dates = [r[0] for r in c.fetchall()]
    if dt in dates:
        dates.remove(dt)
    dates = dates[:7]  # 最多前7天
    
    gains = []
    for pd in reversed(dates):
        c.execute('SELECT p FROM data_cache WHERE date=? AND code=?', (pd, code))
        row = c.fetchone()
        gains.append(row[0] if row else 0)
    
    d1 = gains[0] if len(gains) >= 1 else 0
    d2 = gains[1] if len(gains) >= 2 else 0
    d3 = gains[2] if len(gains) >= 3 else 0
    d4 = gains[3] if len(gains) >= 4 else 0
    d5 = gains[4] if len(gains) >= 5 else 0
    
    # slope5 = 过去5天涨跌幅的线性斜率（简化：d5-d1的平均变化）
    if len(gains) >= 5:
        # 简单计算：总涨幅/天数
        slope5 = (sum(gains[:5]) - gains[0]) / 5  # 近似
    else:
        slope5 = 0
    
    # t4_shadow = T-4日的上影线占比
    t4_shadow = 0
    if len(gains) >= 4:
        c.execute('SELECT close, high, low FROM data_cache WHERE date=? AND code=?', 
                  (dates[3] if len(dates) > 3 else dates[-1], code))
        row = c.fetchone()
        if row and row[1] and row[2]:
            hi, lo, cl = row[1], row[2], row[0]
            t4_shadow = round((hi - cl) / (hi - lo) * 100, 1) if (hi - lo) > 0 else 0
    
    # cons_up = 连续上涨天数（3天内p>0的天数）
    cons_up = sum(1 for g in gains[:5] if g > 0)
    
    # peak_decay = 最近2天涨幅相对于之前3天最大涨幅的衰减
    if len(gains) >= 5:
        prev_max = max(gains[2:5])  # d3,d4,d5
        recent_sum = gains[0] + gains[1]  # d1+d2
        peak_decay = max(0, prev_max - recent_sum)
    else:
        peak_decay = 0
    
    conn.close()
    return {
        'd1': round(d1, 2), 'd2': round(d2, 2), 'd3': round(d3, 2),
        'd4': round(d4, 2), 'd5': round(d5, 2),
        'slope5': round(slope5, 2),
        't4_shadow': round(t4_shadow, 1),
        'cons_up': cons_up,
        'peak_decay': round(peak_decay, 1),
    }

def main():
    print(f'📦 全面数据补全 {datetime.now().strftime(\"%Y-%m-%d %H:%M\")}')
    print(f'{"="*50}')
    
    # 加载股票池
    pool_file = os.path.join(SCRIPTS, '活跃股票池_3043.json')
    with open(pool_file, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    all_codes = [s['code'] if isinstance(s, dict) else s for s in pool]
    all_codes = [c for c in all_codes if c.startswith(('600','601','603','605','000','001','002'))]
    print(f'全股票池: {len(all_codes)}只')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 获取所有日期
    c.execute('SELECT DISTINCT date FROM data_cache ORDER BY date')
    all_dates = [r[0] for r in c.fetchall()]
    print(f'数据库日期: {all_dates[0]}~{all_dates[-1]} ({len(all_dates)}天)')
    
    # 只处理最近60天的数据补全
    dates_to_fix = all_dates[-60:]
    total_inserted = 0
    total_failed = 0
    feature_inserted = 0
    
    for dt in dates_to_fix:
        c.execute('SELECT DISTINCT code FROM data_cache WHERE date=?', (dt,))
        existing = {r[0] for r in c.fetchall()}
        missing = [code for code in all_codes if code not in existing]
        
        if not missing:
            continue
        
        newline = '\n'
        print(f'{newline}{dt}: 缺{len(missing)}只股票')
        
        for code in missing:
            try:
                # 从腾讯K线拉数据
                k = get_daily_close(code, dt)
                if not k:
                    total_failed += 1
                    continue
                
                prev_c = get_prev_close(None, code, dt)  # 用None因为要新连接
                if prev_c <= 0:
                    # 从K线获取前一天的
                    pred = None
                    pred_lines = get_kline_day(code, 60)
                    for kl in reversed(pred_lines):
                        if len(kl) >= 6 and kl[0][:10] < dt:
                            pred = float(kl[2])
                            break
                    prev_c = pred or k['open']  # fallback
                
                p = compute_p(k['close'], prev_c)
                cl = compute_cl(k['close'], k['low'], k['high'])
                
                # 取n值（次日最高涨幅）
                nxt_c, nxt_p = get_next_high(None, code, dt)
                n_val = nxt_p if nxt_p else 0
                
                name = ''
                # 尝试从已有数据找名字
                c.execute('SELECT name FROM data_cache WHERE code=? LIMIT 1', (code,))
                row = c.fetchone()
                if row: name = row[0]
                
                c.execute('''
                    INSERT OR IGNORE INTO data_cache
                    (date, code, name, p, cl, vr, n,
                     dif_val, macd_golden, wr_val, j_val, k_val, d_val,
                     pos_in_day, above_ma5, kdj_golden,
                     close, volume, original_source, cache_version)
                    VALUES (?,?,?,?,?,1.0,?,
                            0,0,50,50,50,50,
                            50,0,0,
                            ?,?,?,?)
                ''', (dt, code, name, round(p, 2), round(cl, 2), round(n_val, 2),
                      round(k['close'], 2), round(k['volume'], 0),
                      'tencent:kline-fix', dt))
                total_inserted += 1
                
                # 计算并插入特征
                if dt <= '2026-05-27':  # features只补到有次日数据的
                    feats = get_momentum_features(None, code, dt)
                    c.execute('''
                        INSERT OR IGNORE INTO features_cache
                        (date, code, d1, d2, d3, d4, d5, slope5, 
                         t4_shadow, cons_up, peak_decay, computed_from, cache_version)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ''', (dt, code, feats['d1'], feats['d2'], feats['d3'],
                          feats['d4'], feats['d5'], feats['slope5'],
                          feats['t4_shadow'], feats['cons_up'], feats['peak_decay'],
                          'computed_from_data_cache', 'full-fix'))
                    feature_inserted += 1
                
                if total_inserted % 20 == 0:
                    conn.commit()
                    
            except Exception as e:
                total_failed += 1
                continue
        
        conn.commit()
        print(f'  已补{total_inserted}只, 失败{total_failed}只')
    
    # 检查05-22之后的日期是否还有缺特征
    print(f'\n\n补全完成!')
    print(f'新增data_cache: {total_inserted}条')
    print(f'新增features_cache: {feature_inserted}条')
    print(f'失败: {total_failed}条')
    
    # 最终检查
    print(f'\n最终检查:')
    for dt in ['2026-05-25','2026-05-26','2026-05-27','2026-05-28']:
        c.execute('SELECT COUNT(*) FROM data_cache WHERE date=?', (dt,))
        cnt = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM features_cache WHERE date=?', (dt,))
        fcnt = c.fetchone()[0]
        print(f'  {dt}: data={cnt}只 | feature={fcnt}条')
    
    conn.close()

if __name__ == '__main__':
    main()
