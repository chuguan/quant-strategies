#!/usr/bin/env python3
"""补齐2.5%回望数据 + 全数据汇总"""
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

def v10_score_full(s, code, dt, mk_cn):
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
        for s in data[all_dates[idx+1]]:
            if s['code'] == code: return s.get('p', 0) or 0
    except: pass
    return 0

# 跑冠军
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
    scored = [(v10_score_full(s, s['code'], dt, mk_cn), s) for s in pool]
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

# 跑2.5% + 已有数据汇总
# 从之前跑过的结果提取(每次跑都一样,因为有固定数据)
# 只跑2.5%新的

print('=' * 80)
print('【回望回落全对比】收盘清仓 / 天天换新票 / 3万本金')
print('=' * 80)

# 从之前的输出已知的数据(不用重跑,结果固定)
known = {
    0.3: 123003, 0.5: 117554, 0.7: 112337,
    0.8: 109812, 1.0: 104516, 1.5: 93696,
    2.0: 83952, 3.0: 67292
}

# 只跑2.5%
cap = 30000
for c in c30:
    if c['d1h'] >= 3.0:
        ret = c['d1h'] - 2.5
    else:
        ret = c['d1_close_pct']
    cap *= (1 + ret/100)

trail_25 = round(cap)
known[2.5] = trail_25

# 汇总展示
print(f'\n{"回望回落":>8} {"30天后":>10} {"盈利":>10} {"%":>8} {"每笔均":>7}')
print('-' * 50)
for t in [0.3, 0.5, 0.7, 0.8, 1.0, 1.5, 2.0, 2.5, 3.0]:
    cap_val = known[t]
    profit = cap_val - 30000
    pct = profit / 30000 * 100
    avg = (cap_val/30000)**(1/30) - 1
    medal = '🥇' if t == 0.3 else ('🥈' if t == 0.5 else '')
    print(f'{medal} ↘{t:.1f}%  ¥{cap_val:>7,} +{profit:>6,} +{pct:>5.1f}% +{avg*100:.2f}%')

# 最优
print(f'\n🥇 最优(理论): 回望-0.3% → ¥123,003 (+310.0%)')
print(f'🥈 次优(实操): 回望-1.0% → ¥104,516 (+248.4%)')

# 绘制收益率曲线(简化)
print(f'\n{"="*80}')
print(f'推荐方案')
print(f'{"="*80}')
print(f'\n如果你能接受盘中可能被震:')
print(f'  回望-0.3% → 3万变12.3万 (+310%) ← 最赚')
print(f'\n如果你要稳健:')
print(f'  回望-0.8% → 3万变10.9万 (+266%) ← 平衡')
print(f'\n如果你怕震荡:')
print(f'  回望-1.5% → 3万变9.3万  (+212%) ← 稳')
print(f'\n如果你最保守:')
print(f'  回望-2.0% → 3万变8.3万  (+180%)')
