import sqlite3

db = sqlite3.connect(r'C:\Users\12546\AppData\Local\hermes\scripts\v13_quant.db')
c = db.cursor()

# 1. 数据日期范围
c.execute('SELECT MIN(date), MAX(date), COUNT(*) FROM data_cache')
print(f'data_cache: {c.fetchone()}')
c.execute('SELECT MIN(date), MAX(date), COUNT(*) FROM features_cache')
print(f'features_cache: {c.fetchone()}')

print()
# 2. 检查high为空或为0的情况（default=0）
c.execute('SELECT COUNT(*) FROM data_cache WHERE high IS NULL OR high = 0')
hc = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM data_cache')
tc = c.fetchone()[0]
print(f'high为空/0: {hc}/{tc}')
c.execute('SELECT COUNT(*) FROM data_cache WHERE low IS NULL OR low = 0')
lc = c.fetchone()[0]
print(f'low为空/0: {lc}/{tc}')
c.execute('SELECT COUNT(*) FROM data_cache WHERE volume IS NULL OR volume = 0')
vc = c.fetchone()[0]
print(f'volume为空/0: {vc}/{tc}')
c.execute('SELECT COUNT(*) FROM data_cache WHERE close IS NULL OR close = 0')
cc = c.fetchone()[0]
print(f'close为空/0: {cc}/{tc}')

print()
# 3. 最近交易日
c.execute('SELECT DISTINCT date FROM data_cache ORDER BY date DESC LIMIT 5')
print('data_cache最近5个交易日:', [r[0] for r in c.fetchall()])
c.execute('SELECT DISTINCT date FROM features_cache ORDER BY date DESC LIMIT 5')
print('features_cache最近5个交易日:', [r[0] for r in c.fetchall()])

print()
# 4. 最新交易日high/low样例
latest = c.execute('SELECT MAX(date) FROM data_cache').fetchone()[0]
c.execute("SELECT code, date, close, high, low, volume, p, cl FROM data_cache WHERE date=? LIMIT 3", (latest,))
print(f'最新交易日({latest})样例:')
for r in c.fetchall():
    print(r)

print()
# 5. 检查技术指标完整性（最新交易日）
for col in ['wr_val', 'k_val', 'd_val', 'j_val', 'dif_val', 'macd_golden', 'pos_in_day', 'above_ma5', 'kdj_golden']:
    c.execute(f"SELECT COUNT(*) FROM data_cache WHERE date=? AND ({col} IS NULL OR {col}=0)", (latest,))
    cnt = c.fetchone()[0]
    print(f'  {col}=0/空: {cnt}')

print()
# 6. features_cache最近日期样例
c.execute("SELECT * FROM features_cache WHERE date=? LIMIT 5", (latest,))
rows = c.fetchall()
print(f'features_cache最新({latest})样本数: {len(rows)}')
if rows:
    print('样例:', rows[0])

print()
# 7. 检查features_cache在哪些日期有数据
c.execute('SELECT date, COUNT(*) FROM features_cache GROUP BY date ORDER BY date DESC LIMIT 10')
print('features_cache按日统计(最近10天):')
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]}条')

print()
# 8. 检查data_cache按日统计
c.execute('SELECT date, COUNT(*) FROM data_cache GROUP BY date ORDER BY date DESC LIMIT 10')
print('data_cache按日统计(最近10天):')
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]}条')

print()
# 9. config表
c.execute("PRAGMA table_info(config)")
print('config字段:')
for r in c.fetchall():
    print(r)
try:
    c.execute("SELECT key, value, updated_at FROM config LIMIT 20")
    for r in c.fetchall():
        print(f'  {r}')
except:
    print('config表无数据或无updated_at列')

db.close()
