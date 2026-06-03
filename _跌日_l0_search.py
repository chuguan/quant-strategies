"""
跌日L0收紧优化：目标池质量≥70%，同时每天>8只候选
"""
import pickle, sys, os

with open(os.path.join(os.path.dirname(__file__), 'big_cache_full.pkl'), 'rb') as f:
    cache = pickle.load(f)
data = cache['data']
real_data = cache.get('real', {})
names = cache.get('names', {})

dates = sorted(x for x in data.keys() if '2025-06-01' <= x < '2026-06-01')

def classify_mkt(stocks):
    ps = [s.get('p',0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps) if ps else 0
    avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

# 收集所有跌日数据
all_down = []
for dt in dates:
    s = data.get(dt, [])
    m = classify_mkt(s)
    if m == 'down':
        all_down.append((dt, s))

print(f"跌日样本: {len(all_down)}天")

def filter_pool(stocks, p1, p2, v1, v2, c1, c2, h1, h2, sz):
    pool = []
    for sx in stocks:
        code = sx.get('code','')
        p = (sx.get('p',0) or 0)
        if p < p1 or p > p2: continue
        if p >= 8: continue
        vr = (sx.get('vol_ratio',0) or 0)
        if vr < v1 or vr > v2: continue
        cl = (sx.get('cl',0) or 0)
        if cl < c1 or cl > c2: continue
        ri = real_data.get(code)
        if ri:
            hsl = (ri.get('hsl',0) or 0)
            if hsl < h1 or hsl > h2: continue
            szv = ri.get('shizhi',0) or 0
            if isinstance(szv,(int,float)) and szv > 1: szv *= 1e-8
            if szv >= sz: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        nh = (sx.get('n',0) or 0)
        if nh <= 0: continue
        pool.append({'code': code, 'nm': names.get(code,'')[:6], 'nh': nh, 'p': p})
    return pool

# 跌日L0收紧搜索
print("\n搜索收紧L0参数...")
results = []

# 跌日当前L0: p[-3,7] vr[0.4,3.5] cl[10,98] hs[1,30] sz[300]
# 收紧方向：缩窄涨幅范围、提高量比下限、缩窄CL范围

# 跌日是跌日，大部分票都是跌的。要选"抗跌/反弹"的票
# p 应该选正涨幅的（逆势上涨的票）
for p1 in [1, 2, 3, 4]:
    for p2 in [5, 6, 7]:
        for v1 in [0.6, 0.8, 1.0]:
            for v2 in [1.2, 1.5, 2.0]:
                for c1 in [50, 60, 65]:
                    for c2 in [80, 85, 90]:
                        for h1 in [3, 5, 8]:
                            for h2 in [10, 15, 20]:
                                for sz_max in [50, 100, 150, 200]:
                                    day_stats = []
                                    for dt, s in all_down:
                                        pool = filter_pool(s, p1, p2, v1, v2, c1, c2, h1, h2, sz_max)
                                        if not pool:
                                            continue
                                        n = len(pool)
                                        qual = sum(1 for x in pool if x['nh'] >= 2.5)
                                        rate = qual/n*100
                                        day_stats.append({'n': n, 'qual': qual, 'rate': rate})
                                    
                                    if len(day_stats) < 3:  # 至少要3天有票
                                        continue
                                    
                                    # 统计
                                    total_n = sum(d['n'] for d in day_stats)
                                    total_qual = sum(d['qual'] for d in day_stats)
                                    pool_rate = total_qual/total_n*100 if total_n else 0
                                    avg_day_rate = sum(d['rate'] for d in day_stats)/len(day_stats)
                                    all_ok = all(8 < d['n'] <= 500 for d in day_stats)  # 每天8~500只
                                    ok_days = sum(1 for d in day_stats if 8 < d['n'])
                                    
                                    if avg_day_rate >= 60 and pool_rate >= 50:  # 目标池质量≥60%
                                        results.append({
                                            'pool_rate': pool_rate,
                                            'avg_day_rate': avg_day_rate,
                                            'n_days': len(day_stats),
                                            'ok_days': ok_days,
                                            'avg_n': total_n/len(day_stats),
                                            'params': (p1, p2, v1, v2, c1, c2, h1, h2, sz_max),
                                            'all_ok': all_ok
                                        })

# 排序
results.sort(key=lambda x: (-x['pool_rate'], -x['avg_day_rate']))

print(f"找到 {len(results)} 组参数 (池质量≥50%)")
print(f"\nTop 15:")
print(f"{'池质量':>8} {'日均率':>7} {'天数':>5} {'出票':>5} {'候选/天':>8} 参数")
print("-"*80)
for r in results[:15]:
    p1,p2,v1,v2,c1,c2,h1,h2,sz = r['params']
    print(f"  {r['pool_rate']:6.1f}% {r['avg_day_rate']:6.1f}% {r['n_days']:5d} {r['ok_days']:5d} {r['avg_n']:8.1f}  p[{p1},{p2}] vr[{v1},{v2}] cl[{c1},{c2}] hsl[{h1},{h2}] sz<{sz}")

# 显示按池质量≥70%过滤的结果
print(f"\n\n池质量≥70%的结果:")
top70 = [r for r in results if r['pool_rate'] >= 70]
if top70:
    for r in top70[:10]:
        p1,p2,v1,v2,c1,c2,h1,h2,sz = r['params']
        print(f"  {r['pool_rate']:6.1f}% {r['avg_day_rate']:6.1f}% {r['n_days']:5d}天 {r['avg_n']:4.0f}只/天 p[{p1},{p2}] vr[{v1},{v2}] cl[{c1},{c2}] hsl[{h1},{h2}] sz<{sz}")
else:
    print("  无结果达到70%")
    # 显示最接近的
    print(f"\n最接近的:")
    for r in results[:5]:
        p1,p2,v1,v2,c1,c2,h1,h2,sz = r['params']
        print(f"  {r['pool_rate']:6.1f}% {r['avg_day_rate']:6.1f}% {r['n_days']:5d}天 {r['avg_n']:4.0f}只/天 p[{p1},{p2}] vr[{v1},{v2}] cl[{c1},{c2}] hsl[{h1},{h2}] sz<{sz}")
