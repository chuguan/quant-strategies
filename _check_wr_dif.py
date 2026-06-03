import sqlite3

db = sqlite3.connect(r'C:\Users\12546\AppData\Local\hermes\scripts\v13_quant.db')
c = db.cursor()

# 检查 wr_val/dif_val 缺失的股票
latest = '2026-05-29'
c.execute(f"""
    SELECT code, name, close, wr_val, dif_val, macd_golden, k_val, d_val, j_val
    FROM data_cache 
    WHERE date=? AND (wr_val IS NULL OR wr_val = 0 OR dif_val IS NULL OR dif_val = 0)
    LIMIT 20
""", (latest,))
print(f"=== {latest} wr/dif 为0的股票 ===")
for r in c.fetchall():
    print(r)

# 检查原版big_cache中这些股票的值
print()
print("=== 检查原版big_cache中对应值 ===")
import pickle
with open(r'C:\Users\12546\AppData\Local\hermes\scripts\release\V13\big_cache_full.pkl', 'rb') as f:
    bc = pickle.load(f)

# 为缺失的股票找原版值
null_codes = set()
c.execute(f"""
    SELECT code FROM data_cache 
    WHERE date=? AND (wr_val IS NULL OR wr_val = 0)
""", (latest,))
for r in c.fetchall():
    null_codes.add(r[0])

print(f"wr=0的股票数: {len(null_codes)}")
for code in sorted(null_codes)[:10]:
    # 在原版big_cache中找
    key = (code, latest)
    if key in bc:
        print(f"  {code}: bc={bc[key].get('wr_val', '?')} | "
              f"db={dict(c.execute('SELECT wr_val,dif_val FROM data_cache WHERE date=? AND code=?', (latest, code)).fetchone())}")
    else:
        # 试试最近的其他日期
        for d in reversed(sorted(bc.keys())):
            if isinstance(d, tuple) and d[0] == code:
                print(f"  {code}: 原版无{latest}数据, 最近{d[1]}: wr={bc[d].get('wr_val', '?')}")
                break

# 统计原版big_cache中wr_val的分布
print()
print("=== 原版big_cache wr_val分布(最新日期) ===")
bc_latest_wrs = {}
for (code, dt), v in bc.items():
    if dt == latest and isinstance(v, dict) and 'wr_val' in v:
        wr = v.get('wr_val', 50)
        bc_latest_wrs[code] = wr
print(f"原版big_cache中{latest}的股票数: {len(bc_latest_wrs)}")
wr_vals = list(bc_latest_wrs.values())
print(f"wr_val范围: {min(wr_vals):.1f}~{max(wr_vals):.1f}")

# 检查refresh_tech_indicators.py是否有bug导致wr/dif被重置
print()
print("=== 原版big_cache vs SQLite对比(低wr样本) ===")
# 找原版中低WR的股票
low_wr = [(code, wr) for code, wr in bc_latest_wrs.items() if wr < 20]
print(f"原版低WR(<20): {len(low_wr)}只")
for code, wr in sorted(low_wr, key=lambda x: x[1])[:10]:
    db_wr = c.execute("SELECT wr_val FROM data_cache WHERE date=? AND code=?", (latest, code)).fetchone()
    db_wr_val = db_wr[0] if db_wr else 'N/A'
    match = '✅' if abs(float(db_wr_val) - wr) < 0.1 else f'❌(差{float(db_wr_val) - wr:.1f})'
    print(f"  {code}: 原版wr={wr:.1f} DB={db_wr_val} {match}")

db.close()
