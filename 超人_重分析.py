"""
重新分析：出票率≥90%硬约束下最大化冠军达2.5%
"""
import pickle, os, json, statistics, itertools
from collections import defaultdict

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
ad = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]
n_total = len(ad)
print(f'2026年 {n_total}天 | 出票率90% = 至少{int(n_total*0.9)}天', flush=True)

def test_params(params, sort_by='p'):
    """返回(天数, 达2.5%, 达5%, 均涨幅, 出票率)"""
    nvs = []
    dcount = 0
    for dt in ad:
        pool = []
        for s in data.get(dt, []):
            code, px = s['code'], s['p']
            if px < params['p_min'] or px > params['p_max']: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < params['vr_min'] or vr > params['vr_max']: continue
            ri = real.get(code)
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < params['hsl_min'] or hsl > params['hsl_max']: continue
            if (ri.get('shizhi',0) or 0) > params['sz_max']: continue
            nm = names.get(code,'')
            if 'ST' in nm or '*ST' in nm: continue
            jv = s.get('j_val',0) or 0
            if jv > params.get('j_max', 100): continue
            cl = s.get('cl',0)
            if cl < params.get('cl_min', 0) or cl > params.get('cl_max', 100): continue
            
            nv = s.get('n',0) or 0
            
            if sort_by == 'p':
                sv = px
            elif sort_by == 'vr':
                sv = vr
            elif sort_by == 'p*vr':
                sv = px * vr
            elif sort_by == 'cl':
                sv = cl
            else:
                sv = px
            
            pool.append((sv, nv))
        
        if not pool: continue
        dcount += 1
        pool.sort(key=lambda x: -x[0])
        nvs.append(pool[0][1])
    
    n = len(nvs)
    cp = dcount * 100 / n_total
    if cp < 90: return 0, 0, 0, 0, cp  # 硬约束：出票率≥90%
    
    w25 = sum(1 for v in nvs if v >= 2.5) * 100 / n
    w5 = sum(1 for v in nvs if v >= 5) * 100 / n
    avg = statistics.mean(nvs) if nvs else 0
    return n, w25, w5, avg, cp

# ===== 全参数搜索 =====
print(f'\n{"="*70}')
print(f'全参数搜索（出票率≥90%硬约束）')
print(f'{"="*70}', flush=True)

# 参数空间
searches = []

# 1. 基础涨幅参数（涨幅5~8%固定）
base_params_list = []
for vr_min in [0.8, 1.0, 1.2]:
  for vr_max in [1.5, 2.0, 3.0]:
    for hsl_min in [5]:
      for hsl_max in [10, 12, 15, 18]:
        for sz_max in [80, 100, 150, 200]:
          for j_max in [80, 100]:
            for cl_min in [0, 60]:
              for cl_max in [85, 90, 100]:
                p = {'p_min':5, 'p_max':8, 'vr_min':vr_min, 'vr_max':vr_max,
                     'hsl_min':hsl_min, 'hsl_max':hsl_max, 'sz_max':sz_max, 
                     'j_max':j_max, 'cl_min':cl_min, 'cl_max':cl_max}
                base_params_list.append(p)

print(f'搜索组合: {len(base_params_list)}', flush=True)

best = (0, 0, 0, 0, 0, {})
idx = 0
for p in base_params_list:
    idx += 1
    n, w25, w5, avg, cp = test_params(p, 'p')
    if n == 0: continue  # 出票率不足
    if w25 > best[1]:
        best = (n, w25, w5, avg, cp, p)
        print(f'[{idx}] 🏆 达2.5%:{w25:.1f}% {n}天 出票{cp:.1f}% | 量{p["vr_min"]}~{p["vr_max"]} 换{p["hsl_min"]}~{p["hsl_max"]}% 市值<{p["sz_max"]} J<{p["j_max"]} CL{p["cl_min"]}~{p["cl_max"]}', flush=True)

print(f'\n🏆 最佳(涨幅排序): 达2.5%:{best[1]:.1f}% {best[0]}天 出票{best[4]:.1f}%', flush=True)
bp = best[5]
print(f'   量{bp["vr_min"]}~{bp["vr_max"]} 换{bp["hsl_min"]}~{bp["hsl_max"]}% 市值<{bp["sz_max"]} J<{bp["j_max"]} CL{bp["cl_min"]}~{bp["cl_max"]}', flush=True)

# ===== 不同排序方式 =====
print(f'\n{"="*70}')
print(f'不同排序方式（最佳参数下）')
print(f'{"="*70}', flush=True)

for sort_by in ['p', 'vr', 'p*vr', 'cl']:
    n, w25, w5, avg, cp = test_params(bp, sort_by)
    if n > 0:
        diff = w25 - best[1]
        sig = '🔥' if diff > 0 else ''
        print(f'{sig} 排序:{sort_by:<4} → 达2.5%:{w25:.1f}% ({diff:+.1f}%) {n}天', flush=True)

# ===== 涨幅范围微调 =====
print(f'\n{"="*70}')
print(f'涨幅范围微调（在最佳参数基础上）')
print(f'{"="*70}', flush=True)

for p_min in [4, 4.5, 5, 5.5]:
    for p_max in [7.5, 8, 8.5, 9]:
        if p_min >= p_max: continue
        p = dict(bp)
        p['p_min'] = p_min
        p['p_max'] = p_max
        n, w25, w5, avg, cp = test_params(p, 'p')
        if n > 0:
            diff = w25 - best[1]
            sig = '🔥' if diff > 2 else ('✅' if diff > 0 else '')
            print(f'{sig} 涨{p_min:.0f}~{p_max:.0f}% → 达2.5%:{w25:.1f}% ({diff:+.1f}%) 出票{cp:.1f}% {n}天', flush=True)

# ===== 量比微调 =====
print(f'\n{"="*70}')
print(f'量比+换手+市值微调')
print(f'{"="*70}', flush=True)

for vr_min in [0.8, 1.0]:
    for vr_max in [1.5, 2.0, 2.5]:
        for hsl_max in [10, 12, 15]:
            for sz_max in [80, 100, 150, 200]:
                p = dict(bp)
                p['vr_min'] = vr_min; p['vr_max'] = vr_max
                p['hsl_max'] = hsl_max; p['sz_max'] = sz_max
                n, w25, w5, avg, cp = test_params(p, 'p')
                if n > 0 and w25 >= best[1] - 1:
                    diff = w25 - best[1]
                    sig = '🔥' if w25 > best[1] else ''
                    print(f'{sig} 量{vr_min:.0f}~{vr_max:.1f} 换5~{hsl_max}% 市值<{sz_max} → 达2.5%:{w25:.1f}% ({diff:+.1f}%) 出票{cp:.1f}% {n}天', flush=True)
                    if w25 > best[1]:
                        best = (n, w25, w5, avg, cp, p)

print(f'\n🏆 最终最佳: 达2.5%:{best[1]:.1f}% {best[0]}天 出票{best[4]:.1f}%', flush=True)
print(f'   涨5~8% 量{bp["vr_min"]}~{bp["vr_max"]} 换{bp["hsl_min"]}~{bp["hsl_max"]}% 市值<{bp["sz_max"]} J<{bp["j_max"]} CL{bp["cl_min"]}~{bp["cl_max"]}', flush=True)
