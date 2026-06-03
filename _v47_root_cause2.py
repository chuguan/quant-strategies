"""
V47 根本原因分析 — 深度分析
"""
import pickle, os, sys, importlib
from collections import Counter

SCRIPTS_DIR = r'C:\Users\12546\AppData\Local\hermes\scripts'
V42_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V42')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')

# 加载V42评分
STRATS = {}
for n in ['真实涨日','虚涨日','跌日','横盘']:
    fp = os.path.join(V42_DIR, '评分策略', f'分而治之_V10_{n}_评分策略.py')
    spec = importlib.util.spec_from_file_location(n, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    STRATS[n] = m

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

all_top3 = []

for dt in dates:
    ss = data[dt]
    ss = [s for s in ss if (s.get('p', 0) or 0) < 15]
    if not ss: continue
    
    mk = mkt_class(ss)
    mk_cn = MK_MAP.get(mk, '横盘')
    if mk_cn not in STRATS: continue
    
    mod = STRATS[mk_cn]
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
    
    if pool is None: continue
    if len(pool) < 10: continue
    
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
        
        sc = mod.score(stock)
        if sc > 0:
            scored.append((sc, code, s))
    
    scored.sort(key=lambda x: -x[0])
    
    # V42 HSL>18 一票否决
    final_top = []
    for sc, code, s in scored:
        ri2 = real.get(code, {})
        if (ri2.get('hsl', 0) or 0) > 18:
            continue
        final_top.append((sc, code, s))
        if len(final_top) >= 3:
            break
    
    for rank, (sc, code, s) in enumerate(final_top, 1):
        nh = s.get('next_high', 0) or 0
        ri3 = real.get(code, {})
        feats2 = precomputed.get((code, dt), {})
        all_top3.append({
            'dt': dt, 'mk': mk_cn, 'rank': rank, 'score': sc,
            'code': code, 'name': names.get(code, code),
            'p': s.get('p',0) or 0,
            'dif': s.get('dif_val',0) or s.get('dif',0),
            'wr': s.get('wr_val',0) or s.get('wrv',50),
            'cl': s.get('cl',50),
            'hsl': ri3.get('hsl',0) or 0,
            'dv': s.get('d_val',0) or s.get('dv',50),
            'vr': s.get('vol_ratio',0) or s.get('vr',0),
            'po': s.get('pos_in_day',50),
            'a5': s.get('above_ma5',0),
            'mg': s.get('macd_golden',0) or s.get('mg',0),
            'kg': s.get('kdj_golden',0) or s.get('kdj_g',0),
            't4s': feats2.get('t4_shadow', 0),
            'sl5': feats2.get('slope5', 0),
            'cu': feats2.get('cons_up', 0),
            'nh': nh,
            'ok': 1 if nh >= 2.5 else 0,
        })

fails = [r for r in all_top3 if not r['ok']]
oks = [r for r in all_top3 if r['ok']]

print(f"总天数: {len(set(r['dt'] for r in all_top3))}")
print(f"TOP3总: {len(all_top3)} | 成功: {len(oks)} | 失败: {len(fails)}")
print(f"胜率: {len(oks)/len(all_top3)*100:.1f}%")
print()

# ===== 深度分析 =====
print("=" * 100)
print("失败票深度分析 — 找共性")
print("=" * 100)

# 失败票明细
print(f"\n▶ 所有失败票明细 ({len(fails)}只):")
print(f"{'日期':>12} {'行情':>8} {'#':>2} {'名称':>12} {'代码':>8} {'p%':>6} {'WR':>5} {'CL':>5} {'HSL':>6} "
      f"{'VR':>5} {'DIF':>7} {'PO':>5} {'评分':>7} {'sl5':>5} {'t4s':>5} {'cu':>3} {'→高':>6}")
print("-" * 120)
for r in sorted(fails, key=lambda x: x['dt']):
    print(f"{r['dt']:>12} {r['mk']:>8} {r['rank']:>2} {r['name'][:10]:>12} {r['code']:>8} "
          f"{r['p']:>+5.1f}% {r['wr']:>4.0f} {r['cl']:>4.0f} {r['hsl']:>5.1f}% "
          f"{r['vr']:>4.1f} {r['dif']:>+6.2f} {r['po']:>4.0f} {r['score']:>6.0f} "
          f"{r['sl5']:>4.1f} {r['t4s']:>4.0f} {r['cu']:>2.0f} →+{r['nh']:>4.1f}%")

print(f"\n▶ HSL>17的失败票:")
for r in sorted(fails, key=lambda x: x['dt']):
    if r['hsl'] > 17:
        print(f"  {r['dt']} #{r['rank']} {r['name']}({r['code']}) HSL={r['hsl']:.1f}% WR={r['wr']:.0f} "
              f"p={r['p']:+.1f}% 评分={r['score']:.0f} →+{r['nh']:.1f}%")

# 精准条件筛选
print(f"\n▶ 精准一票否决条件筛选 (目标: 覆盖失败票>30%, 误伤成功票<10%):")
print(f"{'条件':>38} {'总':>5} {'失败':>5} {'成功':>5} {'覆盖失败':>10} {'误伤成功':>10}")
print("-" * 85)

conds = [
    ("p>6 + WR<15", lambda r: r['p']>6 and r['wr']<15),
    ("p>6 + WR<10", lambda r: r['p']>6 and r['wr']<10),
    ("p>5 + DIF>4", lambda r: r['p']>5 and r['dif']>4),
    ("p>4 + DIF>5", lambda r: r['p']>4 and r['dif']>5),
    ("HSL>18 (V42已有)", lambda r: r['hsl']>18),
    ("HSL>17", lambda r: r['hsl']>17),
    ("HSL>16 + PO>70", lambda r: r['hsl']>16 and r['po']>70),
    ("HSL>17 + CL>88", lambda r: r['hsl']>17 and r['cl']>88),
    ("HSL>16 + WR<10", lambda r: r['hsl']>16 and r['wr']<10),
    ("PO>75 + WR<15", lambda r: r['po']>75 and r['wr']<15),
    ("p>4 + PO>75 + WR<15", lambda r: r['p']>4 and r['po']>75 and r['wr']<15),
    ("DIF>4 + WR<15 + CL>88", lambda r: r['dif']>4 and r['wr']<15 and r['cl']>88),
    ("DIF>5 + WR<15", lambda r: r['dif']>5 and r['wr']<15),
    ("DIF>6", lambda r: r['dif']>6),
    ("DIF>5 + PO>70", lambda r: r['dif']>5 and r['po']>70),
    ("DIF>4 + CL>90 + PO>70", lambda r: r['dif']>4 and r['cl']>90 and r['po']>70),
    ("p>5 + DIF>4 + HSL>15", lambda r: r['p']>5 and r['dif']>4 and r['hsl']>15),
    ("HSL>16 + CL>90", lambda r: r['hsl']>16 and r['cl']>90),
    ("HSL>17 + PO>60", lambda r: r['hsl']>17 and r['po']>60),
    ("HSL>16 + WR<15 + CL>88", lambda r: r['hsl']>16 and r['wr']<15 and r['cl']>88),
]

for name, cond in conds:
    hf = [r for r in fails if cond(r)]
    ho = [r for r in oks if cond(r)]
    cover = len(hf)/len(fails)*100 if fails else 0
    fp_rate = len(ho)/len(oks)*100 if oks else 0
    print(f"  {name:>38}: {len(hf)+len(ho):>5} {len(hf):>5} {len(ho):>5} "
          f"{cover:>9.1f}% {fp_rate:>9.1f}%")

# 哪个HSL阈值最佳？
print(f"\n▶ HSL阈值优化:")
for thr in [14, 15, 16, 17, 18, 19, 20]:
    hf = [r for r in fails if r['hsl'] > thr]
    ho = [r for r in oks if r['hsl'] > thr]
    cover = len(hf)/len(fails)*100 if fails else 0
    fp = len(ho)/len(oks)*100 if oks else 0
    print(f"  HSL>{thr:>2}: 覆盖失败={len(hf):>2}({cover:>4.1f}%) 误伤成功={len(ho):>2}({fp:>4.1f}%)")

# 成交额/市值? 没有sz字段，但有close和vol
print(f"\n▶ 基于日内位置的否决:")
for po_thr in [65, 70, 75, 80, 85]:
    for wr_thr in [10, 12, 15]:
        cond_name = f"PO>{po_thr}+WR<{wr_thr}"
        hf = [r for r in fails if r['po']>po_thr and r['wr']<wr_thr]
        ho = [r for r in oks if r['po']>po_thr and r['wr']<wr_thr]
        cover = len(hf)/len(fails)*100 if fails else 0
        fp = len(ho)/len(oks)*100 if oks else 0
        if cover > 10:
            print(f"  {cond_name:>20}: 覆盖失败={len(hf):>2}({cover:>5.1f}%) 误伤成功={len(ho):>2}({fp:>5.1f}%)")
