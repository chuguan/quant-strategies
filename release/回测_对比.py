#!/usr/bin/env python3
"""
1180 vs 1190 统一回测对比 — 30/50/100天窗口
用法: python 回测_对比.py <版本目录>
"""
import pickle, os, sys, importlib

VER = sys.argv[1] if len(sys.argv) > 1 else '1180'
BASE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(BASE, VER)
STRATEGY_DIR = os.path.join(DIR, '评分策略')

print('加载数据...')
with open(os.path.join(DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d.get('real',{}), d.get('names',{})
with open(os.path.join(DIR, 'features_30d.pkl'), 'rb') as f:
    precomputed = pickle.load(f)
print(f'  big_cache: {len(data)}天, 特征: {len(precomputed)}条')

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
    p_is_max = p >= max(gains[:-1]) if len(gains)>1 else True
    avg_7d = sum(gains)/n
    penalty = 0
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
    if n>=5 and d5>d1 and d5>d2 and p<=d5:
        rs = (d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
        if rs<=2: penalty-=8
    if n>=5:
        last5=gains[-5:]
        if all(last5[i]>=last5[i+1] for i in range(len(last5)-1)): penalty-=10
    return penalty

def v10_score(s, code, dt, mk_cn):
    mod = STRATS[mk_cn]
    stock = {}
    stock['p'] = s.get('p',0) or 0
    stock['cl'] = s.get('cl',50)
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
    stock['nm'] = s.get('nm','') or s.get('name','') or names.get(s['code'],'')
    ri = real.get(s['code'],{})
    stock['hsl'] = ri.get('hsl',0) or 0
    feats = precomputed.get((code, dt), {})
    stock['t4_shadow'] = feats.get('t4_shadow',0)
    stock['slope5'] = feats.get('slope5',0)
    stock['cons_up'] = feats.get('cons_up',0)
    stock['d1'] = feats.get('d1',0)
    stock['d2'] = feats.get('d2',0)
    stock['d3'] = feats.get('d3',0)
    stock['ma5_slope'] = feats.get('ma5_slope',0)
    stock['volume'] = s.get('volume',0) or 0
    stock['close'] = s.get('close',0) or 0
    stock['open'] = s.get('open',0) or 0
    stock['high'] = s.get('high',0) or 0
    stock['low'] = s.get('low',0) or 0
    sp = compute_7day_decay_penalty(code, dt, s.get('p',0) or 0)
    return round(mod.score(stock) + sp, 1)

def run_backtest(dates, label):
    wi = 0; ta = 0
    top3win = {}
    for dt in dates:
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
        scored.sort(key=lambda x: -x[0])
        champ = scored[0][1]
        nh = champ.get('n',0) or 0
        ta += 1
        if nh >= 2.5: wi += 1
        for ti in range(min(3, len(scored))):
            s2 = scored[ti][1]; n2 = s2.get('n',0) or 0
            if n2 >= 2.5: top3win[ti] = top3win.get(ti,0) + 1
        # 记录失败明细
        if nh < 2.5:
            fe = precomputed.get((champ['code'], dt), {})
            print(f'  ❌ {dt} {mk_cn:>5} {names.get(champ["code"],"?"):>8} '
                  f'p={champ.get("p",0):.1f}% n={nh:+.1f}% '
                  f'd2={fe.get("d2",0):.1f} amp/p={max(champ.get("amplitude",0) or 0,0)/max(abs(champ.get("p",0) or 0),0.01):.2f}')
    
    result = f'{label}: #{1}={top3win.get(0,0)}/{ta}={top3win.get(0,0)*100/ta:.1f}%'
    for ti in range(1, 3):
        result += f' | #{ti+1}={top3win.get(ti,0)}/{ta}={top3win.get(ti,0)*100/ta:.1f}%'
    return wi, ta, result

all_dates = sorted(k for k in data.keys())
print(f'\n===== {VER} 回测 =====')
for label, n in [('30天',30),('50天',50),('100天',100)]:
    w,t,r = run_backtest(all_dates[-n:], label)
    print(f'  冠军 {label}: #1={w}/{t}={w*100/t:.1f}% {r}')
