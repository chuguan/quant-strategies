import sqlite3

db = sqlite3.connect(r'C:\Users\12546\AppData\Local\hermes\scripts\v13_quant.db')
c = db.cursor()

# 检查high/low分布
print("=== high/low 分布检查 ===")

# 按月份分组统计high为空/0的占比
c.execute("""
    SELECT 
        substr(date, 1, 7) as ym,
        COUNT(*) as total,
        SUM(CASE WHEN high IS NULL OR high = 0 THEN 1 ELSE 0 END) as high_missing
    FROM data_cache
    GROUP BY ym
    ORDER BY ym DESC
    LIMIT 20
""")
print("月份 | 总数 | high缺失 | 缺失率")
for ym, tot, miss in c.fetchall():
    print(f"{ym} | {tot} | {miss} | {miss*100/tot:.1f}%")

print()

# 检查close和high的相关性
c.execute("SELECT COUNT(*) FROM data_cache WHERE close > 0 AND high > 0")
both = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM data_cache WHERE close > 0")
close_only = c.fetchone()[0]
print(f"有close+high: {both}, 仅有close: {close_only}")

# 检查features_cache最新日期
c.execute("SELECT MAX(date) FROM features_cache")
print(f"\nfeatures_cache最新日期: {c.fetchone()[0]}")
c.execute("SELECT MAX(date) FROM data_cache")
print(f"data_cache最新日期: {c.fetchone()[0]}")

db.close()

# 检查原版features_30d.pkl是否存在
import os
for p in [
    r'C:\Users\12546\AppData\Local\hermes\scripts\release\V13\features_30d.pkl',
    r'C:\Users\12546\AppData\Local\hermes\scripts\release\V13\big_cache_full.pkl',
]:
    exists = os.path.exists(p)
    sz = os.path.getsize(p) if exists else 0
    print(f"\n{'✓' if exists else '✗'} {p} ({sz/1024/1024:.1f}MB)" if exists else f"✗ {p} (不存在)")
