#!/usr/bin/env python3
"""验证V45的200天胜率是否达到60%+"""
import pickle, os, sys, importlib

BASE = os.path.expanduser(r'~/AppData/Local/hermes/scripts')

def run_200d(ver_name):
    V13_DIR = os.path.join(BASE, 'release', 'V13')
    ver_dir = os.path.join(BASE, 'release', ver_name)
    
    with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
        d = pickle.load(f)
    data, real, names = d['data'], d['real'], d['names']
    all_dates = sorted(k for k in data.keys() if '2025-01-01' <= k <= '2026-05-28')[-200:]
    
    def load_mod(fp):
        spec = importlib.util.spec_from_file_location(f'm_{ver_name}', fp)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    
    MODS = {}
    for cn in ['真实涨日','虚涨日','跌日','横盘']:
        fp = os.path.join(ver_dir, '评分策略', f'分而治之_V10_{cn}_评分策略.py')
        if os.path.exists(fp): MODS[cn] = load_mod(fp)
    
    def mkt_class(stocks):
        if not stocks: return 'flat'
        ps = [s.get('p',0) or 0 for s in stocks]
        vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
        ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
        hot = sum(1 for p in ps if 5<=p<=8)
        if ap > 0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
        if ap < -0.5: return 'down'
        return 'flat'
    MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
    LO = ['L0','L1','L2','L3','L4']
    
    total, wins = 0, 0
    by_market = {}
    
    for dt in all_dates:
        stocks = data.get(dt, [])
        if not stocks: continue
        stocks = [s for s in stocks if (s.get('p',0) or 0) < 15]
        if not stocks: continue
        mt = mkt_class(stocks); mk_cn = MK_MAP.get(mt, '横盘')
        mod = MODS.get(mk_cn)
        if not mod: continue
        LEVELS = mod.LEVELS; lm = {l['name']: i for i, l in enumerate(LEVELS)}
        pool = None
        for ln in LO:
            if ln not in lm: continue
            i = lm[ln]; lv = LEVELS[i]; cand = []
            for s in stocks:
                p = s.get('p',0) or 0
                if p < lv['p_min'] or p > min(lv.get('p_max',10),8): continue
                vr = s.get('vol_ratio',0) or 0
                if vr < lv['vr_min'] or vr > lv['vr_max']: continue
                ri = real.get(s['code'],{}); hsl = ri.get('hsl',0) or 0
                if hsl < lv.get('hs_min',0) or hsl > lv.get('hs_max',99): continue
                if (ri.get('shizhi',0) or 0) >= lv.get('sz_max',9999): continue
                nm = names.get(s['code'],'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl = s.get('cl',0)
                if cl < lv.get('cl_min',0) or cl > lv.get('cl_max',100): continue
                cand.append(s)
            if len(cand) >= 10: pool = cand; break
        if not pool: continue
        
        scored = []
        for s in pool:
            code = s.get('code','')
            stock = {
                'p': s.get('p',0) or 0, 'cl': s.get('cl',50),
                'vr': s.get('vol_ratio',1) or s.get('vr',1),
                'dif': s.get('dif_val',0) or s.get('dif',0),
                'mg': s.get('macd_golden',0) or s.get('mg',0),
                'wrv': s.get('wr_val',0) or s.get('wrv',50),
                'jv': s.get('j_val',0) or s.get('jv',50),
                'kv': s.get('k_val',0) or s.get('kv',50),
                'dv': s.get('d_val',0) or s.get('dv',50),
                'a5': s.get('above_ma5',0),
                'kdj_g': s.get('kdj_golden',0) or s.get('kdj_g',0),
                'pos_in_day': s.get('pos_in_day',50),
                'nm': s.get('nm','') or s.get('name','') or names.get(code,''),
                'hsl': real.get(code,{}).get('hsl',0) or 0,
                'buy_c': s.get('close',0) or 0,
                't4_shadow':0,'slope5':0,'cons_up':0,
            }
            sc = mod.score(stock)
            if sc > 0: scored.append((sc, s))
        if not scored: continue
        scored.sort(key=lambda x:-x[0])
        total += 1
        champ_n = scored[0][1].get('n',0) or 0
        if champ_n >= 2.5:
            wins += 1
            by_market[mk_cn] = by_market.get(mk_cn,{'w':0,'t':0})
            by_market[mk_cn]['w'] += 1
        else:
            by_market[mk_cn] = by_market.get(mk_cn,{'w':0,'t':0})
        by_market[mk_cn]['t'] += 1
    
    rate = wins/total*100 if total > 0 else 0
    return rate, total, wins, by_market

print("=" * 60)
print("  V45 200天胜率验证（高位追涨补丁）")
print("=" * 60)

for ver in ['V42', 'V45']:
    rate, total, wins, by_m = run_200d(ver)
    detail = f"  {wins}/{total} = {rate:.1f}%"
    for mk in ['真实涨日','虚涨日','跌日','横盘']:
        if mk in by_m:
            d = by_m[mk]
            detail += f" | {mk}:{d['w']}/{d['t']}={d['w']/d['t']*100:.0f}%"
    print(f"\n{ver}:")
    print(f"  {detail}")

# 对比
print(f"\n{'='*60}")
print(f"  📊 结果对比")
print(f"{'='*60}")
v42_rate, *_ = run_200d('V42')
v45_rate, *_ = run_200d('V45')
diff = v45_rate - v42_rate
print(f"\n  V42 200天: {v42_rate:.1f}%")
print(f"  V45 200天: {v45_rate:.1f}%")
print(f"  变化: {diff:+.1f}% {'✅ 达标！' if v45_rate >= 60 else '❌ 未达标'}")
