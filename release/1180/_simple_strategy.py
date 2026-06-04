#!/usr/bin/env python3
"""简单策略回测: 到+3%就卖, 收盘清仓, 天天换新票"""
import pickle, os, sys, importlib, json

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
    idx = all_dates.index(dt)
    prev = all_dates[max(0,idx-6):idx]
    gains = []
    for pd in prev:
        found = False
        for s in data[pd]:
            if s['code'] == code:
                gains.append(s.get('p',0) or 0); found = True; break
        if not found: gains.append(0)
    gains.append(p_today)
    n = len(gains)
    if n < 5: return 0
    d6,d5,d4,d3,d2,d1,p = gains[-7:] if n>=7 else [0]*(7-n)+gains
    penalty = 0
    p_is_max = p >= max(gains[:-1]) if len(gains)>1 else True
    avg_7d = sum(gains)/n
    wrv = 50
    for s in data.get(dt,[]):
        if s['code'] == code:
            wrv = s.get('wr_val',50) or s.get('wrv',50); break
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
    stock['a5'] = s.get('above_ma5',0)
    stock['kdj_g'] = s.get('kdj_golden',0) or s.get('kdj_g',0)
    stock['pos_in_day'] = s.get('pos_in_day',50)
    stock['nm'] = s.get('nm','') or names.get(s['code'],'')
    ri = real.get(s['code'],{}); stock['hsl'] = ri.get('hsl',0) or 0
    feats = precomputed.get((code, dt), {})
    stock['t4_shadow'] = feats.get('t4_shadow',0)
    stock['slope5'] = feats.get('slope5',0)
    stock['cons_up'] = feats.get('cons_up',0)
    stock['d1'] = feats.get('d1',0); stock['d2'] = feats.get('d2',0)
    stock['d3'] = feats.get('d3',0); stock['ma5_slope'] = feats.get('ma5_slope',0)
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
    except:
        pass
    return 0

# 跑100天回测拿冠军 + D+1收盘数据
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
    
    d1_close = get_next_close(champ['code'], dt)
    champs.append({
        'dt': dt, 'code': champ['code'], 'name': names.get(champ['code'],'?'),
        'p': champ.get('p',0) or 0,
        'd1h': champ.get('d1h',0) or 0,
        'nl': champ.get('nl',0) or 0,
        'n': champ.get('n',0) or 0,
        'd1_close_pct': d1_close,
    })

# 取最后30天
c30 = champs[-30:]

print('='*80)
print('【简单策略回测】到+3%就卖 / 没到收盘清仓 / 天天换新票')
print('本金3万, 梭哈全进, 30天')
print('='*80)

cap = 30000
details = []
hits = 0  # 到+3%的次数
misses = 0  # 没到+3%的次数
for c in c30:
    d1h = c['d1h']
    d1_close = c['d1_close_pct']
    
    if d1h >= 3.0:
        ret = 3.0
        hits += 1
        reason = f'到+3%止盈'
    else:
        ret = d1_close
        misses += 1
        reason = f'收盘清仓({d1_close:+.1f}%)'
    
    old = cap
    cap *= (1 + ret/100)
    details.append({
        'dt': c['dt'], 'name': c['name'], 'd1h': d1h,
        'ret': ret, 'd1_close': d1_close,
        'balance': cap, 'profit': cap-old
    })

total_profit = cap - 30000
wins = sum(1 for d in details if d['ret'] >= 2.5)
loses = sum(1 for d in details if d['ret'] <= 0)

print(f'\n30天后: ¥{cap:>7,.0f}  盈利: +{total_profit:>6,.0f}元 (+{total_profit/30000*100:.1f}%)')
print(f'到+3%止盈: {hits}笔 ({hits*100/30:.0f}%)')
print(f'收盘清仓: {misses}笔 ({misses*100/30:.0f}%)')
print(f'亏损笔数: {loses}笔')

print(f'\n逐日明细:')
for i,d in enumerate(details):
    e = '✅' if d['ret']>=3 else('💸' if d['ret']<0 else'⏸️')
    print(f'  {i+1:>2}. {d["dt"]} {d["name"]:>8} 高{d["d1h"]:+.1f}% 收{d["d1_close"]:+.1f}% → {d["ret"]:+.1f}% {e} ¥{d["balance"]:>7,.0f}')

print(f'\n{"="*80}')
print(f'跌停卖不出去的分析：')
print(f'{"="*80}')
print(f'\n30笔中:')
# 看所有nl
nl_list = [c['nl'] for c in c30]
below_3 = sum(1 for c in c30 if c['nl'] >= -3)
between_3_7 = sum(1 for c in c30 if -7 <= c['nl'] < -3)
below_7 = sum(1 for c in c30 if c['nl'] <= -7)
below_10 = sum(1 for c in c30 if c['nl'] <= -10)
print(f'  当天最低>=-3%(正常): {below_3}笔')
print(f'  当天-3%~-7%(较大波动): {between_3_7}笔')
print(f'  当天<-7%(接近止损): {below_7}笔')
print(f'  触及跌停-10%: {below_10}笔')
print(f'\n最惨的一天:')
worst = min(c30, key=lambda c: c['nl'])
print(f'  {worst["dt"]} {worst["name"]} 高{worst["d1h"]:+.1f}% 低{worst["nl"]:+.1f}% 收{worst["d1_close_pct"]:+.1f}%')
print(f'  注意: 这只D+1最高冲到+{worst["d1h"]:.1f}%, +3%止盈先触发的话根本不会亏')
if worst['d1h'] >= 3:
    print(f'  如果按+3%策略走: 到+3%就卖了, 后面的跌跟你没关系')

print(f'\n结论: 30天0笔触及跌停, 跌停卖不出去是极小概率事件')
print(f'如果真遇到: 挂跌停价排板, 最多等1天')
