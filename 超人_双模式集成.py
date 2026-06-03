"""
双模式集成 — 回马枪80% + 涨幅排序67% = 目标70%+
"""
import pickle, os, json, sys, statistics, time
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
KLINE_CACHE = {}

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
all_days = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]

print(f'2026年 {len(all_days)}天', flush=True)

def get_kline(code):
    if code not in KLINE_CACHE:
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        KLINE_CACHE[code] = json.load(open(fp)) if os.path.exists(fp) else None
    return KLINE_CACHE[code]

def check_huitama(code, dt):
    """涨停回马枪检测"""
    kd = get_kline(code)
    if kd is None: return False, {}
    for i, d in enumerate(kd):
        if d['date'] == dt:
            if i < 8: return False, {}
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
                                    return True, {
                                        'up_pct': round(pct,1),
                                        'retreat_days': retreat,
                                    }
                    break
            return False, {}
    return False, {}

def filter_stocks(dt, params):
    """基础过滤"""
    stocks = data.get(dt, [])
    pool = []
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
        if jv > params.get('j_max', 100): continue
        cl = s.get('cl',0)
        if cl < params.get('cl_min', 0) or cl > params.get('cl_max', 100): continue
        nv = s.get('n',0) or 0
        pool.append((p, nv, code))
    return pool

# 回马枪参数
HT_PARAMS = {'p_min':5,'p_max':7,'vr_min':0.8,'vr_max':1.5,
             'hsl_min':5,'hsl_max':8,'sz_max':80,'j_max':100,'cl_min':0,'cl_max':100}

# 涨幅排序参数（最佳）
PX_PARAMS = {'p_min':5,'p_max':7.5,'vr_min':1.0,'vr_max':1.5,
             'hsl_min':5,'hsl_max':12,'sz_max':100,'j_max':100,'cl_min':0,'cl_max':100}

# ===== 双模式回测 =====
ht_nvs = []      # 回马枪模式冠军
px_nvs = []      # 涨幅排序冠军
hybrid_nvs = []  # 混合模式（回马枪优先）
hybrid_modes = [] # 每天用了哪个模式

for dt in all_days:
    # 涨幅排序候选
    px_pool = filter_stocks(dt, PX_PARAMS)
    px_champ = max(px_pool, key=lambda x: x[0])[1] if px_pool else None
    
    # 回马枪候选（从涨幅排序池中找回马枪）
    ht_pool = []
    for p, nv, code in px_pool:
        hit, _ = check_huitama(code, dt)
        if hit:
            ht_pool.append((p, nv, code))
    
    # 混合模式：回马枪优先，没有则涨幅排序
    if ht_pool:
        ht_champ = max(ht_pool, key=lambda x: x[0])[1]
        hybrid_nvs.append(ht_champ)
        ht_nvs.append(ht_champ)
        hybrid_modes.append('HT')
    elif px_champ is not None:
        hybrid_nvs.append(px_champ)
        hybrid_modes.append('PX')
    
    if px_champ is not None:
        px_nvs.append(px_champ)

# 统计
def calc(nvs):
    n = len(nvs)
    if n == 0: return 0,0,0,0
    w25 = sum(1 for v in nvs if v>=2.5)
    w5 = sum(1 for v in nvs if v>=5)
    return n, w25*100/n, w5*100/n, statistics.mean(nvs)

ht_n, ht_w25, ht_w5, ht_avg = calc(ht_nvs)
px_n, px_w25, px_w5, px_avg = calc(px_nvs)
hy_n, hy_w25, hy_w5, hy_avg = calc(hybrid_nvs)

print(f'\n{"="*70}')
print(f'双模式对比')
print(f'{"="*70}')
print(f'{"模式":<16} {"天数":<6} {"达2.5%":<10} {"达5%":<10} {"均涨幅%":<10}')
print(f'{"-":<55}')
print(f'回马枪(单独)      {ht_n:<6} {ht_w25:<10.1f}% {ht_w5:<10.1f}% {ht_avg:<+10.2f}%')
print(f'涨幅排序(单独)    {px_n:<6} {px_w25:<10.1f}% {px_w5:<10.1f}% {px_avg:<+10.2f}%')
print(f'混合模式(回马枪优先) {hy_n:<6} {hy_w25:<10.1f}% {hy_w5:<10.1f}% {hy_avg:<+10.2f}%')

ht_days = len(ht_nvs)
ht_ratio = ht_days*100/hy_n if hy_n else 0
print(f'\n回马枪使用率: {ht_days}/{hy_n}天 = {ht_ratio:.1f}%')

# ===== 模式分摊 =====
print(f'\n--- 模式分析 ---')
ht_count = sum(1 for m in hybrid_modes if m == 'HT')
px_count = sum(1 for m in hybrid_modes if m == 'PX')
print(f'回马枪命中: {ht_count}天')
print(f'涨幅排序: {px_count}天')

# 回马枪日明细
print(f'\n--- 回马枪命中日（{ht_count}天） ---')
for dt in all_days:
    pool = filter_stocks(dt, PX_PARAMS)
    for p, nv, code in pool:
        hit, info = check_huitama(code, dt)
        if hit:
            nm = names.get(code,'')
            ok = '🔥' if nv >= 5 else ('✅' if nv >= 2.5 else '❌')
            print(f'  {dt} {nm[:8]:<8} 涨{p:.1f}% → {nv:+.2f}% {ok} 回调{info.get("retreat_days","")}天')
            break

# ===== 尝试：放宽回马枪参数增加出票 =====
print(f'\n{"="*70}')
print(f'放宽回马枪参数测试（增加出票率）')
print(f'{"="*70}')

# 回马枪参数放宽
ht_variants = [
    ('紧缩', dict(sz_max=60, hsl_max=6)),
    ('基准', dict(sz_max=80, hsl_max=8)),
    ('放宽', dict(sz_max=100, hsl_max=10)),
    ('更宽', dict(sz_max=150, hsl_max=12)),
    ('最宽', dict(sz_max=200, hsl_max=15)),
]

for v_name, v_changes in ht_variants:
    ht_p = dict(HT_PARAMS)
    ht_p.update(v_changes)
    
    ht_nvs_v = []
    hy_nvs_v = []
    
    for dt in all_days:
        px_pool = filter_stocks(dt, PX_PARAMS)
        px_champ = max(px_pool, key=lambda x: x[0])[1] if px_pool else None
        
        # 用放宽参数找回马枪
        pool_r = filter_stocks(dt, ht_p)
        ht_pool_v = []
        for p, nv, code in pool_r:
            hit, _ = check_huitama(code, dt)
            if hit:
                ht_pool_v.append((p, nv, code))
        
        if ht_pool_v:
            ht_champ = max(ht_pool_v, key=lambda x: x[0])[1]
            hy_nvs_v.append(ht_champ)
            ht_nvs_v.append(ht_champ)
        elif px_champ is not None:
            hy_nvs_v.append(px_champ)
    
    if not hy_nvs_v: continue
    _, hy25, _, hy_avg = calc(hy_nvs_v)
    ht_cnt = len(ht_nvs_v)
    ht_rate = ht_cnt*100/len(hy_nvs_v)
    _, ht25, _, _ = calc(ht_nvs_v)
    
    print(f'{v_name:<8} sz<{ht_p["sz_max"]} hsl<{ht_p["hsl_max"]} → 回马枪{ht_cnt}天({ht_rate:.0f}%) {ht25:.0f}% 混合达2.5%:{hy25:.1f}%')

print(f'\n{"="*70}')
print(f'✅ 结论')
print(f'{"="*70}')
print(f'回马枪单独最佳: {ht_w25:.1f}% 达2.5%（{ht_n}天）')
print(f'混合模式: {hy_w25:.1f}%（{hy_n}天）')
