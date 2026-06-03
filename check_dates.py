"""检查big_cache_full.pkl的日期"""
import pickle
with open('big_cache_full.pkl','rb') as f:
    c = pickle.load(f)
ds = sorted(c['data'].keys())
print(f'范围: {ds[0]} ~ {ds[-1]}')
may = [d for d in ds if d.startswith('2026-05')]
print(f'5月日期: {may}')
# 检查今天5-25的数据
d25 = c['data'].get('2026-05-25', [])
print(f'2026-05-25: {len(d25)}只股票')
if d25:
    print(f'  样本: {d25[0]}')
