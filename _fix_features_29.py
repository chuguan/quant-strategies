import sqlite3, numpy as np

DB_PATH = r'C:\Users\12546\AppData\Local\hermes\scripts\v13_quant.db'
conn = sqlite3.connect(DB_PATH, timeout=30)
conn.execute('PRAGMA synchronous=OFF')
c = conn.cursor()

target_date = '2026-05-29'
print(f'计算 {target_date} 特征...')

# 获取所有交易日顺序
c.execute('SELECT DISTINCT date FROM data_cache WHERE close > 0 ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]

if target_date not in all_dates:
    print(f'{target_date} 不在交易日中')
    conn.close()
    exit()

date_idx = all_dates.index(target_date)
prev = {}
for off in range(1, 6):
    idx = date_idx - off
    prev[f'd{off}'] = all_dates[idx] if idx >= 0 else None
print(f'前5日: {prev}')

# 加载该日所有股票数据
c.execute('SELECT code, p, close, high, low FROM data_cache WHERE date=? AND close>0', (target_date,))
today_data = {r[0]: {'p':r[1] or 0, 'close':r[2], 'high':r[3] or r[2], 'low':r[4] or r[2]} for r in c.fetchall()}

# 加载前5日数据
prev_data = {}
for name, dt in prev.items():
    if dt:
        c.execute('SELECT code, p, close, high, low FROM data_cache WHERE date=? AND close>0', (dt,))
        prev_data[name] = {r[0]: {'p':r[1] or 0, 'close':r[2], 'high':r[3] or r[2], 'low':r[4] or r[2]} for r in c.fetchall()}
    else:
        prev_data[name] = {}

total = 0
rows = []
for code, today in today_data.items():
    # d1~d5
    d1 = prev_data['d1'].get(code, {}).get('p', 0) if 'd1' in prev_data else 0
    d2 = prev_data['d2'].get(code, {}).get('p', 0) if 'd2' in prev_data else 0
    d3 = prev_data['d3'].get(code, {}).get('p', 0) if 'd3' in prev_data else 0
    d4 = prev_data['d4'].get(code, {}).get('p', 0) if 'd4' in prev_data else 0
    d5 = prev_data['d5'].get(code, {}).get('p', 0) if 'd5' in prev_data else 0
    
    # slope5
    p_vals = [d5, d4, d3, d2, d1]
    slope5 = round(np.polyfit([0,1,2,3,4], np.array(p_vals), 1)[0], 2) if len(set(p_vals)) > 1 else 0.0
    
    # t4_shadow: T-4日影线率
    t4 = prev_data.get('d4', {}).get(code, {})
    t4_shadow = round((t4.get('high',0)-t4.get('low',0))/t4['close']*100,1) if t4 and t4.get('close',0)>0 else 0.0
    
    # cons_up: 连续上涨天数（从远到近）
    cons_up = 0
    for pn in [d5, d4, d3, d2, d1]:
        if pn >= 0: cons_up += 1
        else: break
    
    # peak_decay
    p_max = max(p_vals)
    today_p = today['p']
    peak_decay = round(p_max - abs(today_p), 2) if p_max > 3 and abs(today_p) < p_max * 0.3 else 0.0
    
    rows.append((target_date, code, round(d1,2), round(d2,2), round(d3,2),
                 round(d4,2), round(d5,2), slope5, t4_shadow, cons_up, peak_decay,
                 'auto_compute'))
    total += 1
    
    if len(rows) >= 500:
        c.executemany('''INSERT OR REPLACE INTO features_cache
            (date,code,d1,d2,d3,d4,d5,slope5,t4_shadow,cons_up,peak_decay,computed_from)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', rows)
        conn.commit()
        rows = []
        print(f'  {total}条...', end='\r')

if rows:
    c.executemany('''INSERT OR REPLACE INTO features_cache
        (date,code,d1,d2,d3,d4,d5,slope5,t4_shadow,cons_up,peak_decay,computed_from)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', rows)
    conn.commit()

# 验证
c.execute('SELECT date, COUNT(*) FROM features_cache GROUP BY date ORDER BY date DESC LIMIT 5')
print(f'\n✅ {target_date}: {total}条')
for dt, cnt in c.fetchall():
    print(f'  {dt}: {cnt}条')

conn.close()
