"""
全因子扫描：找V42评分没用到但有预测力的字段
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

# ===== 收集所有V42评分用到的字段 =====
V42_FIELDS = {'p','cl','vr','dif','mg','wrv','dv','a5','kdj_g','pos_in_day',
              'hsl','t4_shadow','slope5','cons_up','nm','name'}

# ===== 扫描所有候选池中票的未用字段，分析每个字段与达标率的关系 =====
all_cands = []  # 所有通过筛选的候选票

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
    
    for s in pool:
        code = s.get('code', '')
        nh = s.get('next_high', 0) or 0
        all_cands.append({
            'code': code, 'dt': dt, 'mk': mk_cn,
            'p': s.get('p',0) or 0,
            'close': s.get('close',0) or 0,
            'amplitude': s.get('amplitude',0) or 0,
            'body_pct': s.get('body_pct',0) or 0,
            'vol': s.get('vol',0) or 0,
            'n': s.get('n',0) or 0,
            'is_yang': s.get('is_yang',0) or 0,
            'above_ma10': s.get('above_ma10',0) or 0,
            'above_ma20': s.get('above_ma20',0) or 0,
            'ma5_slope': s.get('ma5_slope',0) or 0,
            'nh': nh, 'ok': 1 if nh >= 2.5 else 0,
        })

oks = [c for c in all_cands if c['ok']]
fails = [c for c in all_cands if not c['ok']]
print(f"候选池总计: {len(all_cands)}条")
print(f"达标: {len(oks)} ({len(oks)/len(all_cands)*100:.1f}%)")
print(f"失败: {len(fails)}")

# ===== 逐个因子扫描 =====
print("\n" + "="*80)
print("未用因子扫描：成功率差异")
print("="*80)

factors = [
    ('close', '股价', [(0,10),(10,20),(20,35),(35,50),(50,80),(80,150),(150,500)]),
    ('amplitude', '振幅%', [(0,2),(2,4),(4,6),(6,8),(8,10),(10,12),(12,15),(15,100)]),
    ('body_pct', '实体%', [(0,2),(2,4),(4,6),(6,8),(8,10),(10,15),(15,100)]),
    ('vol', '成交量', [(0,100000),(100000,300000),(300000,500000),(500000,1000000),(1000000,5000000),(5000000,99999999)]),
    ('n', 'n值', [(0,50),(50,100),(100,300),(300,500),(500,1000),(1000,2000),(2000,5000)]),
    ('above_ma10', '站MA10', [(0,0.5),(0.5,1.5),(1.5,2)]),
    ('above_ma20', '站MA20', [(0,0.5),(0.5,1.5),(1.5,2)]),
    ('ma5_slope', 'MA5斜率', [(-100,0),(0,5),(5,10),(10,20),(20,50),(50,100)]),
]

for fkey, fname, buckets in factors:
    print(f"\n▶ {fname}({fkey}):")
    vals = [c[fkey] for c in all_cands if c[fkey] is not None]
    print(f"  范围: {min(vals):.2f} ~ {max(vals):.2f}  均值: {sum(vals)/len(vals):.2f}")
    
    for lo, hi in buckets:
        subset = [c for c in all_cands if lo <= c[fkey] < hi]
        if not subset: continue
        sub_ok = [c for c in subset if c['ok']]
        rate = len(sub_ok)/len(subset)*100
        diff = rate - (len(oks)/len(all_cands)*100)
        marker = '🚀' if diff > 5 else ('❌' if diff < -5 else '')
        bar = '█' * int(rate/5) + '░' * (20 - int(rate/5))
        print(f"  {lo:>8}~{hi:<8}: {len(subset):>5}只 {bar} {rate:>5.1f}% ({diff:>+5.1f}%) {marker}")

# ===== 交叉分析：最有潜力的两两组合 =====
print("\n" + "="*80)
print("交叉分析：两条件组合达标率")
print("="*80)

cross_conds = [
    ("振幅<3%+股价10-50", lambda r: r['amplitude']<3 and 10<=r['close']<=50),
    ("振幅<3%+站MA10+MA20", lambda r: r['amplitude']<3 and r['above_ma10'] and r['above_ma20']),
    ("实体>5%+股价10-50", lambda r: r['body_pct']>5 and 10<=r['close']<=50),
    ("n>2000+股价10-50", lambda r: r['n']>2000 and 10<=r['close']<=50),
    ("n>2000+振幅<4%", lambda r: r['n']>2000 and r['amplitude']<4),
    ("n>2000+振幅>10%", lambda r: r['n']>2000 and r['amplitude']>10),
    ("阳线+振幅<4%", lambda r: r['is_yang'] and r['amplitude']<4),
    ("阳线+n>2000", lambda r: r['is_yang'] and r['n']>2000),
    ("站MA10+MA20+振幅<4%", lambda r: r['above_ma10'] and r['above_ma20'] and r['amplitude']<4),
    ("站MA10+MA20+股价10-50", lambda r: r['above_ma10'] and r['above_ma20'] and 10<=r['close']<=50),
    ("振幅<2%", lambda r: r['amplitude']<2),
    ("振幅<2%+站MA10+MA20", lambda r: r['amplitude']<2 and r['above_ma10'] and r['above_ma20']),
    ("n>3000+股价10-35", lambda r: r['n']>3000 and 10<=r['close']<=35),
    ("n<100", lambda r: r['n']<100),
    ("n<100+振幅>8%", lambda r: r['n']<100 and r['amplitude']>8),
    ("n<100+振幅<4%", lambda r: r['n']<100 and r['amplitude']<4),
    ("实体>8%+阳线", lambda r: r['body_pct']>8 and r['is_yang']),
    ("实体<2%+阳线", lambda r: r['body_pct']<2 and r['is_yang']),
]

for name, cond in cross_conds:
    subset = [c for c in all_cands if cond(c)]
    if len(subset) < 10: continue
    sub_ok = [c for c in subset if c['ok']]
    rate = len(sub_ok)/len(subset)*100
    diff = rate - (len(oks)/len(all_cands)*100)
    print(f"  {name:>30}: {len(subset):>4}只 达标率{rate:>5.1f}% ({diff:>+5.1f}%)")

# ===== n值到底是什么？ =====
print("\n" + "="*80)
print("n字段深度分析")
print("="*80)
n_vals = [c['n'] for c in all_cands]
from collections import Counter
n_dist = Counter(n_vals)
print(f"n值分布(Top10): {n_dist.most_common(10)}")
# 看几个具体案例
samples = [c for c in all_cands if 0 < c['n'] < 10]
print(f"n<10的样本数: {len(samples)}")
for s in samples[:5]:
    print(f"  {s['code']} n={s['n']} p={s['p']:.1f}% close={s['close']:.2f} amp={s['amplitude']:.1f}")
