"""超人优化版 — 1~2月回测详情"""
import pickle
from collections import defaultdict

with open('big_cache.pkl','rb') as f:
    c = pickle.load(f)
d, real, names = c['data'], c['real'], c['names']
dates = sorted(d.keys())

# 优化后的最佳参数
P = {
    'p_min':5, 'p_max':8, 'base':10,
    'p_best_low':4.5, 'p_best_high':6.5, 'p_score_best':12, 'p_score_ok':5,
    'p_penalty_high':(7,10),
    'cl_best_low':60, 'cl_best_high':85, 'cl_score_best':10, 'cl_score_ok':0, 'cl_penalty':15,
    'vr_best_low':0.8, 'vr_best_high':1.5, 'vr_score_best':10, 'vr_score_ok':0, 'vr_penalty':10,
    'hsl_min':5, 'hsl_max':18, 'sz_max':150, 'j_max':100,
}

def run_opt(dt):
    """优化版选股"""
    stocks = d.get(dt, [])
    cand = []
    for s in stocks:
        pct = s['p']
        if pct < P['p_min'] or pct > P['p_max']: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < 1.0: continue
        ri = real.get(s['code'])
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < P['hsl_min'] or hsl > P['hsl_max']: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= P['sz_max']: continue
        nm = names.get(s['code'],'')
        if 'ST' in nm or '*ST' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > P['j_max']: continue
        cl = s.get('cl',0)
        
        sc = P['base']
        if P['p_best_low'] <= pct <= P['p_best_high']: sc += P['p_score_best']
        elif pct > P['p_penalty_high'][0]: sc -= P['p_penalty_high'][1]
        else: sc += P['p_score_ok']
        if P['cl_best_low'] <= cl <= P['cl_best_high']: sc += P['cl_score_best']
        elif cl > 90: sc -= P['cl_penalty']
        else: sc += P['cl_score_ok']
        if P['vr_best_low'] <= vr <= P['vr_best_high']: sc += P['vr_score_best']
        elif vr > 3: sc -= P['vr_penalty']
        else: sc += P['vr_score_ok']
        
        nv = s.get('n',0) or 0
        cand.append((sc, nm, s['code'], pct, nv, vr, cl, hsl, sz, jv, s.get('close',0)))
    
    if not cand: return []
    cand.sort(key=lambda x: (-x[0], -x[3]))
    return cand[:3]

def run_original(dt):
    """原版选股"""
    stocks = d.get(dt, [])
    cand = []
    for s in stocks:
        pct = s['p']
        if pct < 5 or pct > 8: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < 1.0: continue
        ri = real.get(s['code'])
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > 15: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= 200: continue
        nm = names.get(s['code'],'')
        if 'ST' in nm or '*ST' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > 100: continue
        cl = s.get('cl',0)
        
        sc = 10
        if 5 <= pct <= 6.5: sc += 15
        elif 6.5 < pct <= 7: sc += 8
        elif 4.5 <= pct < 5: sc += 5
        if pct > 7: sc -= 15
        if 70 <= cl <= 85: sc += 15
        elif 85 < cl <= 90: sc += 5
        elif 60 <= cl < 70: sc += 3
        if cl > 90: sc -= 20
        if 1.2 <= vr <= 2.0: sc += 10
        elif 2.0 < vr <= 3.0: sc += 5
        elif 1.0 <= vr < 1.2: sc += 3
        if vr > 3: sc -= 15
        
        nv = s.get('n',0) or 0
        cand.append((sc, nm, s['code'], pct, nv, vr, cl, hsl, sz, jv, s.get('close',0)))
    
    if not cand: return []
    cand.sort(key=lambda x: (-x[0], -x[3]))
    return cand[:3]

for month, label in [('2026-01','2026年1月'), ('2026-02','2026年2月')]:
    month_dates = [dt for dt in dates if dt.startswith(month)]
    
    opt_results = []
    ori_results = []
    
    for dt in month_dates:
        opt_top3 = run_opt(dt)
        ori_top3 = run_original(dt)
        if opt_top3:
            opt_results.append({'dt':dt, 'c1':opt_top3[0], 'top3':opt_top3})
        if ori_top3:
            ori_results.append({'dt':dt, 'c1':ori_top3[0], 'top3':ori_top3})
    
    print(f'\n{"="*80}', flush=True)
    print(f'  {label} — 优化版 vs 原版 逐日对比', flush=True)
    print(f'{"="*80}', flush=True)
    
    # 汇总
    opt_n = [r['c1'][4] for r in opt_results]
    ori_n = [r['c1'][4] for r in ori_results]
    opt_h2 = sum(1 for v in opt_n if v >= 2.5)
    ori_h2 = sum(1 for v in ori_n if v >= 2.5)
    opt_h5 = sum(1 for v in opt_n if v >= 5)
    ori_h5 = sum(1 for v in ori_n if v >= 5)
    opt_avg = sum(opt_n)/len(opt_n)
    ori_avg = sum(ori_n)/len(ori_n)
    
    # Top3任意达标
    opt_any = sum(1 for r in opt_results if any(t[4] >= 2.5 for t in r['top3']))
    ori_any = sum(1 for r in ori_results if any(t[4] >= 2.5 for t in r['top3']))
    
    print(f'{"":-<80}')
    print(f'{"":<10} {"天数":<5} {"冠军均%":<9} {"冠达2.5":<12} {"冠达5%":<10} {"Top3任达":<10}', flush=True)
    print(f'{"":-<80}')
    print(f'{"优化版":<10} {len(opt_results):<5} {opt_avg:<9.2f} {opt_h2}({opt_h2/len(opt_results)*100:5.1f}%) {opt_h5}({opt_h5/len(opt_results)*100:4.1f}%) {opt_any}/{len(opt_results)}({opt_any/len(opt_results)*100:5.1f}%)', flush=True)
    print(f'{"原版":<10} {len(ori_results):<5} {ori_avg:<9.2f} {ori_h2}({ori_h2/len(ori_results)*100:5.1f}%) {ori_h5}({ori_h5/len(ori_results)*100:4.1f}%) {ori_any}/{len(ori_results)}({ori_any/len(ori_results)*100:5.1f}%)', flush=True)
    
    # 逐天详情
    print(f'\n逐天详情（优化版冠军 vs 原版冠军）：', flush=True)
    print(f'{"日期":<12} {"优化版":<30} {"原版":<30}', flush=True)
    print(f'{"":-<80}', flush=True)
    
    all_dts = sorted(set(r['dt'] for r in opt_results) | set(r['dt'] for r in ori_results))
    for dt in all_dts:
        opt_r = next((r for r in opt_results if r['dt'] == dt), None)
        ori_r = next((r for r in ori_results if r['dt'] == dt), None)
        
        opt_str = ''
        ori_str = ''
        
        if opt_r:
            c = opt_r['c1']
            ns = f'{c[4]:+.2f}%' if c[4] else 'N/A'
            ok = '🔥' if c[4] >= 5 else ('✅' if c[4] >= 2.5 else '❌')
            opt_str = f'{c[1][:6]}({c[2]}) 评{c[0]} 涨{c[3]:.1f}% → {ns} {ok}'
        else:
            opt_str = '无候选'
        
        if ori_r:
            c = ori_r['c1']
            ns = f'{c[4]:+.2f}%' if c[4] else 'N/A'
            ok = '🔥' if c[4] >= 5 else ('✅' if c[4] >= 2.5 else '❌')
            ori_str = f'{c[1][:6]}({c[2]}) 评{c[0]} 涨{c[3]:.1f}% → {ns} {ok}'
        else:
            ori_str = '无候选'
        
        print(f'{dt:<12} {opt_str:<30} {ori_str:<30}', flush=True)
    
    print()
    
    # 分析优化版输在哪
    print(f'优化版失败日分析（冠军未达2.5%）：', flush=True)
    fails = [r for r in opt_results if r['c1'][4] < 2.5]
    for r in fails:
        c = r['c1']
        # 看原版同期表现
        ori_r = next((x for x in ori_results if x['dt'] == r['dt']), None)
        ori_str = ''
        if ori_r:
            oc = ori_r['c1']
            ori_str = f'原版:{oc[1][:6]}({oc[2]}) 评{oc[0]} 涨{oc[3]:.1f}% → {oc[4]:+.2f}%'
        print(f'  {r["dt"]}: 优化{c[1][:6]}({c[2]}) 评{c[0]} 涨{c[3]:.1f}% 量{c[5]:.2f} CL{c[6]:.0f}% 换{c[7]:.0f}% J{c[9]:.0f} → {c[4]:+.2f}% ❌ | {ori_str}', flush=True)
