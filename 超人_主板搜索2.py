"""
超人策略 — 主板版搜索 p_min=-8, p_max=8
把所有可交易的股票都纳入（排除涨停买不进）
"""
import pickle, json, os
from itertools import product

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR)

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target_dates = [d for d in dates if d >= '2026-04-24']
print(f'回测: {len(target_dates)}天  {target_dates[0]}~{target_dates[-1]}')

# 精简参数：重点看p_min=-8, p_max=8 + 各种其他条件组合
# p_min固定-8, p_max固定8
param_grid = {
    'p_range': [(-8, 8), (-5, 8), (-3, 8), (0, 8), (1, 8), (3, 8), (5, 8)],
    'vr_min': [0.6, 0.8, 1.0],
    'vr_max': [1.5, 2.0, 3.0],
    'hsl_range': [(3,20), (3,30), (5,20), (5,30)],
    'sz_max': [200, 300, 500],
    'cl_range': [(0,100), (30,100), (50,100)],
    'j_max': [100, 120, 150],
}

# 转成扁平列表
all_combs = []
for p in param_grid['p_range']:
    for vr_min in param_grid['vr_min']:
        for vr_max in param_grid['vr_max']:
            for hsl_min, hsl_max in param_grid['hsl_range']:
                for sz_max in param_grid['sz_max']:
                    for cl_min, cl_max in param_grid['cl_range']:
                        for j_max in param_grid['j_max']:
                            all_combs.append((p[0], p[1], vr_min, vr_max, hsl_min, hsl_max, sz_max, cl_min, cl_max, j_max))

print(f'组合数: {len(all_combs)}')

# 预加载K线加速
cache_dir = CACHE_DIR
kline_cache = {}
def get_nxt(code, date):
    key = f'{code}_{date}'
    if key in kline_cache: return kline_cache[key]
    fp = os.path.join(cache_dir, f'{code}.json')
    if not os.path.exists(fp):
        kline_cache[key] = 0; return 0
    try:
        with open(fp) as f:
            kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is not None and idx+1 < len(kdata):
            buy_c = kdata[idx]['close']
            res = (kdata[idx+1]['high']/buy_c-1)*100 if buy_c>0 else 0
            kline_cache[key] = res; return res
    except: pass
    kline_cache[key] = 0; return 0

results = []
for params in all_combs:
    p_min, p_max, vr_min, vr_max, hsl_min, hsl_max, sz_max, cl_min, cl_max, j_max = params
    daily_counts = []; all_hits = []
    
    for dt in target_dates:
        day_cand = []
        for s in data.get(dt, []):
            code, p = s['code'], s['p']
            if p < p_min or p > p_max: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < vr_min or vr > vr_max: continue
            ri = real.get(code)
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < hsl_min or hsl > hsl_max: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz >= sz_max: continue
            nm = names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv = s.get('j_val',0) or 0
            if jv > j_max: continue
            cl = s.get('cl',0)
            if cl < cl_min or cl > cl_max: continue
            day_cand.append(get_nxt(code, dt))
        daily_counts.append(len(day_cand))
        all_hits.extend(day_cand)
    
    avg = sum(daily_counts)/len(daily_counts)
    under10 = sum(1 for c in daily_counts if c < 10)
    total = len(all_hits)
    w25 = sum(1 for v in all_hits if v >= 2.5)
    rate = w25*100/total if total>0 else 0
    
    if avg >= 10 and under10 <= 3:
        results.append({'p':params,'avg':avg,'min':min(daily_counts),'u10':under10,'n':total,'w25':w25,'rate':rate})

results.sort(key=lambda x: -x['rate'])

print(f'\n候选≥10的组合: {len(results)}')
print(f'{"#":<3} {"涨":<10} {"量比":<12} {"换手":<10} {"市值":<6} {"CL":<10} {"J<":<6} {"日均":<5} {"<10":<4} {"总数":<5} {"达2.5%":<8} {"胜率":<5}')
print('-'*95)

for i, r in enumerate(results[:30]):
    p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max,j_max = r['p']
    print(f'{i+1:<3} {p_min}~{p_max:<5} {vr_min}~{vr_max:<7} {hsl_min}~{hsl_max:<5} <{sz_max:<3} '
          f'{cl_min}~{cl_max:<4} {j_max:<6} {r["avg"]:<5.1f} {r["u10"]:<4} '
          f'{r["n"]:<5} {r["w25"]:<8} {r["rate"]:<5.1f}%')

print()
print('=== 推荐组合(涨只含正数+票适中) ===')
good = [r for r in results if r['p'][0] >= 0 and r['avg'] <= 50]
for r in good[:10]:
    p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max,j_max = r['p']
    print(f'涨{p_min}~{p_max}% 量比{vr_min}~{vr_max} 换手{hsl_min}~{hsl_max}% '
          f'市值<{sz_max}亿 CL{cl_min}~{cl_max}% J<{j_max} '
          f'→ 日均{r["avg"]:.0f}只 胜率{r["rate"]:.1f}%')

print()
print('=== 含负数(跌的也买)的前5 ===')
neg = [r for r in results if r['p'][0] < 0]
for r in neg[:5]:
    p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max,j_max = r['p']
    print(f'涨{p_min}~{p_max}% 量比{vr_min}~{vr_max} 换手{hsl_min}~{hsl_max}% '
          f'市值<{sz_max}亿 CL{cl_min}~{cl_max}% J<{j_max} '
          f'→ 日均{r["avg"]:.0f}只 胜率{r["rate"]:.1f}%')
