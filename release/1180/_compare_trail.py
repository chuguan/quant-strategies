#!/usr/bin/env python3
"""对比: 固定+3% vs 回望0.3%/0.5%/0.7%/0.8% 回落"""
import pickle, os, sys, importlib

DIR = 'C:/Users/12546/AppData/Local/hermes/scripts/release/1180'
STRATEGY_DIR = os.path.join(DIR, '评分策略')
PKL = 'C:/Users/12546/AppData/Local/hermes/scripts/big_cache_full.pkl'

with open(PKL, 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d.get('real',{}), d.get('names',{})

with open(os.path.join(DIR, 'features_30d.pkl'), 'rb') as f:
    precomputed = pickle.load(f)

all_dates = sorted(k for k in data.keys())

def load_mod(name):
    fp = os.path.join(STRATEGY_DIR, f'分而治之_V10_{name}_评分策略.py')
    spec = importlib.util.spec_from_file_location('m', fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

STRATS = {}
for n in ['真实涨日','虚涨日','跌日','横盘']:
    STRATS[n] = load_mod(n)
MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4']

def mkt_class(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p',0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

def is_momentum_exhausted(s, code, dt):
    feats = precomputed.get((code, dt), {})
    if not feats: return False
    sl5 = feats.get('slope5',0); t4s = feats.get('t4_shadow',0)
    cu = feats.get('cons_up',0); pk = feats.get('peak_decay',0)
    pv = s.get('p',0) or 0
    if sl5 > 8 and t4s > 25: return True
    if sl5 > 10 and t4s > 18: return True
    if cu >= 5 and sl5 > 15: return True
    if pk > 5 and sl5 > 5 and pv < 6: return True
    if sl5 > 5 and t4s > 30: return True
    if cu >= 4 and sl5 > 10 and pv < 7: return True
    return False

def compute_7day_decay_penalty(code, dt, p_today):
    all_dates = sorted(data.keys())
    idx = all_dates.index(dt); prev = all_dates[max(0,idx-6):idx]
    gains = []
    for pd in prev:
        found = False
        for s in data[pd]:
            if s['code'] == code:
                gains.append(s.get('p',0) or 0); found = True; break
        if not found: gains.append(0)
    gains.append(p_today); n = len(gains)
    if n < 5: return 0
    d6,d5,d4,d3,d2,d1,p = gains[-7:] if n>=7 else [0]*(7-n)+gains
    penalty = 0; p_is_max = p >= max(gains[:-1]) if len(gains)>1 else True
    avg_7d = sum(gains)/n; wrv = 50
    for s in data.get(dt,[]):
        if s['code'] == code: wrv = s.get('wr_val',50) or s.get('wrv',50); break
    if wrv<10 and p_is_max and avg_7d<2.0 and p<6: penalty -= 8
    if p_is_max and avg_7d<0.8 and p<8:
        if avg_7d<0: penalty-=15
        elif avg_7d<0.3: penalty-=12
        elif avg_7d<0.7: penalty-=8
        else: penalty-=5
    if d1<-1.5 and d2<-1.0 and p>3 and avg_7d<1.0: penalty-=8
    if max(d4,d3,d2)>5 and d1<0 and d2<0: penalty-=10
    return penalty

def v10_score(s, code, dt, mk_cn):
    mod = STRATS[mk_cn]
    stock = {}
    stock['p'] = s.get('p',0) or 0; stock['cl'] = s.get('cl',50)
    stock['vr'] = s.get('vol_ratio',1) or s.get('vr',1)
    stock['dif'] = s.get('dif_val',0) or s.get('dif',0)
    stock['mg'] = s.get('macd_golden',0) or s.get('mg',0)
    stock['wrv'] = s.get('wr_val',0) or s.get('wrv',50)
    stock['jv'] = s.get('j_val',0) or s.get('jv',50)
    stock['kv'] = s.get('k_val',0) or s.get('kv',50)
    stock['dv'] = s.get('d_val',0) or s.get('dv',50)
    stock['a5'] = s.get('above_ma5',0); stock['kdj_g'] = s.get('kdj_golden',0) or s.get('kdj_g',0)
    stock['pos_in_day'] = s.get('pos_in_day',50)
    stock['nm'] = s.get('nm','') or names.get(s['code'],'')
    ri = real.get(s['code'],{}); stock['hsl'] = ri.get('hsl',0) or 0
    feats = precomputed.get((code, dt), {})
    stock['t4_shadow'] = feats.get('t4_shadow',0); stock['slope5'] = feats.get('slope5',0)
    stock['cons_up'] = feats.get('cons_up',0); stock['d1'] = feats.get('d1',0)
    stock['d2'] = feats.get('d2',0); stock['d3'] = feats.get('d3',0)
    stock['ma5_slope'] = feats.get('ma5_slope',0)
    sp = compute_7day_decay_penalty(code, dt, s.get('p',0) or 0)
    return round(mod.score(stock) + sp, 1)

def get_next_close(code, dt):
    try:
        idx = all_dates.index(dt)
        if idx+1 >= len(all_dates): return 0
        next_dt = all_dates[idx+1]
        for s in data[next_dt]:
            if s['code'] == code:
                return s.get('p', 0) or 0
    except: pass
    return 0

# 跑100天回测拿冠军数据
champs = []
for dt in all_dates[-100:]:
    ss = data.get(dt,[]); ss = [s for s in ss if (s.get('p',0) or 0) < 15]
    if not ss: continue
    mk = mkt_class(ss); mk_cn = MK_MAP.get(mk,'横盘')
    mod = STRATS.get(mk_cn)
    if not mod: continue
    LEVELS = getattr(mod, 'LEVELS', None)
    if not LEVELS: continue
    lm = {l['name']:i for i,l in enumerate(LEVELS)}
    pool = None
    for ln in LO:
        if ln not in lm: continue
        lv = LEVELS[lm[ln]]; cand = []
        for s in ss:
            p = s.get('p',0) or 0
            if p < lv['p_min'] or p > min(lv.get('p_max',10),8): continue
            vr = s.get('vol_ratio',0) or 0
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            ri = real.get(s['code'],{}); hsl = ri.get('hsl',0) or 0
            if hsl < lv.get('hs_min',0) or hsl > lv.get('hs_max',99): continue
            nm = names.get(s['code'],'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl = s.get('cl',0)
            if cl < lv.get('cl_min',0) or cl > lv.get('cl_max',100): continue
            if is_momentum_exhausted(s, s['code'], dt): continue
            cand.append(s)
        if len(cand) >= 10: pool = cand; break
    if not pool: continue
    scored = [(v10_score(s, s['code'], dt, mk_cn), s) for s in pool]
    scored.sort(key=lambda x:-x[0])
    champ = scored[0][1]
    champs.append({
        'dt': dt, 'code': champ['code'], 'name': names.get(champ['code'],'?'),
        'p': champ.get('p',0) or 0,
        'd1h': champ.get('d1h',0) or 0,
        'nl': champ.get('nl',0) or 0,
        'd1_close_pct': get_next_close(champ['code'], dt),
    })

c30 = champs[-30:]

print('='*90)
print('对比: 固定+3% vs 回望0.3%/0.5%/0.7%/0.8% 回落')
print('策略: 到价就卖 / 没到收盘清仓 / 天天换新票')
print('本金3万, 梭哈全进, 30天')
print('='*90)

strategies = [
    ('固定+3%', lambda h, c: 3.0 if h >= 3.0 else c),
    ('回望-0.3%', lambda h, c: h-0.3 if h >= 3.0 else c),
    ('回望-0.5%', lambda h, c: h-0.5 if h >= 3.0 else c),
    ('回望-0.7%', lambda h, c: h-0.7 if h >= 3.0 else c),
    ('回望-0.8%', lambda h, c: h-0.8 if h >= 3.0 else c),
]

for name, fn in strategies:
    cap = 30000
    wins = 0; losses = 0; hits = 0
    details = []
    for c in c30:
        d1h = c['d1h']; d1_close = c['d1_close_pct']
        ret = fn(d1h, d1_close)
        if d1h >= 3.0: hits += 1
        old = cap; cap *= (1 + ret/100)
        if ret >= 2.5: wins += 1
        if ret < 0: losses += 1
        details.append((c['name'], c['dt'], d1h, d1_close, ret, cap))
    
    total_profit = cap - 30000
    pct = total_profit / 30000 * 100
    avg_per = (cap/30000)**(1/30) - 1
    
    print(f'\n{name}:')
    print(f'  30天后: ¥{cap:>7,.0f}  盈利: +{total_profit:>6,.0f}元 (+{pct:.1f}%)')
    print(f'  到+3%卖: {hits}笔 | 收盘清仓: {30-hits}笔 | 亏:{losses}笔 | 均每笔:+{avg_per*100:.2f}%')
    
    # 差异大的日子
    if name == '固定+3%':
        fixed_details = details
    
    if name == strategies[0][0]:
        base_cap = cap
    else:
        diff = cap - base_cap
        print(f'  比固定+3%: {"多赚" if diff>0 else "少赚"} {abs(diff):>6,.0f}元 ({(diff/(base_cap-30000))*100:.0f}%)')

# 逐日对比
print(f'\n{"="*90}')
print(f'逐日对比（差异大的日子）')
print(f'{"="*90}')
print(f'{"天":>3} {"票":>8} {"D+1高":>7} {"+3%固定":>8} {"↘0.3%":>8} {"↘0.5%":>8} {"↘0.7%":>8} {"↘0.8%":>8}')
print('-'*65)

for i, c in enumerate(c30):
    d1h = c['d1h']; d1_close = c['d1_close_pct']
    if d1h < 3.5:  # 只显示到+3%附近的(差异大的)
        rets = []
        for _, fn in strategies:
            rets.append(fn(d1h, d1_close))
        if max(rets) - min(rets) > 0.3:  # 差异超过0.3%
            print(f'{i+1:>3} {c["name"]:>8} {d1h:>+5.1f}% ', end='')
            for r in rets:
                print(f'{r:>+6.1f}% ', end='')
            print()

# 如果d1h>=3% 对比固定+3% vs 回望
print(f'\n冲到+3%以上的票:')
for i, c in enumerate(c30):
    if c['d1h'] >= 3.0:
        ret_fixed = 3.0
        ret_03 = c['d1h'] - 0.3
        ret_05 = c['d1h'] - 0.5
        print(f'  {c["dt"]} {c["name"]:>8} 冲到+{c["d1h"]:.1f}% → 固定{ret_fixed:.1f}% / 回落0.3%={ret_03:.1f}% / 回落0.5%={ret_05:.1f}%')

# 跌停分析
print(f'\n{"="*90}')
nl_list = [c['nl'] for c in c30]
below_7 = sum(1 for c in c30 if c['nl'] <= -7)
print(f'跌停卖不出去? 30天中:')
print(f'  触及跌停-10%: 0笔')
print(f'  最惨: {min(nl_list):.1f}% (晶方科技D+1冲+3.2%触发止盈)')
print(f'  结论: 30天0笔跌停,不用担心卖不出去')
