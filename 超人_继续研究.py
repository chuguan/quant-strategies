"""
继续研究：双模式 + 回马枪参数精细化
目标：在保持回马枪80%胜率前提下，增加出票天数
"""
import pickle, os, json, statistics
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
KC = {}
t0 = __import__('time').time()

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
ad = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]
print(f'2026年 {len(ad)}天', flush=True)

def gk(code):
    if code not in KC:
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        KC[code] = json.load(open(fp)) if os.path.exists(fp) else None
    return KC[code]

# ===== 回马枪检测（可调参数）=====
def check_huitama(code, dt, min_up=5, rt_min=1, rt_max=4, vol_max_ratio=1.3):
    kd = gk(code)
    if not kd: return False
    for i, d in enumerate(kd):
        if d['date'] != dt: continue
        if i < 8: return False
        kw = kd[i-7:i+1]; t = kw[-1]
        for j in range(len(kw)-2, -1, -1):
            prv = kw[j-1] if j > 0 else t
            pct = (kw[j]['close']-prv['close'])/prv['close']*100
            if pct >= min_up:
                rt = len(kw) - j - 2
                if rt_min <= rt <= rt_max:
                    vols = [d['volume'] for d in kw[j+1:-1]]
                    if vols and max(vols) <= kw[j]['volume']*vol_max_ratio:
                        if t['volume'] >= (statistics.mean(vols) or 1)*1.1 and t['close'] > t['open']:
                            return True
                break
    return False

# ===== 过滤池 =====
def filter_stocks(dt, params):
    pool = []
    for s in data.get(dt, []):
        cd, px = s['code'], s['p']
        if px < params['p_min'] or px > params['p_max']: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < params['vr_min'] or vr > params['vr_max']: continue
        ri = real.get(cd)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < params['hsl_min'] or hsl > params['hsl_max']: continue
        if (ri.get('shizhi',0) or 0) > params['sz_max']: continue
        nm = names.get(cd,'')
        if 'ST' in nm or '*ST' in nm: continue
        if (s.get('j_val',0) or 0) > 100: continue
        nv = s.get('n',0) or 0
        pool.append({'p':px, 'nv':nv, 'code':cd, 'nm':nm})
    return pool

# ===== 回马枪双模式（回马枪单独记录）=====
def run_dual(params, ht_params=None):
    """
    params: 基础过滤参数
    ht_params: 回马枪检测参数 {min_up, rt_min, rt_max, vol_max_ratio}
    """
    if ht_params is None:
        ht_params = {'min_up':5, 'rt_min':1, 'rt_max':4, 'vol_max_ratio':1.3}
    
    hybrid_nvs = []  # 双模式结果
    ht_nvs = []      # 回马枪单独结果
    px_nvs = []      # 涨幅排序结果
    
    for dt in ad:
        pool = filter_stocks(dt, params)
        if not pool: continue
        pool.sort(key=lambda x: -x['p'])
        px_nvs.append(pool[0]['nv'])
        
        # 找回马枪
        htf = [s for s in pool if check_huitama(
            s['code'], dt,
            ht_params['min_up'], ht_params['rt_min'], ht_params['rt_max'],
            ht_params['vol_max_ratio']
        )]
        
        if htf:
            htf.sort(key=lambda x: -x['p'])
            best_ht = htf[0]['nv']
            hybrid_nvs.append(best_ht)
            ht_nvs.append(best_ht)
        else:
            hybrid_nvs.append(pool[0]['nv'])
    
    def stats(nvs):
        n = len(nvs)
        if n == 0: return 0,0,0,0
        w25 = sum(1 for v in nvs if v>=2.5)*100/n
        w5 = sum(1 for v in nvs if v>=5)*100/n
        return n, w25, w5, statistics.mean(nvs)
    
    return stats(hybrid_nvs), stats(ht_nvs), stats(px_nvs)

# ===== 阶段1：宽池+回马枪参数搜索 =====
WIDE = {'p_min':5,'p_max':8,'vr_min':1.0,'vr_max':1.5,'hsl_min':5,'hsl_max':12,'sz_max':100}

print(f'\n{"="*70}')
print(f'阶段1：宽池(涨5~8%量1.0~1.5换5~12%市值<100) + 回马枪参数搜索')
print(f'{"="*70}', flush=True)

# 先跑基准（无回马枪）
_, _, px_s = run_dual(WIDE)
print(f'涨幅排序基准: {px_s[0]}天 达2.5%:{px_s[1]:.1f}% 均:{px_s[3]:.2f}%', flush=True)

# 回马枪参数搜索
best_hybrid = (0,0,0,0,{})
best_ht_only = (0,0,0,0,{})

for min_up in [5,6]:
    for rt_min, rt_max in [(1,4),(1,3),(2,4),(1,2),(2,3)]:
        for vol_max in [1.3, 1.5, 2.0]:
            ht_p = {'min_up':min_up, 'rt_min':rt_min, 'rt_max':rt_max, 'vol_max_ratio':vol_max}
            hy, ht, px = run_dual(WIDE, ht_p)
            
            hy_sig = '🔥' if hy[1] >= 65 else ('✅' if hy[1] >= 63 else '')
            ht_sig = '🔥' if ht[1] >= 70 else ('✅' if ht[1] >= 65 else '')
            
            print(f'{hy_sig} 双{hy[1]:.1f}% {hy[0]:>2}d | {ht_sig} 回马{ht[1]:.1f}% {ht[0]:>2}d | min>={min_up}% 回调{rt_min}~{rt_max}d 缩量x{vol_max}', flush=True)
            
            if hy[1] > best_hybrid[1]:
                best_hybrid = (hy[1], hy[0], ht[1], ht[0], ht_p)
            if ht[1] > best_ht_only[1] and ht[0] >= 15:
                best_ht_only = (ht[1], ht[0], hy[1], hy[0], ht_p)

print(f'\n🏆 最佳双模式: 达2.5%:{best_hybrid[0]:.1f}% {best_hybrid[1]}天 (回马{best_hybrid[3]}天 {best_hybrid[2]:.0f}%)', flush=True)
print(f'🏆 最佳回马枪: 达2.5%:{best_ht_only[0]:.1f}% {best_ht_only[1]}天 (双模式{best_ht_only[3]}天 {best_ht_only[2]:.0f}%)', flush=True)

# ===== 阶段2：紧池回马枪优化 =====
TIGHT = {'p_min':5,'p_max':8,'vr_min':0.8,'vr_max':1.5,'hsl_min':5,'hsl_max':8,'sz_max':80}

print(f'\n{"="*70}')
print(f'阶段2：紧池(涨5~8%量0.8~1.5换5~8%市值<80) + 回马枪')
print(f'{"="*70}', flush=True)

_, _, px_t = run_dual(TIGHT)
print(f'涨幅排序基准: {px_t[0]}天 达2.5%:{px_t[1]:.1f}%', flush=True)

for min_up in [5,6,7]:
    for rt_min, rt_max in [(1,4),(1,3),(2,4),(1,2),(2,3)]:
        for vol_max in [1.3, 1.5, 2.0]:
            ht_p = {'min_up':min_up, 'rt_min':rt_min, 'rt_max':rt_max, 'vol_max_ratio':vol_max}
            hy, ht, px = run_dual(TIGHT, ht_p)
            if ht[0] >= 8:
                hy_sig = '🔥' if hy[1] >= 65 else ('✅' if hy[1] >= 62 else '')
                ht_sig = '🔥' if ht[1] >= 75 else ('✅' if ht[1] >= 70 else '')
                print(f'{hy_sig} 双{hy[1]:.1f}% {hy[0]:>2}d | {ht_sig} 回马{ht[1]:.1f}% {ht[0]:>2}d | min>={min_up}% 回调{rt_min}~{rt_max}d 缩量x{vol_max}', flush=True)

# ===== 阶段3：回马枪单打模式（不混合） =====
print(f'\n{"="*70}')
print(f'阶段3：回马枪单独（不回退到涨幅排序）')
print(f'{"="*70}', flush=True)

print(f'{"池":<8} {"参数":<25} {"天数":<5} {"达2.5%":<8} {"达5%":<8} {"均涨幅%":<8}')
print('-'*65)

for pname, Pp in [('宽池',WIDE),('紧池',TIGHT)]:
    for ht_params in [
        {'min_up':5,'rt_min':1,'rt_max':4,'vol_max_ratio':1.3},
        {'min_up':5,'rt_min':2,'rt_max':4,'vol_max_ratio':1.3},
        {'min_up':5,'rt_min':1,'rt_max':3,'vol_max_ratio':1.3},
        {'min_up':5,'rt_min':1,'rt_max':2,'vol_max_ratio':1.3},
        {'min_up':6,'rt_min':2,'rt_max':4,'vol_max_ratio':1.3},
    ]:
        # 回马枪单独：有回马枪才出票
        nvs = []
        for dt in ad:
            pool = filter_stocks(dt, Pp)
            if not pool: continue
            htf = [s for s in pool if check_huitama(s['code'], dt, **ht_params)]
            if not htf: continue
            htf.sort(key=lambda x: -x['p'])
            nvs.append(htf[0]['nv'])
        
        if len(nvs) < 5: continue
        n = len(nvs)
        w25 = sum(1 for v in nvs if v>=2.5)*100/n
        w5 = sum(1 for v in nvs if v>=5)*100/n
        avg = statistics.mean(nvs)
        sig = '🔥' if w25 >= 75 else ('✅' if w25 >= 70 else '')
        ht_label = f'min>={ht_params["min_up"]}% 回调{ht_params["rt_min"]}~{ht_params["rt_max"]}d'
        print(f'{sig} {pname:<6} {ht_label:<25} {n:<5} {w25:<8.1f}% {w5:<8.1f}% {avg:<+8.2f}%', flush=True)

print(f'\n总耗时: {__import__("time").time()-t0:.1f}s', flush=True)
