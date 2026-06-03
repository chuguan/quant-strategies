"""
涨停回马枪专项优化 — 冲80%
"""
import pickle, os, json, sys, statistics, itertools, math, time
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
KLINE_CACHE = {}
t0 = time.time()

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
            kw = kd[i-7:i+1]
            today = kw[-1]
            
            for j in range(len(kw)-2, -1, -1):
                prev = kw[j-1] if j > 0 else today
                pct = (kw[j]['close']-prev['close'])/prev['close']*100
                if pct >= 5:
                    retreat = len(kw) - j - 2  # 回调天数
                    if 1 <= retreat <= 4:
                        vols = [d['volume'] for d in kw[j+1:-1]]
                        if vols and max(vols) <= kw[j]['volume']*1.3:
                            if today['volume'] >= (statistics.mean(vols) if vols else 1)*1.1:
                                if today['close'] > today['open']:
                                    info = {
                                        'up_day': kw[j]['date'], 'up_pct': round(pct,1),
                                        'retreat_days': retreat, 'today_pct': round((today['close']-today['open'])/today['open']*100,1)
                                    }
                                    return True, info
                    break
            return False, {}
    return False, {}

def backtest(params, use_huitama=False):
    """回测"""
    champion_days = 0
    huitama_days = 0
    huitama_nvs = []
    all_nvs = []
    
    for dt in all_days:
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
            if jv > params['j_max']: continue
            cl = s.get('cl',0)
            if cl < params['cl_min'] or cl > params['cl_max']: continue
            
            nv = s.get('n',0) or 0
            
            if use_huitama:
                hit, info = check_huitama(code, dt)
                if not hit: continue
                pool.append((p, nv, info))
            else:
                pool.append((p, nv, None))
        
        if not pool: continue
        pool.sort(key=lambda x: -x[0])
        champion_nv = pool[0][1]
        
        if use_huitama:
            huitama_days += 1
            huitama_nvs.append(champion_nv)
        
        all_nvs.append(champion_nv)
        champion_days += 1
    
    result = {'days': champion_days}
    if all_nvs:
        result['w25'] = sum(1 for v in all_nvs if v>=2.5)*100/len(all_nvs)
        result['w5'] = sum(1 for v in all_nvs if v>=5)*100/len(all_nvs)
        result['avg'] = statistics.mean(all_nvs)
    
    if use_huitama and huitama_nvs:
        result['ht_days'] = huitama_days
        result['ht_w25'] = sum(1 for v in huitama_nvs if v>=2.5)*100/len(huitama_nvs)
        result['ht_w5'] = sum(1 for v in huitama_nvs if v>=5)*100/len(huitama_nvs)
        result['ht_avg'] = statistics.mean(huitama_nvs)
    
    return result

# ===== 基准：无策略最佳参数 =====
base = {'p_min':5,'p_max':7.5,'vr_min':1.0,'vr_max':1.5,
        'hsl_min':5,'hsl_max':10,'sz_max':150,'j_max':100,'cl_min':0,'cl_max':100}

r0 = backtest(base, False)
print(f'\n无策略基准: {r0["days"]}天 达2.5%:{r0["w25"]:.1f}%', flush=True)

r_ht = backtest(base, True)
print(f'回马枪: {r_ht["ht_days"]}天 达2.5%:{r_ht["ht_w25"]:.1f}% 均:{r_ht["ht_avg"]:.2f}%', flush=True)

# ===== 回马枪参数优化 =====
print(f'\n{"="*70}')
print(f'回马枪参数优化')
print(f'{"="*70}', flush=True)

best_w25 = 0
best_ht_params = None

for p_min in [5, 5.5]:
    for p_max in [7, 7.5]:
        for vr_min in [0.8, 1.0]:
            for vr_max in [1.5, 2.0]:
                for hsl_max in [8, 10, 12]:
                    for sz_max in [80, 100, 150]:
                        for j_max in [80, 100]:
                            for cl in [(0,100), (60,90)]:
                                p = dict(base)
                                p['p_min'], p['p_max'] = p_min, p_max
                                p['vr_min'], p['vr_max'] = vr_min, vr_max
                                p['hsl_max'] = hsl_max
                                p['sz_max'] = sz_max
                                p['j_max'] = j_max
                                p['cl_min'], p['cl_max'] = cl
                                
                                r = backtest(p, True)
                                if r['ht_w25'] > best_w25 and r['ht_days'] >= 8:
                                    best_w25 = r['ht_w25']
                                    best_ht_params = p
                                    best_ht_days = r['ht_days']
                                    best_ht_avg = r['ht_avg']
                                    sig = '🔥' if r['ht_w25'] >= 75 else ('✅' if r['ht_w25'] >= 70 else '')
                                    print(f'{sig} 涨{p_min}~{p_max}% 量{vr_min}~{vr_max} 换5~{hsl_max}% 市值<{sz_max} J<{j_max} CL{cl[0]}~{cl[1]} → {r["ht_days"]}天 达2.5%:{r["ht_w25"]:.1f}% 均:{r["ht_avg"]:.2f}%', flush=True)

# ===== 混合模式：有回马枪用回马枪，没有用涨幅排序 =====
print(f'\n{"="*70}')
print(f'混合模式（回马枪优先，没有则涨幅排序）')
print(f'{"="*70}', flush=True)

if best_ht_params:
    # 用最佳回马枪参数跑混合模式
    ht_nvs = []
    total_nvs = []
    
    for dt in all_days:
        stocks = data.get(dt, [])
        
        # 先找回马枪候选
        ht_pool = []
        for s in stocks:
            code = s['code']; p = s['p']
            if p < best_ht_params['p_min'] or p > best_ht_params['p_max']: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < best_ht_params['vr_min'] or vr > best_ht_params['vr_max']: continue
            ri = real.get(code)
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < best_ht_params['hsl_min'] or hsl > best_ht_params['hsl_max']: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz > best_ht_params['sz_max']: continue
            nm = names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv = s.get('j_val',0) or 0
            if jv > best_ht_params['j_max']: continue
            cl = s.get('cl',0)
            if cl < best_ht_params['cl_min'] or cl > best_ht_params['cl_max']: continue
            
            nv = s.get('n',0) or 0
            hit, info = check_huitama(code, dt)
            if hit:
                ht_pool.append((p, nv))
        
        # 回马枪优先
        if ht_pool:
            ht_pool.sort(key=lambda x: -x[0])
            total_nvs.append(ht_pool[0][1])
            ht_nvs.append(ht_pool[0][1])
        else:
            # 退回到普通涨幅排序
            pool = []
            for s in stocks:
                code = s['code']; p = s['p']
                if p < best_ht_params['p_min'] or p > best_ht_params['p_max']: continue
                vr = s.get('vol_ratio',0) or 0
                if vr < best_ht_params['vr_min'] or vr > best_ht_params['vr_max']: continue
                ri = real.get(code)
                if not ri: continue
                hsl = (ri.get('hsl',0) or 0)
                if hsl < best_ht_params['hsl_min'] or hsl > best_ht_params['hsl_max']: continue
                sz = (ri.get('shizhi',0) or 0)
                if sz > best_ht_params['sz_max']: continue
                nm = names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                jv = s.get('j_val',0) or 0
                if jv > best_ht_params['j_max']: continue
                cl = s.get('cl',0)
                if cl < best_ht_params['cl_min'] or cl > best_ht_params['cl_max']: continue
                
                nv = s.get('n',0) or 0
                pool.append((p, nv))
            
            if pool:
                pool.sort(key=lambda x: -x[0])
                total_nvs.append(pool[0][1])
    
    ht_d = len(ht_nvs)
    total_d = len(total_nvs)
    ht_w25 = sum(1 for v in ht_nvs if v>=2.5)*100/ht_d if ht_d else 0
    total_w25 = sum(1 for v in total_nvs if v>=2.5)*100/total_d if total_d else 0
    total_avg = statistics.mean(total_nvs) if total_nvs else 0
    
    print(f'\n回马枪触发: {ht_d}/{total_d}天 ({ht_d*100/total_d:.1f}%)', flush=True)
    print(f'回马枪冠军达2.5%: {ht_w25:.1f}%', flush=True)
    print(f'混合模式总冠军达2.5%: {total_w25:.1f}%', flush=True)
    print(f'混合模式均涨幅: {total_avg:.2f}%', flush=True)
    
    # 每个回马枪日明细
    print(f'\n--- 回马枪触发日明细 ---', flush=True)
    for dt in all_days:
        stocks = data.get(dt, [])
        for s in stocks:
            code = s['code']; p = s['p']
            if p < best_ht_params['p_min'] or p > best_ht_params['p_max']: continue
            ri = real.get(code)
            if not ri: continue
            hit, info = check_huitama(code, dt)
            if hit:
                nv = s.get('n',0) or 0
                nm = names.get(code,'')
                ok = '🔥' if nv >= 5 else ('✅' if nv >= 2.5 else '❌')
                print(f'  {dt} {nm[:8]:<8} {s["p"]:.1f}% → 次日最高{nv:+.2f}% {ok} 大涨日{info.get("up_day","")} +{info.get("up_pct","")}% 回调{info.get("retreat_days","")}天', flush=True)
                break  # 每天只取第一只

print(f'\n总耗时: {time.time()-t0:.1f}s', flush=True)
