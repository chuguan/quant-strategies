"""补5月29日VR + 回测验证"""
import sqlite3, os
DB = os.path.expanduser('~/AppData/Local/hermes/scripts/v13_quant.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

# 1. 补VR
c.execute('SELECT DISTINCT code FROM data_cache WHERE date="2026-05-29" AND volume>0')
codes = [r[0] for r in c.fetchall()]
fixed = 0
for code in codes:
    c.execute('SELECT volume FROM data_cache WHERE code=? AND date<"2026-05-29" AND volume>0 ORDER BY date DESC LIMIT 5', (code,))
    vols = [r[0] for r in c.fetchall()]
    if len(vols) < 3: continue
    avg = sum(vols)/len(vols)
    c.execute('SELECT volume FROM data_cache WHERE date="2026-05-29" AND code=?', (code,))
    row = c.fetchone()
    if not row: continue
    v = row[0]
    vr = round(v/avg, 2) if avg>0 else 1.0
    vr = max(0.01, min(vr, 10.0))
    c.execute('UPDATE data_cache SET vr=? WHERE date="2026-05-29" AND code=?', (vr, code))
    fixed += 1
conn.commit()

c.execute('SELECT COUNT(*), ROUND(MIN(vr),2), ROUND(MAX(vr),2), ROUND(AVG(vr),2) FROM data_cache WHERE date="2026-05-29"')
cnt,mn,mx,avg = c.fetchone()
print(f'5/29 VR补完: {cnt}只, 范围[{mn}~{mx}], 均值{avg}')
c.execute('SELECT vr FROM data_cache WHERE date="2026-05-29" AND code="603316"')
print(f'诚邦VR: {c.fetchone()[0]}')

# 2. 再看冠军是否变化
c.execute('SELECT name, code, p, cl, vr, wr_val FROM data_cache WHERE date="2026-05-29" AND code IN ("603316","603938","600183","001259","002847")')
print('\n关键票VR修正后:')
for r in c.fetchall():
    print(f'  {r[0]}({r[1]}): p={r[2]:+.1f}% cl={r[3]} vr={r[4]} wr={r[5]}')

conn.close()
print('\n✅ 再跑回测看冠军是否变')
