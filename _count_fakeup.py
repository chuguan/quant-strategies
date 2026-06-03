#!/usr/bin/env python3
"""统计全部数据中虚涨日天数"""
import sqlite3, os

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

conn = sqlite3.connect(DB, timeout=30)
c = conn.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]

# 逐天判断行情
fake_days = []
real_days = []
down_days = []
flat_days = []

for dt in all_dates:
    c = conn.execute('SELECT p, vr FROM data_cache WHERE date=?', (dt,))
    rows = c.fetchall()
    ps = [r[0] or 0 for r in rows if abs(r[0] or 0) < 15]
    vrs = [r[1] or 0 for r in rows if (r[1] or 0) > 0]
    if not ps: continue
    ap = sum(ps)/len(ps)
    av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    
    if ap > 0.5:
        if hot < 15 or av < 0.9:
            fake_days.append(dt)
        else:
            real_days.append(dt)
    elif ap < -0.5:
        down_days.append(dt)
    else:
        flat_days.append(dt)

count = len(real_days)+len(fake_days)+len(down_days)+len(flat_days)
print(f'总交易日: {len(all_dates)}, 有数据: {count}')
print(f'  真实涨日: {len(real_days)} ({len(real_days)*100//count}%)')
print(f'  虚涨日:   {len(fake_days)} ({len(fake_days)*100//count}%)')
print(f'  跌日:     {len(down_days)} ({len(down_days)*100//count}%)')
print(f'  横盘:     {len(flat_days)} ({len(flat_days)*100//count}%)')
print(f'\n虚涨日列表:')
for d in fake_days[-30:]:
    print(f'  {d}')
conn.close()
