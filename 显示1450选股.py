"""V13 2026-05-29 14:50 选股结果"""
import sqlite3, os, sys, importlib
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
sys.path.insert(0, V13_DIR)

STRATS = {}
for n in ['真实涨日','虚涨日','跌日','横盘']:
    fp = os.path.join(V13_DIR, '评分策略', '分而治之_V10_%s_评分策略.py' % n)
    spec = importlib.util.spec_from_file_location(n, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    STRATS[n] = m

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]
idx = all_dates.index('2026-05-29')

prev_dates = [all_dates[idx-o] for o in range(1,8) if idx-o>=0]
c.execute('SELECT code, close FROM data_cache WHERE date=?', (all_dates[idx-1],))
prev_closes = {r[0]: r[1] or 0 for r in c.fetchall()}

c.execute('SELECT code,name,p,cl,vr,n,dif_val,macd_golden,wr_val,j_val,k_val,d_val,pos_in_day,above_ma5,kdj_golden,close FROM data_cache WHERE date="2026-05-29"')
cols = ['code','name','p','cl','vr','n','dif_val','macd_golden','wr_val','j_val','k_val','d_val','pos_in_day','above_ma5','kdj_golden','close']
stocks = [dict(zip(cols, row)) for row in c.fetchall()]

for s in stocks:
    cp = s.get('p',0) or 0
    pc = prev_closes.get(s['code'],0)
    cl = s.get('close',0) or 0
    if pc > 0 and cl > 0:
        ep = pc * (1 + cp/100*0.95)
        s['_p_est'] = round((ep-pc)/pc*100, 2)
    else:
        s['_p_est'] = cp
    s['_vr_est'] = round((s.get('vr',1) or 1) * 0.95, 2)

features = {}
c.execute('SELECT * FROM features_cache WHERE date="2026-05-29"')
fcols = [desc[0] for desc in c.description]
for row in c.fetchall():
    f = dict(zip(fcols, row))
    features[f['code']] = f

c.execute('SELECT code, hsl, shizhi FROM data_stock_info')
stock_info = {r[0]: {'hsl': r[1] or 0, 'shizhi': r[2] or 0} for r in c.fetchall()}

MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4']

def mkt_class(ss):
    ps = [s.get('_p_est',0) for s in ss if abs(s.get('_p_est',0)) < 15]
    vrs = [s.get('_vr_est',1) for s in ss if s.get('_vr_est',0)]
    if not ps: return 'flat'
    ap = sum(ps)/len(ps)
    av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if ap > 0.5:
        return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

def exhausted(s):
    ft = features.get(s['code'], {})
    if not ft: return False
    sl5 = ft.get('slope5',0); t4s = ft.get('t4_shadow',0); cu = ft.get('cons_up',0)
    pk = ft.get('peak_decay',0); pv = s.get('_p_est',0)
    if sl5>8 and t4s>25: return True
    if sl5>10 and t4s>18: return True
    if cu>=5 and sl5>15: return True
    if pk>5 and sl5>5 and pv<6: return True
    if sl5>5 and t4s>30: return True
    if cu>=4 and sl5>10 and pv<7: return True
    return False

def penalty(code, p_today):
    g = []
    for dt in sorted(prev_dates):
        r = c.execute('SELECT p FROM data_cache WHERE date=? AND code=?', (dt,code)).fetchone()
        g.append(r[0] if r and r[0] else 0)
    g.append(p_today)
    n = len(g)
    if n < 5: return 0
    short = g[-7:] if n >= 7 else [0]*(7-n) + g[-n:]
    d6,d5,d4,d3,d2,d1,p_ = short if n>=7 else [0]*(7-len(short))+short
    pm = p_ >= max(g[:-1])
    a7 = sum(g)/n
    pen = 0
    w = 50
    r = c.execute('SELECT wr_val FROM data_cache WHERE date="2026-05-29" AND code=?', (code,)).fetchone()
    if r: w = r[0] or 50
    if w<10 and pm and a7<2.0 and p_<6: pen -= 8
    if pm and a7<0.8 and p_<8:
        if a7<0: pen -= 15
        elif a7<0.3: pen -= 12
        elif a7<0.7: pen -= 8
        else: pen -= 5
    if n>=6 and d1<-1.5 and d2<-1.0 and p_>3 and a7<1.0: pen -= 8
    if len(g)>=7 and max(d4,d3,d2)>5 and d1<0 and d2<0: pen -= 10
    if n>=5 and d5>d1 and d5>d2 and p_<=d5:
        rs = (d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
        if rs<=2: pen -= 8
    if n>=5 and all(g[-5+i]>=g[-4+i] for i in range(4)): pen -= 10
    return pen

def v10_score(s, mk_cn):
    code = s['code']; mod = STRATS[mk_cn]; stock = {}
    stock['p'] = s.get('_p_est',0); stock['cl'] = s.get('cl',50)
    stock['vr'] = s.get('_vr_est',1)
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
    ft = features.get(code,{})
    for k in ['t4_shadow','slope5','cons_up','d1','d2','d3']:
        stock[k] = ft.get(k,0) if ft else 0
    pn = penalty(code, s.get('_p_est',0))
    return round(mod.score(stock)+pn, 1), round(pn, 1), round(mod.score(stock), 1)

mk = mkt_class(stocks)
mk_cn = MK_MAP.get(mk, '横盘')
mod = STRATS[mk_cn]
levels = mod.LEVELS
lm = {l['name']:i for i,l in enumerate(levels)}

print()
print('=' * 85)
print('  V13 2026-05-29 14:50 实时估算选股 | 行情: %s' % mk_cn)
print('=' * 85)

pool = None; used_level = '无'
for ln in LO:
    if ln not in lm: continue
    i = lm[ln]; lv = levels[i]; cand = []
    for s in stocks:
        p = s.get('_p_est',0)
        if p < lv['p_min'] or p > min(lv.get('p_max',10),8): continue
        vr = s.get('_vr_est',0)
        if vr < lv['vr_min'] or vr > lv['vr_max']: continue
        si = stock_info.get(s['code'],{}); hsl = si.get('hsl',0) or 0
        if hsl < lv.get('hs_min',0) or hsl > lv.get('hs_max',99): continue
        if (si.get('shizhi',0) or 0) >= lv.get('sz_max',9999): continue
        nm = s.get('name','')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        cl = s.get('cl',0)
        if cl < lv.get('cl_min',0) or cl > lv.get('cl_max',100): continue
        if exhausted(s): continue
        cand.append(s)
    if len(cand) >= 10:
        pool = cand; used_level = ln; break

if not pool:
    print('候选池不足')
    conn.close(); exit()

scored = [(v10_score(s, mk_cn), s) for s in pool]
scored.sort(key=lambda x: -x[0][0])

print('级 别: %s | 候选: %d只' % (used_level, len(pool)))
print('')
hdr = '%4s %10s %6s %8s %6s %4s %4s %6s %5s %6s' % ('排名','名称','代码','14:50涨','收盘涨','CL','WR','基础分','衰减','总分')
print(hdr)
print('-' * 85)

for rank, ((total, pn, base), s) in enumerate(scored[:15], 1):
    ep = s.get('_p_est',0); cp = s.get('p',0) or 0
    cl = s.get('cl',0) or 50; wr = s.get('wr_val',0) or s.get('wrv',50)
    mark = '🏆' if rank == 1 else ' '
    line = '%s%3d %10s %6s %+5.1f%% %+5.1f%% %3.0f %3.0f %6.1f %5.1f %6.1f' % (
        mark, rank, s['name'], s['code'], ep, cp, cl, wr, base, pn, total)
    print(line)

# 冠军次日高
champ = scored[0][1]
nh = champ.get('n',0) or 0
print('')
if nh >= 2.5:
    print('冠军 %s 次日高 %+.1f%% ✅ 达标' % (champ['name'], nh))
elif nh > 0:
    print('冠军 %s 次日高 %+.1f%% ❌ 未达标' % (champ['name'], nh))
else:
    print('冠军 %s 次日高待验证 ⏳' % champ['name'])

conn.close()
