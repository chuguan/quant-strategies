"""
超人策略 — 组合优化搜索 第二轮
基于单变量分析，针对放量条件找最佳组合
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
print(f'回测: {len(target_dates)}天 ({target_dates[0]}~{target_dates[-1]})')

# 精简参数空间（基于单变量分析）
param_grid = {
    'p_min': [4, 5],
    'p_max': [8, 10, 12],
    'vr_min': [0.6, 0.8, 1.0],
    'vr_max': [1.5, 2.0, 3.0],
    'hsl_min': [3, 5],
    'hsl_max': [15, 20, 30],
    'sz_max': [200, 300, 500],
    'cl_min': [0, 30, 50],  # 放开CL
    'cl_max': [100],        # CL上限放开
    'j_max': [100, 120, 150],
}

all_combs = list(product(*param_grid.values()))
print(f'组合数: {len(all_combs)}')
print()

# 预加载K线数据加速
cache_dir = CACHE_DIR
kline_cache = {}

def get_kline_data(code, date):
    """获取K线中指定日期之后1天的最高价"""
    key = f'{code}_{date}'
    if key in kline_cache:
        return kline_cache[key]
    fp = os.path.join(cache_dir, f'{code}.json')
    if not os.path.exists(fp):
        kline_cache[key] = 0
        return 0
    try:
        with open(fp) as f:
            kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is not None and idx+1 < len(kdata):
            buy_c = kdata[idx]['close']
            res = (kdata[idx+1]['high']/buy_c-1)*100 if buy_c>0 else 0
            kline_cache[key] = res
            return res
    except:
        pass
    kline_cache[key] = 0
    return 0

# 逐组合搜索
results = []
total_combs = len(all_combs)

for ci, params in enumerate(all_combs):
    p_min, p_max, vr_min, vr_max, hsl_min, hsl_max, sz_max, cl_min, cl_max, j_max = params
    
    daily_counts = []
    all_hits = []
    
    for dt in target_dates:
        stocks = data[dt]
        day_cand = []
        for s in stocks:
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
            nxt = get_kline_data(code, dt)
            day_cand.append(nxt)
        
        daily_counts.append(len(day_cand))
        all_hits.extend(day_cand)
    
    avg_count = sum(daily_counts)/len(daily_counts)
    min_count = min(daily_counts)
    days_under_10 = sum(1 for c in daily_counts if c < 10)
    total = len(all_hits)
    w25 = sum(1 for v in all_hits if v >= 2.5) if total > 0 else 0
    w25_rate = w25*100/total if total > 0 else 0
    
    # 只关心候选≥10的组合
    if avg_count >= 10 and days_under_10 <= 5:
        results.append({
            'params': params,
            'avg_count': avg_count,
            'min_count': min_count,
            'days_under_10': days_under_10,
            'total': total,
            'w25': w25,
            'w25_rate': w25_rate,
        })

# 按达标率排序
results.sort(key=lambda x: -x['w25_rate'])

print(f'满足候选≥10的组合: {len(results)}')
print()
print(f'{"排名":<4} {"涨":<8} {"量比":<10} {"换手":<10} {"市值":<8} {"CL":<8} {"J<":<5} {"日均":<5} {"<10天":<6} {"总样本":<6} {"达2.5%":<8} {"胜率":<6}')
print('-'*95)

for i, r in enumerate(results[:30]):
    p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max,j_max = r['params']
    print(f'{i+1:<4} {p_min}~{p_max:<4} {vr_min}~{vr_max:<5} {hsl_min}~{hsl_max:<5} <{sz_max:<4} '
          f'{cl_min}~{cl_max:<3} {j_max:<5} {r["avg_count"]:<5.1f} {r["days_under_10"]:<6} '
          f'{r["total"]:<6} {r["w25"]:<8} {r["w25_rate"]:<5.1f}%')

print()
print('=== 推荐组合（高胜率+票数稳定） ===')
# 找最优平衡
for r in results:
    if r['avg_count'] >= 10 and r['avg_count'] <= 50 and r['days_under_10'] <= 2:
        p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max,j_max = r['params']
        print(f'涨{p_min}~{p_max}% 量比{vr_min}~{vr_max} 换手{hsl_min}~{hsl_max}% '
              f'市值<{sz_max}亿 CL{cl_min}~{cl_max}% J<{j_max} '
              f'→ 日均{r["avg_count"]:.1f}只 胜率{r["w25_rate"]:.1f}%')
