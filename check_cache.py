"""检查big_cache.pkl数据结构"""
import pickle
with open('big_cache.pkl','rb') as f:
    c = pickle.load(f)
d = c['data']
ds = sorted(d.keys())
print(f'天数: {len(ds)} 范围: {ds[0]}~{ds[-1]}')
s = d[ds[0]][0]
print(f'sample keys: {list(s.keys())}')
print(f'sample: {s}')
# Check dates with next_day data
has_n = sum(1 for dt in ds if any(st.get('n',0) for st in d[dt]))
print(f'有次日数据(n): {has_n}/{len(ds)}')
# Check 5 in range
cnt = 0
for dt in ds:
    for st in d[dt]:
        p = st.get('p',0)
        if 5 <= p <= 8:
            cnt += 1
            break
print(f'有涨幅5~8%的天数: {cnt}/{len(ds)}')
