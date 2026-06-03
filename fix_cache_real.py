"""补上缓存的real和names字段"""
import pickle, json, os, subprocess
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))

# 从活跃股票池获取info
with open('活跃股票池_3043.json', 'r') as f:
    pool = json.load(f)

# 加载缓存
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data = d['data']

# 收集所有出现在缓存中的code
all_codes_in_cache = set()
for dt, stocks in data.items():
    for s in stocks:
        all_codes_in_cache.add(s['code'])

print(f'缓存中总唯一code: {len(all_codes_in_cache)}只')

# 构建real和names
real = {}
names = {}
for code in all_codes_in_cache:
    if code in pool['info']:
        info = pool['info'][code]
        real[code] = {'hsl': info.get('hsl', 0), 'pe': info.get('pe', 0), 'shizhi': info.get('sz', 0)}
        names[code] = info.get('name', f'?{code}')
    else:
        # 不在3043池中的（可能是已退市），给默认值
        real[code] = {'hsl': 0, 'pe': 0, 'shizhi': 0}
        names[code] = f'?{code}'

# 保存
pickle.dump({'data': data, 'real': real, 'names': names}, open('big_cache_full.pkl', 'wb'))
print(f'real: {len(real)}只  names: {len(names)}只')
print('✅ 缓存补全完成')
