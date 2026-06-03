"""
跌日L0收紧 - 高效版
条件：出票率=100%（每天>8只） | 目标池质量≥70%
"""
import pickle, sys, os, time
sys.stdout.reconfigure(line_buffering=True)

t0 = time.time()
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

# 预加载跌日数据
print("加载跌日数据...", flush=True)
down_data = []
for dt in dates:
    s = data.get(dt, [])
    m = classify_mkt(s)
    if m == 'down':
        down_data.append((dt, s))
print(f"跌日: {len(down_data)}天", flush=True)

# 第1轮：粗筛 - 只调p和cl（最关键的两个参数），固定其他
print("\n=== 第1轮: p×cl粗筛 (固定vr[0.6,1.5] hsl[3,15] sz<150) ===", flush=True)
r1_results = []
for p1 in range(1, 6):
    for p2 in [5,6,7]:
        if p1 >= p2: continue
        for c1 in [30, 40, 50, 60]:
            for c2 in [75, 80, 85]:
                all_ok = True
                day_stats = []
                for dt, s in down_data:
                    pool_nh = []
                    for sx in s:
                        code = sx.get('code','')
                        p = (sx.get('p',0) or 0)
                        if p < p1 or p > p2: continue
                        if p >= 8: continue
                        vr = (sx.get('vol_ratio',0) or 0)
                        if vr < 0.6 or vr > 1.5: continue
                        cl = (sx.get('cl',0) or 0)
                        if cl < c1 or cl > c2: continue
                        ri = real_data.get(code)
                        if ri:
                            hsl = (ri.get('hsl',0) or 0)
                            if hsl < 3 or hsl > 15: continue
                            szv = ri.get('shizhi',0) or 0
                            if isinstance(szv,(int,float)) and szv > 1: szv *= 1e-8
                            if szv >= 150: continue
                        nm = names.get(code,'')
                        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                        nh = (sx.get('n',0) or 0)
                        if nh <= 0: continue
                        pool_nh.append(nh)
                    
                    if len(pool_nh) <= 8:
                        all_ok = False
                        break
                    qual = sum(1 for nh in pool_nh if nh >= 2.5)
                    day_stats.append({'n': len(pool_nh), 'qual': qual})
                
                if not all_ok: continue
                total = sum(d['n'] for d in day_stats)
                qual = sum(d['qual'] for d in day_stats)
                rate = qual/total*100
                r1_results.append({'rate': rate, 'avg_n': total/len(day_stats), 
                                   'params': f"p[{p1},{p2}] cl[{c1},{c2}]"})

r1_results.sort(key=lambda x: -x['rate'])
print(f"100%出票: {len(r1_results)}组", flush=True)
for r in r1_results[:15]:
    print(f"  {r['rate']:5.1f}%  {r['avg_n']:3.0f}只/天  {r['params']}", flush=True)

# 第2轮：基于r1最佳参数，调vr
print("\n\n=== 第2轮: 基于最佳p/cl + 调vr/hsl/sz ===", flush=True)
# 从r1取前5的p/cl组合
top5_pcl = [(r['params'], r['rate']) for r in r1_results[:5]]
for pc_str, base_rate in top5_pcl:
    print(f"\n基于 {pc_str} (基础{base_rate:.1f}%)", flush=True)
    # 解析参数
    parts = pc_str.replace('p[','').replace('] cl[',' ').replace(']','').split()
    p1, p2 = map(int, parts[0].split(','))
    c1, c2 = map(int, parts[1].split(','))
    
    for v1 in [0.6, 0.8, 1.0]:
        for v2 in [1.2, 1.5, 2.0]:
            for h1 in [3, 5, 8]:
                for h2 in [10, 15, 20]:
                    for sz_max in [50, 100, 150, 200]:
                        all_ok = True
                        day_stats = []
                        for dt, s in down_data:
                            pool_nh = []
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
                                pool_nh.append(nh)
                            
                            if len(pool_nh) <= 8:
                                all_ok = False
                                break
                            qual = sum(1 for nh in pool_nh if nh >= 2.5)
                            day_stats.append({'n': len(pool_nh), 'qual': qual})
                        
                        if all_ok:
                            total = sum(d['n'] for d in day_stats)
                            qual = sum(d['qual'] for d in day_stats)
                            rate = qual/total*100
                            if rate >= 60 or (rate >= base_rate - 5):
                                print(f"  {rate:5.1f}%  {total/len(day_stats):3.0f}只/天  p[{p1},{p2}] vr[{v1},{v2}] cl[{c1},{c2}] hsl[{h1},{h2}] sz<{sz_max}", flush=True)

print(f"\n耗时: {time.time()-t0:.0f}s", flush=True)
