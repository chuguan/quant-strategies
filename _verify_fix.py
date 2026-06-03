import sqlite3
db = sqlite3.connect(r'C:\Users\12546\AppData\Local\hermes\scripts\v13_quant.db')
c = db.cursor()
c.execute('SELECT date, COUNT(*) FROM features_cache GROUP BY date ORDER BY date DESC LIMIT 10')
print('features_cache最新10天:')
for dt, cnt in c.fetchall():
    print(f'  {dt}: {cnt}条')

# 检查5月29日的特征样例
c.execute('SELECT * FROM features_cache WHERE date="2026-05-29" LIMIT 5')
cols = [desc[0] for desc in c.description]
print('\n5月29日特征样例:')
for row in c.fetchall():
    print(dict(zip(cols, row)))

# 验证技术指标
c.execute('SELECT date, COUNT(*) as total, SUM(CASE WHEN wr_val IS NOT NULL AND wr_val != 50 THEN 1 ELSE 0 END) as wr_ok FROM data_cache GROUP BY date ORDER BY date DESC LIMIT 5')
print('\ndata_cache技术指标完整性:')
for dt, tot, wr_ok in c.fetchall():
    print(f'  {dt}: {wr_ok}/{tot}只有WR')

db.close()
