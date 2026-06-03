"""
全量缓存重建 v3 - 极简版
不算MACD/KDJ，只算翻身策略需要的字段
"""
import os, json, time, pickle
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
t0 = time.time()

# 1. 获取沪深主板股票代码
main_codes = [f.replace('.json','') for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_codes = [c for c in main_codes if c.startswith('sh60') or c.startswith('sz000') or c.startswith('sz001') or c.startswith('sz002') or c.startswith('sz003')]
print(f'沪深主板: {len(main_codes)}只', flush=True)

# 2. 加载旧数据（names和real）
with open('big_cache.pkl', 'rb') as f:
    old = pickle.load(f)
names = old.get('names', {})
real = old.get('real', {})

# 3. 逐股计算
data_by_date = defaultdict(list)
processed = 0

for code in main_codes:
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    try:
        with open(fp, 'r') as f:
            kl = json.load(f)
    except:
        continue
    if len(kl) < 60:
        continue

    n = len(kl)
    for i in range(1, n):
        cl = kl[i]['close']; hi = kl[i]['high']; lo = kl[i]['low']; op = kl[i]['open']; vo = kl[i]['volume']
        pc = kl[i-1]['close']
        dt = kl[i]['date']
        if dt < '2025-01-01':
            continue

        p = (cl / pc - 1) * 100
        if abs(p) > 20:
            continue

        # 收盘位
        pos = (cl - lo) / (hi - lo) * 100 if hi != lo else 50

        # 阳线
        yang = 1 if cl > op else 0

        # MA5
        if i >= 4:
            m5 = sum(kl[j]['close'] for j in range(i-4, i+1)) / 5
            a5 = 1 if cl > m5 else 0
        else:
            m5 = cl; a5 = 0

        # MA10,20,60
        m10 = sum(kl[j]['close'] for j in range(max(0,i-9), i+1)) / min(10,i+1)
        m20 = sum(kl[j]['close'] for j in range(max(0,i-19), i+1)) / min(20,i+1)
        m60 = sum(kl[j]['close'] for j in range(max(0,i-59), i+1)) / min(60,i+1)

        # 量比
        v5 = sum(kl[j]['volume'] for j in range(max(0,i-4), i+1)) / min(5,i+1)
        vr = vo / v5 if v5 > 0 else 1

        # 次日最高
        nv = 0; nc = 0
        if i < n - 1:
            nv = (kl[i+1]['high'] / cl - 1) * 100
            nc = (kl[i+1]['close'] / cl - 1) * 100

        data_by_date[dt].append({
            'code': code, 'p': round(p,2), 'cl': round(pos,1),
            'close': cl, 'is_yang': yang, 'above_ma5': a5,
            'vol_ratio': round(vr,2), 'n': round(nv,2),
            'next_close': round(nc,2),
            'ma5': round(m5,3), 'ma10': round(m10,3),
            'ma20': round(m20,3), 'ma60': round(m60,3),
        })

    processed += 1
    if processed % 500 == 0:
        print(f'{processed}/{len(main_codes)} ({time.time()-t0:.0f}s)', flush=True)

print(f'完成: {processed}只, {time.time()-t0:.0f}s', flush=True)
print(f'天数: {len(data_by_date)}', flush=True)

# 4. 保存
new_cache = {'data': dict(data_by_date), 'names': names, 'real': real, 'build_time': time.time()}
with open('big_cache_full.pkl', 'wb') as f:
    pickle.dump(new_cache, f)

elapsed = time.time() - t0
sz = os.path.getsize('big_cache_full.pkl')
print(f'保存完成 {sz/1024/1024:.0f}MB, {elapsed:.0f}s', flush=True)
