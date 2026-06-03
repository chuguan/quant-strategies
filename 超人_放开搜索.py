"""
超人策略 — 放开条件搜索
目标：票≥10只/天 且 达2.5%概率最大
"""
import pickle, json, os, sys
from itertools import product

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR)

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())

# 近一个月交易日
target_dates = [d for d in dates if d >= '2026-04-24']
print(f'回测区间: {target_dates[0]} ~ {target_dates[-1]} ({len(target_dates)}天)')

# 参数搜索空间（逐步放开）
params_grid = {
    'p_min': [3, 4, 5],
    'p_max': [8, 10, 12, 15],
    'vr_min': [0.6, 0.8, 1.0],
    'vr_max': [1.5, 2.0, 3.0, 5.0],
    'hsl_min': [3, 5],
    'hsl_max': [15, 20, 30],
    'sz_max': [200, 300, 500, 1000],
    'cl_min': [30, 40, 50, 60],
    'cl_max': [90, 95, 100],
    'j_max': [100, 120, 150],
}

print(f'搜索空间大小: {len(list(product(*params_grid.values())))} 组合...')
print('这太多了，先做一轮单变量分析找方向')
print()

# 先看基础状态下各条件的分布
# 用最松条件（涨3~15%, 量比0.6~5, 换手3~30%, 市值<1000亿, CL30~100%, J<150）
# 只看近一个月

base_filter = {'p_min':3,'p_max':15,'vr_min':0.6,'vr_max':5.0,
               'hsl_min':3,'hsl_max':30,'sz_max':1000,'cl_min':30,'cl_max':100,'j_max':150}

all_candidates = {}
for dt in target_dates:
    stocks = data[dt]
    cand = []
    for s in stocks:
        code, p = s['code'], s['p']
        if p < base_filter['p_min'] or p > base_filter['p_max']: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < base_filter['vr_min'] or vr > base_filter['vr_max']: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < base_filter['hsl_min'] or hsl > base_filter['hsl_max']: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= base_filter['sz_max']: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > base_filter['j_max']: continue
        cl = s.get('cl',0)
        if cl < base_filter['cl_min'] or cl > base_filter['cl_max']: continue
        buy_c = s.get('close', 0)
        # 次日最高
        next_high = 0
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    kdata = json.load(f)
                idx = next((i for i,k in enumerate(kdata) if k['date']==dt), None)
                if idx is not None and idx+1 < len(kdata):
                    next_high = (kdata[idx+1]['high']/buy_c-1)*100
            except: pass
        cand.append({'code':code,'nm':nm,'p':p,'cl':cl,'vr':vr,'hsl':hsl,
                     'sz':sz,'jv':jv,'buy_c':buy_c,'next_high':next_high})
    all_candidates[dt] = cand

# 统计最松条件下的基础分布
print('=== 最松条件基础分布 ===')
avgs = []; all_stocks = []
all_cand_list = []
for dt, cand in all_candidates.items():
    avgs.append(len(cand))
    for c in cand:
        all_stocks.append(c['next_high'])
        all_cand_list.append(c)

n_days = len(avgs)
n_total = sum(avgs)
w25 = sum(1 for v in all_stocks if v>=2.5)
print(f'平均候选: {n_total/n_days:.1f}只/天 (min={min(avgs)}, max={max(avgs)})')
print(f'总样本: {n_total}只')
print(f'达2.5%: {w25}({w25*100/n_total:.1f}%)')
print()

# 单变量维度分析：每个维度在不同区间下的达标率
print('=== 各维度区间达标率分析 ===')
print()

def analyze_dimension(key, bins, label):
    """分析单一维度的各区间达标率"""
    results = []
    for bin_min, bin_max in bins:
        subset = [s for s in all_cand_list if bin_min <= s.get(key, 0) < bin_max]
        count = len(subset)
        if count < 5: continue
        w = sum(1 for s in subset if s.get('next_high',0) >= 2.5)
        cand_count = sum(1 for dt, clist in all_candidates.items() 
                        for c in clist if bin_min <= c.get(key,0) < bin_max)
        print(f'  {label} {bin_min:>5}~{bin_max:<4}: {count:>4}只 达2.5%:{w:>3}({w*100/count:5.1f}%) 日均{cand_count/n_days:.1f}只')
        results.append({'range':f'{bin_min}~{bin_max}','count':count,'win':w,'win_rate':w*100/count,'cand_per_day':cand_count/n_days})
    return results

# 按各个维度分组
print('【涨幅 p】')
analyze_dimension('p', [(3,4),(4,5),(5,6),(6,7),(7,8),(8,10),(10,15)], '涨')
print()

print('【量比 vr】')
analyze_dimension('vr', [(0.6,0.8),(0.8,1.0),(1.0,1.2),(1.2,1.5),(1.5,2.0),(2.0,3.0),(3.0,5.0)], '量')
print()

print('【换手 hsl】')
analyze_dimension('hsl', [(3,5),(5,8),(8,10),(10,15),(15,20),(20,30)], '换手')
print()

print('【市值 sz】')
analyze_dimension('sz', [(0,30),(30,50),(50,100),(100,200),(200,300),(300,500),(500,1000)], '市值')
print()

print('【CL 收盘位】')
analyze_dimension('cl', [(0,20),(20,40),(40,50),(50,60),(60,70),(70,80),(80,90),(90,95),(95,100)], 'CL')
print()

print('【J值】')
analyze_dimension('jv', [(0,20),(20,40),(40,60),(60,80),(80,100),(100,120),(120,150)], 'J')
