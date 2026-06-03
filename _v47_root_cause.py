"""
V47根本原因分析 — 失败票共性分析
不调参，只分析数据
"""
import pickle, os, sys, importlib

SCRIPTS_DIR = r'C:\Users\12546\AppData\Local\hermes\scripts'
V42_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V42')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')

# 加载V42评分策略
STRATS = {}
for n in ['真实涨日','虚涨日','跌日','横盘']:
    fp = os.path.join(V42_DIR, '评分策略', f'分而治之_V10_{n}_评分策略.py')
    spec = importlib.util.spec_from_file_location(n, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    STRATS[n] = m

# 直接加载数据
print("加载big_cache...", flush=True)
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d['real'], d['names']

print("加载features...", flush=True)
with open(os.path.join(V13_DIR, 'features_30d.pkl'), 'rb') as f:
    precomputed = pickle.load(f)

dates = sorted(k for k in data.keys() if '2025-01-01'<=k<='2026-05-28')
print(f"数据: {len(dates)}天, {len(names)}只股, {len(precomputed)}条特征", flush=True)

def mkt_class(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    ap = sum(ps) / len(ps); av = sum(vrs) / len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

MK_MAP = {'real_up': '真实涨日', 'fake_up': '虚涨日', 'down': '跌日', 'flat': '横盘'}
LO = ['L0','L1','L2','L3','L4']

date_index = {dt: i for i, dt in enumerate(dates)}

def get_next_day_high(code, dt_idx):
    best = 0
    for offset in range(1, 6):
        if dt_idx + offset >= len(dates): break
        nd = dates[dt_idx + offset]
        for s in data[nd]:
            if s.get('code') == code:
                p = s.get('p', 0) or 0
                if p > best: best = p
                break
    return best

# 运行回测
test_dates = [dt for dt in dates if '2026-04-01' <= dt <= '2026-05-28']
results = []

for dt in test_dates:
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
            sz = s.get('sz',0) or 0
            if sz > lv.get('sz_max', 99999): continue
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
    
    dt_idx = date_index[dt]
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
    
    for rank, (sc, code, s) in enumerate(scored[:10], 1):
        nh = get_next_day_high(code, dt_idx)
        ri = real.get(code, {})
        results.append({
            'dt': dt, 'mk': mk_cn, 'rank': rank, 'score': sc,
            'code': code, 'name': names.get(code, code),
            'p': s.get('p',0) or 0,
            'dif': s.get('dif_val',0) or s.get('dif',0),
            'wr': s.get('wr_val',0) or s.get('wrv',50),
            'cl': s.get('cl',50),
            'hsl': ri.get('hsl',0) or 0,
            'dv': s.get('d_val',0) or s.get('dv',50),
            'vr': s.get('vol_ratio',0) or s.get('vr',0),
            'po': s.get('pos_in_day',50),
            'a5': s.get('above_ma5',0),
            'mg': s.get('macd_golden',0) or s.get('mg',0),
            'kg': s.get('kdj_golden',0) or s.get('kdj_g',0),
            'nh': nh,
            'ok': 1 if nh >= 2.5 else 0,
        })

print(f"\n分析完成: {len(results)}条候选记录", flush=True)

ok_stocks = [r for r in results if r['ok']]
fail_stocks = [r for r in results if not r['ok']]
all_top3 = [r for r in results if r['rank'] <= 3]
top3_ok = [r for r in ok_stocks if r['rank'] <= 3]
top3_fail = [r for r in fail_stocks if r['rank'] <= 3]

print(f"\n===== 基础统计 =====")
print(f"TOP3总记录: {len(all_top3)}")
print(f"TO3达标: {len(top3_ok)} ({len(top3_ok)/max(len(all_top3),1)*100:.1f}%)")
print(f"TOP3失败: {len(top3_fail)}")

# 特征对比：成功 vs 失败
print(f"\n===== 特征均值对比 (TOP3) =====")
features = [('p','涨幅%'),('dif','DIF'),('wr','WR'),('cl','CL'),
            ('hsl','换手'),('dv','D值'),('vr','量比'),('po','位置'),
            ('score','评分')]
for fkey, fname in features:
    sv = [r[fkey] for r in top3_ok]
    fv = [r[fkey] for r in top3_fail]
    if not sv or not fv: continue
    sm = sum(sv)/len(sv)
    fm = sum(fv)/len(fv)
    print(f"  {fname:>8}: 成功={sm:.2f}  失败={fm:.2f}  差={sm-fm:+.2f}")

# ===== 核心：条件组合分析 =====
print(f"\n===== 条件组合分析 (TOP3, 59天数据) =====")
print(f"{'条件':>35} {'总':>5} {'达标':>5} {'胜率':>8} {'失败':>5}")
print("-"*65)

conds = [
    # 单一条件
    ("基线(全部)", lambda r: True),
    ("p>6", lambda r: r['p'] > 6),
    ("p>5", lambda r: r['p'] > 5),
    ("p>7", lambda r: r['p'] > 7),
    ("WR<20", lambda r: r['wr'] < 20),
    ("WR<15", lambda r: r['wr'] < 15),
    ("WR<10", lambda r: r['wr'] < 10),
    ("WR<8", lambda r: r['wr'] < 8),
    ("CL>90", lambda r: r['cl'] > 90),
    ("VR>2", lambda r: r['vr'] > 2),
    ("VR>3", lambda r: r['vr'] > 3),
    ("HSL>15", lambda r: r['hsl'] > 15),
    ("DIF<0", lambda r: r['dif'] < 0),
    ("PO<30", lambda r: r['po'] < 30),
    ("PO>70", lambda r: r['po'] > 70),
    ("HSL<5", lambda r: r['hsl'] < 5),
    # 两条件组合
    ("p>6+WR<20", lambda r: r['p']>6 and r['wr']<20),
    ("p>6+WR<15", lambda r: r['p']>6 and r['wr']<15),
    ("p>6+WR<10", lambda r: r['p']>6 and r['wr']<10),
    ("p>6+CL>90", lambda r: r['p']>6 and r['cl']>90),
    ("p>6+VR>2", lambda r: r['p']>6 and r['vr']>2),
    ("p>5+WR<15", lambda r: r['p']>5 and r['wr']<15),
    ("p>5+CL>90", lambda r: r['p']>5 and r['cl']>90),
    ("VR>2+p<4", lambda r: r['vr']>2 and r['p']<4),
    ("WR<10+CL>90", lambda r: r['wr']<10 and r['cl']>90),
    ("WR<15+HSL>15", lambda r: r['wr']<15 and r['hsl']>15),
    ("DIF<0+p>4", lambda r: r['dif']<0 and r['p']>4),
    ("DIF<0+WR<20", lambda r: r['dif']<0 and r['wr']<20),
    ("PO<20+WR<15", lambda r: r['po']<20 and r['wr']<15),
    ("PO>70+WR<20", lambda r: r['po']>70 and r['wr']<20),
    # 三条件组合（最值得关注的）
    ("p>6+WR<15+CL>90", lambda r: r['p']>6 and r['wr']<15 and r['cl']>90),
    ("p>6+WR<10+CL>90", lambda r: r['p']>6 and r['wr']<10 and r['cl']>90),
    ("p>6+WR<15+VR>2", lambda r: r['p']>6 and r['wr']<15 and r['vr']>2),
    ("p>6+WR<10+VR>2", lambda r: r['p']>6 and r['wr']<10 and r['vr']>2),
    ("p>6+WR<10+HSL>15", lambda r: r['p']>6 and r['wr']<10 and r['hsl']>15),
    ("p>7+WR<10", lambda r: r['p']>7 and r['wr']<10),
    ("p>7+WR<15", lambda r: r['p']>7 and r['wr']<15),
    ("p>7+WR<10+CL>90", lambda r: r['p']>7 and r['wr']<10 and r['cl']>90),
    ("p>7+WR<15+CL>90", lambda r: r['p']>7 and r['wr']<15 and r['cl']>90),
]

for name, cond in conds:
    matched = [r for r in all_top3 if cond(r)]
    matched_ok = [r for r in matched if r['ok']]
    total = len(matched)
    hit = len(matched_ok)
    fail_cnt = total - hit
    rate = hit / total * 100 if total > 0 else 0
    print(f"  {name:>35}: {total:>5} {hit:>5} {rate:>7.1f}% {fail_cnt:>5}")

# ===== 详细查看所有失败TOP3的明细 =====
print(f"\n===== 所有TOP3失败票明细 (按排名) =====")
print(f"{'日期':>12} {'行情':>8} {'排名':>4} {'名称':>12} {'代码':>8} {'p%':>6} {'WR':>6} {'CL':>6} {'VR':>6} {'换手':>6} {'DIF':>8} {'评分':>8} {'次日高':>8}")
print("-"*110)
for r in sorted(top3_fail, key=lambda x: x['dt']):
    print(f"{r['dt']:>12} {r['mk']:>8} {r['rank']:>4} {r['name'][:10]:>12} {r['code']:>8} "
          f"{r['p']:>+5.1f}% {r['wr']:>5.0f} {r['cl']:>5.0f} {r['vr']:>5.1f} "
          f"{r['hsl']:>5.1f} {r['dif']:>+7.2f} {r['score']:>7.1f} {r['nh']:>+6.1f}%")

# 分析失败票最集中的行情
print(f"\n===== 失败票按行情分布 (TOP3) =====")
from collections import Counter
mk_fail = Counter(r['mk'] for r in top3_fail)
mk_all = Counter(r['mk'] for r in all_top3)
for mk in ['真实涨日','虚涨日','跌日','横盘']:
    fcnt = mk_fail.get(mk, 0)
    acnt = mk_all.get(mk, 0)
    rate = (acnt-fcnt)/acnt*100 if acnt > 0 else 0
    print(f"  {mk:>8}: 总{acnt:>4} 失败{fcnt:>4} 胜率{rate:>5.1f}%")
