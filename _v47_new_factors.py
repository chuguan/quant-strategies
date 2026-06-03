"""
V47新因子分析：振幅、实体占比、股价等对胜率的影响
"""
import pickle, os, sys, importlib

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
        
        sc = mod.score(stock)
        if sc > 0:
            scored.append((sc, code, s))
    
    scored.sort(key=lambda x: -x[0])
    
    for rank, (sc, code, s) in enumerate(scored[:3], 1):
        nh = s.get('next_high', 0) or 0
        ri2 = real.get(code, {})
        all_top3.append({
            'dt': dt, 'mk': mk_cn, 'rank': rank, 'score': sc,
            'code': code, 'name': names.get(code, code[:8]),
            # V42已有的
            'p': s.get('p',0) or 0,
            'wr': s.get('wr_val',0) or s.get('wrv',50),
            'cl': s.get('cl',50),
            'vr': s.get('vol_ratio',0) or s.get('vr',0),
            'hsl': ri2.get('hsl',0) or 0,
            'dif': s.get('dif_val',0) or s.get('dif',0),
            'po': s.get('pos_in_day',50),
            # 新因子
            'amplitude': s.get('amplitude',0) or 0,
            'body_pct': s.get('body_pct',0) or 0,
            'close': s.get('close',0) or 0,
            'is_yang': s.get('is_yang',0) or 0,
            'vol': s.get('vol',0) or 0,
            'ma10': s.get('above_ma10',0) or 0,
            'ma20': s.get('above_ma20',0) or 0,
            'n': s.get('n',0) or 0,
            'nh': nh,
            'ok': 1 if nh >= 2.5 else 0,
        })

oks = [r for r in all_top3 if r['ok']]
fails = [r for r in all_top3 if not r['ok']]

print(f"样本数: {len(all_top3)} | 达标: {len(oks)} | 失败: {len(fails)}")
print(f"胜率: {len(oks)/len(all_top3)*100:.1f}%")
print()

# 新因子分析
print("=" * 80)
print("新因子分析：成功 vs 失败 (TOP3)")
print("=" * 80)

new_features = [
    ('amplitude', '振幅%'),
    ('body_pct', '实体%'), 
    ('close', '股价'),
    ('vol', '成交量'),
    ('ma10', '站MA10'),
    ('ma20', '站MA20'),
    ('is_yang', '阳线'),
    ('n', '上市日数'),
]

for fkey, fname in new_features:
    sv = [r[fkey] for r in oks if r[fkey] is not None]
    fv = [r[fkey] for r in fails if r[fkey] is not None]
    if not sv or not fv: continue
    sm = sum(sv)/len(sv)
    fm = sum(fv)/len(fv)
    print(f"  {fname:>8}: 成功={sm:>8.2f}  失败={fm:>8.2f}  差={sm-fm:>+8.2f}")

# 条件组合分析：新因子的条件达标率
print(f"\n=== 新因子条件组合达标率 ===")
for name, cond in [
    ("振幅>8%", lambda r: r['amplitude'] > 8),
    ("振幅>10%", lambda r: r['amplitude'] > 10),
    ("振幅>12%", lambda r: r['amplitude'] > 12),
    ("实体<3%", lambda r: r['body_pct'] < 3),
    ("实体>5%", lambda r: r['body_pct'] > 5),
    ("实体>8%", lambda r: r['body_pct'] > 8),
    ("振幅>10%+实体<3%", lambda r: r['amplitude'] > 10 and r['body_pct'] < 3),
    ("振幅>10%+实体>5%", lambda r: r['amplitude'] > 10 and r['body_pct'] > 5),
    ("股价>100", lambda r: r['close'] > 100),
    ("股价>50", lambda r: r['close'] > 50),
    ("股价<10", lambda r: r['close'] < 10),
    ("阳线+振幅>8%", lambda r: r['is_yang'] and r['amplitude'] > 8),
    ("阴线+振幅>8%", lambda r: not r['is_yang'] and r['amplitude'] > 8),
    ("MA10+MA20", lambda r: r['ma10'] and r['ma20']),
    ("MA10+MA20+阳线", lambda r: r['ma10'] and r['ma20'] and r['is_yang']),
    # 与p/WR的交叉
    ("p>6+振幅>10%", lambda r: r['p']>6 and r['amplitude']>10),
    ("p>6+振幅<8%", lambda r: r['p']>6 and r['amplitude']<8),
    ("p>6+实体<3%", lambda r: r['p']>6 and r['body_pct']<3),
    ("p>6+实体>5%", lambda r: r['p']>6 and r['body_pct']>5),
    ("p>6+WR<15+振幅>10%", lambda r: r['p']>6 and r['wr']<15 and r['amplitude']>10),
    ("p>6+WR<15+实体<3%", lambda r: r['p']>6 and r['wr']<15 and r['body_pct']<3),
    ("p>6+WR<15+振幅<8%", lambda r: r['p']>6 and r['wr']<15 and r['amplitude']<8),
    ("p>6+WR<15+实体>5%", lambda r: r['p']>6 and r['wr']<15 and r['body_pct']>5),
    # 上市日数
    ("上市<100天", lambda r: 0 < r['n'] < 100),
    ("上市100-500天", lambda r: 100 <= r['n'] <= 500),
    ("上市>2000天", lambda r: r['n'] > 2000),
]:
    matched = [r for r in all_top3 if cond(r)]
    m_ok = [r for r in matched if r['ok']]
    total = len(matched)
    rate = len(m_ok)/total*100 if total > 0 else 0
    if total >= 5:
        print(f"  {name:>35}: {total:>4}只 {rate:>5.1f}%达标")
