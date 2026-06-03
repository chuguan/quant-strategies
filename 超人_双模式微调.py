"""
双模式微调 — 目标70%+
"""
import pickle, os, json, sys, statistics, itertools, time
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
KLINE_CACHE = {}

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
all_days = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]

def get_kline(code):
    if code not in KLINE_CACHE:
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        KLINE_CACHE[code] = json.load(open(fp)) if os.path.exists(fp) else None
    return KLINE_CACHE[code]

def check_huitama(code, dt):
    kd = get_kline(code)
    if kd is None: return False
    for i, d in enumerate(kd):
        if d['date'] == dt:
            if i < 8: return False
            kw = kd[i-7:i+1]; today = kw[-1]
            for j in range(len(kw)-2, -1, -1):
                prev = kw[j-1] if j > 0 else today
                pct = (kw[j]['close']-prev['close'])/prev['close']*100
                if pct >= 5:
                    retreat = len(kw) - j - 2
                    if 1 <= retreat <= 4:
                        vols = [d['volume'] for d in kw[j+1:-1]]
                        if vols and max(vols) <= kw[j]['volume']*1.3:
                            if today['volume'] >= (statistics.mean(vols) if vols else 1)*1.1:
                                if today['close'] > today['open']:
                                    return True
                    break
    return False

def filter_pool(dt, p):
    stocks = data.get(dt, [])
    pool = []
    for s in stocks:
        code = s['code']; px = s['p']
        if px < p['p_min'] or px > p['p_max']: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < p['vr_min'] or vr > p['vr_max']: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < p['hsl_min'] or hsl > p['hsl_max']: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz > p['sz_max']: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        if (s.get('j_val',0) or 0) > p.get('j_max',100): continue
        cl = s.get('cl',0)
        if cl < p.get('cl_min',0) or cl > p.get('cl_max',100): continue
        nv = s.get('n',0) or 0
        pool.append((px, nv, code))
    return pool

# 回马枪基准参数
HT_BASE = {'p_min':5,'p_max':7,'vr_min':0.8,'vr_max':1.5,'hsl_min':5,'hsl_max':8,'sz_max':80,'j_max':100,'cl_min':0,'cl_max':100}

# 涨幅排序参数 - 尝试不同组合
PX_OPTIONS = [
    ('涨5~7%量1.0~1.5换5~10%市值<80', dict(p_min=5,p_max=7,vr_min=1.0,vr_max=1.5,hsl_max=10,sz_max=80)),
    ('涨5~7%量1.0~1.5换5~12%市值<100', dict(p_min=5,p_max=7,vr_min=1.0,vr_max=1.5,hsl_max=12,sz_max=100)),
    ('涨5~7.5%量1.0~1.5换5~12%市值<100', dict(p_min=5,p_max=7.5,vr_min=1.0,vr_max=1.5,hsl_max=12,sz_max=100)),
    ('涨5~8%量1.0~1.5换5~15%市值<200', dict(p_min=5,p_max=8,vr_min=1.0,vr_max=1.5,hsl_max=15,sz_max=200)),
    ('涨5~7%量0.8~1.5换5~8%市值<80', dict(p_min=5,p_max=7,vr_min=0.8,vr_max=1.5,hsl_max=8,sz_max=80)),  # 跟回马枪同参数
]

print(f'双模式优化：回马枪(基准) + 涨幅排序各方案')
print(f'{"涨幅排序方案":<35} {"总天数":<6} {"达2.5%":<10} {"回马枪天数":<10} {"回马枪%":<8}', flush=True)
print(f'{"-":<70}')

best_hy = 0
best_px = None

for px_name, px_changes in PX_OPTIONS:
    px_p = dict(HT_BASE)
    px_p.update(px_changes)
    
    ht_nvs, hy_nvs = [], []
    
    for dt in all_days:
        px_pool = filter_pool(dt, px_p)
        px_champ = max(px_pool, key=lambda x: x[0])[1] if px_pool else None
        
        ht_pool = [(x, nv, code) for x, nv, code in px_pool if check_huitama(code, dt)]
        
        if ht_pool:
            ht_best = max(ht_pool, key=lambda x: x[0])[1]
            hy_nvs.append(ht_best)
            ht_nvs.append(ht_best)
        elif px_champ is not None:
            hy_nvs.append(px_champ)
    
    if not hy_nvs: continue
    n = len(hy_nvs)
    hy25 = sum(1 for v in hy_nvs if v>=2.5)*100/n
    ht_cnt = len(ht_nvs)
    ht_pct = ht_cnt*100/n
    ht25 = sum(1 for v in ht_nvs if v>=2.5)*100/ht_cnt if ht_cnt else 0
    
    sig = '🔥' if hy25 >= 68 else ('✅' if hy25 >= 65 else '')
    print(f'{sig} {px_name:<33} {n:<6} {hy25:<10.1f}% 回马{ht_cnt}天({ht_pct:.0f}%) {ht25:.0f}%')
    
    if hy25 > best_hy:
        best_hy = hy25
        best_px = (px_name, px_p, ht_cnt, ht_pct)

print(f'\n🏆 最优: {best_px[0]} → {best_hy:.1f}% (回马枪{best_px[2]}天 {best_px[3]:.1f}%)', flush=True)

# 再微调：在最优方案基础上调回马枪参数
print(f'\n{"="*70}')
print(f'回马枪参数微调（在最优涨幅排序基础上）')
print(f'{"="*70}', flush=True)

# 回马枪参数微调
ht_tweaks = [
    ('基准', dict(sz_max=80, hsl_max=8)),
    ('sz<100', dict(sz_max=100, hsl_max=8)),
    ('hsl<10', dict(sz_max=80, hsl_max=10)),
    ('sz<100+hsl<10', dict(sz_max=100, hsl_max=10)),
    ('sz<60', dict(sz_max=60, hsl_max=8)),
    ('hsl<6', dict(sz_max=80, hsl_max=6)),
]

for ht_name, ht_changes in ht_tweaks:
    ht_p = dict(HT_BASE)
    ht_p.update(ht_changes)
    
    # 用最优涨幅排序参数
    px_p = best_px[1]
    
    ht_nvs, hy_nvs = [], []
    for dt in all_days:
        px_pool = filter_pool(dt, px_p)
        px_champ = max(px_pool, key=lambda x: x[0])[1] if px_pool else None
        
        # 用ht_p过滤找马
        ht_pool_v = filter_pool(dt, ht_p)
        ht_pool = [(x, nv, code) for x, nv, code in ht_pool_v if check_huitama(code, dt)]
        
        if ht_pool:
            ht_best2 = max(ht_pool, key=lambda x: x[0])[1]
            hy_nvs.append(ht_best2)
            ht_nvs.append(ht_best2)
        elif px_champ is not None:
            hy_nvs.append(px_champ)
    
    n = len(hy_nvs)
    hy25 = sum(1 for v in hy_nvs if v>=2.5)*100/n
    ht_cnt = len(ht_nvs)
    ht25 = sum(1 for v in ht_nvs if v>=2.5) * 100 / max(ht_cnt, 1)
    sig = '🔥' if hy25 >= 70 else ('✅' if hy25 >= 68 else '')
    print(f'{sig} {ht_name:<20} 回马枪{ht_cnt}天({ht_cnt*100/n:.0f}%) {ht25:.0f}% 混合{hy25:.1f}%')

print(f'\n总耗时: {time.time()-0:.1f}s', flush=True)
