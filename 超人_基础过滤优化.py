"""
基础硬过滤条件优化 — 网格搜索最佳参数组合
目标：冠军达2.5%最大化的同时保留出票率
"""
import pickle, os, json, statistics, itertools, math
from collections import defaultdict

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
all_days = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]

print(f'2026年 {len(all_days)}天 全量3427只', flush=True)

# ===== 参数空间 =====
# 基础条件参数
p_min_opts = [5.0]           # 涨幅下限
p_max_opts = [7.0, 7.5, 8.0]  # 涨幅上限

vr_min_opts = [0.8, 1.0, 1.2]  # 量比下限
vr_max_opts = [1.5, 2.0, 3.0]  # 量比上限

hsl_min_opts = [5]            # 换手下限
hsl_max_opts = [12, 15, 18]    # 换手上限

sz_max_opts = [100, 150, 200]  # 市值上限

j_max_opts = [80, 100]         # J值上限

# CL硬过滤（不加分）
cl_min_opts = [0, 60, 65, 70]
cl_max_opts = [85, 90, 100]

total_combos = (len(p_max_opts) * len(vr_min_opts) * len(vr_max_opts) * 
                len(hsl_max_opts) * len(sz_max_opts) * len(j_max_opts) *
                len(cl_min_opts) * len(cl_max_opts))
print(f'总组合: {total_combos}', flush=True)

# ===== 回测函数 =====
def backtest(p_min, p_max, vr_min, vr_max, hsl_min, hsl_max, sz_max, j_max, cl_min, cl_max):
    """取每天冠军（不评分，按涨幅降序），返回达标率、天数等"""
    champ_results = []
    
    for dt in all_days:
        stocks = data.get(dt, [])
        filtered = []
        for s in stocks:
            code, p = s['code'], s['p']
            # 涨幅
            if p < p_min or p > p_max: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < vr_min or vr > vr_max: continue
            ri = real.get(code)
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < hsl_min or hsl > hsl_max: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz > sz_max: continue
            nm = names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv = s.get('j_val',0) or 0
            if jv > j_max: continue
            cl = s.get('cl',0)
            if cl < cl_min or cl > cl_max: continue
            
            nv = s.get('n',0) or 0
            filtered.append((p, nv))
        
        if not filtered: continue
        # 取涨幅最高为冠军
        filtered.sort(key=lambda x: -x[0])
        champ_nv = filtered[0][1]
        champ_results.append(champ_nv)
    
    if not champ_results: return 0, 0, 0, 0, 0
    
    n = len(champ_results)
    w25 = sum(1 for v in champ_results if v >= 2.5)
    w5 = sum(1 for v in champ_results if v >= 5)
    avg = statistics.mean(champ_results) if champ_results else 0
    chupiao = n * 100 / len(all_days)
    
    return w25*100/n, w5*100/n, avg, chupiao, n

# ===== 简单搜索：逐个参数测试 =====
print(f'\n{"="*80}')
print(f'逐个参数测试（控制变量）')
print(f'{"="*80}', flush=True)

# 基准
base_p_min, base_p_max = 5.0, 8.0
base_vr_min, base_vr_max = 0.8, 3.0
base_hsl_min, base_hsl_max = 5, 15
base_sz_max = 150
base_j_max = 80
base_cl_min, base_cl_max = 0, 100

base_w25, base_w5, base_avg, base_cp, base_n = backtest(
    base_p_min, base_p_max, base_vr_min, base_vr_max,
    base_hsl_min, base_hsl_max, base_sz_max, base_j_max, base_cl_min, base_cl_max
)
print(f'基准(5~8%/量比0.8~/换手5~15%/市值<150/J<80): {base_n}天 | 达2.5%:{base_w25:.1f}% | 出票率:{base_cp:.1f}%', flush=True)

# 测试每个参数
tests = [
    # (名称, 参数变更)
    ('涨幅上限6.5%', dict(p_max=6.5)),
    ('涨幅上限7%', dict(p_max=7.0)),
    ('涨幅上限7.5%', dict(p_max=7.5)),
    ('涨幅上限8%', dict(p_max=8.0)),
    
    ('量比下限1.0', dict(vr_min=1.0)),
    ('量比下限1.2', dict(vr_min=1.2)),
    ('量比上限1.5', dict(vr_max=1.5)),
    ('量比上限2.0', dict(vr_max=2.0)),
    
    ('换手上限12%', dict(hsl_max=12)),
    ('换手上限18%', dict(hsl_max=18)),
    
    ('市值上限100亿', dict(sz_max=100)),
    ('市值上限200亿', dict(sz_max=200)),
    
    ('J值上限100', dict(j_max=100)),
    
    ('CL下限60%', dict(cl_min=60)),
    ('CL下限65%', dict(cl_min=65)),
    ('CL下限70%', dict(cl_min=70)),
    ('CL上限85%', dict(cl_max=85)),
    ('CL上限90%', dict(cl_max=90)),
    ('CL 60~85%', dict(cl_min=60, cl_max=85)),
    ('CL 65~90%', dict(cl_min=65, cl_max=90)),
    ('CL 70~85%', dict(cl_min=70, cl_max=85)),
]

for name, changes in tests:
    params = {
        'p_min': base_p_min, 'p_max': base_p_max,
        'vr_min': base_vr_min, 'vr_max': base_vr_max,
        'hsl_min': base_hsl_min, 'hsl_max': base_hsl_max,
        'sz_max': base_sz_max, 'j_max': base_j_max,
        'cl_min': base_cl_min, 'cl_max': base_cl_max
    }
    params.update(changes)
    
    w25, w5, avg, cp, n = backtest(**params)
    diff_w25 = w25 - base_w25
    sig = '🔥' if diff_w25 > 5 else ('✅' if diff_w25 > 2 else ('📊' if diff_w25 > 0 else ''))
    
    print(f'{sig} {name:<30} {n:>2}天 | 达2.5%:{w25:>5.1f}% ({diff_w25:>+5.1f}%) | 出票率:{cp:>5.1f}% | 均{avg:.2f}%', flush=True)

print(f'\n{"="*80}')
print(f'最佳单参数调整')
print(f'{"="*80}', flush=True)

# 找每个维度最佳值
best_params = {}
for pname, popts, key in [
    ('涨幅上限', [(5,7.0),(5,7.5),(5,8.0)], 'p_max'),
    ('涨幅下限', [(5.0,8),(5.5,8)], 'p_min'),
    ('量比下限', [(0.8,3),(1.0,3),(1.2,3)], 'vr_min'),
    ('量比上限', [(0.8,1.5),(0.8,2.0),(0.8,3.0)], 'vr_max'),
    ('换手上限', [(5,12),(5,15),(5,18)], 'hsl_max'),
    ('市值上限', [(5,15,100),(5,15,150),(5,15,200)], 'sz_max'),
    ('J值上限', [(5,15,150,80),(5,15,150,100)], 'j_max'),
]:
    pass

print(f'\n{"="*80}')
print(f'组合优化：最佳条件分段')
print(f'{"="*80}', flush=True)

# 手动测试最有希望的组合
combos = [
    # 名称, 参数
    ('基准', dict(p_max=8)),
    ('涨幅上限7%', dict(p_max=7)),
    ('涨幅上限7%+量比0.8~2.0', dict(p_max=7, vr_max=2.0)),
    ('涨幅上限7%+量比0.8~2.0+换手上限12%', dict(p_max=7, vr_max=2.0, hsl_max=12)),
    ('涨幅上限7%+量比0.8~2.0+CL60~85', dict(p_max=7, vr_max=2.0, cl_min=60, cl_max=85)),
    ('涨幅上限7%+CL60~85', dict(p_max=7, cl_min=60, cl_max=85)),
    ('涨幅上限7%+CL60~85+换手上限12%', dict(p_max=7, cl_min=60, cl_max=85, hsl_max=12)),
    ('涨幅上限7%+CL60~85+市值<200', dict(p_max=7, cl_min=60, cl_max=85, sz_max=200)),
    ('涨幅上限7.5%', dict(p_max=7.5)),
    ('涨幅上限7.5%+CL60~85', dict(p_max=7.5, cl_min=60, cl_max=85)),
    ('涨幅上限7.5%+量比0.8~2.0', dict(p_max=7.5, vr_max=2.0)),
    ('CL60~85', dict(cl_min=60, cl_max=85)),
    ('CL60~85+J<100', dict(cl_min=60, cl_max=85, j_max=100)),
    ('CL60~85+市值<200', dict(cl_min=60, cl_max=85, sz_max=200)),
    ('CL60~85+量比1.0~2.0', dict(cl_min=60, cl_max=85, vr_min=1.0, vr_max=2.0)),
    ('CL65~90', dict(cl_min=65, cl_max=90)),
    ('涨幅7%+CL60~85+量比1.0~2.0+换手<12', dict(p_max=7, cl_min=60, cl_max=85, vr_min=1.0, vr_max=2.0, hsl_max=12)),
]

print(f'{"条件":<45} {"天数":<4} {"达2.5%":<10} {"出票率":<8} {"均涨幅%":<8}')
print(f'{"-":<80}')
for name, changes in combos:
    params = {
        'p_min': 5.0, 'p_max': 8.0,
        'vr_min': 0.8, 'vr_max': 3.0,
        'hsl_min': 5, 'hsl_max': 15,
        'sz_max': 150, 'j_max': 80,
        'cl_min': 0, 'cl_max': 100
    }
    params.update(changes)
    w25, w5, avg, cp, n = backtest(**params)
    diff = w25 - base_w25
    sig = '🔥' if diff > 5 else ('✅' if diff > 2 else '')
    print(f'{sig} {name:<43} {n:<4} {w25:<10.1f}% {cp:<8.1f}% {avg:<8.2f}%', flush=True)

# ===== 联合最优：先定基础条件再上评分 =====
print(f'\n{"="*80}')
print(f'🏆 最优基础+评分测试')
print(f'{"="*80}', flush=True)

# 用最佳基础条件跑，然后加上评分
best_basic = dict(
    p_min=5.0, p_max=7.0,
    vr_min=0.8, vr_max=2.0,
    hsl_min=5, hsl_max=12,
    sz_max=150, j_max=80,
    cl_min=60, cl_max=85
)

# 重新跑最佳基础的冠军
kline_cache = {}
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

def get_kline(code):
    if code not in kline_cache:
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    kline_cache[code] = json.load(f)
            except:
                kline_cache[code] = None
        else:
            kline_cache[code] = None
    return kline_cache[code]

import importlib.util
spec = importlib.util.spec_from_file_location('sm', '超人策略_v2.0.py')
sm = importlib.util.module_from_spec(spec)

# 直接用最佳基础过滤，然后+基础评分（不读K线）和+K线评分
print(f'\n最佳基础过滤(涨幅5~7%/量比0.8~2.0/换手5~12%/CL60~85/市值<150/J<80):')

p_max, vr_max, hsl_max = 7.0, 2.0, 12
cl_min, cl_max = 60, 85

champ_results = []
for dt in all_days:
    stocks = data.get(dt, [])
    filtered = []
    for s in stocks:
        code, p = s['code'], s['p']
        if p < 5 or p > p_max: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < 0.8 or vr > vr_max: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > hsl_max: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz > 150: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > 80: continue
        cl = s.get('cl',0)
        if cl < cl_min or cl > cl_max: continue
        
        nv = s.get('n',0) or 0
        buy_c = s.get('close', 0)
        filtered.append((p, nv, code, vr, cl, hsl, sz, jv, buy_c))
    
    if not filtered: continue
    filtered.sort(key=lambda x: -x[0])
    champ_results.append(filtered[0])

n = len(champ_results)
w25 = sum(1 for c in champ_results if c[1] >= 2.5)
print(f'  无评分: {n}天 | 达2.5%:{w25*100/n:.1f}%', flush=True)

# 加上伯乐v4评分
scored_champ = []
for dt in all_days:
    stocks = data.get(dt, [])
    filtered = []
    for s in stocks:
        code, p = s['code'], s['p']
        if p < 5 or p > p_max: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < 0.8 or vr > vr_max: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > hsl_max: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz > 150: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > 80: continue
        cl = s.get('cl',0)
        if cl < cl_min or cl > cl_max: continue
        
        nv = s.get('n',0) or 0
        buy_c = s.get('close', 0)
        
        # 伯乐v4评分
        sc = 10
        if 5 <= p <= 6.5: sc += 15
        elif 6.5 < p <= 7: sc += 8
        elif 4.5 <= p < 5: sc += 5
        elif p > 7: sc -= 15
        if 60 <= cl <= 85: sc += 10
        elif cl > 90: sc -= 15
        if 0.8 <= vr <= 1.5: sc += 10
        elif 1.5 < vr <= 2.0: sc += 5
        elif vr > 2: sc -= 8
        
        filtered.append((sc, p, nv, code, vr, cl))
    
    if not filtered: continue
    filtered.sort(key=lambda x: (-x[0], -x[1]))
    scored_champ.append(filtered[0])

n2 = len(scored_champ)
w25_2 = sum(1 for c in scored_champ if c[2] >= 2.5)
print(f'  +伯乐评分: {n2}天 | 达2.5%:{w25_2*100/n2:.1f}%', flush=True)

# 加上K线评分
kline_champ = []
kline_reads = 0
for dt in all_days:
    stocks = data.get(dt, [])
    filtered = []
    for s in stocks:
        code, p = s['code'], s['p']
        if p < 5 or p > p_max: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < 0.8 or vr > vr_max: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > hsl_max: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz > 150: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > 80: continue
        cl = s.get('cl',0)
        if cl < cl_min or cl > cl_max: continue
        
        nv = s.get('n',0) or 0
        buy_c = s.get('close', 0)
        
        # 伯乐v4基础评分
        sc = 10
        if 5 <= p <= 6.5: sc += 15
        elif 6.5 < p <= 7: sc += 8
        elif 4.5 <= p < 5: sc += 5
        elif p > 7: sc -= 15
        if 60 <= cl <= 85: sc += 10
        elif cl > 90: sc -= 15
        if 0.8 <= vr <= 1.5: sc += 10
        elif 1.5 < vr <= 2.0: sc += 5
        elif vr > 2: sc -= 8
        
        kd = get_kline(code)
        if kd:
            today_idx = None
            for i, d in enumerate(kd):
                if d['date'] == dt:
                    today_idx = i; break
            if today_idx and today_idx >= 20:
                td = kd[today_idx]
                close_price = td['close']
                # 多头排列
                ma10 = statistics.mean([kd[i]['close'] for i in range(today_idx-9, today_idx+1)])
                ma20 = statistics.mean([kd[i]['close'] for i in range(today_idx-19, today_idx+1)])
                sc += 5 if ma10 >= ma20 else 0
                sc += 2 if close_price >= ma10 else 0
                sc += 3 if close_price >= ma20 else 0
                # 加速度
                prev_pct = (kd[today_idx-1]['close']/kd[today_idx-2]['close']-1)*100
                today_pct = (close_price/kd[today_idx-1]['close']-1)*100
                accel = today_pct - prev_pct
                sc += 3 if accel < 7 else 0
                # 量
                vol_ma5 = statistics.mean([kd[i]['volume'] for i in range(today_idx-4, today_idx+1)])
                vol_ratio_v = td['volume']/vol_ma5 if vol_ma5 > 0 else 0
                sc += 2 if vol_ratio_v < 2 else (-3 if vol_ratio_v > 3 else 0)
                # 位置
                h20 = max([kd[i]['high'] for i in range(today_idx-19, today_idx+1)])
                l20 = min([kd[i]['low'] for i in range(today_idx-19, today_idx+1)])
                near20 = (close_price-l20)/(h20-l20)*100 if h20>l20 else 50
                sc += 3 if 40 <= near20 <= 80 else (-3 if near20 > 90 else 0)
        
        filtered.append((sc, p, nv, code, vr, cl))
    
    if not filtered: continue
    filtered.sort(key=lambda x: (-x[0], -x[1]))
    kline_champ.append(filtered[0])

n3 = len(kline_champ)
w25_3 = sum(1 for c in kline_champ if c[2] >= 2.5)
print(f'  +K线评分: {n3}天 | 达2.5%:{w25_3*100/n3:.1f}%', flush=True)

print(f'\n{"="*80}')
print(f'  🚀 最终结论')
print(f'{"="*80}', flush=True)
print(f'1. 最佳基础过滤: 涨幅5~7%/量比0.8~2.0/换手5~12%/CL60~85/市值<150/J<80', flush=True)
print(f'2. 无评分冠军: {w25*100/n:.1f}%', flush=True)
print(f'3. +伯乐评分: {w25_2*100/n2:.1f}%', flush=True)
print(f'4. +K线评分: {w25_3*100/n3:.1f}%', flush=True)
print(f'5. 出票率: {n*100/len(all_days):.1f}%', flush=True)
