"""
策略+参数联合搜索（修正版）
每个策略取自己的冠军（不是总体冠军）
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

def get_kline_window(code, dt, n=20):
    kd = get_kline(code)
    if kd is None: return None
    for i, d in enumerate(kd):
        if d['date'] == dt:
            if i < n: return None
            return kd[i-n+1:i+1]
    return None

# ===== 策略函数（输入：20天K线窗口，返回True/False）=====
STRATEGIES = {}

def s_n_break(kw):
    """N字突破"""
    if len(kw) < 10: return False
    today, p10d = kw[-1], kw[-10:-1]
    highs = [d['high'] for d in p10d]
    mx = max(highs); mxi = highs.index(mx)
    if 3 <= mxi <= 7:
        aft = p10d[mxi:]
        pb = (mx - min(d['low'] for d in aft)) / mx * 100
        if 1 <= pb <= 8 and today['close'] >= mx * 0.98:
            return True
    return False
STRATEGIES['N字突破'] = s_n_break

def s_limit_pullback(kw):
    """涨停回马枪"""
    if len(kw) < 8: return False
    p6d = kw[-7:-1]; today = kw[-1]
    for i in range(len(p6d)-1, -1, -1):
        prev = kw[-8+i]
        pct = (p6d[i]['close']-prev['close'])/prev['close']*100
        if pct >= 6:
            retreat = len(p6d) - i - 1
            if 1 <= retreat <= 4:
                vols = [d['volume'] for d in p6d[i+1:]]
                if vols and max(vols) <= p6d[i]['volume'] * 1.2:
                    if today['volume'] >= statistics.mean(vols)*1.2 and today['close'] > today['open']:
                        return True
            break
    return False
STRATEGIES['涨停回马枪'] = s_limit_pullback

def s_ma_stick(kw):
    """均线粘合突破"""
    if len(kw) < 20: return False
    ma5 = statistics.mean([kw[-5+i]['close'] for i in range(-5,0)])
    ma10 = statistics.mean([kw[-10+i]['close'] for i in range(-10,0)])
    ma20 = statistics.mean([d['close'] for d in kw])
    spread = max(ma5,ma10,ma20)/min(ma5,ma10,ma20)-1
    if spread*100 < 3 and kw[-1]['close'] > max(ma5,ma10,ma20):
        return True
    return False
STRATEGIES['均线粘合'] = s_ma_stick

def s_consecutive_up(kw):
    """连续阳线"""
    cnt = 0
    for d in kw[-8:-1]:
        if d['close'] > d['open']: cnt += 1
        else: cnt = 0
    if 3 <= cnt <= 7 and kw[-1]['close'] > kw[-2]['close']:
        return True
    return False
STRATEGIES['连续阳线'] = s_consecutive_up

def s_double_vol(kw):
    """倍量突破"""
    if len(kw) < 3: return False
    today, prev = kw[-1], kw[-3]
    if prev['volume'] > 0 and today['volume'] >= prev['volume']*2:
        pct = (today['close']-kw[-2]['close'])/kw[-2]['close']*100
        if pct > 0: return True
    return False
STRATEGIES['倍量突破'] = s_double_vol

def s_shrink_up(kw):
    """缩量大涨"""
    if len(kw) < 6: return False
    today = kw[-1]
    avg_vol = statistics.mean([kw[-6+i]['volume'] for i in range(0,5)]) if len(kw)>=6 else 1
    pct = (today['close']-kw[-2]['close'])/kw[-2]['close']*100
    if pct >= 6 and today['volume'] < avg_vol * 0.8:
        return True
    return False
STRATEGIES['缩量大涨'] = s_shrink_up

# ===== 基础过滤（最佳参数范围搜索）=====
def backtest_with_strategies(params, use_strats=None):
    """
    返回每个策略各自的冠军达2.5%
    use_strats=None: 不加策略条件，只按涨幅排序
    use_strats=['N字突破']: 只看符合该策略的票
    """
    strat_results = defaultdict(list)  # strategy -> [nv1, nv2, ...]
    
    for dt in all_days:
        stocks = data.get(dt, [])
        
        # 按策略分组收集通过基础过滤的股票
        strategy_pool = defaultdict(list)
        
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
            
            if use_strats is not None:
                # 检查策略条件
                kw = get_kline_window(code, dt, 20)
                if kw is None: continue
                for sname in use_strats:
                    if STRATEGIES[sname](kw):
                        strategy_pool[sname].append((p, nv))
            else:
                strategy_pool['无策略'].append((p, nv))
        
        # 每策略取涨幅最高的冠军
        for sname, pool in strategy_pool.items():
            if pool:
                pool.sort(key=lambda x: -x[0])
                strat_results[sname].append(pool[0][1])
    
    result = {}
    for sname, nvs in strat_results.items():
        n = len(nvs)
        w25 = sum(1 for v in nvs if v >= 2.5)
        w5 = sum(1 for v in nvs if v >= 5)
        result[sname] = {
            'days': n, 'w25': w25*100/n, 'w5': w5*100/n,
            'avg': statistics.mean(nvs), 'nvs': nvs
        }
    return result

# ===== 测试：基准参数 + 各策略 =====
base_params = {'p_min':5.0,'p_max':7.5,'vr_min':1.0,'vr_max':1.5,
               'hsl_min':5,'hsl_max':12,'sz_max':100,'j_max':100,'cl_min':0,'cl_max':100}

print(f'\n{"="*70}')
print(f'基准参数 + 各策略冠军')
print(f'{"="*70}', flush=True)

# 无策略基准
r_base = backtest_with_strategies(base_params, None)
br = r_base['无策略']
print(f'无策略基准: {br["days"]}天 达2.5%:{br["w25"]:.1f}% 均:{br["avg"]:.2f}%', flush=True)

# 各策略
for sname in STRATEGIES:
    r = backtest_with_strategies(base_params, [sname])
    for sn, sr in r.items():
        diff = sr['w25'] - br['w25']
        sig = '🔥' if diff > 5 else ('✅' if diff > 0 else '❌')
        print(f'{sig} {sname:<12} {sr["days"]:<4}天 达2.5%:{sr["w25"]:<5.1f}% ({diff:+>+5.1f}%) 均:{sr["avg"]:.2f}%', flush=True)

# ===== 联合策略 =====
print(f'\n--- 联合策略 ---', flush=True)
for combo_size in [2, 3]:
    for combo in itertools.combinations(list(STRATEGIES.keys()), combo_size):
        r = backtest_with_strategies(base_params, list(combo))
        for sn, sr in r.items():
            if sr['days'] >= 10:
                diff = sr['w25'] - br['w25']
                if diff > 0:
                    print(f'✅ {"+".join(combo):<25} {sr["days"]:<4}天 达2.5%:{sr["w25"]:.1f}% (+{diff:.1f}%)', flush=True)

# ===== 参数+策略联合搜索（仅最佳策略）=====
print(f'\n{"="*70}')
print(f'参数+策略联合搜索')
print(f'{"="*70}', flush=True)

best_strat_name = None
best_strat_w25 = 0
for sname, sr in r_base.items():
    pass

# 只对最佳策略做参数搜索
# 先确定哪个策略最好
strat_rank = []
for sname in STRATEGIES:
    r = backtest_with_strategies(base_params, [sname])
    for sn, sr in r.items():
        strat_rank.append((sr['w25'], sr['days'], sname))
strat_rank.sort(key=lambda x: -x[0])

best_sname = strat_rank[0][2]
print(f'最佳策略: {best_sname} ({strat_rank[0][0]:.1f}%)', flush=True)

# 精细参数搜索 + 最佳策略
p_tests = [(5,7),(5,7.5),(5,8),(5.5,7.5),(6,7.5)]
vr_tests = [(1,1.5),(0.8,1.5),(1,2)]
hs_tests = [(5,10),(5,12),(5,15)]
sz_tests = [80, 100, 150]
cl_tests = [(0,100),(60,90),(60,85)]

print(f'\n参数搜索 + {best_sname}策略:', flush=True)
print(f'{"涨%":<12} {"量比":<12} {"换手":<12} {"市值":<8} {"CL":<10} {"天数":<6} {"达2.5%":<10}', flush=True)

best_w25 = 0
best_params = None

for pm in p_tests:
    for vm in vr_tests:
        for hm in hs_tests:
            for sz in sz_tests:
                for cl in cl_tests:
                    p = dict(base_params)
                    p['p_min'], p['p_max'] = pm
                    p['vr_min'], p['vr_max'] = vm
                    p['hsl_min'], p['hsl_max'] = hm
                    p['sz_max'] = sz
                    p['cl_min'], p['cl_max'] = cl
                    
                    r = backtest_with_strategies(p, [best_sname])
                    for sn, sr in r.items():
                        if sr['days'] >= 15 and sr['w25'] > best_w25:
                            best_w25 = sr['w25']
                            best_params = p
                            best_days = sr['days']
                            print(f'🏆 {pm[0]}~{pm[1]}%  {vm[0]}~{vm[1]}  {hm[0]}~{hm[1]}%  <{sz}  {cl[0]}~{cl[1]}  {sr["days"]:<6} {sr["w25"]:<10.1f}%', flush=True)

if best_params:
    # 用最佳参数再跑所有策略验证
    print(f'\n--- 最优参数验证 ---', flush=True)
    print(f'参数: 涨{best_params["p_min"]}~{best_params["p_max"]}% 量{best_params["vr_min"]}~{best_params["vr_max"]} 换{best_params["hsl_min"]}~{best_params["hsl_max"]}% 市值<{best_params["sz_max"]} CL{best_params["cl_min"]}~{best_params["cl_max"]}', flush=True)
    
    for sname in list(STRATEGIES.keys()) + [None]:
        if sname is None:
            r = backtest_with_strategies(best_params, None)
            label = '无策略'
        else:
            r = backtest_with_strategies(best_params, [sname])
            label = sname
        for sn, sr in r.items():
            sig = '🔥' if sr['w25'] >= 70 else ('✅' if sr['w25'] >= best_w25-3 else '')
            print(f'{sig} {label:<12} {sr["days"]:<4}天 达2.5%:{sr["w25"]:.1f}% 均:{sr["avg"]:.2f}%', flush=True)

print(f'\n总耗时: {time.time()-t0:.1f}s', flush=True)
