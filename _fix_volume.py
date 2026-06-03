#!/usr/bin/env python
"""从原版big_cache的vol字段补data_cache的volume"""
import sqlite3, pickle, time, sys

DB = r'C:\Users\12546\AppData\Local\hermes\scripts\v13_quant.db'
PKL = r'C:\Users\12546\AppData\Local\hermes\scripts\release\V13\big_cache_full.pkl'

print('▶ 加载原版big_cache...')
t0 = time.time()
with open(PKL, 'rb') as f:
    d = pickle.load(f)
data = d['data']
dates = sorted(data.keys())
print(f'  加载完成: {len(dates)}天, {time.time()-t0:.1f}s')

conn = sqlite3.connect(DB, timeout=120)
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA synchronous=OFF')
c = conn.cursor()

updated = 0
t1 = time.time()

for idx, dt in enumerate(dates):
    stocks = data.get(dt, [])
    batch = []
    for s in stocks:
        code = s.get('code', '')
        vol_val = s.get('vol', 0) or 0
        if not code or vol_val <= 0:
            continue
        batch.append((vol_val, dt, code))

    if batch:
        c.executemany('UPDATE data_cache SET volume=? WHERE date=? AND code=?', batch)
        updated += len(batch)
        conn.commit()

    if (idx + 1) % 30 == 0:
        pct = (idx + 1) * 100 // len(dates)
        rate = updated / (time.time() - t1) if (time.time() - t1) > 0 else 0
        print(f'  进度: {pct}% | 已补{updated}条 | {rate:.0f}条/秒')

elapsed = time.time() - t1
print(f'\n  补完: {updated}条, {elapsed:.0f}s')

# 验证
c.execute('SELECT COUNT(*) FROM data_cache WHERE volume > 0')
has = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM data_cache')
tot = c.fetchone()[0]
print(f'\n✅ volume修复: {has}/{tot} 有成交量 ({has*100/tot:.1f}%)')

c.execute('SELECT date, COUNT(*) FROM data_cache WHERE volume>0 GROUP BY date ORDER BY date DESC LIMIT 5')
for dt, cnt in c.fetchall():
    print(f'  {dt}: {cnt}只')

conn.close()
