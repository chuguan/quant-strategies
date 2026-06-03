"""
跌日L1~L4分级设计
- L1: 最严，池质量最高（>8只就停）
- L2: 略放宽
- L3: 再放宽
- L4: 最宽松（保底出票）
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
    if sum(ps)/len(ps) < -0.5: return 'down'
    return 'flat'

down_dates = [dt for dt in dates if classify_mkt(data.get(dt,[])) == 'down']
print(f"跌日: {len(down_dates)}天", flush=True)

def test_level(label, p1, p2, v1, v2, c1, c2, h1, h2, sz):
    """测试一个级别的池质量和出票情况"""
    day_stats = []
    for dt in down_dates:
        s = data.get(dt, [])
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
        return 0, 0, 0, 0, 0
    
    total_n = sum(d['n'] for d in day_stats)
    total_qual = sum(d['qual'] for d in day_stats)
    return (
        total_qual/total_n*100,          # 池总质量
        total_n/len(day_stats),          # 平均候选
        len(day_stats),                   # 出票天数
        len(down_dates),                  # 总天数
        sum(d['rate'] for d in day_stats)/len(day_stats)  # 日均质量
    )

# 搜索L1~L4的4级参数
# 从最严到最松
print("\n=== 搜索L1最佳参数（最高质量）===", flush=True)
l1_options = []
for p1 in [2, 3]:
    for p2 in [6, 7]:
        for v1 in [0.6, 0.8]:
            for v2 in [1.2, 1.5]:
                for c1 in [40, 50, 60]:
                    for c2 in [80, 85]:
                        for h1 in [5, 8]:
                            for h2 in [12, 15, 20]:
                                for sz_max in [50, 80, 100]:
                                    rate, avg, ok, total, day_rate = test_level('', p1, p2, v1, v2, c1, c2, h1, h2, sz_max)
                                    if ok >= total * 0.5 and avg >= 10:  # 至少一半天出票，候选>=10
                                        l1_options.append((rate, ok, total, avg, day_rate, p1, p2, v1, v2, c1, c2, h1, h2, sz_max))

l1_options.sort(key=lambda x: (-x[0], -x[1]))
for r in l1_options[:15]:
    rate, ok, total, avg, day_rate, *params = r
    p1,p2,v1,v2,c1,c2,h1,h2,sz = params
    print(f"  质量{rate:5.1f}% 出票{ok}/{total}天 候选{avg:3.0f}只 日质量{day_rate:5.1f}%  p[{p1},{p2}] vr[{v1},{v2}] cl[{c1},{c2}] hsl[{h1},{h2}] sz<{sz}", flush=True)

# 从中选择L1
print("\n\n=== 推荐L1~L4方案 ===", flush=True)

# 方案1: 质量优先 (L1质量最高+逐级放宽)
levels_schemes = [
    {
        'name': '方案A: 质量优先',
        'L1': {'p1':3,'p2':7,'v1':0.8,'v2':1.5,'c1':50,'c2':85,'h1':8,'h2':20,'sz':100},
        'L2': {'p1':2,'p2':7,'v1':0.6,'v2':1.5,'c1':40,'c2':90,'h1':5,'h2':20,'sz':150},
        'L3': {'p1':1,'p2':7,'v1':0.5,'v2':2.0,'c1':30,'c2':95,'h1':3,'h2':30,'sz':200},
        'L4': {'p1':-1,'p2':7,'v1':0.4,'v2':2.5,'c1':10,'c2':98,'h1':1,'h2':30,'sz':300},
    },
    {
        'name': '方案B: 平衡型',
        'L1': {'p1':2,'p2':7,'v1':0.6,'v2':1.5,'c1':50,'c2':85,'h1':5,'h2':15,'sz':80},
        'L2': {'p1':2,'p2':7,'v1':0.6,'v2':2.0,'c1':40,'c2':90,'h1':3,'h2':20,'sz':150},
        'L3': {'p1':1,'p2':7,'v1':0.5,'v2':2.5,'c1':20,'c2':95,'h1':1,'h2':30,'sz':200},
        'L4': {'p1':-1,'p2':7,'v1':0.3,'v2':3.0,'c1':5,'c2':99,'h1':1,'h2':30,'sz':300},
    },
]

for scheme in levels_schemes:
    print(f"\n--- {scheme['name']} ---", flush=True)
    lvl_names = ['L1','L2','L3','L4']
    prev_ok = 0
    for lvl in lvl_names:
        p = scheme[lvl]
        rate, avg, ok, total, day_rate = test_level(lvl, p['p1'],p['p2'],p['v1'],p['v2'],
                                                     p['c1'],p['c2'],p['h1'],p['h2'],p['sz'])
        # 模拟分级选股：L1先筛，不够到L2...
        cumulative = ok
        if cumulative >= total:
            label = "✅独立出票100%"
        elif cumulative >= total * 0.8:
            label = f"✅独立出票{ok}/{total}"
        else:
            label = f"⚠️独立出票{ok}/{total}，需上级兜底"
        print(f"  {lvl}: 质量{rate:5.1f}%  候选{avg:4.0f}只  {label}", flush=True)

print(f"\n耗时: {time.time()-t0:.0f}s", flush=True)
