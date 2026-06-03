"""超人策略 参数自动优化 — 小缓存版"""
import pickle
import os
from collections import defaultdict

CACHE = os.path.expanduser('~/AppData/Local/hermes/scripts/big_cache.pkl')
print(f'加载缓存: {CACHE}...', flush=True)
with open(CACHE, 'rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
print(f'日期: {len(dates)}天, {dates[0]}~{dates[-1]}', flush=True)
print(f'实时数据: {len(real)}只 名称: {len(names)}个', flush=True)

def run_backtest(params):
    p_min, p_max = 5, 8
    p_bl, p_bh = params['p_best_low'], params['p_best_high']
    p_sb, p_so = params['p_score_best'], params['p_score_ok']
    p_ph = params['p_penalty_high']
    cl_bl, cl_bh = params['cl_best_low'], params['cl_best_high']
    cl_sb, cl_so = params['cl_score_best'], params['cl_score_ok']
    vr_bl, vr_bh = params['vr_best_low'], params['vr_best_high']
    vr_sb, vr_so = params['vr_score_best'], params['vr_score_ok']
    hsl_min, hsl_max = params['hsl_min'], params['hsl_max']
    sz_max = params['sz_max']
    base = 10
    
    results = []
    for date in dates:
        if date.endswith('-22') and '2026' in date:
            continue
        stocks = data.get(date, [])
        cand = []
        for s in stocks:
            p = s['p']
            if p < p_min or p > p_max: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < 1.0: continue
            code = s['code']
            ri = real.get(code)
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < hsl_min or hsl > hsl_max: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz >= sz_max: continue
            nm = names.get(code,'')
            if 'ST' in nm or '*ST' in nm: continue
            jv = s.get('j_val',0) or 0
            if jv > 100: continue
            
            cl = s.get('cl',0)
            sc = base
            if p_bl <= p <= p_bh:
                sc += p_sb
            elif p > p_ph[0]:
                sc -= p_ph[1]
            else:
                sc += p_so
            if cl_bl <= cl <= cl_bh:
                sc += cl_sb
            elif cl > 90:
                sc -= 20
            else:
                sc += cl_so
            if vr_bl <= vr <= vr_bh:
                sc += vr_sb
            elif vr > 3:
                sc -= 15
            else:
                sc += vr_so
            
            nv = s.get('n',0) or 0
            cand.append((sc, nm, code, p, nv, vr, cl, hsl, sz, jv, s.get('close',0)))
        
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[3]))
        champ = cand[0]
        results.append({'dt':date, 'n':champ[4], 'name':champ[1],
                        'sc':champ[0], 'p':champ[3]})
    
    for year in ['2025','2026']:
        yr = [r for r in results if r['dt'].startswith(year)]
        if not yr: continue
        nv = [r['n'] for r in yr]
        hit2 = sum(1 for v in nv if v >= 2.5)
        hit5 = sum(1 for v in nv if v >= 5)
        avg = sum(nv)/len(nv)
        return {'year':year, 'days':len(yr), 'hit2':hit2,
                'hit2_pct':hit2/len(yr)*100, 'hit5':hit5,
                'hit5_pct':hit5/len(yr)*100, 'avg':avg}
    return None

# 网格搜索
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

import itertools
keys = list(grids.keys())
total = 1
for k in keys:
    total *= len(grids[k])
print(f'参数组合总数: {total}', flush=True)

best_hit2 = 0
best = None
results_log = []

# Generate combinations manually with proper filtering
combos = []
for p_bl in grids['p_best_low']:
    for p_bh in grids['p_best_high']:
        if p_bh <= p_bl: continue
        for p_sb in grids['p_score_best']:
            for p_so in grids['p_score_ok']:
                for p_ph in grids['p_penalty_high']:
                    for cl_bl in grids['cl_best_low']:
                        for cl_bh in grids['cl_best_high']:
                            if cl_bh <= cl_bl: continue
                            for cl_sb in grids['cl_score_best']:
                                for cl_so in grids['cl_score_ok']:
                                    for vr_bl in grids['vr_best_low']:
                                        for vr_bh in grids['vr_best_high']:
                                            if vr_bh <= vr_bl: continue
                                            for vr_sb in grids['vr_score_best']:
                                                for vr_so in grids['vr_score_ok']:
                                                    for hsl_min in grids['hsl_min']:
                                                        for hsl_max in grids['hsl_max']:
                                                            if hsl_max <= hsl_min: continue
                                                            for sz_max in grids['sz_max']:
                                                                combos.append({
                                                                    'p_best_low':p_bl, 'p_best_high':p_bh,
                                                                    'p_score_best':p_sb, 'p_score_ok':p_so,
                                                                    'p_penalty_high':p_ph,
                                                                    'cl_best_low':cl_bl, 'cl_best_high':cl_bh,
                                                                    'cl_score_best':cl_sb, 'cl_score_ok':cl_so,
                                                                    'vr_best_low':vr_bl, 'vr_best_high':vr_bh,
                                                                    'vr_score_best':vr_sb, 'vr_score_ok':vr_so,
                                                                    'hsl_min':hsl_min, 'hsl_max':hsl_max,
                                                                    'sz_max':sz_max,
                                                                })

print(f'实际有效组合: {len(combos)}', flush=True)
idx = 0
for params in combos:
    idx += 1
    res = run_backtest(params)
    if not res: continue
    if res['year'] == '2026':
        h2 = res['hit2_pct']
        results_log.append((h2, res['avg'], res['hit5_pct'], params, res))
        if h2 > best_hit2:
            best_hit2 = h2
            best = (params, res)
    if idx % 500 == 0:
        print(f'  [{idx}/{len(combos)}] 当前最佳达2.5%: {best_hit2:.1f}%', flush=True)

results_log.sort(key=lambda x: -x[0])
print(f'\n{"="*60}', flush=True)
print(f'优化完成! 测试{idx}种组合', flush=True)
print(f'{"="*60}', flush=True)

print(f'\n=== Top 5 最佳参数（按冠军达2.5%排序）===', flush=True)
for rank, (h2, avg, h5, p, res) in enumerate(results_log[:5], 1):
    print(f'\n#{rank} | 2026年 | 达2.5%: {h2:.1f}% | 均:{avg:.2f}% | 达5%: {h5:.1f}% | 天数:{res["days"]}', flush=True)
    print(f'  涨: {p["p_best_low"]:.1f}~{p["p_best_high"]:.1f}(+{p["p_score_best"]}) 超{p["p_penalty_high"][0]}:{p["p_penalty_high"][1]}', flush=True)
    print(f'  CL: {p["cl_best_low"]:.0f}~{p["cl_best_high"]:.0f}(+{p["cl_score_best"]})', flush=True)
    print(f'  量比: {p["vr_best_low"]:.1f}~{p["vr_best_high"]:.1f}(+{p["vr_score_best"]})', flush=True)
    print(f'  换手: {p["hsl_min"]}~{p["hsl_max"]}% 市值<{p["sz_max"]}亿', flush=True)

if best:
    p, res = best
    print(f'\n{"="*60}', flush=True)
    print(f'最佳参数回测详情', flush=True)
    print(f'{"="*60}', flush=True)
    print(f'涨幅最佳: {p["p_best_low"]}~{p["p_best_high"]}% +{p["p_score_best"]}分 | 超{p["p_penalty_high"][0]}:{p["p_penalty_high"][1]}分', flush=True)
    print(f'CL最佳: {p["cl_best_low"]}~{p["cl_best_high"]}% +{p["cl_score_best"]}分', flush=True)
    print(f'量比最佳: {p["vr_best_low"]}~{p["vr_best_high"]} +{p["vr_score_best"]}分', flush=True)
    print(f'换手: {p["hsl_min"]}~{p["hsl_max"]}% 市值<{p["sz_max"]}亿', flush=True)
    
    # 各年
    for y in ['2025','2026']:
        r2 = run_backtest(p)
        if r2 and r2['year'] == y:
            print(f'{y}: {r2["days"]}天 | 冠军达2.5%: {r2["hit2_pct"]:.1f}% | 达5%: {r2["hit5_pct"]:.1f}% | 均: {r2["avg"]:.2f}%', flush=True)
    
    # 近5天
    print(f'\n--- 近5天冠军 ---', flush=True)
    for dt in ['2026-05-19','2026-05-20','2026-05-21','2026-05-22','2026-05-25']:
        stocks = data.get(dt, [])
        cand = []
        for s in stocks:
            code = s['code']
            pct = s['p']
            if pct < 5 or pct > 8: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < 1.0: continue
            ri = real.get(code)
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < p['hsl_min'] or hsl > p['hsl_max']: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz >= p['sz_max']: continue
            nm = names.get(code,'')
            if 'ST' in nm or '*ST' in nm: continue
            jv = s.get('j_val',0) or 0
            if jv > 100: continue
            cl = s.get('cl',0)
            
            sc = 10
            if p['p_best_low'] <= pct <= p['p_best_high']:
                sc += p['p_score_best']
            elif pct > p['p_penalty_high'][0]:
                sc -= p['p_penalty_high'][1]
            else:
                sc += p['p_score_ok']
            if p['cl_best_low'] <= cl <= p['cl_best_high']:
                sc += p['cl_score_best']
            elif cl > 90:
                sc -= 20
            else:
                sc += p['cl_score_ok']
            if p['vr_best_low'] <= vr <= p['vr_best_high']:
                sc += p['vr_score_best']
            elif vr > 3:
                sc -= 15
            else:
                sc += p['vr_score_ok']
            
            nv = s.get('n',0) or 0
            cand.append((sc, nm, code, pct, nv, vr, cl, hsl, sz, jv, s.get('close',0)))
        
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[3]))
        c = cand[0]
        ns = f'{c[4]:.2f}%' if c[4] != 0 else 'N/A'
        ok = '🔥' if c[4] >= 5 else ('✅' if c[4] >= 2.5 else '❌')
        print(f'{dt}: {c[1]}({c[2]}) 评分{c[0]} 涨{c[3]:.1f}% CL{c[6]:.0f}% 量{c[5]:.2f} 买{c[10]:.2f} 次日最高{ns} {ok}', flush=True)
