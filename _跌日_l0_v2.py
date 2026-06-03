"""
跌日L0收紧搜索 - 条件：
1️⃣ 出票率=100%（每天必须>8只）
2️⃣ 目标池质量≥70%（候选票中次日≥2.5%比例）
3️⃣ 只用当天数据选股，nh仅用于验证
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
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps)
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

down_dates = [dt for dt in dates if classify_mkt(data.get(dt,[])) == 'down']
print(f"跌日: {len(down_dates)}天")

# 跌日收紧方向：选逆势上涨+缩量回调+CL中位
# 先分析单参数对池质量的影响
print("\n=== 单参数分析 ===")

# 固定其他条件：p[2,6] vr[0.8,1.5] cl[50,85] hsl[3,15] sz<100
def test_param(param_name, values):
    results = []
    for val in values:
        day_pools = []
        for dt in down_dates:
            s = data.get(dt, [])
            pool = []
            for sx in s:
                code = sx.get('code','')
                p = (sx.get('p',0) or 0)
                if p < 2 or p > 6: continue
                if p >= 8: continue
                vr = (sx.get('vol_ratio',0) or 0)
                if vr < 0.8 or vr > 1.5: continue
                cl = (sx.get('cl',0) or 0)
                if cl < 50 or cl > 85: continue
                ri = real_data.get(code)
                if ri:
                    hsl = (ri.get('hsl',0) or 0)
                    if hsl < 3 or hsl > 15: continue
                    szv = ri.get('shizhi',0) or 0
                    if isinstance(szv,(int,float)) and szv > 1: szv *= 1e-8
                    if szv >= 100: continue
                nm = names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                nh = (sx.get('n',0) or 0)
                if nh <= 0: continue
                pool.append(nh)
            if len(pool) > 8:
                day_pools.append(pool)
        
        if day_pools and len(day_pools) == len(down_dates):  # 100%出票
            total = sum(len(p) for p in day_pools)
            qual = sum(sum(1 for nh in p if nh >= 2.5) for p in day_pools)
            rate = qual/total*100
            avg_n = total/len(day_pools)
            results.append((val, rate, len(day_pools), avg_n))
    return results

# p（涨幅）影响
print("\n【p涨幅】固定: vr[0.8,1.5] cl[50,85] hsl[3,15] sz<100")
for p_min in [1, 2, 3]:
    for p_max in [5, 6, 7]:
        # 不能>=8
        if p_max >= 8: p_max = 7
        day_pools = []
        for dt in down_dates:
            s = data.get(dt, [])
            pool = []
            for sx in s:
                code = sx.get('code','')
                p = (sx.get('p',0) or 0)
                if p < p_min or p > p_max: continue
                if p >= 8: continue
                vr = (sx.get('vol_ratio',0) or 0)
                if vr < 0.8 or vr > 1.5: continue
                cl = (sx.get('cl',0) or 0)
                if cl < 50 or cl > 85: continue
                ri = real_data.get(code)
                if ri:
                    hsl = (ri.get('hsl',0) or 0)
                    if hsl < 3 or hsl > 15: continue
                    szv = ri.get('shizhi',0) or 0
                    if isinstance(szv,(int,float)) and szv > 1: szv *= 1e-8
                    if szv >= 100: continue
                nm = names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                nh = (sx.get('n',0) or 0)
                if nh <= 0: continue
                pool.append(nh)
            if len(pool) > 8:
                day_pools.append(pool)
        if len(day_pools) == len(down_dates):  # 100%出票
            total = sum(len(p) for p in day_pools)
            qual = sum(sum(1 for nh in p if nh >= 2.5) for p in day_pools)
            print(f"  p[{p_min},{p_max}]: {qual/total*100:.1f}% ({qual}/{total})  {total/len(day_pools):.0f}只/天 ✅100%出票")
        elif day_pools:
            print(f"  p[{p_min},{p_max}]: {len(day_pools)}/{len(down_dates)}天 ❌")

print("\n\n=== 综合网格搜索（仅100%出票结果）===")
results = []
checked = 0
for p1 in [1, 2, 3]:
    for p2 in [5, 6, 7]:
        for v1 in [0.6, 0.8, 1.0]:
            for v2 in [1.2, 1.5]:
                for c1 in [40, 50, 60]:
                    for c2 in [75, 80, 85]:
                        for h1 in [3, 5, 8]:
                            for h2 in [10, 15]:
                                for sz_max in [50, 100, 150]:
                                    checked += 1
                                    if checked % 500 == 0:
                                        print(f"  进度: {checked}", end='\r')
                                    
                                    day_stats = []
                                    for dt in down_dates:
                                        s = data.get(dt, [])
                                        pool = []
                                        for sx in s:
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
                                                if szv >= sz_max: continue
                                            nm = names.get(code,'')
                                            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                                            nh = (sx.get('n',0) or 0)
                                            if nh <= 0: continue
                                            pool.append({'nh': nh})
                                        if len(pool) > 8:
                                            qual = sum(1 for x in pool if x['nh'] >= 2.5)
                                            day_stats.append({'n': len(pool), 'qual': qual})
                                    
                                    # 出票率=100%
                                    if len(day_stats) == len(down_dates):
                                        total = sum(d['n'] for d in day_stats)
                                        qual = sum(d['qual'] for d in day_stats)
                                        rate = qual/total*100
                                        results.append({
                                            'rate': rate, 'n_days': len(day_stats),
                                            'avg_n': total/len(day_stats),
                                            'params': (p1,p2,v1,v2,c1,c2,h1,h2,sz_max)
                                        })

print(f"\n检查了{checked}组参数")
print(f"100%出票的参数: {len(results)}组")

results.sort(key=lambda x: (-x['rate']))

print(f"\n{'='*70}")
print("跌日L0参数搜索 | 出票率=100%条件 | 按池质量排序")
print(f"{'='*70}")
print(f"{'池质量':>8} {'天数':>4} {'候选/天':>9}  参数")
print("-"*60)

for r in results[:30]:
    p1,p2,v1,v2,c1,c2,h1,h2,sz = r['params']
    print(f"{r['rate']:6.1f}% {r['n_days']:4d}天 {r['avg_n']:5.0f}只   p[{p1},{p2}] vr[{v1},{v2}] cl[{c1},{c2}] hsl[{h1},{h2}] sz<{sz}")

# 池质量≥70%过滤
print(f"\n\n=== 池质量≥65% ===")
top = [r for r in results if r['rate'] >= 65]
if top:
    for r in top[:15]:
        p1,p2,v1,v2,c1,c2,h1,h2,sz = r['params']
        print(f"{r['rate']:6.1f}% {r['n_days']:3d}天 {r['avg_n']:3.0f}只  p[{p1},{p2}] vr[{v1},{v2}] cl[{c1},{c2}] hsl[{h1},{h2}] sz<{sz}")
else:
    print("无≥65%的结果")
    if results:
        print(f"\n最接近的:")
        for r in results[:5]:
            p1,p2,v1,v2,c1,c2,h1,h2,sz = r['params']
            print(f"{r['rate']:6.1f}% {r['n_days']:3d}天 {r['avg_n']:3.0f}只  p[{p1},{p2}] vr[{v1},{v2}] cl[{c1},{c2}] hsl[{h1},{h2}] sz<{sz}")
