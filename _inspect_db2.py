import sqlite3
import pickle, os

db = sqlite3.connect(r'C:\Users\12546\AppData\Local\hermes\scripts\v13_quant.db')
c = db.cursor()

# 1. 检查dates技术上缺失情况
print('=== 数据完整性检查 ===')
c.execute('SELECT MIN(date), MAX(date) FROM data_cache')
dc_min, dc_max = c.fetchone()
c.execute('SELECT MIN(date), MAX(date) FROM features_cache')
fc_min, fc_max = c.fetchone()
print(f'data_cache: {dc_min} ~ {dc_max} ({c.execute("SELECT COUNT(DISTINCT date) FROM data_cache").fetchone()[0]}个交易日)')
print(f'features_cache: {fc_min} ~ {fc_max} ({c.execute("SELECT COUNT(DISTINCT date) FROM features_cache").fetchone()[0]}个交易日)')

# 2. 统计data_cache各字段非空情况
print()
print('=== data_cache字段非空统计(最近30天) ===')
last30 = c.execute("SELECT DISTINCT date FROM data_cache ORDER BY date DESC LIMIT 30").fetchall()
dates_30 = [r[0] for r in last30]
placeholders = ','.join(['?' for _ in dates_30])
c.execute(f"SELECT COUNT(*) FROM data_cache WHERE date IN ({placeholders})", dates_30)
total30 = c.fetchone()[0]
for col in ['close','high','low','volume','p','cl','vr','dif_val','macd_golden','wr_val','j_val','k_val','d_val','pos_in_day','above_ma5','kdj_golden']:
    c.execute(f"SELECT COUNT(*) FROM data_cache WHERE date IN ({placeholders}) AND ({col} IS NULL OR {col}=0)", dates_30)
    zero = c.fetchone()[0]
    pct = zero*100/total30 if total30 else 0
    print(f'  {col}: {zero}/{total30}={pct:.1f}% 为0/空')

# 3. 检查features_cache字段
print()
print('=== features_cache字段非空统计(全部) ===')
c.execute('SELECT COUNT(*) FROM features_cache')
total_fc = c.fetchone()[0]
for col in ['d1','d2','d3','d4','d5','slope5','t4_shadow','cons_up','peak_decay']:
    c.execute(f"SELECT COUNT(*) FROM features_cache WHERE {col} IS NULL")
    zero = c.fetchone()[0]
    print(f'  {col}: {zero}/{total_fc}={zero*100/total_fc:.1f}% 为空')

# 4. 检查big_cache_full.pkl的字段
print()
print('=== big_cache_full.pkl字段 ===')
try:
    pkl_path = r'C:\Users\12546\AppData\Local\hermes\hermes_workspace\V13\big_cache_full.pkl'
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    if isinstance(data, dict):
        print(f'类型: dict, keys={list(data.keys())[:10]}')
        for k, v in data.items():
            if hasattr(v, 'columns'):
                print(f'{k}: {list(v.columns)}')
                break
    elif hasattr(data, 'columns'):
        print(f'列名: {list(data.columns)}')
        print(f'形状: {data.shape}')
        print(f'前3行:')
        print(data.head(3))
    else:
        print(f'类型: {type(data)}')
        if isinstance(data, list):
            print(f'长度: {len(data)}, 第一项: {data[0] if data else None}')
except Exception as e:
    print(f'读取失败: {e}')

# 5. 检查features_30d.pkl的字段
print()
print('=== features_30d.pkl字段 ===')
try:
    feat_path = r'C:\Users\12546\AppData\Local\hermes\hermes_workspace\V13\features_30d.pkl'
    with open(feat_path, 'rb') as f:
        feat = pickle.load(f)
    if hasattr(feat, 'columns'):
        print(f'列名: {list(feat.columns)}')
        print(f'形状: {feat.shape}')
        print(f'前3行:')
        print(feat.head(3))
    elif isinstance(feat, dict):
        print(f'keys: {list(feat.keys())[:10]}')
    else:
        print(f'类型: {type(feat)}')
except Exception as e:
    print(f'读取失败: {e}')

db.close()
