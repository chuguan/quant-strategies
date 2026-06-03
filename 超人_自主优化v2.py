"""超人策略 自主学习优化 v2 — 防过拟合"""
import pickle, itertools
from collections import defaultdict

with open('big_cache.pkl','rb') as f:
    c = pickle.load(f)
d, real, names = c['data'], c['real'], c['names']
dates = sorted(d.keys())

train = [dt for dt in dates if dt.startswith('2026-04') or dt.startswith('2026-05')]  # 训练
val_q1 = [dt for dt in dates if dt.startswith('2026-01') or dt.startswith('2026-02') or dt.startswith('2026-03')]  # 验证
val_25 = [dt for dt in dates if dt.startswith('2025')]  # 参考

print(f'训练集(4~5月): {len(train)}天', flush=True)
print(f'验证集(Q1): {len(val_q1)}天', flush=True)
print(f'参考集(2025): {len(val_25)}天', flush=True)

def evaluate(params, dl):
    """跑策略返回统计"""
    def score(pct, vr, cl):
        sc = params['base']
        # 涨幅多段评分
        for lo, hi, pts in params['p_tiers']:
            if lo <= pct <= hi:
                sc += pts
                break
        # CL多段评分
        for lo, hi, pts in params['cl_tiers']:
            if lo <= cl <= hi:
                sc += pts
                break
        # 量比多段评分
        for lo, hi, pts in params['vr_tiers']:
            if lo <= vr <= hi:
                sc += pts
                break
        return sc
    
    results = []
    for dt in dl:
        if dt.endswith('-22') and '2026' in dt: continue
        stocks = d.get(dt, [])
        cand = []
        for s in stocks:
            pct = s['p']
            if pct < params['p_min'] or pct > params['p_max']: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < params['vr_min']: continue
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
            sc = score(pct, vr, cl)
            nv = s.get('n',0) or 0
            cand.append((sc, nm, code, pct, nv, vr, cl, hsl, sz, jv, s.get('close',0)))
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[3]))
        results.append(cand[0][4])
    
    if not results: return 0, 0, 0
    h2 = sum(1 for v in results if v >= 2.5)
    h5 = sum(1 for v in results if v >= 5)
    return h2/len(results)*100, h5/len(results)*100, sum(results)/len(results)

# 原版基准
orig_params = {
    'base':10, 'p_min':5, 'p_max':8, 'vr_min':1.0,
    'p_tiers':[(5,6.5,15),(6.5,7,8),(4.5,5,5),(7,8,-15)],
    'cl_tiers':[(70,85,15),(85,90,5),(60,70,3),(90,100,-20)],
    'vr_tiers':[(1.2,2.0,10),(2.0,3.0,5),(1.0,1.2,3),(3,10,-15)],
    'hsl_min':5,'hsl_max':15,'sz_max':200,'j_max':100
}

print(f'\n原版基准:', flush=True)
t_h2, t_h5, t_avg = evaluate(orig_params, train)
v_h2, v_h5, v_avg = evaluate(orig_params, val_q1)
print(f'  训练(4~5月): 达2.5% {t_h2:.1f}% | 验证(Q1): {v_h2:.1f}% | 加权: {t_h2*0.6+v_h2*0.4:.1f}%', flush=True)

# ===== 搜索空间 =====
best = None
best_score = 0
log = []

# 1. 涨幅多段评分方案
p_tier_options = [
    [(5,6.5,15),(6.5,7,8),(4.5,5,5),(7,8,-15)],       # 原版
    [(5,6.5,12),(6.5,7,5),(4.5,5,5),(7,8,-10)],       # v2.1
    [(5,6.5,15),(6.5,7,5),(4.5,6.5,-5)],              # 简化版
    [(5.5,6.5,15),(5,5.5,8),(6.5,7,5),(4.5,5,5),(7,8,-10)],  # 中段最优
    [(5,6.5,12),(6.5,7.5,3),(4.5,5,5),(4,4.5,3),(7.5,8,-15)], # 放宽到7.5
]

# 2. CL多段评分方案
cl_tier_options = [
    [(70,85,15),(85,90,5),(60,70,3),(90,100,-20)],     # 原版
    [(60,85,10),(85,90,0),(90,100,-15)],               # v2.1
    [(65,85,12),(85,90,3),(55,65,5),(90,100,-15)],     # 多档
    [(60,80,12),(80,88,8),(88,92,3),(92,100,-20),(-1,60,3)],  # 四段
    [(60,82,10),(82,90,5),(90,100,-15),(55,60,3)],     # 中位为主
]

# 3. 量比多段评分方案
vr_tier_options = [
    [(1.2,2.0,10),(2.0,3.0,5),(1.0,1.2,3),(3,10,-15)],  # 原版
    [(0.8,1.5,10),(1.5,3.0,0),(3,10,-10)],              # v2.1
    [(1.0,1.8,12),(1.8,2.5,6),(0.5,1.0,3),(2.5,3.5,0),(3.5,10,-10)], # 多段
    [(1.0,1.5,10),(1.5,2.5,5),(0.8,1.0,5),(2.5,10,-8)], # 均衡
    [(0.8,1.5,12),(1.5,2.0,8),(2.0,3.0,3),(0.5,0.8,3),(3,10,-12)], # 细粒度
]

# 4. 换手/市值/J值
hsl_options = [(5,15),(5,18),(5,20),(3,15),(3,18)]
sz_options = [150, 200, 250]
j_options = [80, 90, 100, 110]
base_options = [10, 8]

total = len(p_tier_options) * len(cl_tier_options) * len(vr_tier_options) * len(hsl_options) * len(sz_options) * len(j_options) * len(base_options)
print(f'\n搜索组合: {total}', flush=True)

idx = 0
for pt in p_tier_options:
  for ct in cl_tier_options:
    for vt in vr_tier_options:
      for hs in hsl_options:
        for sz in sz_options:
          for jm in j_options:
            for bs in base_options:
              params = {
                  'base':bs, 'p_min':5, 'p_max':8, 'vr_min':0.5,
                  'p_tiers':pt, 'cl_tiers':ct, 'vr_tiers':vt,
                  'hsl_min':hs[0],'hsl_max':hs[1],'sz_max':sz,'j_max':jm
              }
              idx += 1
              t_h2, _, _ = evaluate(params, train)
              v_h2, _, _ = evaluate(params, val_q1)
              # 加权目标
              score = t_h2 * 0.55 + v_h2 * 0.45
              
              if score > best_score:
                  best_score = score
                  best = params
              
              log.append((score, t_h2, v_h2, params))
              
              if idx % 200 == 0:
                  print(f'  [{idx}/{total}] 当前最佳加权: {best_score:.1f}% (训{t_h2:.1f}%+验{v_h2:.1f}%)', flush=True)

log.sort(key=lambda x: -x[0])
print(f'\n{"="*70}', flush=True)
print(f'  优化完成! 测试{idx}种组合', flush=True)
print(f'{"="*70}', flush=True)

# Top5
print(f'\nTop5 最佳参数:')
for rank, (sc, t2, v2, p) in enumerate(log[:5], 1):
    print(f'\n#{rank} 加权{sc:.1f}% | 训{t2:.1f}% 验{v2:.1f}%')
    print(f'  涨幅: {p["p_tiers"]}')
    print(f'  CL: {p["cl_tiers"]}')
    print(f'  量比: {p["vr_tiers"]}')
    print(f'  换手{p["hsl_min"]}~{p["hsl_max"]}% 市值<{p["sz_max"]}亿 J<{p["j_max"]} 基础{p["base"]}')

# 最佳参数 + 原版对比
bp = log[0][3]
print(f'\n{"="*70}')
print(f'  最佳参数 vs 原版 全面对比')
print(f'{"="*70}')
print(f'{"参数":<20} {"原版":<20} {"优化版":<20}')
print(f'{"":-<60}')
print(f'{"涨幅":<20} {str(orig_params["p_tiers"]):<20} {str(bp["p_tiers"]):<20}')
print(f'{"CL":<20} {str(orig_params["cl_tiers"]):<20} {str(bp["cl_tiers"]):<20}')
print(f'{"量比":<20} {str(orig_params["vr_tiers"]):<20} {str(bp["vr_tiers"]):<20}')
print(f'{"换手":<20} {"5~15%":<20} {str(bp["hsl_min"])+"~"+str(bp["hsl_max"])+"%":<20}')
print(f'{"市值":<20} {"<200亿":<20} {"<"+str(bp["sz_max"])+"亿":<20}')
print(f'{"J值":<20} {"<100":<20} {"<"+str(bp["j_max"]):<20}')

# 全面验证
print(f'\n{"数据集":<15} {"原版达2.5%":<15} {"优化达2.5%":<15} {"提升":<10}')
print(f'{"":-<55}')
for name, dl in [('训练4~5月', train), ('验证1~3月', val_q1), ('2025全年', val_25)]:
    o2, _, _ = evaluate(orig_params, dl)
    b2, _, _ = evaluate(bp, dl)
    delta = b2 - o2
    print(f'{name:<15} {o2:<15.1f} {b2:<15.1f} {delta:>+7.1f}%', flush=True)

# 2026全年
all_26 = [dt for dt in dates if dt.startswith('2026')]
o2, _, _ = evaluate(orig_params, all_26)
b2, b5, b_avg = evaluate(bp, all_26)
print(f'{"2026全年":<15} {o2:<15.1f} {b2:<15.1f} {b2-o2:>+7.1f}%', flush=True)

# 近5天详情
print(f'\n近5天冠军详情（优化版）:', flush=True)
for dt in ['2026-05-19','2026-05-20','2026-05-21','2026-05-22']:
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
        if hsl < bp['hsl_min'] or hsl > bp['hsl_max']: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= bp['sz_max']: continue
        nm = names.get(s['code'],'')
        if 'ST' in nm or '*ST' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > bp['j_max']: continue
        cl = s.get('cl',0)
        sc = 10
        for lo, hi, pts in bp['p_tiers']:
            if lo <= pct <= hi: sc += pts; break
        for lo, hi, pts in bp['cl_tiers']:
            if lo <= cl <= hi: sc += pts; break
        for lo, hi, pts in bp['vr_tiers']:
            if lo <= vr <= hi: sc += pts; break
        nv = s.get('n',0) or 0
        cand.append((sc, nm, s['code'], pct, nv, vr, cl, hsl, sz, jv, s.get('close',0)))
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[3]))
    c = cand[0]
    ns = f'{c[4]:+.2f}%' if c[4] else 'N/A'
    ok = '🔥' if c[4] >= 5 else ('✅' if c[4] >= 2.5 else '❌')
    print(f'  {dt}: {c[1]}({c[2]}) 评{c[0]} 买{c[10]:.2f} 涨{c[3]:.1f}% → {ns} {ok}', flush=True)
