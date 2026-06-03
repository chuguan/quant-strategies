"""V13 回测 — 全SQLite版，匹配原版100%"""
import sqlite3, os, sys, importlib
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')

print('连接数据库...')
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# █ 获取所有日期
c.execute('SELECT DISTINCT date FROM data_cache ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]
print(f'日期: {all_dates[0]}~{all_dates[-1]} ({len(all_dates)}天)')

# 使用最新50天
backtest_dates = [d for d in all_dates if d >= '2025-01-01']
dates_50 = backtest_dates[-50:]
# 多取前6天用于7天衰减计算
extended = all_dates[all_dates.index(dates_50[0])-6:all_dates.index(dates_50[-1])+1] if dates_50[0] in all_dates else dates_50
recent = extended
print(f'回测: {dates_50[0]}~{dates_50[-1]} ({len(dates_50)}天)')

# █ 加载数据
print('加载50天数据...')
data = {}
for dt in recent:
    c.execute('SELECT * FROM data_cache WHERE date=?', (dt,))
    cols = [desc[0] for desc in c.description]
    stocks = []
    for row in c.fetchall():
        s = dict(zip(cols, row))
        stocks.append(s)
    data[dt] = stocks

# █ 加载特征
print('加载特征...')
features = {}
for dt in dates_50:
    c.execute('SELECT * FROM features_cache WHERE date=?', (dt,))
    fcols = [desc[0] for desc in c.description]
    for row in c.fetchall():
        f = dict(zip(fcols, row))
        features[(f['code'], dt)] = f

# █ 构建names
names = {}
for dt in recent:
    for s in data.get(dt, []):
        code = s.get('code', '')
        nm = s.get('name', '') or ''
        if code and nm and code not in names:
            names[code] = nm

print(f'  数据: {sum(len(v) for v in data.values())}条, 特征: {len(features)}条')

# █ 加载股票基本信息(hsl/市值等)
conn2 = sqlite3.connect(DB_PATH)
c2 = conn2.cursor()
stock_info = {}
c2.execute('SELECT code, hsl, shizhi FROM data_stock_info')
for code, hsl, sz in c2.fetchall():
    stock_info[code] = {'hsl': hsl or 0, 'shizhi': sz or 0}
conn2.close()
print(f'  股票信息: {len(stock_info)}只')

# 关闭数据库连接
import sqlite3 as _sqlite3
# conn already used above, close it
conn.close()

# █ 市场分类(同原版)
def mkt_class(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vr', 0) or 0 for s in stocks if s.get('vr', 0)]
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

# █ 加载策略
def load_mod(name):
    fp = os.path.join(V13_DIR, '评分策略', f'分而治之_V10_{name}_评分策略.py')
    spec = importlib.util.spec_from_file_location('m', fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

STRATS = {}
for n in ['真实涨日', '虚涨日', '跌日', '横盘']:
    STRATS[n] = load_mod(n)
MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4']

# █ 动力衰竭过滤(同原版)
def is_momentum_exhausted(s, code, dt):
    feats = features.get((code, dt), {})
    if not feats: return False
    sl5 = feats.get('slope5', 0)
    t4s = feats.get('t4_shadow', 0)
    cu = feats.get('cons_up', 0)
    pk = feats.get('peak_decay', 0)
    pv = s.get('p', 0) or 0
    if sl5 > 8 and t4s > 25: return True
    if sl5 > 10 and t4s > 18: return True
    if cu >= 5 and sl5 > 15: return True
    if pk > 5 and sl5 > 5 and pv < 6: return True
    if sl5 > 5 and t4s > 30: return True
    if cu >= 4 and sl5 > 10 and pv < 7: return True
    return False

# █ 7天动量衰减(同原版)
def compute_7day_decay(code, dt, p_today):
    all_dates_sorted = sorted(data.keys())
    try: idx = all_dates_sorted.index(dt)
    except: return 0
    prev = all_dates_sorted[max(0,idx-6):idx]
    gains = []
    for pd in prev:
        found = False
        for s in data.get(pd, []):
            if s['code'] == code:
                gains.append(s.get('p', 0) or 0)
                found = True; break
        if not found: gains.append(0)
    gains.append(p_today)
    n = len(gains)
    if n < 5: return 0
    d6=d5=d4=d3=d2=d1=p = 0
    if n >= 7: d6,d5,d4,d3,d2,d1,p = gains[-7:]
    elif n >= 6: d5,d4,d3,d2,d1,p = gains[-6:]
    elif n >= 5: d4,d3,d2,d1,p = gains[-5:]
    p_is_max = p >= max(gains[:-1]) if len(gains) > 1 else True
    avg_7d = sum(gains)/n
    penalty = 0
    wrv = 50
    for s in data.get(dt, []):
        if s['code'] == code:
            wrv = s.get('wr_val', 50) or s.get('wrv', 50); break
    if wrv < 10 and p_is_max and avg_7d < 2.0 and p < 6: penalty -= 8
    if p_is_max and avg_7d < 0.8 and p < 8:
        if avg_7d < 0: penalty -= 15
        elif avg_7d < 0.3: penalty -= 12
        elif avg_7d < 0.7: penalty -= 8
        else: penalty -= 5
    if d1 < -1.5 and d2 < -1.0 and p > 3 and avg_7d < 1.0: penalty -= 8
    if max(d4, d3, d2) > 5 and d1 < 0 and d2 < 0: penalty -= 10
    if n >= 5 and d5 > d1 and d5 > d2 and p <= d5:
        recent_sum = (d4+d3+d2+d1) if n >= 6 else (d3+d2+d1)
        if recent_sum <= 2: penalty -= 8
    if n >= 5:
        last5 = gains[-5:]
        if all(last5[i] >= last5[i+1] for i in range(len(last5)-1)): penalty -= 10
    return penalty

# █ 回测
wi = 0; ta = 0; confirmed_pending = 0
results = []
print(f'\n===== V13 回测 ({dates_50[0]}~{dates_50[-1]}) =====')
print(f'{"日期":>12} {"行情":>5} {"冠军":>10} {"涨":>5} {"评分":>5} {"次日高":>6} {"结果"}')
print('-' * 55)

for dt in dates_50:
    ss = data.get(dt, [])
    ss = [s for s in ss if (s.get('p', 0) or 0) < 15]
    if not ss: continue
    
    mk = mkt_class(ss); mk_cn = MK_MAP.get(mk, '横盘')
    mod = STRATS[mk_cn]; LEVELS = mod.LEVELS
    lm = {l['name']:i for i,l in enumerate(LEVELS)}
    pool = None; eliminated = 0
    
    for ln in LO:
        if ln not in lm: continue
        i = lm[ln]; lv = LEVELS[i]; cand = []
        for s in ss:
            p = s.get('p', 0) or 0
            if p < lv['p_min'] or p > min(lv.get('p_max', 10), 8): continue
            vr = s.get('vr', 0) or 0
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            cl = s.get('cl', 0)
            if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
            nm = names.get(s['code'], '')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            if is_momentum_exhausted(s, s['code'], dt):
                eliminated += 1
                continue
            # n(次日高)仅用于结果验证，不参与选股筛选
            si = stock_info.get(s['code'], {})
            hsl = si.get('hsl', 0) or 0
            if hsl < lv.get('hs_min', 0) or hsl > lv.get('hs_max', 99): continue
            sz = si.get('shizhi', 0) or 0
            if sz >= lv.get('sz_max', 9999): continue
            cand.append(s)
        if len(cand) >= 10:
            pool = cand
            break
    
    if not pool:
        if eliminated > 3:
            pass  # 被过滤太多
        continue
    
    # 评分
    scored = []
    for s in pool:
        stock = {}
        stock['p'] = s.get('p', 0) or 0
        stock['cl'] = s.get('cl', 50)
        stock['vr'] = s.get('vr', 1) or s.get('vol_ratio', 1)
        stock['dif'] = s.get('dif_val', 0) or s.get('dif', 0)
        stock['mg'] = s.get('macd_golden', 0) or s.get('mg', 0)
        stock['wrv'] = s.get('wr_val', 0) or s.get('wrv', 50)
        stock['jv'] = s.get('j_val', 0) or s.get('jv', 50)
        stock['kv'] = s.get('k_val', 0) or s.get('kv', 50)
        stock['dv'] = s.get('d_val', 0) or s.get('dv', 50)
        stock['a5'] = s.get('above_ma5', 0)
        stock['kdj_g'] = s.get('kdj_golden', 0) or s.get('kdj_g', 0)
        stock['pos_in_day'] = s.get('pos_in_day', 50)
        stock['nm'] = names.get(s['code'], '')
        stock['hsl'] = stock_info.get(s['code'], {}).get('hsl', 0) or 0
        
        # 从features读取
        feats = features.get((s['code'], dt), {})
        stock['t4_shadow'] = feats.get('t4_shadow', 0)
        stock['slope5'] = feats.get('slope5', 0)
        stock['cons_up'] = feats.get('cons_up', 0)
        stock['d1'] = feats.get('d1', 0)
        stock['d2'] = feats.get('d2', 0)
        stock['d3'] = feats.get('d3', 0)
        
        base = mod.score(stock)
        penalty = compute_7day_decay(s['code'], dt, s.get('p', 0) or 0)
        scored.append((base + penalty, s))
    
    scored.sort(key=lambda x: -x[0])
    champ = scored[0][1]
    nh = champ.get('n', 0) or 0
    nm = names.get(champ['code'], '?')
    p = champ.get('p', 0)
    # 有D+1数据：显示实际次日高；没有：标待验证
    has_next = (dt != dates_50[-1])  # 非最新日都有D+1
    if has_next:
        nh_display = f'{nh:+.1f}%'
        win = '✅' if nh >= 2.5 else '❌'
        if win == '✅': wi += 1
    else:
        confirmed_pending += 1
        nh_display = '待验证'
        win = '⏳'
    ta += 1
    
    results.append((dt, mk_cn, nm, p, scored[0][0], nh_display, win))

# 从最新日期倒序输出
print(f'\n{"="*55}')
for r in reversed(results):
    print(f'{r[0]} {r[1]:>5} {r[2]:>10} {r[3]:>+5.1f} {r[4]:>5.0f} {r[5]:>8} {r[6]}')
 
print(f'{"="*55}')
print(f'50天: {wi}/{ta-confirmed_pending} = {wi*100/(ta-confirmed_pending):.1f}% (已确认) | 待验证: {confirmed_pending}天')
