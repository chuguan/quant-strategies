"""V13 多时间点回测 — 2:30 vs 2:40 vs 2:50"""
import sqlite3, os, sys, importlib
from datetime import datetime

TIME_LABEL = sys.argv[1] if len(sys.argv) > 1 else '14:50'  # 14:30, 14:40, 14:50
N = int(sys.argv[2]) if len(sys.argv) > 2 else 30
tl_clean = TIME_LABEL.replace(':', '')
VER = f'V13_{tl_clean}_{N}d'

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
sys.path.insert(0, V13_DIR)

STRATS = {}
for n in ['真实涨日','虚涨日','跌日','横盘']:
    fp = os.path.join(V13_DIR, '评分策略', f'分而治之_V10_{n}_评分策略.py')
    spec = importlib.util.spec_from_file_location(n, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    STRATS[n] = m

# 时间-日内进度映射（A股9:30-15:00共240分钟）
TIME_PROGRESS = {'14:30': 0.85, '14:40': 0.90, '14:50': 0.95}
progress = TIME_PROGRESS.get(TIME_LABEL, 0.95)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]

dates_n = all_dates[-N:]
extended = all_dates[all_dates.index(dates_n[0])-6:all_dates.index(dates_n[-1])+1]

# 加载数据 — 包含OHLC
data = {}
for dt in extended:
    c.execute('SELECT code, name, p, cl, vr, n, dif_val, macd_golden, wr_val, j_val, k_val, d_val, pos_in_day, above_ma5, kdj_golden, close, volume, high, low FROM data_cache WHERE date=?', (dt,))
    cols = ['code','name','p','cl','vr','n','dif_val','macd_golden','wr_val','j_val','k_val','d_val','pos_in_day','above_ma5','kdj_golden','close','volume','high','low']
    data[dt] = [dict(zip(cols, row)) for row in c.fetchall()]

# 加载前一天收盘价(prev_close)
c.execute('SELECT code, close FROM data_cache WHERE date=?', (all_dates[all_dates.index(dates_n[0])-1],))
prev_closes = {r[0]: r[1] or 0 for r in c.fetchall()}
# 补充更多天的prev_close
for dt in dates_n:
    idx = all_dates.index(dt)
    if idx > 0:
        c.execute('SELECT code, close FROM data_cache WHERE date=?', (all_dates[idx-1],))
        for r in c.fetchall():
            if r[0] not in prev_closes: prev_closes[r[0]] = r[1] or 0

features = {}
for dt in dates_n:
    c.execute('SELECT * FROM features_cache WHERE date=?', (dt,))
    fcols = [desc[0] for desc in c.description]
    for row in c.fetchall():
        f = dict(zip(fcols, row))
        features[(f['code'], dt)] = f

c.execute('SELECT code, hsl, shizhi FROM data_stock_info')
stock_info = {r[0]: {'hsl': r[1] or 0, 'shizhi': r[2] or 0} for r in c.fetchall()}

MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4']

def estimate_p_at_time(s, dt):
    """估算指定时间的实时涨幅"""
    close_p = s.get('p', 0) or 0  # 收盘涨幅
    # 用close+open估计日内进度
    # 更精确：open ≈ prev_close * (1 + morning_move)
    # 但data_cache没存open，用close和high/low估算
    high = s.get('high', 0) or 0
    low = s.get('low', 0) or 0
    close = s.get('close', 0) or 0
    code = s['code']
    prev_close = prev_closes.get(code, 0)
    
    if prev_close <= 0 or close <= 0:
        return close_p  # fallback
    
    # 估算开盘价：从p和close反推
    # p = (close - prev_close) / prev_close * 100
    # 思路：用close和p是确定的，日内价格按比例
    est_price = prev_close * (1 + close_p / 100 * progress)
    est_p = (est_price - prev_close) / prev_close * 100
    return round(est_p, 2)

def estimate_vr_at_time(s):
    """估算当前的量比 — 按时间比例缩"""
    vr_day = s.get('vr', 1) or 1
    # 到2:30完成了85%交易时间，量也应该是85%
    return round(vr_day * progress, 2)

def mkt_class(ss):
    if not ss: return 'flat'
    ps = [s.get('_p_est', 0) for s in ss if abs(s.get('_p_est', 0)) < 15]
    vrs = [s.get('_vr_est', 1) for s in ss if s.get('_vr_est', 0)]
    if not ps: return 'flat'
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

def is_momentum_exhausted(s, code, dt):
    feats = features.get((code, dt), {})
    if not feats: return False
    sl5 = feats.get('slope5', 0); t4s = feats.get('t4_shadow', 0); cu = feats.get('cons_up', 0)
    pk = feats.get('peak_decay', 0); pv = s.get('_p_est', 0)
    if sl5 > 8 and t4s > 25: return True
    if sl5 > 10 and t4s > 18: return True
    if cu >= 5 and sl5 > 15: return True
    if pk > 5 and sl5 > 5 and pv < 6: return True
    if sl5 > 5 and t4s > 30: return True
    if cu >= 4 and sl5 > 10 and pv < 7: return True
    return False

def compute_7day_penalty(code, dt, p_today):
    ad = sorted(data.keys())
    try: idx = ad.index(dt)
    except: return 0
    prev = ad[max(0, idx-6):idx]
    gains = []
    for pd in prev:
        found = False
        for s in data.get(pd, []):
            if s['code'] == code:
                p_close = s.get('p', 0) or 0
                gains.append(p_close)
                found = True; break
        if not found: gains.append(0)
    gains.append(p_today)
    n = len(gains)
    if n < 5: return 0
    d6, d5, d4, d3, d2, d1, p_ = gains[-7:] if n >= 7 else [0]*(7-n)+gains[-n:]
    p_is_max = p_ >= max(gains[:-1])
    avg_7d = sum(gains)/n
    penalty = 0
    wrv = 50
    for s in data.get(dt, []):
        if s['code'] == code: wrv = s.get('wr_val', 50) or s.get('wrv', 50); break
    if wrv < 10 and p_is_max and avg_7d < 2.0 and p_ < 6: penalty -= 8
    if p_is_max and avg_7d < 0.8 and p_ < 8:
        if avg_7d < 0: penalty -= 15
        elif avg_7d < 0.3: penalty -= 12
        elif avg_7d < 0.7: penalty -= 8
        else: penalty -= 5
    if n >= 6 and d1 < -1.5 and d2 < -1.0 and p_ > 3 and avg_7d < 1.0: penalty -= 8
    if len(gains) >= 7 and max(d4, d3, d2) > 5 and d1 < 0 and d2 < 0: penalty -= 10
    if n >= 5 and d5 > d1 and d5 > d2 and p_ <= d5:
        rs = (d4 + d3 + d2 + d1) if n >= 6 else (d3 + d2 + d1)
        if rs <= 2: penalty -= 8
    if n >= 5 and all(gains[-5+i] >= gains[-4+i] for i in range(4)): penalty -= 10
    return penalty

def v10_score(s, code, dt, mk_cn):
    mod = STRATS[mk_cn]; stock = {}
    stock['p'] = s.get('_p_est', 0)
    stock['cl'] = s.get('cl', 50)
    stock['vr'] = s.get('_vr_est', 1)
    stock['dif'] = s.get('dif_val', 0) or s.get('dif', 0)
    stock['mg'] = s.get('macd_golden', 0) or s.get('mg', 0)
    stock['wrv'] = s.get('wr_val', 0) or s.get('wrv', 50)
    stock['jv'] = s.get('j_val', 0) or s.get('jv', 50)
    stock['kv'] = s.get('k_val', 0) or s.get('kv', 50)
    stock['dv'] = s.get('d_val', 0) or s.get('dv', 50)
    stock['a5'] = s.get('above_ma5', 0); stock['kdj_g'] = s.get('kdj_golden', 0) or s.get('kdj_g', 0)
    stock['pos_in_day'] = s.get('pos_in_day', 50)
    stock['nm'] = s.get('name', '') or ''
    si = stock_info.get(code, {}); stock['hsl'] = si.get('hsl', 0) or 0
    feats = features.get((code, dt), {})
    stock['t4_shadow'] = feats.get('t4_shadow', 0) if feats else 0
    stock['slope5'] = feats.get('slope5', 0) if feats else 0
    stock['cons_up'] = feats.get('cons_up', 0) if feats else 0
    stock['d1'] = feats.get('d1', 0) if feats else 0
    stock['d2'] = feats.get('d2', 0) if feats else 0
    stock['d3'] = feats.get('d3', 0) if feats else 0
    penalty = compute_7day_penalty(code, dt, s.get('_p_est', 0))
    return round(mod.score(stock) + penalty, 1)

wi = 0; ta = 0; confirmed_ta = 0
results = []
mk_s = {k: [0, 0] for k in ['real_up', 'fake_up', 'down', 'flat']}

print(f'⏰ {TIME_LABEL} 回测 (进度{int(progress*100)}%)')
print(f'='*55)

for dt in reversed(dates_n):
    ss = data.get(dt, [])
    # 估算实时p和vr
    for s in ss:
        s['_p_est'] = estimate_p_at_time(s, dt)
        s['_vr_est'] = estimate_vr_at_time(s)
    ss = [s for s in ss if abs(s.get('_p_est', 0)) < 15]
    if not ss: continue
    
    mk = mkt_class(ss); mk_cn = MK_MAP.get(mk, '横盘')
    mod = STRATS[mk_cn]; levels = mod.LEVELS
    lm = {l['name']: i for i, l in enumerate(levels)}
    pool = None
    for ln in LO:
        if ln not in lm: continue
        i = lm[ln]; lv = levels[i]; cand = []
        for s in ss:
            p = s['_p_est']
            if p < lv['p_min'] or p > min(lv.get('p_max', 10), 8): continue
            vr = s['_vr_est']
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            si = stock_info.get(s['code'], {}); hsl = si.get('hsl', 0) or 0
            if hsl < lv.get('hs_min', 0) or hsl > lv.get('hs_max', 99): continue
            if (si.get('shizhi', 0) or 0) >= lv.get('sz_max', 9999): continue
            nm = s.get('name', '')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl = s.get('cl', 0)
            if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
            if is_momentum_exhausted(s, s['code'], dt): continue
            cand.append(s)
        if len(cand) >= 10: pool = cand; break
    if not pool: continue
    scored = [(v10_score(s, s['code'], dt, mk_cn), s) for s in pool]
    scored.sort(key=lambda x: -x[0])
    champ = scored[0][1]; nh = champ.get('n', 0) or 0
    has_next = (dt != dates_n[-1])
    mk_s[mk][1] += 1
    if has_next:
        win = '✅' if nh >= 2.5 else '❌'
        if win == '✅': wi += 1; mk_s[mk][0] += 1
        confirmed_ta += 1
    else:
        win = '⏳'
    ta += 1
    cname = champ.get('name', '') or champ.get('nm', '')
    results.append((dt, mk_cn, cname, round(champ['_p_est'], 1), round(scored[0][0], 1), round(nh, 1), win))

total_pct = wi * 100 / confirmed_ta if confirmed_ta else 0
print(f'{TIME_LABEL} {N}天: {wi}/{confirmed_ta} = {total_pct:.1f}% | 待验证: {ta - confirmed_ta}天')

mk_names = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
for mk in ['real_up','fake_up','down','flat']:
    w, t = mk_s[mk]
    if t: print(f'  {mk_names[mk]}: {w}/{t} = {w*100/t:.1f}%')

# 和2:50收盘对比
c.execute('SELECT COUNT(*), SUM(CASE WHEN result=\"✅\" THEN 1 ELSE 0 END) FROM backtest_results WHERE strategy_version=? AND result!=\"⏳\"', (f'V13_{N}d',))
close_r = c.fetchone()
if close_r and close_r[0]:
    print(f'\n对比 收盘: {close_r[1]}/{close_r[0]}={close_r[1]*100/close_r[0]:.1f}% ↔ {TIME_LABEL} {wi}/{confirmed_ta}={total_pct:.1f}%')

conn.close()
