"""V13 2026-05-29 全部候选 + 评分明细（回测版本一致）"""
import sqlite3, os, sys, importlib
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

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]
idx = all_dates.index('2026-05-29')
extended = all_dates[max(0,idx-6):idx+1]

# 加载数据（和回测一样）
data = {}
for dt in extended:
    c.execute('SELECT * FROM data_cache WHERE date=?', (dt,))
    cols = [desc[0] for desc in c.description]
    data[dt] = [dict(zip(cols, row)) for row in c.fetchall()]

# 特征
features = {}
c.execute('SELECT * FROM features_cache WHERE date="2026-05-29"')
fcols = [desc[0] for desc in c.description]
for row in c.fetchall():
    f = dict(zip(fcols, row))
    features[(f['code'], f['date'])] = f

c.execute('SELECT code, hsl, shizhi FROM data_stock_info')
stock_info = {r[0]: {'hsl': r[1] or 0, 'shizhi': r[2] or 0} for r in c.fetchall()}

MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4']

def mkt_class(ss):
    ps = [s.get('p',0) or 0 for s in ss if abs(s.get('p',0) or 0) < 15]
    vrs = [s.get('vr',0) or 1 for s in ss if s.get('vr',0)]
    if not ps: return 'flat'
    ap = sum(ps)/len(ps)
    av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

def is_momentum_exhausted(s, code, dt):
    feats = features.get((code, dt), {})
    if not feats: return False
    sl5 = feats.get('slope5',0); t4s = feats.get('t4_shadow',0); cu = feats.get('cons_up',0)
    pk = feats.get('peak_decay',0); pv = s.get('p',0) or 0
    if sl5>8 and t4s>25: return True
    if sl5>10 and t4s>18: return True
    if cu>=5 and sl5>15: return True
    if pk>5 and sl5>5 and pv<6: return True
    if sl5>5 and t4s>30: return True
    if cu>=4 and sl5>10 and pv<7: return True
    return False

def compute_7day_penalty(code, dt, p_today):
    ad = sorted(data.keys())
    try: idx2 = ad.index(dt)
    except: return 0
    prev = ad[max(0, idx2-6):idx2]
    gains = []
    for pd in prev:
        found = False
        for s in data.get(pd, []):
            if s['code'] == code:
                gains.append(s.get('p',0) or 0); found = True; break
        if not found: gains.append(0)
    gains.append(p_today)
    n = len(gains)
    if n < 5: return 0
    d6,d5,d4,d3,d2,d1,p_ = gains[-7:] if n >= 7 else [0]*(7-n)+gains[-n:]
    p_is_max = p_ >= max(gains[:-1]); avg_7d = sum(gains)/n
    penalty = 0; wrv = 50
    for s in data.get(dt, []):
        if s['code'] == code: wrv = s.get('wr_val',50) or s.get('wrv',50); break
    if wrv<10 and p_is_max and avg_7d<2.0 and p_<6: penalty -= 8
    if p_is_max and avg_7d<0.8 and p_<8:
        if avg_7d<0: penalty -= 15
        elif avg_7d<0.3: penalty -= 12
        elif avg_7d<0.7: penalty -= 8
        else: penalty -= 5
    if n>=6 and d1<-1.5 and d2<-1.0 and p_>3 and avg_7d<1.0: penalty -= 8
    if len(gains)>=7 and max(d4,d3,d2)>5 and d1<0 and d2<0: penalty -= 10
    if n>=5 and d5>d1 and d5>d2 and p_<=d5:
        rs = (d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
        if rs<=2: penalty -= 8
    if n>=5 and all(gains[-5+i]>=gains[-4+i] for i in range(4)): penalty -= 10
    return penalty

def v10_score(s, code, dt, mk_cn):
    mod = STRATS[mk_cn]; stock = {}
    stock['p'] = s.get('p',0) or 0; stock['cl'] = s.get('cl',50)
    stock['vr'] = s.get('vr',1) or s.get('vol_ratio',1)
    stock['dif'] = s.get('dif_val',0) or s.get('dif',0)
    stock['mg'] = s.get('macd_golden',0) or s.get('mg',0)
    stock['wrv'] = s.get('wr_val',0) or s.get('wrv',50)
    stock['jv'] = s.get('j_val',0) or s.get('jv',50)
    stock['kv'] = s.get('k_val',0) or s.get('kv',50)
    stock['dv'] = s.get('d_val',0) or s.get('dv',50)
    stock['a5'] = s.get('above_ma5',0); stock['kdj_g'] = s.get('kdj_golden',0) or s.get('kdj_g',0)
    stock['pos_in_day'] = s.get('pos_in_day',50)
    stock['nm'] = s.get('name','') or ''
    si = stock_info.get(code,{}); stock['hsl'] = si.get('hsl',0) or 0
    feats = features.get((code,dt),{})
    for k in ['t4_shadow','slope5','cons_up','d1','d2','d3']:
        stock[k] = feats.get(k,0) if feats else 0
    penalty = compute_7day_penalty(code, dt, s.get('p',0) or 0)
    return round(mod.score(stock) + penalty, 1), round(penalty, 1), round(mod.score(stock), 1)

dt = '2026-05-29'
ss = data.get(dt, [])
ss = [s for s in ss if abs(s.get('p',0) or 0) < 15]
mk = mkt_class(ss); mk_cn = MK_MAP.get(mk, '横盘')
mod = STRATS[mk_cn]; levels = mod.LEVELS
lm = {l['name']:i for i,l in enumerate(levels)}

pool = None; used_level = '无'
for ln in LO:
    if ln not in lm: continue
    i = lm[ln]; lv = levels[i]; cand = []
    for s in ss:
        p = s.get('p',0) or 0
        if p < lv['p_min'] or p > min(lv.get('p_max',10),8): continue
        vr = s.get('vr',0) or s.get('vol_ratio',0) or 0
        if vr < lv['vr_min'] or vr > lv['vr_max']: continue
        si = stock_info.get(s['code'],{}); hsl = si.get('hsl',0) or 0
        if hsl < lv.get('hs_min',0) or hsl > lv.get('hs_max',99): continue
        if (si.get('shizhi',0) or 0) >= lv.get('sz_max',9999): continue
        nm = s.get('name','')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        cl = s.get('cl',0)
        if cl < lv.get('cl_min',0) or cl > lv.get('cl_max',100): continue
        if is_momentum_exhausted(s, s['code'], dt): continue
        cand.append(s)
    if len(cand) >= 10: pool = cand; used_level = ln; break

if not pool:
    print('候选池不足')
    conn.close(); exit()

scored = [(v10_score(s, s['code'], dt, mk_cn), s) for s in pool]
scored.sort(key=lambda x: -x[0][0])

print('V13 2026-05-29 选股结果 | 行情: %s | 级别: %s | 候选: %d只' % (mk_cn, used_level, len(pool)))
print('')
print('%-4s %-10s %-6s %5s %5s %4s %4s %4s %6s %5s %5s %5s' % ('排名','名称','代码','涨','CL','WR','VR','HSL','基础分','衰减','总分','次日高'))
print('-' * 85)

for rank, ((total, pn, base), s) in enumerate(scored, 1):
    p = s.get('p',0) or 0; cl = s.get('cl',0) or 50
    wr = s.get('wr_val',0) or s.get('wrv',50)
    vr = s.get('vr',0) or 1; si = stock_info.get(s['code'],{}); hsl = si.get('hsl',0) or 0
    nh = s.get('n',0) or 0
    mark = '🏆' if rank == 1 else ' '
    nh_str = '%+.1f%%' % nh if nh != 0 else '待验证'
    print('%s%3d %-10s %-6s %+4.1f%% %3.0f %3.0f %3.1f %3.1f %6.1f %5.1f %5.1f %5s' % (
        mark, rank, s['name'], s['code'], p, cl, wr, vr, hsl, base, pn, total, nh_str))

print('')
print('冠军: %s | 评分 %.1f' % (scored[0][1]['name'], scored[0][0][0]))
print('次日高: 待验证 ⏳')
conn.close()
