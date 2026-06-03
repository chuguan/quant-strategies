import sqlite3

db = sqlite3.connect(r'C:\Users\12546\AppData\Local\hermes\scripts\v13_quant.db')
c = db.cursor()

latest = '2026-05-29'

# 1. 查出wr=0的股票，验证是否因为当天收盘=14日最低
print("=== wr=0 分析 ===")
zero_wr = []
c.execute(f"SELECT code, name, close, high, low, wr_val, k_val, d_val, j_val FROM data_cache WHERE date=? AND wr_val=0", (latest,))
for r in c.fetchall():
    code, name, close, high, low, wr, k, d, j = r
    # wr=0意味着收盘价=14日最低
    c.execute(f"SELECT close FROM data_cache WHERE code=? AND date<? AND date>=? ORDER BY date DESC LIMIT 14",
              (code, latest, f"{int(latest[:4])-1}-{latest[5:]}"))
    prev_closes = [x[0] for x in c.fetchall() if x[0] > 0]
    min14 = min(prev_closes) if prev_closes else close
    print(f"  {code} {name} close={close} low={low} min14={min14:.2f} wr={wr} k={k:.1f} d={d:.1f} j={j:.1f}")
    zero_wr.append(code)

print(f"\nwr=0共{len(zero_wr)}只")

# 2. 检查refresh脚本是否覆盖了历史值
print("\n=== 参数错位检测 ===")
# 原版big_cache中正确的d_val应该和k_val不同，但被刷新的股票d_val=k_val
c.execute(f"""
    SELECT code, k_val, d_val, j_val, dif_val, macd_golden, above_ma5, pos_in_day
    FROM data_cache 
    WHERE date=? AND k_val IS NOT NULL AND d_val IS NOT NULL 
    AND ABS(k_val - d_val) < 0.01 AND k_val != 50 
    LIMIT 10
""", (latest,))
print("d_val≈k_val的股票（指示参数错位BUG）:")
for r in c.fetchall():
    print(f"  code={r[0]} k={r[1]:.1f} d={r[2]:.1f} (diff={r[1]-r[2]:.2f}) j={r[3]:.1f} dif={r[4]} mg={r[5]} a5={r[6]} pid={r[7]}")

# 统计d_val=k_val的股票数量
c.execute(f"""
    SELECT COUNT(*) FROM data_cache 
    WHERE date=? AND k_val IS NOT NULL AND d_val IS NOT NULL 
    AND ABS(k_val - d_val) < 0.01 AND k_val != 50
""", (latest,))
swapped = c.fetchone()[0]
c.execute(f"SELECT COUNT(*) FROM data_cache WHERE date=? AND k_val IS NOT NULL and k_val != 50", (latest,))
total_calc = c.fetchone()[0]
print(f"\nd_val≈k_val: {swapped}/{total_calc} 只 (指示参数错位)")

# 3. 检查原版big_cache的同一天对比（如果有）
import pickle
with open(r'C:\Users\12546\AppData\Local\hermes\scripts\release\V13\big_cache_full.pkl', 'rb') as f:
    bc = pickle.load(f)

print(f"\n=== 原版big_cache类型 ===")
print(f"类型: {type(bc)}")
if isinstance(bc, dict):
    keys = list(bc.keys())
    print(f"键：{keys[:5]}...")
    sample = bc[keys[0]]
    print(f"值类型：{type(sample)}")
    if isinstance(sample, dict):
        print(f"值字段：{list(sample.keys())[:15]}")
    # 找华塑控股
    for k in keys:
        if isinstance(k, tuple) and k[0] == '000509' and k[1] >= '2026-05-25':
            print(f"\n华塑控股原版数据 {k}: {bc[k]}")

db.close()
