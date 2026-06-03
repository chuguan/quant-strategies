import sqlite3
DB = r'C:\Users\12546\AppData\Local\hermes\scripts\v13_quant.db'
conn = sqlite3.connect(DB, timeout=60)
c = conn.cursor()
target = '2026-05-29'
code = '002851'

# 查前一天K/D值
c.execute("SELECT date, k_val, d_val FROM data_cache WHERE code=? AND date<? AND close>0 ORDER BY date DESC LIMIT 1", (code, target))
prev = c.fetchone()
if prev:
    pk = prev[1] if prev[1] and prev[1] != 50 else 50
    pd = prev[2] if prev[2] and prev[2] != 50 else 50
else:
    pk, pd = 50, 50

# 当日RSV
c.execute("SELECT close, high, low FROM data_cache WHERE date=? AND code=?", (target, code))
r = c.fetchone()
close, high, low = r[0], r[1] or r[0], r[2] or r[0]

# 前8天的high/low
c.execute("SELECT date, high, low FROM data_cache WHERE code=? AND date<=? AND date>=? ORDER BY date", 
          (code, target, '2026-05-20'))
rows = c.fetchall()
highs = [r[1] if r[1] else close for r in rows]
lows = [r[2] if r[2] else close for r in rows]
h9 = max(highs[-9:]) if len(highs) >= 9 else high
l9 = min(lows[-9:]) if len(lows) >= 9 else low
rsv = (close - l9) / (h9 - l9) * 100 if (h9 - l9) > 0 else 50

k_val = round(2/3 * pk + 1/3 * rsv, 2)
d_val = round(2/3 * pd + 1/3 * k_val, 2)
j_val = round(3 * k_val - 2 * d_val, 2)

c.execute("UPDATE data_cache SET k_val=?, d_val=?, j_val=? WHERE date=? AND code=?",
          (k_val, d_val, j_val, target, code))
conn.commit()

c.execute("SELECT k_val, d_val, j_val FROM data_cache WHERE date=? AND code=?", (target, code))
r = c.fetchone()
print('✅ %s: k=%.2f d=%.2f j=%.2f' % (code, r[0], r[1], r[2]))
conn.close()
