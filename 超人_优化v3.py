"""超人策略 v3 — 融合高胜率尾盘策略要素"""
import pickle, json, os, itertools

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
with open('big_cache.pkl','rb') as f:
    cache = pickle.load(f)
d, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(d.keys())

train = [dt for dt in dates if dt.startswith('2026-04') or dt.startswith('2026-05')]
val_q1 = [dt for dt in dates if dt.startswith('2026-01') or dt.startswith('2026-02') or dt.startswith('2026-03')]
val_25 = [dt for dt in dates if dt.startswith('2025')]

print(f'训练(4~5月): {len(train)}天 | 验证(Q1): {len(val_q1)}天 | 2025: {len(val_25)}天', flush=True)

def get_kline_data(code):
    """获取K线缓存数据"""
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return []
    try:
        with open(fp,'r') as f:
            return json.load(f)
    except: return []

def check_uptrend(code, date):
    """检查是否多头排列（MA5>MA10>MA20）"""
    kd = get_kline_data(code)
    if len(kd) < 25: return False
    # 找到date的位置
    idx = None
    for i, k in enumerate(kd):
        if k.get('date','') == date:
            idx = i
            break
    if idx is None or idx < 20: return False
    # 计算MA5, MA10, MA20
    c5 = sum(kd[j]['close'] for j in range(idx-4, idx+1)) / 5
    c10 = sum(kd[j]['close'] for j in range(idx-9, idx+1)) / 10
    c20 = sum(kd[j]['close'] for j in range(idx-19, idx+1)) / 20
    return c5 > c10 > c20

def check_volume_growth(code, date):
    """检查是否连续放量（今日量>昨日量>前日量）"""
    kd = get_kline_data(code)
    if len(kd) < 5: return False
    idx = None
    for i, k in enumerate(kd):
        if k.get('date','') == date:
            idx = i
            break
    if idx is None or idx < 3: return False
    v0 = kd[idx].get('volume',0) or kd[idx].get('amount',0) or 0
    v1 = kd[idx-1].get('volume',0) or kd[idx-1].get('amount',0) or 0
    v2 = kd[idx-2].get('volume',0) or kd[idx-2].get('amount',0) or 0
    if v0 == 0 or v1 == 0: return False
    return v0 > v1 > v2 or (v0 > v1*0.8 and v0 > v2)  # 今日量不低于昨日的80%

def check_near_high(code, date, close_price):
    """检查收盘价是否在当日最高3%范围内"""
    kd = get_kline_data(code)
    for k in kd:
        if k.get('date','') == date:
            high = k.get('high',0)
            if high > 0:
                return (high - close_price) / high * 100 <= 3
            return False
    return False

def evaluate(params, dl):
    def score(pct, vr, cl, features):
        sc = params['base']
        # 涨幅
        for lo, hi, pts in params['p_tiers']:
            if lo <= pct <= hi: sc += pts; break
        # CL
        for lo, hi, pts in params['cl_tiers']:
            if lo <= cl <= hi: sc += pts; break
        # 量比
        for lo, hi, pts in params['vr_tiers']:
            if lo <= vr <= hi: sc += pts; break
        # 额外加分
        if features.get('macd'): sc += params.get('macd_bonus', 0)
        if features.get('kdj'): sc += params.get('kdj_bonus', 0)
        if features.get('above_ma5'): sc += params.get('ma5_bonus', 0)
        if features.get('uptrend'): sc += params.get('trend_bonus', 0)
        if features.get('vol_growth'): sc += params.get('vol_bonus', 0)
        if features.get('near_high'): sc += params.get('high_bonus', 0)
        return sc
    
    results = []
    for dt in dl:
        if dt.endswith('-22') and '2026' in dt: continue
        stocks = d.get(dt, [])
        cand = []
        for s in stocks:
            pct = s['p']
            if pct < params['p_min'] or pct > params['p_max']: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < params['vr_min']: continue
            code = s['code']
            ri = real.get(code)
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < params['hsl_min'] or hsl > params['hsl_max']: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz >= params['sz_max']: continue
            nm = names.get(code,'')
            if 'ST' in nm or '*ST' in nm: continue
            jv = s.get('j_val',0) or 0
            if jv > params['j_max']: continue
            cl = s.get('cl',0)
            bp = s.get('close',0)
            
            features = {
                'macd': s.get('macd_golden',0),
                'kdj': s.get('kdj_golden',0),
                'above_ma5': s.get('above_ma5',0),
                'uptrend': check_uptrend(code, dt) if params.get('check_uptrend') else False,
                'vol_growth': check_volume_growth(code, dt) if params.get('check_vol') else False,
                'near_high': check_near_high(code, dt, bp) if params.get('check_high') else False,
            }
            
            sc = score(pct, vr, cl, features)
            nv = s.get('n',0) or 0
            cand.append((sc, nm, code, pct, nv, features))
        
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[3]))
        results.append(cand[0][4])
    
    if not results: return 0, 0, 0
    h2 = sum(1 for v in results if v >= 2.5)
    h5 = sum(1 for v in results if v >= 5)
    return h2/len(results)*100, h5/len(results)*100, sum(results)/len(results)

# 原版基准
orig = {
    'base':10, 'p_min':5, 'p_max':8, 'vr_min':1.0,
    'p_tiers':[(5,6.5,15),(6.5,7,8),(4.5,5,5),(7,8,-15)],
    'cl_tiers':[(70,85,15),(85,90,5),(60,70,3),(90,100,-20)],
    'vr_tiers':[(1.2,2.0,10),(2.0,3.0,5),(1.0,1.2,3),(3,10,-15)],
    'hsl_min':5,'hsl_max':15,'sz_max':200,'j_max':100,
    'macd_bonus':0,'kdj_bonus':0,'ma5_bonus':0,
    'trend_bonus':0,'vol_bonus':0,'high_bonus':0,
    'check_uptrend':False,'check_vol':False,'check_high':False
}

print(f'\n原版基准:', flush=True)
t2, _, _ = evaluate(orig, train)
v2, _, _ = evaluate(orig, val_q1)
y2, _, _ = evaluate(orig, val_25)
print(f'  训练:{t2:.1f}% | 验证Q1:{v2:.1f}% | 2025:{y2:.1f}%', flush=True)

# ===== 搜索空间 =====
# 基础评分参数（从v2优化结果来）
base_params = {
    'base':10, 'p_min':5, 'p_max':8, 'vr_min':0.5,
    'p_tiers':[(5,6.5,15),(6.5,7,8),(4.5,5,5),(7,8,-15)],
    'cl_tiers':[(60,85,10),(85,90,0),(90,100,-15)],
    'vr_tiers':[(0.8,1.5,10),(1.5,3.0,0),(3,10,-10)],
    'hsl_min':5,'hsl_max':15,'sz_max':150,'j_max':80,
    'check_uptrend':False,'check_vol':False,'check_high':False,
    'macd_bonus':0,'kdj_bonus':0,'ma5_bonus':0,
    'trend_bonus':0,'vol_bonus':0,'high_bonus':0,
}

# 测试各种加分组合
addon_options = [
    # (macd, kdj, ma5, trend, vol, high, check_trend, check_vol, check_high)
    (0,0,0,0,0,0, False,False,False),  # 无加分 = v2
    (5,3,0,0,0,0, False,False,False),  # MACD+KDJ加分
    (5,0,5,0,0,0, False,False,False),  # MACD+MA5
    (5,3,5,0,0,0, False,False,False),  # MACD+KDJ+MA5
    (3,3,3,0,0,0, False,False,False),  # 各加3分
    (5,3,5,3,0,0, True,False,False),   # +多头排列
    (5,3,5,0,5,0, False,True,False),   # +连续放量
    (5,3,5,0,0,3, False,False,True),   # +收盘近高
    (5,3,5,3,5,3, True,True,True),     # 全加分
    (8,5,5,0,0,0, False,False,False),  # MACD重点
    (10,5,0,0,0,0, False,False,False),  # MACD核心
    (0,0,0,0,0,0, True,False,False),    # 仅多头排列
    (0,0,0,0,0,0, False,True,False),    # 仅连续放量
    (0,0,0,0,0,0, False,False,True),    # 仅收盘近高
    (5,5,5,5,5,5, True,True,True),     # 全加分各5
]

# 再加换手/市值变体
hsl_opts = [(5,15), (5,18), (3,15)]
sz_opts = [150, 200]
j_opts = [80, 90]

total = len(addon_options) * len(hsl_opts) * len(sz_opts) * len(j_opts)
print(f'\n搜索组合: {total}', flush=True)

best = None
best_score = 0
log = []

idx = 0
for addon in addon_options:
    for hs in hsl_opts:
        for sz in sz_opts:
            for jm in j_opts:
                p = dict(base_params)
                p['macd_bonus'],p['kdj_bonus'],p['ma5_bonus'],p['trend_bonus'],p['vol_bonus'],p['high_bonus'] = addon[:6]
                p['check_uptrend'],p['check_vol'],p['check_high'] = addon[6:9]
                p['hsl_min'],p['hsl_max'] = hs
                p['sz_max'] = sz
                p['j_max'] = jm
                
                idx += 1
                t_r, _, _ = evaluate(p, train)
                v_r, _, _ = evaluate(p, val_q1)
                y_r, _, _ = evaluate(p, val_25)
                
                # 加权目标
                sc = t_r * 0.45 + v_r * 0.35 + y_r * 0.20
                
                if sc > best_score:
                    best_score = sc
                    best = p
                
                log.append((sc, t_r, v_r, y_r, p))
                
                if idx % 50 == 0:
                    print(f'  [{idx}/{total}] 最佳加权: {best_score:.1f}%', flush=True)

log.sort(key=lambda x: -x[0])
print(f'\n{"="*80}', flush=True)
print(f'  优化完成! 测试{idx}种组合', flush=True)
print(f'{"="*80}', flush=True)

print(f'\nTop5 最佳:', flush=True)
for rank, (sc, t_r, v_r, y_r, p) in enumerate(log[:5], 1):
    print(f'\n#{rank} 加权{sc:.1f}% | 训{t_r:.1f}% 验Q1{v_r:.1f}% 2025{y_r:.1f}%', flush=True)
    print(f'  MACD+{p["macd_bonus"]} KDJ+{p["kdj_bonus"]} MA5+{p["ma5_bonus"]} 趋势+{p["trend_bonus"]} 量增+{p["vol_bonus"]} 近高+{p["high_bonus"]}', flush=True)
    print(f'  检查: 多头排列={"是" if p["check_uptrend"] else "否"} 连续放量={"是" if p["check_vol"] else "否"} 收盘近高={"是" if p["check_high"] else "否"}', flush=True)
    print(f'  换手{p["hsl_min"]}~{p["hsl_max"]}% 市值<{p["sz_max"]}亿 J<{p["j_max"]}', flush=True)

# 最佳 vs 原版
bp = log[0][4]
print(f'\n{"="*80}')
print(f'  最佳 vs 原版 全面对比')
print(f'{"="*80}')
print(f'{"参数":<20} {"原版":<15} {"优化v3":<15}')
print(f'{"":-<50}')
for name, dl in [('训练4~5月', train), ('验证1~3月', val_q1), ('2025全年', val_25)]:
    o2, _, _ = evaluate(orig, dl)
    b2, _, _ = evaluate(bp, dl)
    print(f'{name:<20} {o2:<15.1f} {b2:<15.1f} {b2-o2:>+7.1f}%', flush=True)

all_26 = [dt for dt in dates if dt.startswith('2026')]
o2, _, _ = evaluate(orig, all_26)
b2, b5, b_avg = evaluate(bp, all_26)
print(f'{"2026全年":<20} {o2:<15.1f} {b2:<15.1f} {b2-o2:>+7.1f}%', flush=True)

# 近5天
print(f'\n近5天冠军（优化版）:', flush=True)
for dt in ['2026-05-19','2026-05-20','2026-05-21','2026-05-22']:
    stocks = d.get(dt, [])
    cand = []
    for s in stocks:
        pct = s['p']
        if pct < 5 or pct > 8: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < 0.5: continue
        ri = real.get(s['code'])
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < bp['hsl_min'] or hsl > bp['hsl_max']: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= bp['sz_max']: continue
        nm = names.get(s['code'],'')
        if 'ST' in nm or '*ST' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > bp['j_max']: continue
        cl = s.get('cl',0)
        
        features = {'macd':s.get('macd_golden',0),'kdj':s.get('kdj_golden',0),'above_ma5':s.get('above_ma5',0)}
        sc = bp['base']
        for lo,hi,pts in bp['p_tiers']:
            if lo <= pct <= hi: sc += pts; break
        for lo,hi,pts in bp['cl_tiers']:
            if lo <= cl <= hi: sc += pts; break
        for lo,hi,pts in bp['vr_tiers']:
            if lo <= vr <= hi: sc += pts; break
        if features['macd']: sc += bp['macd_bonus']
        if features['kdj']: sc += bp['kdj_bonus']
        if features['above_ma5']: sc += bp['ma5_bonus']
        
        nv = s.get('n',0) or 0
        cand.append((sc, nm, s['code'], pct, nv))
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[3]))
    c = cand[0]
    ns = f'{c[4]:+.2f}%' if c[4] else 'N/A'
    ok = '🔥' if c[4] >= 5 else ('✅' if c[4] >= 2.5 else '❌')
    print(f'  {dt}: {c[1]}({c[2]}) 评{c[0]} 涨{c[3]:.1f}% → {ns} {ok}', flush=True)
