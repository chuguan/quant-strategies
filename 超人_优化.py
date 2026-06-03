"""超人策略 参数自动优化 — 目标：冠军达2.5%概率最大化"""
import pickle, os, sys
from collections import defaultdict

CACHE = os.path.expanduser('~/AppData/Local/hermes/scripts/big_cache_full.pkl')
with open(CACHE, 'rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())

def run_backtest(params):
    """给定参数组合，返回冠军达2.5%的统计"""
    p_min, p_max = params['p_min'], params['p_max']
    p_best_low, p_best_high = params['p_best_low'], params['p_best_high']
    p_score_best, p_score_ok = params['p_score_best'], params['p_score_ok']
    p_penalty_high = params['p_penalty_high']
    
    cl_best_low, cl_best_high = params['cl_best_low'], params['cl_best_high']
    cl_score_best, cl_score_ok = params['cl_score_best'], params['cl_score_ok']
    cl_penalty = params.get('cl_penalty', 20)
    
    vr_best_low, vr_best_high = params['vr_best_low'], params['vr_best_high']
    vr_score_best, vr_score_ok = params['vr_score_best'], params['vr_score_ok']
    vr_penalty = params.get('vr_penalty', 15)
    
    hsl_min, hsl_max = params.get('hsl_min', 5), params.get('hsl_max', 15)
    sz_max = params.get('sz_max', 200)
    j_max = params.get('j_max', 100)
    base = params.get('base', 10)
    
    results = []
    for date in dates:
        if date.endswith('-22') and '2026' in date: continue
        stocks = data.get(date, [])
        cand = []
        for s in stocks:
            p = s['p']
            if p < p_min or p > p_max: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < 1.0: continue
            ri = real.get(s['code'])
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < hsl_min or hsl > hsl_max: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz >= sz_max: continue
            nm = names.get(s['code'],'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv = s.get('j_val',0) or 0
            if jv > j_max: continue
            
            cl = s.get('cl',0)
            sc = base
            # 涨幅评分
            if p_best_low <= p <= p_best_high:
                sc += p_score_best
            elif p_penalty_high and p > p_penalty_high[0]:
                sc -= p_penalty_high[1]
            else:
                sc += p_score_ok
            
            # CL评分
            if cl_best_low <= cl <= cl_best_high:
                sc += cl_score_best
            elif cl > 90:
                sc -= cl_penalty
            else:
                sc += cl_score_ok
            
            # 量比评分
            if vr_best_low <= vr <= vr_best_high:
                sc += vr_score_best
            elif vr > 3:
                sc -= vr_penalty
            else:
                sc += vr_score_ok
            
            nv = s.get('n',0) or 0
            cand.append((sc, nm, s['code'], p, nv, vr, cl, hsl, sz, jv, s.get('close',0)))
        
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[3]))
        champ = cand[0]
        results.append({'dt':date, 'n':champ[4], 'name':champ[1], 'sc':champ[0],
                        'p':champ[3], 'vr':champ[5], 'cl':champ[6],
                        'cand_count':len(cand)})
    
    # 统计
    for year in ['2025','2026']:
        yr = [r for r in results if r['dt'].startswith(year)]
        if not yr: continue
        n_vals = [r['n'] for r in yr]
        hit2 = sum(1 for v in n_vals if v >= 2.5)
        hit5 = sum(1 for v in n_vals if v >= 5)
        avg = sum(n_vals)/len(n_vals)
        avg_c = sum(r['cand_count'] for r in yr)/len(yr)
        return {'year':year, 'days':len(yr), 'hit2':hit2, 'hit2_pct':hit2/len(yr)*100,
                'hit5':hit5, 'hit5_pct':hit5/len(yr)*100, 'avg':avg,
                'avg_cand':avg_c}
    return None

# ===== 网格搜索 =====
best = None
best_hit2 = 0
results_log = []

# 参数网格
grids = {
    'p_best_low': [5.0, 5.5],
    'p_best_high': [6.0, 6.5],
    'p_score_best': [12, 15, 18],
    'p_score_ok': [3, 5, 8],
    'p_penalty_high': [(7, 15), (7.5, 10)],
    'cl_best_low': [65, 70, 75],
    'cl_best_high': [80, 85],
    'cl_score_best': [12, 15, 18],
    'cl_score_ok': [3, 5],
    'vr_best_low': [1.0, 1.2, 1.5],
    'vr_best_high': [1.5, 2.0, 2.5],
    'vr_score_best': [8, 10, 12],
    'vr_score_ok': [2, 3, 5],
    'hsl_min': [3, 5],
    'hsl_max': [12, 15, 18],
    'sz_max': [150, 200],
}

keys = list(grids.keys())
import itertools

total = 1
for k in keys:
    total *= len(grids[k])

print(f'参数量: {total}种组合', flush=True)
idx = 0

for p_best_low in grids['p_best_low']:
  for p_best_high in grids['p_best_high']:
    if p_best_high <= p_best_low: continue
    for p_score_best in grids['p_score_best']:
      for p_score_ok in grids['p_score_ok']:
        for p_penalty_high in grids['p_penalty_high']:
          for cl_best_low in grids['cl_best_low']:
            for cl_best_high in grids['cl_best_high']:
              if cl_best_high <= cl_best_low: continue
              for cl_score_best in grids['cl_score_best']:
                for cl_score_ok in grids['cl_score_ok']:
                  for vr_best_low in grids['vr_best_low']:
                    for vr_best_high in grids['vr_best_high']:
                      if vr_best_high <= vr_best_low: continue
                      for vr_score_best in grids['vr_score_best']:
                        for vr_score_ok in grids['vr_score_ok']:
                          for hsl_min in grids['hsl_min']:
                            for hsl_max in grids['hsl_max']:
                              if hsl_max <= hsl_min: continue
                              for sz_max in grids['sz_max']:
                                idx += 1
                                params = {
                                    'p_min':5, 'p_max':8,
                                    'p_best_low':p_best_low, 'p_best_high':p_best_high,
                                    'p_score_best':p_score_best, 'p_score_ok':p_score_ok,
                                    'p_penalty_high':p_penalty_high,
                                    'cl_best_low':cl_best_low, 'cl_best_high':cl_best_high,
                                    'cl_score_best':cl_score_best, 'cl_score_ok':cl_score_ok,
                                    'vr_best_low':vr_best_low, 'vr_best_high':vr_best_high,
                                    'vr_score_best':vr_score_best, 'vr_score_ok':vr_score_ok,
                                    'hsl_min':hsl_min, 'hsl_max':hsl_max,
                                    'sz_max':sz_max,
                                }
                                res = run_backtest(params)
                                if not res: continue
                                # 关注2026年达2.5%概率
                                if res['year'] == '2026':
                                    h2 = res['hit2_pct']
                                    results_log.append((h2, res['avg'], res['hit5_pct'], params, res))
                                    if h2 > best_hit2:
                                        best_hit2 = h2
                                        best = (params, res)
                                    if idx % 100 == 0:
                                        print(f'  [{idx}/{total}] 当前最佳: 达2.5%={best_hit2:.1f}%', flush=True)

results_log.sort(key=lambda x: -x[0])
print(f'\n===== 优化完成! 共测试{idx}种组合 =====', flush=True)
print(f'\n=== Top 5 最佳参数（按达2.5%排序）===', flush=True)
for rank, (h2, avg, h5, params, res) in enumerate(results_log[:5], 1):
    print(f'\n#{rank} 达2.5%: {h2:.1f}% | 均:{avg:.2f}% | 达5%: {h5:.1f}% | 天数:{res["days"]}', flush=True)
    print(f'  涨幅最佳: {params["p_best_low"]}~{params["p_best_high"]}(+{params["p_score_best"]}/{params["p_score_ok"]}分) 惩罚>{params["p_penalty_high"][0]}:{params["p_penalty_high"][1]}', flush=True)
    print(f'  CL最佳: {params["cl_best_low"]}~{params["cl_best_high"]}(+{params["cl_score_best"]}/{params["cl_score_ok"]}分)', flush=True)
    print(f'  量比最佳: {params["vr_best_low"]}~{params["vr_best_high"]}(+{params["vr_score_best"]}/{params["vr_score_ok"]}分)', flush=True)
    print(f'  换手: {params["hsl_min"]}~{params["hsl_max"]}% 市值<{params["sz_max"]}亿', flush=True)

# 输出最佳参数下各年详情
if best:
    params, res = best
    print(f'\n===== 最佳参数回测详情 =====', flush=True)
    print(f'参数: 涨幅最佳{params["p_best_low"]}~{params["p_best_high"]} +{params["p_score_best"]}分', flush=True)
    print(f'      CL最佳{params["cl_best_low"]}~{params["cl_best_high"]} +{params["cl_score_best"]}分', flush=True)
    print(f'      量比最佳{params["vr_best_low"]}~{params["vr_best_high"]} +{params["vr_score_best"]}分', flush=True)
    print(f'      换手{params["hsl_min"]}~{params["hsl_max"]}% 市值<{params["sz_max"]}亿', flush=True)
    print(f'      涨幅>{params["p_penalty_high"][0]}:{params["p_penalty_high"][1]}分', flush=True)
    
    # 再跑一次全量
    print(f'\n--- 各年表现 ---', flush=True)
    for y in ['2025','2026']:
        params2 = dict(params, p_min=5, p_max=8)
        r2 = run_backtest(params2)
        if r2 and r2['year'] == y:
            print(f'{y}: {r2["days"]}天 冠军达2.5%:{r2["hit2"]}({r2["hit2_pct"]:.1f}%) 达5%:{r2["hit5"]}({r2["hit5_pct"]:.1f}%) 均:{r2["avg"]:.2f}% 候选:{r2["avg_cand"]:.0f}只', flush=True)
    
    # 近5天详情
    print(f'\n--- 近5天冠军详情 ---', flush=True)
    for dt in ['2026-05-19','2026-05-20','2026-05-21','2026-05-22','2026-05-25']:
        stocks = data.get(dt, [])
        cand = []
        for s in stocks:
            p = s['p']
            if p < 5 or p > 8: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < 1.0: continue
            ri = real.get(s['code'])
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < params['hsl_min'] or hsl > params['hsl_max']: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz >= params['sz_max']: continue
            nm = names.get(s['code'],'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv = s.get('j_val',0) or 0
            if jv > 100: continue
            cl = s.get('cl',0)
            sc = 10
            if params['p_best_low'] <= p <= params['p_best_high']:
                sc += params['p_score_best']
            elif p > params['p_penalty_high'][0]:
                sc -= params['p_penalty_high'][1]
            else:
                sc += params['p_score_ok']
            if params['cl_best_low'] <= cl <= params['cl_best_high']:
                sc += params['cl_score_best']
            elif cl > 90:
                sc -= 20
            else:
                sc += params['cl_score_ok']
            if params['vr_best_low'] <= vr <= params['vr_best_high']:
                sc += params['vr_score_best']
            elif vr > 3:
                sc -= 15
            else:
                sc += params['vr_score_ok']
            nv = s.get('n',0) or 0
            cand.append((sc, nm, s['code'], p, nv, vr, cl, hsl, sz, jv, s.get('close',0)))
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[3]))
        c = cand[0]
        ns = f'{c[4]:.2f}%' if c[4] != 0 else 'N/A'
        ok = '🔥' if c[4] >= 5 else ('✅' if c[4] >= 2.5 else '❌')
        print(f'{dt}: #{c[1]}({c[2]}) | 评分{c[0]} | 涨{c[3]:.1f}% | CL{c[6]:.0f}% | 量{c[5]:.2f} | 买{c[10]:.2f} | 次日最高{ns} {ok}', flush=True)
