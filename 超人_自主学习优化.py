"""超人策略 自主学习优化
训练集：2026年4~5月（最佳月份）
目标：冠军达2.5%概率最大化
"""
import pickle
from collections import defaultdict
import itertools

with open('big_cache.pkl','rb') as f:
    c = pickle.load(f)
d, real, names = c['data'], c['real'], c['names']
dates = sorted(d.keys())

# 训练集: 2026-04 ~ 2026-05
train_dates = [dt for dt in dates if dt.startswith('2026-04') or dt.startswith('2026-05')]
# 验证集: 2026-01~03 和 2025全年
val_dates_2026q1 = [dt for dt in dates if dt.startswith('2026-01') or dt.startswith('2026-02') or dt.startswith('2026-03')]
val_dates_2025 = [dt for dt in dates if dt.startswith('2025')]

print(f'训练集: {len(train_dates)}天 (2026-04~05)', flush=True)
print(f'验证集: {len(val_dates_2026q1)}天 (2026-01~03) + {len(val_dates_2025)}天 (2025)', flush=True)

def evaluate_params(params, date_list):
    """对一组日期跑策略，返回冠军达2.5%率"""
    p_bl, p_bh = params['p_best_low'], params['p_best_high']
    p_sb, p_so = params['p_score_best'], params['p_score_ok']
    p_ph_v, p_ph_s = params['p_penalty_high']
    cl_bl, cl_bh = params['cl_best_low'], params['cl_best_high']
    cl_sb, cl_so = params['cl_score_best'], params['cl_score_ok']
    cl_pen = params.get('cl_penalty', 20)
    vr_bl, vr_bh = params['vr_best_low'], params['vr_best_high']
    vr_sb, vr_so = params['vr_score_best'], params['vr_score_ok']
    vr_pen = params.get('vr_penalty', 15)
    hsl_min, hsl_max = params['hsl_min'], params['hsl_max']
    sz_max = params['sz_max']
    j_max = params.get('j_max', 100)
    p_min, p_max = params.get('p_min', 5), params.get('p_max', 8)
    base = params.get('base', 10)
    
    results = []
    for dt in date_list:
        if dt.endswith('-22') and '2026' in dt: continue
        stocks = d.get(dt, [])
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
            if jv > j_max: continue
            cl = s.get('cl',0)
            
            sc = base
            if p_bl <= p <= p_bh: sc += p_sb
            elif p > p_ph_v: sc -= p_ph_s
            else: sc += p_so
            
            if cl_bl <= cl <= cl_bh: sc += cl_sb
            elif cl > 90: sc -= cl_pen
            else: sc += cl_so
            
            if vr_bl <= vr <= vr_bh: sc += vr_sb
            elif vr > 3: sc -= vr_pen
            else: sc += vr_so
            
            nv = s.get('n',0) or 0
            cand.append((sc, nm, code, p, nv, vr, cl, hsl, sz, jv, s.get('close',0)))
        
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[3]))
        results.append(cand[0][4])  # 冠军的n值
    
    if not results: return 0, 0, 0
    hit2 = sum(1 for v in results if v >= 2.5)
    hit5 = sum(1 for v in results if v >= 5)
    avg = sum(results)/len(results)
    return hit2/len(results)*100, hit5/len(results)*100, avg

# ===== 智能参数扫描 =====
# 策略1: 先调单一维度，找到每个参数的最佳值
# 策略2: 再组合最佳参数

# 基准参数（当前超人v2）
base_params = {
    'p_best_low':5.0, 'p_best_high':6.5, 'p_score_best':15, 'p_score_ok':5,
    'p_penalty_high':(7,15), 'p_min':5, 'p_max':8,
    'cl_best_low':70, 'cl_best_high':85, 'cl_score_best':15, 'cl_score_ok':3,
    'vr_best_low':1.2, 'vr_best_high':2.0, 'vr_score_best':10, 'vr_score_ok':3,
    'hsl_min':5, 'hsl_max':15, 'sz_max':200,
}

print(f'\n基准参数（原版）训练集表现:', flush=True)
h2, h5, avg = evaluate_params(base_params, train_dates)
print(f'  冠军达2.5%: {h2:.1f}% | 达5%: {h5:.1f}% | 均: {avg:.2f}%', flush=True)

# ===== 维度一：涨幅区间 =====
print(f'\n{"="*60}', flush=True)
print(f'阶段1：优化涨幅参数', flush=True)
print(f'{"="*60}', flush=True)

best_p = None
best_p_h2 = 0
for p_bl in [4.5, 5.0, 5.5]:
    for p_bh in [6.0, 6.5, 7.0]:
        if p_bh <= p_bl: continue
        for p_sb in [12, 15, 18]:
            for p_so in [3, 5, 8]:
                for p_ph_v in [7, 7.5]:
                    for p_ph_s in [10, 15]:
                        params = dict(base_params)
                        params.update({'p_best_low':p_bl,'p_best_high':p_bh,'p_score_best':p_sb,'p_score_ok':p_so,'p_penalty_high':(p_ph_v,p_ph_s)})
                        h2, h5, avg = evaluate_params(params, train_dates)
                        if h2 > best_p_h2:
                            best_p_h2 = h2
                            best_p = params

print(f'最佳涨幅参数: 区间{best_p["p_best_low"]}~{best_p["p_best_high"]} (+{best_p["p_score_best"]}/{best_p["p_score_ok"]}分) 超{best_p["p_penalty_high"][0]}:{best_p["p_penalty_high"][1]}分', flush=True)
print(f'  达2.5%: {best_p_h2:.1f}%', flush=True)

# ===== 维度二：CL区间 =====
print(f'\n{"="*60}', flush=True)
print(f'阶段2：优化CL参数', flush=True)
print(f'{"="*60}', flush=True)

best_cl = None
best_cl_h2 = 0
for cl_bl in [60, 65, 70, 75]:
    for cl_bh in [80, 85, 90]:
        if cl_bh <= cl_bl: continue
        for cl_sb in [10, 12, 15, 18]:
            for cl_so in [0, 3, 5]:
                for cl_pen in [15, 20, 25]:
                    params = dict(best_p)
                    params.update({'cl_best_low':cl_bl,'cl_best_high':cl_bh,'cl_score_best':cl_sb,'cl_score_ok':cl_so,'cl_penalty':cl_pen})
                    h2, h5, avg = evaluate_params(params, train_dates)
                    if h2 > best_cl_h2:
                        best_cl_h2 = h2
                        best_cl = params

print(f'最佳CL参数: {best_cl["cl_best_low"]}~{best_cl["cl_best_high"]} (+{best_cl["cl_score_best"]}/{best_cl["cl_score_ok"]}分) 超90扣{best_cl["cl_penalty"]}', flush=True)
print(f'  达2.5%: {best_cl_h2:.1f}%', flush=True)

# ===== 维度三：量比区间 =====
print(f'\n{"="*60}', flush=True)
print(f'阶段3：优化量比参数', flush=True)
print(f'{"="*60}', flush=True)

best_vr = None
best_vr_h2 = 0
for vr_bl in [0.8, 1.0, 1.2, 1.5]:
    for vr_bh in [1.5, 2.0, 2.5, 3.0]:
        if vr_bh <= vr_bl: continue
        for vr_sb in [8, 10, 12, 15]:
            for vr_so in [0, 2, 3, 5]:
                for vr_pen in [10, 15, 20]:
                    params = dict(best_cl)
                    params.update({'vr_best_low':vr_bl,'vr_best_high':vr_bh,'vr_score_best':vr_sb,'vr_score_ok':vr_so,'vr_penalty':vr_pen})
                    h2, h5, avg = evaluate_params(params, train_dates)
                    if h2 > best_vr_h2:
                        best_vr_h2 = h2
                        best_vr = params

print(f'最佳量比参数: {best_vr["vr_best_low"]}~{best_vr["vr_best_high"]} (+{best_vr["vr_score_best"]}/{best_vr["vr_score_ok"]}分) 超3扣{best_vr["vr_penalty"]}', flush=True)
print(f'  达2.5%: {best_vr_h2:.1f}%', flush=True)

# ===== 维度四：换手/市值/J值 =====
print(f'\n{"="*60}', flush=True)
print(f'阶段4：优化换手/市值/J值门槛', flush=True)
print(f'{"="*60}', flush=True)

best_filter = None
best_filter_h2 = 0
for hsl_min in [3, 5]:
    for hsl_max in [12, 15, 18, 20]:
        if hsl_max <= hsl_min: continue
        for sz_max in [100, 150, 200, 250]:
            for j_max in [80, 90, 100, 110]:
                params = dict(best_vr)
                params.update({'hsl_min':hsl_min,'hsl_max':hsl_max,'sz_max':sz_max,'j_max':j_max})
                h2, h5, avg = evaluate_params(params, train_dates)
                if h2 > best_filter_h2:
                    best_filter_h2 = h2
                    best_filter = params

print(f'最佳门槛: 换手{best_filter["hsl_min"]}~{best_filter["hsl_max"]}% 市值<{best_filter["sz_max"]}亿 J<{best_filter["j_max"]}', flush=True)
print(f'  达2.5%: {best_filter_h2:.1f}%', flush=True)

# ===== 最终验证 =====
print(f'\n{"="*70}', flush=True)
print(f'  优化结果验证', flush=True)
print(f'{"="*70}', flush=True)

best_params = best_filter
print(f'\n最佳参数组合:', flush=True)
print(f'  涨幅: {best_params["p_best_low"]}~{best_params["p_best_high"]}% (+{best_params["p_score_best"]}/{best_params["p_score_ok"]}分) 超{best_params["p_penalty_high"][0]}:{best_params["p_penalty_high"][1]}分', flush=True)
print(f'  CL: {best_params["cl_best_low"]}~{best_params["cl_best_high"]}% (+{best_params["cl_score_best"]}/{best_params["cl_score_ok"]}分) 超90扣{best_params["cl_penalty"]}', flush=True)
print(f'  量比: {best_params["vr_best_low"]}~{best_params["vr_best_high"]} (+{best_params["vr_score_best"]}/{best_params["vr_score_ok"]}分) 超3扣{best_params["vr_penalty"]}', flush=True)
print(f'  换手: {best_params["hsl_min"]}~{best_params["hsl_max"]}% 市值<{best_params["sz_max"]}亿 J<{best_params["j_max"]}', flush=True)

print(f'\n{"":-<70}', flush=True)
print(f'{"数据集":<15} {"天数":<6} {"达2.5%":<10} {"达5%":<10} {"均涨幅":<10}', flush=True)
print(f'{"":-<70}', flush=True)

for name, dl in [('训练集(4~5月)', train_dates), ('验证集(1~3月)', val_dates_2026q1), ('验证集(2025)', val_dates_2025)]:
    h2, h5, avg = evaluate_params(best_params, dl)
    print(f'{name:<15} {len(dl):<6} {h2:<10.1f} {h5:<10.1f} {avg:<10.2f}', flush=True)

# 和原版对比
print(f'\n与原版对比（训练集4~5月）:', flush=True)
base_h2, base_h5, base_avg = evaluate_params(base_params, train_dates)
opt_h2, opt_h5, opt_avg = evaluate_params(best_params, train_dates)
print(f'  原版: 达2.5% {base_h2:.1f}% | 优化: {opt_h2:.1f}% | 提升: {opt_h2-base_h2:+.1f}%', flush=True)
print(f'  原版: 均 {base_avg:.2f}% | 优化: {opt_avg:.2f}% | 提升: {opt_avg-base_avg:+.2f}%', flush=True)

# 2026全年汇总
all_2026 = [dt for dt in dates if dt.startswith('2026')]
print(f'\n2026全年对比:', flush=True)
base_h2_a, base_h5_a, base_avg_a = evaluate_params(base_params, all_2026)
opt_h2_a, opt_h5_a, opt_avg_a = evaluate_params(best_params, all_2026)
print(f'  原版: 达2.5% {base_h2_a:.1f}% 均{base_avg_a:.2f}%', flush=True)
print(f'  优化: 达2.5% {opt_h2_a:.1f}% 均{opt_avg_a:.2f}%', flush=True)
print(f'  提升: {opt_h2_a-base_h2_a:+.1f}%', flush=True)

# 近5天详情
print(f'\n近5天冠军详情（优化版）:', flush=True)
for dt in ['2026-05-19','2026-05-20','2026-05-21','2026-05-22']:
    stocks = d.get(dt, [])
    # 用最佳参数跑
    p = best_params
    cand = []
    for s in stocks:
        pct = s['p']
        if pct < p['p_min'] or pct > p['p_max']: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < 1.0: continue
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
        if p['p_best_low'] <= pct <= p['p_best_high']: sc += p['p_score_best']
        elif pct > p['p_penalty_high'][0]: sc -= p['p_penalty_high'][1]
        else: sc += p['p_score_ok']
        if p['cl_best_low'] <= cl <= p['cl_best_high']: sc += p['cl_score_best']
        elif cl > 90: sc -= p['cl_penalty']
        else: sc += p['cl_score_ok']
        if p['vr_best_low'] <= vr <= p['vr_best_high']: sc += p['vr_score_best']
        elif vr > 3: sc -= p['vr_penalty']
        else: sc += p['vr_score_ok']
        
        nv = s.get('n',0) or 0
        cand.append((sc, nm, s['code'], pct, nv, vr, cl, hsl, sz, jv, s.get('close',0)))
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[3]))
    c = cand[0]
    ns = f'{c[4]:+.2f}%' if c[4] else 'N/A'
    ok = '🔥' if c[4] >= 5 else ('✅' if c[4] >= 2.5 else '❌')
    print(f'  {dt}: {c[1]}({c[2]}) 评{c[0]} 买{c[10]:.2f} 涨{c[3]:.1f}% 量{c[5]:.2f} CL{c[6]:.0f}% 换{c[7]:.0f}% 次日{c[4]:+.1f}% {ok}', flush=True)
