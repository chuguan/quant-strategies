"""V42 vs V47 分段回测：100天 / 50天 / 近30天"""
import pickle, os, sys, importlib

SCRIPTS_DIR = r'C:\Users\12546\AppData\Local\hermes\scripts'
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')

def run_ver(ver):
    VDIR = os.path.join(SCRIPTS_DIR, 'release', ver, '评分策略')
    STRATS = {}
    for n in ['真实涨日','虚涨日','跌日','横盘']:
        fp = os.path.join(VDIR, f'分而治之_V10_{n}_评分策略.py')
        spec = importlib.util.spec_from_file_location(f'{ver}_{n}', fp)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        STRATS[n] = (m, m.score)
    return STRATS

V42 = run_ver('V42')
V47 = run_ver('V47')
V48 = run_ver('V48')

with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d['real'], d['names']

with open(os.path.join(V13_DIR, 'features_30d.pkl'), 'rb') as f:
    precomputed = pickle.load(f)

dates = sorted(k for k in data.keys() if '2025-01-01'<=k<='2026-05-28')

def mkt_class(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

MK_MAP = {'real_up': '真实涨日', 'fake_up': '虚涨日', 'down': '跌日', 'flat': '横盘'}
LO = ['L0','L1','L2','L3','L4']

for ver_name, strats in [('V42', V42), ('V47', V47), ('V48', V48)]:
    all_days = {}  # dt -> {ok, total, #1ok, mk}
    
    for dt in dates:
        ss = data[dt]
        ss = [s for s in ss if (s.get('p', 0) or 0) < 15]
        if not ss: continue
        
        mk = mkt_class(ss)
        mk_cn = MK_MAP.get(mk, '横盘')
        if mk_cn not in strats: continue
        
        mod, score_fn = strats[mk_cn]
        LEVELS = mod.LEVELS
        
        lm = {l['name']:i for i,l in enumerate(LEVELS)}
        pool = None
        for ln in LO:
            if ln not in lm: continue
            i = lm[ln]; lv = LEVELS[i]
            cand = []
            for s in ss:
                p = s.get('p',0) or 0
                if p < lv.get('p_min', -999) or p > lv.get('p_max', 999): continue
                vr = s.get('vol_ratio', 0) or s.get('vr', 0) or 0
                if vr < lv.get('vr_min', 0) or vr > lv.get('vr_max', 999): continue
                ri_hsl = real.get(s.get('code',''), {})
                hs = ri_hsl.get('hsl', 0) or 0
                if hs < lv.get('hs_min', 0) or hs > lv.get('hs_max', 999): continue
                cl = s.get('cl',50) or 50
                if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
                if lv.get('a5_req', 0) and not s.get('above_ma5',0): continue
                if lv.get('kdj_g_req', 0) and not (s.get('kdj_golden',0) or s.get('kdj_g',0)): continue
                cand.append(s)
            if len(cand) >= 10:
                pool = cand
                break
        
        if pool is None or len(pool) < 10: continue
        
        scored = []
        for s in pool:
            code = s.get('code', '')
            stock = {}
            stock['p'] = s.get('p', 0) or 0
            stock['cl'] = s.get('cl', 50)
            stock['vr'] = s.get('vol_ratio', 1) or s.get('vr', 1)
            stock['dif'] = s.get('dif_val', 0) or s.get('dif', 0)
            stock['mg'] = s.get('macd_golden', 0) or s.get('mg', 0)
            stock['wrv'] = s.get('wr_val', 0) or s.get('wrv', 50)
            stock['dv'] = s.get('d_val', 0) or s.get('dv', 50)
            stock['a5'] = s.get('above_ma5', 0)
            stock['kdj_g'] = s.get('kdj_golden', 0) or s.get('kdj_g', 0)
            stock['pos_in_day'] = s.get('pos_in_day', 50)
            stock['nm'] = s.get('nm', '') or s.get('name', '') or names.get(code, '')
            ri = real.get(code, {})
            stock['hsl'] = ri.get('hsl', 0) or 0
            feats = precomputed.get((code, dt), {})
            stock['t4_shadow'] = feats.get('t4_shadow', 0)
            stock['slope5'] = feats.get('slope5', 0)
            stock['cons_up'] = feats.get('cons_up', 0)
            stock['amplitude'] = s.get('amplitude', 0) or 0
            
            sc = score_fn(stock)
            if sc > 0:
                scored.append((sc, code, s))
        
        scored.sort(key=lambda x: -x[0])
        
        day_ok = False
        day_ok1 = False
        for rank, (sc, code, s) in enumerate(scored[:3], 1):
            nh = s.get('next_high', 0) or 0
            ok = 1 if nh >= 2.5 else 0
            if ok:
                day_ok = True
                if rank == 1:
                    day_ok1 = True
        
        all_days[dt] = {'ok': day_ok, 'ok1': day_ok1, 'mk': mk_cn}
    
    sorted_dates = sorted(all_days.keys())
    
    for label, n_days in [('近30天', 30), ('近50天', 50), ('近100天', 100), ('全量', 9999)]:
        subset = sorted_dates[-n_days:] if n_days != 9999 else sorted_dates
        win = sum(1 for dt in subset if all_days[dt]['ok'])
        win1 = sum(1 for dt in subset if all_days[dt]['ok1'])
        total = len(subset)
        print(f"{ver_name} {label:>8}: {win:>3}/{total:>3} = {win/total*100:>5.1f}%  (#1胜率 {win1}/{total} = {win1/total*100:.1f}%)")
    
    # 分行情
    print(f"  【行情分布】")
    for mk in ['真实涨日','虚涨日','跌日','横盘']:
        mkd = [dt for dt in sorted_dates[-100:] if all_days[dt]['mk'] == mk]
        if mkd:
            mw = sum(1 for dt in mkd if all_days[dt]['ok'])
            print(f"    {mk:>8}: {mw:>2}/{len(mkd):>2} = {mw/len(mkd)*100:>5.1f}%")
    print()
