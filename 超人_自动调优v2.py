"""
版本突破记录 — 自动调优日志
目标：冠军达2.5%→80%
每个突破版本都记录在案
"""
import pickle, os, json, sys, statistics, itertools, math, time
from collections import defaultdict
from datetime import datetime

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
KLINE_CACHE = {}

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
all_days = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]

print(f'2026年 {len(all_days)}天 | 目标80%', flush=True)

def get_kline(code):
    if code not in KLINE_CACHE:
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    KLINE_CACHE[code] = json.load(f)
            except:
                KLINE_CACHE[code] = None
        else:
            KLINE_CACHE[code] = None
    return KLINE_CACHE[code]

def backtest(params, sort_by='p'):
    """
    params: 基础过滤参数
    sort_by: 'p'=涨幅, 'sc'=评分, 'combo'=涨幅*量比
    """
    champ_nvs = []
    days_with = 0
    
    for dt in all_days:
        stocks = data.get(dt, [])
        filtered = []
        for s in stocks:
            code, p = s['code'], s['p']
            if p < params['p_min'] or p > params['p_max']: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < params['vr_min'] or vr > params['vr_max']: continue
            ri = real.get(code)
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < params['hsl_min'] or hsl > params['hsl_max']: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz > params['sz_max']: continue
            nm = names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv = s.get('j_val',0) or 0
            if jv > params['j_max']: continue
            cl = s.get('cl',0)
            if cl < params['cl_min'] or cl > params['cl_max']: continue
            
            nv = s.get('n',0) or 0
            
            if sort_by == 'p':
                sv = p
            elif sort_by == 'vr':
                sv = vr
            elif sort_by == 'p*vr':
                sv = p * vr
            elif sort_by == 'p+vr':
                sv = p + vr
            elif sort_by == 'sc':
                sv = 10
                if 5<=p<=6.5: sv+=15
                elif 6.5<p<=7: sv+=8
                elif 4.5<=p<5: sv+=5
                if 60<=cl<=85: sv+=10
                if 0.8<=vr<=1.5: sv+=10
                elif 1.5<vr<=2.0: sv+=5
            else:
                sv = p
            
            filtered.append((sv, p, nv, vr, code))
        
        if not filtered: continue
        days_with += 1
        filtered.sort(key=lambda x: (-x[0], -x[1]))
        champ_nvs.append(filtered[0][2])
    
    if not champ_nvs: return 0, 0, 0, 0, 0
    n = len(champ_nvs)
    w25 = sum(1 for v in champ_nvs if v >= 2.5)
    w5 = sum(1 for v in champ_nvs if v >= 5)
    avg = statistics.mean(champ_nvs)
    cp = days_with * 100 / len(all_days)
    return w25*100/n, w5*100/n, avg, cp, n

# ===== 版本记录 =====
versions = []

def record(v, w25, cp, n, sort_by, note=''):
    versions.append({
        'ver': f'v{len(versions)+1}',
        'params': v.copy(),
        'w25': round(w25, 1),
        'cp': round(cp, 1),
        'n': n,
        'sort': sort_by,
        'note': note,
        'time': datetime.now().strftime('%H:%M')
    })
    print(f'  📝 记录: {versions[-1]}', flush=True)

def params_str(d):
    return f'涨{d["p_min"]}~{d["p_max"]}% 量{d["vr_min"]}~{d["vr_max"]} 换手{d["hsl_min"]}~{d["hsl_max"]}% 市值<{d["sz_max"]} J<{d["j_max"]} CL{d["cl_min"]}~{d["cl_max"]}'

# ===== 第1阶段：精细调参 =====
print(f'\n{"="*80}')
print(f'第1阶段：精细参数搜索（涨幅降序）')
print(f'{"="*80}', flush=True)

# 更精细的网格
fine_grid = {
    'p_min': [5.0, 5.5, 6.0],
    'p_max': [7.0, 7.5, 8.0],
    'vr_min': [0.8, 1.0, 1.2],
    'vr_max': [1.5, 2.0, 2.5],
    'hsl_min': [5],
    'hsl_max': [10, 12, 15],
    'sz_max': [60, 80, 100, 150],
    'j_max': [80, 100],
    'cl_min': [0, 60],
    'cl_max': [85, 90, 100],
}

total = 1
for k, v in fine_grid.items():
    total *= len(v)

keys = list(fine_grid.keys())
values = list(fine_grid.values())
best_score = 0
best_result = None
idx = 0

for combo in itertools.product(*values):
    params = dict(zip(keys, combo))
    idx += 1
    w25, w5, avg, cp, n = backtest(params, 'p')
    
    # 评分：达标率×出票率
    score = w25 + cp * 0.3  # 加权
    if score > best_score:
        best_score = score
        best_result = (w25, cp, n, params)
        print(f'[{idx}/{total}] 🏆 {params_str(params)} → 达2.5%:{w25:.1f}% 出票率:{cp:.1f}%', flush=True)

w25_best, cp_best, n_best, best_p = best_result
record(best_p, w25_best, cp_best, n_best, 'p', f'精细搜索最佳')

# 记录其他高达标率方案（即使出票率低）
print(f'\n--- 高达标率方案（出票率可能低） ---', flush=True)
candidates = []
for combo in itertools.product(*values):
    params = dict(zip(keys, combo))
    w25, w5, avg, cp, n = backtest(params, 'p')
    candidates.append((w25, cp, n, params))

candidates.sort(key=lambda x: -x[0])
for i, (w25, cp, n, p) in enumerate(candidates[:5]):
    if i == 0 and (w25 != w25_best or cp != cp_best):
        record(p, w25, cp, n, 'p', f'最高达标率方案#{i+1}')

print(f'\n最佳精细参数: {params_str(best_p)} → 达2.5%:{w25_best:.1f}% 出票率:{cp_best:.1f}%', flush=True)

# ===== 第2阶段：不同排序方式 =====
print(f'\n{"="*80}')
print(f'第2阶段：不同排序方式测试')
print(f'{"="*80}', flush=True)

sort_methods = ['p', 'vr', 'p*vr', 'p+vr', 'sc']
for sm in sort_methods:
    w25, w5, avg, cp, n = backtest(best_p, sm)
    diff = w25 - w25_best
    sig = '🔥' if diff > 0 else ('✅' if diff > -2 else '')
    print(f'{sig} 排序:{sm:<6} → 达2.5%:{w25:.1f}% ({diff:+.1f}%) 出票率:{cp:.1f}%', flush=True)
    if w25 >= w25_best:
        record(best_p, w25, cp, n, sm, f'排序优化:{sm}')

# ===== 第3阶段：窄条件高胜率 =====
print(f'\n{"="*80}')
print(f'第3阶段：窄条件高胜率方案')
print(f'{"="*80}', flush=True)

# 尝试各种窄条件组合，看谁能冲80%
narrow_tests = [
    # (名称, 参数调整)
    ('涨6~7.5%+量1.0~1.5+换5~10+市值<80', dict(p_min=6.0, p_max=7.5, vr_min=1.0, vr_max=1.5, hsl_max=10, sz_max=80)),
    ('涨6.5~8%+量1.0~2.0+换5~10+市值<100', dict(p_min=6.5, vr_min=1.0, vr_max=2.0, hsl_max=10, sz_max=100)),
    ('涨6~7.5%+量1.0~2.0+换5~10+市值<100', dict(p_min=6.0, p_max=7.5, vr_min=1.0, vr_max=2.0, hsl_max=10, sz_max=100)),
    ('涨6~7%+量1.0~1.5+换5~8+市值<100', dict(p_min=6.0, p_max=7.0, vr_min=1.0, vr_max=1.5, hsl_max=8, sz_max=100)),
    ('涨5~7%+量1.0~1.5+换5~8+市值<80', dict(p_min=5.0, p_max=7.0, vr_min=1.0, vr_max=1.5, hsl_max=8, sz_max=80)),
    ('涨5~7%+量1.0~1.5+换5~10+市值<60', dict(p_min=5.0, p_max=7.0, vr_min=1.0, vr_max=1.5, hsl_max=10, sz_max=60)),
    ('涨6~7%+量1.0~1.5+换5~10+市值<60', dict(p_min=6.0, p_max=7.0, vr_min=1.0, vr_max=1.5, hsl_max=10, sz_max=60)),
    ('涨6~7.5%+量0.8~1.5+换5~10+市值<80', dict(p_min=6.0, p_max=7.5, vr_min=0.8, vr_max=1.5, hsl_max=10, sz_max=80)),
    ('涨5~7%+量1.2~1.5+换5~10+市值<100', dict(p_min=5.0, p_max=7.0, vr_min=1.2, vr_max=1.5, hsl_max=10, sz_max=100)),
]

for name, changes in narrow_tests:
    p = dict(best_p)
    p.update(changes)
    w25, w5, avg, cp, n = backtest(p, 'p')
    if w25 > 0:
        sig = '🔥' if w25 >= 70 else ('✅' if w25 >= 65 else '')
        print(f'{sig} {name:<35} 达2.5%:{w25:.1f}% 出票率:{cp:.1f}% 天数:{n}', flush=True)
        if w25 >= w25_best:
            record(p, w25, cp, n, 'p', name)

# ===== 第4阶段：CL细分优化 =====
print(f'\n{"="*80}')
print(f'第4阶段：CL区间优化')
print(f'{"="*80}', flush=True)

cl_tests = [(0,85), (60,85), (65,85), (70,85), (0,90), (60,90), (65,90), (0,80), (60,80), (75,85)]
for cl_min, cl_max in cl_tests:
    p = dict(best_p)
    p['cl_min'] = cl_min
    p['cl_max'] = cl_max
    w25, w5, avg, cp, n = backtest(p, 'p')
    if w25 > 0:
        sig = '🔥' if w25 >= 70 else ''
        print(f'{sig} CL{cl_min}~{cl_max} → 达2.5%:{w25:.1f}% 出票率:{cp:.1f}%', flush=True)
        if w25 >= w25_best:
            record(p, w25, cp, n, 'p', f'CL优化{cl_min}~{cl_max}')

# ===== 第5阶段：极限窄条件冲70% =====
print(f'\n{"="*80}')
print(f'第5阶段：极限窄条件冲70%')
print(f'{"="*80}', flush=True)

# 用涨幅6%以上+量比1.0~1.5为核心，不断收窄
for sz in [200, 150, 100, 80, 60]:
    for hsl in [15, 12, 10, 8]:
        for cl_min in [0, 60]:
            for cl_max in [100, 90, 85]:
                for p_min in [5, 5.5, 6]:
                    for p_max in [7.5, 7, 8]:
                        p = dict(best_p)
                        p['p_min'] = p_min
                        p['p_max'] = p_max
                        p['hsl_max'] = hsl
                        p['sz_max'] = sz
                        p['cl_min'] = cl_min
                        p['cl_max'] = cl_max
                        w25, w5, avg, cp, n = backtest(p, 'p')
                        if w25 >= 68:
                            sig = '🔥' if w25 >= 70 else '✅'
                            print(f'{sig} 达2.5%:{w25:.1f}% 出票率:{cp:.1f}% {params_str(p)}', flush=True)
                            record(p, w25, cp, n, 'p', f'极限优选{w25:.0f}%')

# ===== 报告 =====
print(f'\n{"="*80}')
print(f'📊 全版本记录')
print(f'{"="*80}', flush=True)
print(f'{"版本":<6} {"达2.5%":<8} {"出票率":<8} {"天数":<5} {"排序":<6} {"参数":<50}')
print(f'{"-":<85}')
for v in sorted(versions, key=lambda x: -x['w25']):
    ps = params_str(v['params'])
    print(f'{v["ver"]:<6} {v["w25"]:<8.1f}% {v["cp"]:<8.1f}% {v["n"]:<5} {v["sort"]:<6} {ps}  # {v.get("note","")}')

best_ver = max(versions, key=lambda x: x['w25'])
print(f'\n🏆 最优版本: {best_ver["ver"]} 达2.5%:{best_ver["w25"]}%')
print(f'参数: {params_str(best_ver["params"])}')
print(f'排序: {best_ver["sort"]}')

if best_ver['w25'] >= 80:
    print(f'\n🎉🎉🎉 达成目标80%!')
elif best_ver['w25'] >= 70:
    print(f'\n🎉 达成70%! 继续冲80%...')
else:
    print(f'\n⚠️ 当前最优 {best_ver["w25"]}%, 距离80%差{80-best_ver["w25"]:.1f}%')
    print(f'出票率 {best_ver["cp"]}% → 每年约{int(best_ver["cp"]*len(all_days)/100)}天有交易')

# 保存版本记录
with open('auto_opt_versions.json','w') as f:
    json.dump(versions, f, ensure_ascii=False, indent=2)
print(f'\n版本记录已保存到 auto_opt_versions.json', flush=True)
