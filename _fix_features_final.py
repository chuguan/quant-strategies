import sqlite3, time
import numpy as np

DB_PATH = r'C:\Users\12546\AppData\Local\hermes\scripts\v13_quant.db'

# 重试连接，避免锁
conn = None
for attempt in range(5):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute('PRAGMA synchronous=OFF')
        conn.execute('PRAGMA journal_mode=WAL')
        break
    except:
        time.sleep(1)

c = conn.cursor()

# 获取所有交易日
c.execute('SELECT DISTINCT date FROM data_cache WHERE close > 0 ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]

# features_cache已有日期
c.execute('SELECT DISTINCT date FROM features_cache')
feat_dates = set(r[0] for r in c.fetchall())

# 缺的日期
need = sorted(set(all_dates) - feat_dates)
print(f'缺特征的日期: {need}')
if not need:
    print('✅ 已全部补全')
    conn.close()
    exit(0)

# 只算最晚的3天（增量模式）
targets = need[-3:]
print(f'本次计算: {targets}')

# 预加载p数据
c.execute('SELECT code, date, p, close, high, low FROM data_cache WHERE close > 0 ORDER BY code, date')
p_data = {}
for code, dt, p, close, high, low in c.fetchall():
    if code not in p_data:
        p_data[code] = {}
    p_data[code][dt] = {'p': p or 0, 'close': close or 0, 'high': high or 0, 'low': low or 0}

total = 0
for dt in targets:
    if dt not in all_dates:
        continue
    date_idx = all_dates.index(dt)
    
    # 前5个交易日
    prev = {}
    for off in range(1, 6):
        idx = date_idx - off
        prev[f'd{off}'] = all_dates[idx] if idx >= 0 else None
    
    rows = []
    for code in p_data:
        cd = p_data[code]
        today = cd.get(dt)
        if not today or today['close'] <= 0:
            continue
        
        # d1-d5
        d1 = cd[prev['d1']]['p'] if prev['d1'] and prev['d1'] in cd else 0.0
        d2 = cd[prev['d2']]['p'] if prev['d2'] and prev['d2'] in cd else 0.0
        d3 = cd[prev['d3']]['p'] if prev['d3'] and prev['d3'] in cd else 0.0
        d4 = cd[prev['d4']]['p'] if prev['d4'] and prev['d4'] in cd else 0.0
        d5 = cd[prev['d5']]['p'] if prev['d5'] and prev['d5'] in cd else 0.0
        
        # slope5
        p_vals = [d5, d4, d3, d2, d1]
        if len(set(p_vals)) > 1:
            slope5 = round(np.polyfit([0,1,2,3,4], np.array(p_vals), 1)[0], 2)
        else:
            slope5 = 0.0
        
        # t4_shadow
        t4_dt = prev.get('d4')
        if t4_dt and t4_dt in cd:
            t4 = cd[t4_dt]
            t4_shadow = round((t4['high'] - t4['low']) / t4['close'] * 100, 1) if t4['close'] > 0 else 0.0
        else:
            t4_shadow = 0.0
        
        # cons_up
        cons_up = 0
        for pn in ['d1','d2','d3','d4','d5']:
            if locals()[pn] >= 0:
                cons_up += 1
            else:
                break
        
        # peak_decay
        p_max = max(p_vals)
        today_p = today['p']
        peak_decay = 0.0
        if p_max > 3 and abs(today_p) < p_max * 0.3:
            peak_decay = round(p_max - abs(today_p), 2)
        
        rows.append((dt, code, round(d1,2), round(d2,2), round(d3,2),
                     round(d4,2), round(d5,2), slope5, t4_shadow, cons_up, peak_decay,
                     'auto_compute'))
        total += 1
    
    if rows:
        c.executemany('''
            INSERT OR REPLACE INTO features_cache
            (date, code, d1, d2, d3, d4, d5,
             slope5, t4_shadow, cons_up, peak_decay, computed_from)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ''', rows)
        conn.commit()
        print(f'  {dt}: {len(rows)}条 ✓')

print(f'\n✅ 补完 {total} 条')

# 验证
c.execute('SELECT date, COUNT(*) FROM features_cache GROUP BY date ORDER BY date DESC LIMIT 5')
print('\n最终验证:')
for dt, cnt in c.fetchall():
    print(f'  {dt}: {cnt}条')

conn.close()
