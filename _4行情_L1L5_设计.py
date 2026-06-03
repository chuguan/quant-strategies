"""
4行情L1~L5分级选股设计
规则：
1. L1最严→L5最松，L1达标(>8只)即停
2. 只用当天数据选池，次日nh只用于验证
3. 遵从基本准则：p<8%, 非ST, 主板A股
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

def test_level(stocks_list, p1, p2, v1, v2, c1, c2, h1, h2, sz):
    """测试该级别在某行情的池质量"""
    day_stats = []
    for s in stocks_list:
        pool = []
        for sx in s:
            code = sx.get('code','')
            pv = (sx.get('p',0) or 0)
            if pv < p1 or pv > p2: continue
            if pv >= 8: continue
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
            pool.append(nh)
        
        if len(pool) > 8:
            qual = sum(1 for nh in pool if nh >= 2.5)
            day_stats.append({'n': len(pool), 'qual': qual, 'rate': qual/len(pool)*100})
    
    if not day_stats:
        return 0, 0, 0, len(stocks_list), 0
    total_n = sum(d['n'] for d in day_stats)
    total_qual = sum(d['qual'] for d in day_stats)
    return (
        total_qual/total_n*100,          # 池总质量
        total_n/len(day_stats),          # 平均候选
        len(day_stats),                   # 出票天数
        len(stocks_list),                 # 总天数
        sum(d['rate'] for d in day_stats)/len(day_stats)  # 日均质量
    )

# 按行情分组
mkt_data = {'real_up':[], 'fake_up':[], 'down':[], 'flat':[]}
for dt in dates:
    s = data.get(dt, [])
    m = classify_mkt(s)
    if m in mkt_data:
        mkt_data[m].append(s)

# ===== 设计各行情分级 =====
print("="*80, flush=True)
print("4行情 L1~L4分级选股设计", flush=True)
print("="*80, flush=True)

# --- 真实涨日 ---
print("\n\n【真实涨日】87天", flush=True)
# L1: 基于当前V260529最优参数收紧
# L2: 略放宽
# L3: 中等
# L4: 保底
levels_real = [
    ('L1', (3.5, 6, 0.8, 2.0, 65, 85, 5, 10, 100)),
    ('L2', (3, 7, 0.6, 2.5, 60, 90, 5, 15, 150)),
    ('L3', (2, 7, 0.6, 2.5, 50, 95, 3, 20, 200)),
    ('L4', (1, 7, 0.5, 3.0, 40, 98, 2, 25, 300)),
]
stocks = mkt_data['real_up']
for name, params in levels_real:
    p1,p2,v1,v2,c1,c2,h1,h2,sz = params
    rate, avg, ok, total, day_r = test_level(stocks, *params)
    pct = (ok/total*100) if total > 0 else 0
    print(f"  {name}: p[{p1},{p2}] vr[{v1},{v2}] cl[{c1},{c2}] hsl[{h1},{h2}] sz<{sz}", flush=True)
    print(f"        质量{rate:5.1f}%  日均{avg:4.0f}只  出票{ok}/{total}天({pct:.0f}%)  日平均质量{day_r:.1f}%", flush=True)

# 模拟分级结果
print(f"\n  分级模拟:", flush=True)
for name, params in levels_real:
    p1,p2,v1,v2,c1,c2,h1,h2,sz = params
    cnt = 0
    for s in stocks:
        pool_l = []
        for sx in s:
            code = sx.get('code','')
            pv = (sx.get('p',0) or 0)
            if pv < p1 or pv > p2: continue
            if pv >= 8: continue
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
            pool_l.append(nh)
        if len(pool_l) > 8:
            cnt += 1
    print(f"    {name}: 独立出票{cnt}/{len(stocks)}天({cnt/len(stocks)*100:.0f}%)", flush=True)

# --- 跌日 ---
print("\n\n【跌日】57天", flush=True)
levels_down = [
    ('L1', (3, 7, 0.8, 1.5, 50, 85, 8, 20, 100)),
    ('L2', (2, 7, 0.6, 1.5, 40, 90, 5, 20, 150)),
    ('L3', (1, 7, 0.5, 2.0, 30, 95, 3, 25, 200)),
    ('L4', (-1, 7, 0.4, 2.5, 10, 98, 1, 30, 300)),
]
stocks = mkt_data['down']
for name, params in levels_down:
    p1,p2,v1,v2,c1,c2,h1,h2,sz = params
    rate, avg, ok, total, day_r = test_level(stocks, *params)
    pct = (ok/total*100) if total > 0 else 0
    print(f"  {name}: p[{p1},{p2}] vr[{v1},{v2}] cl[{c1},{c2}] hsl[{h1},{h2}] sz<{sz}", flush=True)
    print(f"        质量{rate:5.1f}%  日均{avg:4.0f}只  出票{ok}/{total}天({pct:.0f}%)", flush=True)

# --- 横盘 ---
print("\n\n【横盘】90天", flush=True)
levels_flat = [
    ('L1', (2, 6, 0.8, 1.5, 60, 85, 5, 15, 100)),
    ('L2', (1, 7, 0.6, 2.0, 50, 90, 3, 20, 150)),
    ('L3', (0, 7, 0.5, 2.5, 40, 95, 2, 25, 200)),
    ('L4', (-1, 7, 0.4, 3.0, 30, 98, 1, 30, 300)),
]
stocks = mkt_data['flat']
for name, params in levels_flat:
    p1,p2,v1,v2,c1,c2,h1,h2,sz = params
    rate, avg, ok, total, day_r = test_level(stocks, *params)
    pct = (ok/total*100) if total > 0 else 0
    print(f"  {name}: p[{p1},{p2}] vr[{v1},{v2}] cl[{c1},{c2}] hsl[{h1},{h2}] sz<{sz}", flush=True)
    print(f"        质量{rate:5.1f}%  日均{avg:4.0f}只  出票{ok}/{total}天({pct:.0f}%)", flush=True)

# --- 虚涨日 ---
print("\n\n【虚涨日】5天(样本少，仅供参考)", flush=True)
levels_fake = [
    ('L1', (2, 6, 0.8, 1.5, 50, 85, 8, 15, 100)),
    ('L2', (1, 6, 0.6, 2.0, 40, 90, 5, 20, 150)),
    ('L3', (0, 7, 0.5, 2.5, 30, 95, 3, 25, 200)),
    ('L4', (-1, 7, 0.4, 3.0, 20, 98, 2, 30, 300)),
]
stocks = mkt_data['fake_up']
for name, params in levels_fake:
    p1,p2,v1,v2,c1,c2,h1,h2,sz = params
    rate, avg, ok, total, day_r = test_level(stocks, *params)
    pct = (ok/total*100) if total > 0 else 0
    print(f"  {name}: p[{p1},{p2}] vr[{v1},{v2}] cl[{c1},{c2}] hsl[{h1},{h2}] sz<{sz}", flush=True)
    print(f"        质量{rate:5.1f}%  日均{avg:4.0f}只  出票{ok}/{total}天({pct:.0f}%)", flush=True)

# ===== 分级模拟：L1→L5选股结果 =====
print("\n\n" + "="*80, flush=True)
print("分级选股模拟 (L1先筛，不够到L2，以此类推)", flush=True)
print("="*80, flush=True)

def simulate_grading(stocks_list, level_defs):
    """模拟L1→L5分级选股"""
    day_results = []
    for s in stocks_list:
        used_lvl = None
        pool = []
        for name, params in level_defs:
            p1,p2,v1,v2,c1,c2,h1,h2,sz = params
            pool = []
            for sx in s:
                code = sx.get('code','')
                pv = (sx.get('p',0) or 0)
                if pv < p1 or pv > p2: continue
                if pv >= 8: continue
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
                pool.append(nh)
            
            if len(pool) > 8:
                used_lvl = name
                break
            pool = []
        
        if pool:
            qual = sum(1 for nh in pool if nh >= 2.5)
            day_results.append({'n': len(pool), 'qual': qual, 'rate': qual/len(pool)*100, 'lvl': used_lvl})
        else:
            day_results.append({'n': 0, 'qual': 0, 'rate': 0, 'lvl': '弃权'})
    
    return day_results

for mk, levels, label in [('real_up', levels_real, '真实涨日'), 
                              ('down', levels_down, '跌日'),
                              ('flat', levels_flat, '横盘'),
                              ('fake_up', levels_fake, '虚涨日')]:
    stocks = mkt_data[mk]
    results = simulate_grading(stocks, levels)
    
    total_days = len(results)
    has_cand = sum(1 for r in results if r['n'] > 0)
    all_n = sum(r['n'] for r in results)
    all_qual = sum(r['qual'] for r in results)
    pool_rate = all_qual/all_n*100 if all_n else 0
    
    lvl_count = {}
    for r in results:
        lvl_count[r['lvl']] = lvl_count.get(r['lvl'], 0) + 1
    
    print(f"\n{label}: {total_days}天", flush=True)
    print(f"  最终池质量: {pool_rate:.1f}% ({all_qual}/{all_n})", flush=True)
    print(f"  出票率: {has_cand}/{total_days}天 ({has_cand/total_days*100:.0f}%)", flush=True)
    lvl_order = ['L1','L2','L3','L4','弃权']
    for l in lvl_order:
        if l in lvl_count:
            print(f"    {l}: {lvl_count[l]}天", flush=True)

print(f"\n\n总耗时: {time.time()-t0:.0f}s", flush=True)
