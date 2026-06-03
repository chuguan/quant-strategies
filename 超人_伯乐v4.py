"""超人策略 v4 — 伯乐优化版（根据达标分析修正评分盲区）"""
import pickle, json, os, itertools

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
with open('big_cache.pkl','rb') as f:
    cache = pickle.load(f)
d, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(d.keys())

train = [dt for dt in dates if dt.startswith('2026-04') or dt.startswith('2026-05')]
val_q1 = [dt for dt in dates if dt.startswith('2026-01') or dt.startswith('2026-02') or dt.startswith('2026-03')]
val_25 = [dt for dt in dates if dt.startswith('2025')]

print(f'训练(4~5月): {len(train)}天 | Q1:{len(val_q1)}天 | 2025:{len(val_25)}天', flush=True)

def evaluate(params, dl):
    def score(pct, vr, cl, sz):
        sc = params['base']
        # 涨幅细分
        for lo, hi, pts in params['p_tiers']:
            if lo <= pct <= hi: sc += pts; break
        # CL细分
        for lo, hi, pts in params['cl_tiers']:
            if lo <= cl <= hi: sc += pts; break
        # 量比细分
        for lo, hi, pts in params['vr_tiers']:
            if lo <= vr <= hi: sc += pts; break
        # 市值加分（中盘股加分）
        for lo, hi, pts in params.get('sz_tiers', []):
            if lo <= sz <= hi: sc += pts; break
        return sc
    
    results = []
    for dt in dl:
        if dt.endswith('-22') and '2026' in dt: continue
        stocks = d.get(dt, [])
        cand = []
        for s in stocks:
            pct = s['p']
            if pct < 5 or pct > 8: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < 0.5: continue
            code = s['code']
            ri = real.get(code)
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < params['hsl_min'] or hsl > params['hsl_max']: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz >= params['sz_max']: continue
            nm = names.get(code,'')
            if 'ST' in nm or '*ST' in nm: continue
            jv = s.get('j_val',0) or 0
            if jv > params['j_max']: continue
            cl = s.get('cl',0)
            
            sc = score(pct, vr, cl, sz)
            nv = s.get('n',0) or 0
            cand.append((sc, nm, code, pct, nv, sz))
        
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[3]))
        results.append(cand[0][4])
    
    if not results: return 0, 0, 0
    h2 = sum(1 for v in results if v >= 2.5)
    h5 = sum(1 for v in results if v >= 5)
    return h2/len(results)*100, h5/len(results)*100, sum(results)/len(results)

# 原版基准
orig = {
    'base':10,
    'p_tiers':[(5,6.5,15),(6.5,7,8),(4.5,5,5),(7,8,-15)],
    'cl_tiers':[(70,85,15),(85,90,5),(60,70,3),(90,100,-20)],
    'vr_tiers':[(1.2,2.0,10),(2.0,3.0,5),(1.0,1.2,3),(3,10,-15)],
    'hsl_min':5,'hsl_max':15,'sz_max':200,'j_max':100,
}
v22 = {  # 当前最优v2.2
    'base':10,
    'p_tiers':[(5,6.5,15),(6.5,7,8),(4.5,5,5),(7,8,-15)],
    'cl_tiers':[(60,85,10),(85,90,0),(90,100,-15)],
    'vr_tiers':[(0.8,1.5,10),(1.5,3.0,0),(3,10,-10)],
    'hsl_min':5,'hsl_max':15,'sz_max':150,'j_max':80,
    'sz_tiers':[]
}

print(f'\n原版:  训{evaluate(orig, train)[0]:.1f}% 验{evaluate(orig, val_q1)[0]:.1f}% 25{evaluate(orig, val_25)[0]:.1f}%', flush=True)
print(f'v2.2: 训{evaluate(v22, train)[0]:.1f}% 验{evaluate(v22, val_q1)[0]:.1f}% 25{evaluate(v22, val_25)[0]:.1f}%', flush=True)

# ===== 新发现优化 =====
# 根据达标分析，关键发现：
# 1. CL 85~90%达标率65.5%（最高！）但当前给0分 → 应加分
# 2. 涨幅5~5.5%达标率64.3% vs 5.5~6%仅38.9% → 应分开评分
# 3. 量比1.0~1.2达标率65.2% → 当前0分，应加分
# 4. 市值80亿+达标率更高 → 应加分
# 5. J值50~65达标率65.2% → 可加分

best = None
best_score = 0
log = []

# 参数测试
p_tier_options = [
    [(5,6.5,15),(6.5,7,8),(4.5,5,5),(7,8,-15)],                            # v2.2原样
    [(5,5.5,18),(5.5,6,8),(6,6.5,18),(6.5,7,8),(4.5,5,5),(7,8,-15)],      # 细分5~5.5和6~6.5
    [(5,5.5,18),(5.5,6,8),(6,6.5,18),(6.5,7,10),(4.5,5,5),(7,8,-15)],     # 同上+6.5~7加分
]

cl_tier_options = [
    [(60,85,10),(85,90,0),(90,100,-15)],                                        # v2.2
    [(60,85,10),(85,90,8),(90,100,-15)],                                         # 85~90给8分（黄金区间！）
    [(60,80,8),(80,88,10),(88,92,5),(92,100,-15)],                              # 80~88给10分
    [(60,85,10),(85,88,10),(88,92,5),(92,100,-15)],                             # 细分
    [(60,80,10),(80,85,12),(85,90,10),(90,100,-15)],                            # 80~85最高
    [(60,85,10),(85,90,10),(90,100,-15)],                                        # 85~90给10分
]

vr_tier_options = [
    [(0.8,1.5,10),(1.5,3.0,0),(3,10,-10)],                                      # v2.2
    [(0.8,1.0,8),(1.0,1.2,12),(1.2,1.5,10),(1.5,2.5,3),(2.5,10,-8)],           # 1.0~1.2最高分
    [(1.0,1.2,15),(0.8,1.0,10),(1.2,1.5,10),(1.5,2.0,5),(2.0,10,-8)],          # 1.0~1.2重点
    [(0.8,1.5,10),(1.5,2.0,5),(2.0,10,-8)],                                     # 简化
]

sz_tier_options = [
    [],                                                                          # 无市值加分
    [(50,80,3),(80,150,5)],                                                      # 80亿+加5分
    [(50,80,5),(80,150,8)],                                                      # 80亿+加8分
    [(50,150,5)],                                                                # 50亿以上都加
]

j_tier_options = [
    [80],  # J<80
    [90],  # J<90
]

hsl_opts = [(5,15), (5,18)]
sz_max_opts = [150, 200]

total = len(p_tier_options) * len(cl_tier_options) * len(vr_tier_options) * len(sz_tier_options) * len(j_tier_options) * len(hsl_opts) * len(sz_max_opts)
print(f'\n搜索组合: {total}', flush=True)

idx = 0
for pt in p_tier_options:
  for ct in cl_tier_options:
    for vt in vr_tier_options:
      for st in sz_tier_options:
        for jm in j_tier_options:
          for hs in hsl_opts:
            for szm in sz_max_opts:
                p = dict(v22)
                p['p_tiers'] = pt
                p['cl_tiers'] = ct
                p['vr_tiers'] = vt
                p['sz_tiers'] = st
                p['j_max'] = jm[0]
                p['hsl_min'], p['hsl_max'] = hs[0], hs[1]
                p['sz_max'] = szm
                
                idx += 1
                t_r, _, _ = evaluate(p, train)
                v_r, _, _ = evaluate(p, val_q1)
                y_r, _, _ = evaluate(p, val_25)
                
                sc = t_r * 0.45 + v_r * 0.35 + y_r * 0.20
                
                if sc > best_score:
                    best_score = sc
                    best = p
                
                log.append((sc, t_r, v_r, y_r, p))

log.sort(key=lambda x: -x[0])
print(f'\n测试{idx}组合完成', flush=True)

print(f'\nTop5 最佳（伯乐优化版）:', flush=True)
for rank, (sc, t_r, v_r, y_r, p) in enumerate(log[:5], 1):
    print(f'\n#{rank} 加权{sc:.1f}% | 训{t_r:.1f}% 验Q1{v_r:.1f}% 25{y_r:.1f}%', flush=True)
    print(f'  涨幅: {p["p_tiers"]}', flush=True)
    print(f'  CL:   {p["cl_tiers"]}', flush=True)
    print(f'  量比: {p["vr_tiers"]}', flush=True)
    print(f'  市值: {p["sz_tiers"] or "无"}{" | 市值上限"+str(p["sz_max"]):<15} 换手{p["hsl_min"]}~{p["hsl_max"]}% J<{p["j_max"]}', flush=True)

# 最佳 vs v2.2 vs 原版
bp = log[0][4]
print(f'\n{"="*80}')
print(f'  全面对比')
print(f'{"="*80}')
print(f'{"":<20} {"原版":<12} {"v2.2":<12} {"伯乐v4":<12} {"v4提升":<10}')
print(f'{"":-<70}')
for name, dl in [('训练4~5月', train), ('验证1~3月', val_q1), ('2025全年', val_25)]:
    o2, _, _ = evaluate(orig, dl)
    v2, _, _ = evaluate(v22, dl)
    b2, _, _ = evaluate(bp, dl)
    print(f'{name:<20} {o2:<12.1f} {v2:<12.1f} {b2:<12.1f} {b2-v2:>+7.1f}%', flush=True)

all_26 = [dt for dt in dates if dt.startswith('2026')]
o2, _, _ = evaluate(orig, all_26)
v2, _, _ = evaluate(v22, all_26)
b2, _, _ = evaluate(bp, all_26)
print(f'{"2026全年":<20} {o2:<12.1f} {v2:<12.1f} {b2:<12.1f} {b2-v2:>+7.1f}%', flush=True)

print(f'\n近5天（伯乐v4）:', flush=True)
for dt in ['2026-05-19','2026-05-20','2026-05-21','2026-05-22']:
    p = bp
    stocks = d.get(dt, [])
    cand = []
    for s in stocks:
        pct = s['p']
        if pct < 5 or pct > 8: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < 0.5: continue
        ri = real.get(s['code'])
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < p['hsl_min'] or hsl > p['hsl_max']: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= p['sz_max']: continue
        nm = names.get(s['code'],'')
        if 'ST' in nm or '*ST' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > p['j_max']: continue
        cl = s.get('cl',0)
        
        sc = p['base']
        for lo,hi,pts in p['p_tiers']:
            if lo <= pct <= hi: sc += pts; break
        for lo,hi,pts in p['cl_tiers']:
            if lo <= cl <= hi: sc += pts; break
        for lo,hi,pts in p['vr_tiers']:
            if lo <= vr <= hi: sc += pts; break
        for lo,hi,pts in p.get('sz_tiers',[]):
            if lo <= sz <= hi: sc += pts; break
        
        nv = s.get('n',0) or 0
        cand.append((sc, nm, s['code'], pct, nv, sz, cl, vr, jv))
    
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[3]))
    c = cand[0]
    ns = f'{c[4]:+.2f}%' if c[4] else 'N/A'
    ok = '🔥' if c[4] >= 5 else ('✅' if c[4] >= 2.5 else '❌')
    print(f'  {dt}: {c[1]}({c[2]}) 评{c[0]} 涨{c[3]:.1f}% CL{c[6]:.0f}% 量{c[7]:.2f} 市值{c[5]:.0f}亿 → {ns} {ok}', flush=True)
