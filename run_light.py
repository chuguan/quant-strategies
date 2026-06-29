"""
轻量版尾盘选股 — 从data_cache(当天实时)读数据 + 策略模块打分
不做全市场API扫 + 不跑回测
用法: python run_light.py V13
       python run_light.py V42
       python run_light.py V50
"""
import sqlite3, os, sys, importlib
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
today = datetime.now().strftime('%Y-%m-%d')

STRAT_DIRS = {
    'V13': os.path.join(SCRIPTS_DIR, 'strategies', 'V13'),
    'V42': os.path.join(SCRIPTS_DIR, 'strategies', 'V42'),
    'V50': os.path.join(SCRIPTS_DIR, 'strategies', 'V50'),
}

MK_MAP = {'real_up': '真实涨日', 'fake_up': '虚涨日', 'down': '跌日', 'flat': '横盘'}
MK_LIST = ['真实涨日', '虚涨日', '跌日', '横盘']

name = sys.argv[1] if len(sys.argv) > 1 else 'V13'
strat_dir = STRAT_DIRS.get(name)
if not strat_dir:
    print(f'❌ 未知策略: {name}')
    sys.exit(1)

sys.path.insert(0, strat_dir)
STRATS = {}
for n in MK_LIST:
    fp = os.path.join(strat_dir, '评分策略', f'分而治之_V10_{n}_评分策略.py')
    if not os.path.exists(fp):
        continue
    spec = importlib.util.spec_from_file_location(n, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    STRATS[n] = m

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 用当天数据（data_cache在14:30/14:42已预热写入）
use_date = today

# 大盘行情类型
c.execute("SELECT market FROM market_days WHERE date=?", (use_date,))
mkt = c.fetchone()
mk = mkt[0] if mkt else 'flat'
mk_cn = MK_MAP.get(mk, '横盘')

mod = STRATS.get(mk_cn)
if not mod:
    print(f'❌ 无{mk_cn}策略')
    sys.exit(1)

# 读 data_cache(当天实时) + JOIN data_stock_info(hsl/shizhi)
rows = c.execute('''
    SELECT dc.code, dc.name, dc.p, dc.close, dc.cl, dc.vr, 
           dc.dif_val, dc.wr_val, dc.j_val, dc.k_val, dc.d_val,
           dc.above_ma5, dc.pos_in_day, dc.high, dc.low,
           dsi.hsl, dsi.shizhi
    FROM data_cache dc
    LEFT JOIN data_stock_info dsi ON dc.code = dsi.code
    WHERE dc.date=? AND dc.close>0 AND dc.name IS NOT NULL
    ORDER BY dc.code
''', (use_date,)).fetchall()

cols = ['code','name','p','close','cl','vr',
        'dif','wr','j_val','k_val','d_val',
        'above_ma5','pos_in_day','high','low',
        'hsl','shizhi']

def to_stock(r):
    s = dict(zip(cols, r))
    s['nm'] = s['name']
    s['a5'] = s.pop('above_ma5', 0)
    s['pos'] = s.pop('pos_in_day', 50)
    s['sz'] = s.pop('shizhi', 0) or 0
    s['j'] = s.pop('j_val', 50)
    s['k'] = s.pop('k_val', 50)
    s['d'] = s.pop('d_val', 50)
    s['dif'] = s.pop('dif', 0) or 0
    s['wr'] = s.pop('wr', 50) or 50
    s['hsl'] = s.pop('hsl', 0) or 0
    s['cl'] = s.get('cl', 50) or 50
    s['vr'] = s.get('vr', 1) or 1
    s['p'] = s.get('p', 0) or 0
    return s

stocks = [to_stock(r) for r in rows]
print(f'股票池: {len(stocks)}只')

# 应用LEVELS + 评分
LEVELS = mod.LEVELS if hasattr(mod, 'LEVELS') else []
picked = []
used_level = 'L4'

for lv in LEVELS:
    pool = []
    for s in stocks:
        pct = s.get('p', 0) or 0
        vr = s.get('vr', 1) or 1
        hsl = s.get('hsl', 0) or 0
        cl = s.get('cl', 50) or 50
        sz = s.get('sz', 0) or 0
        
        ok = True
        if 'p_min' in lv and pct < lv['p_min']: ok = False
        if 'p_max' in lv and pct > lv['p_max']: ok = False
        if 'vr_min' in lv and vr < lv['vr_min']: ok = False
        if 'vr_max' in lv and vr > lv['vr_max']: ok = False
        if 'hs_min' in lv and hsl < lv['hs_min']: ok = False
        if 'hs_max' in lv and hsl > lv['hs_max']: ok = False
        if 'sz_max' in lv and sz > lv['sz_max'] and lv['sz_max'] > 0: ok = False
        if 'cl_min' in lv and cl < lv['cl_min']: ok = False
        if 'cl_max' in lv and cl > lv['cl_max']: ok = False
        if not ok: continue
        
        sc = mod.score(s)
        if sc > 0:
            pool.append((sc, s))
    
    if len(pool) >= 10:
        pool.sort(key=lambda x: -x[0])
        picked = pool[:10]
        used_level = lv.get('name', 'L0')
        break
    elif len(pool) >= 3:
        pool.sort(key=lambda x: -x[0])
        picked = pool[:10]
        used_level = lv.get('name', 'L0')
        break

if not picked:
    print(f'❌ 候选不足')
    conn.close()
    sys.exit(0)

# 输出TOP10
print(f'级别: {used_level}')
print(f'')
print(f'{"#":<3}{"代码":<8}{"名称":<10}{"得分":<7}{"涨幅%":<7}{"位置":<7}{"换手":<7}{"DIF":<8}{"J值":<7}{"量比":<7}')
print('-' * 70)
for i, (sc, s) in enumerate(picked):
    print(f'{i+1:<3}{s["code"]:<8}{s["name"]:<10}{sc:<7.1f}{s["p"]:<+7.2f}{s["cl"]:<7.1f}{s["hsl"]:<7.2f}{s["dif"]:<8.4f}{s["j"]:<7.0f}{s["vr"]:<7.2f}')

champ = picked[0][1]
print(f'')
print(f'🏆 {champ["name"]}({champ["code"]}) 得分={picked[0][0]} p={champ["p"]:+.2f}% cl={champ["cl"]} hsl={champ["hsl"]}%')

# 保存到selection_candidates
t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
for i, (sc, s) in enumerate(picked):
    c.execute('''INSERT OR REPLACE INTO selection_candidates
        (date, run_time, version, rank, code, name, price, pct, score, cl, vr, hsl, dif, wr)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (use_date, t, name, i+1, s['code'], s['nm'], s.get('close',0),
         s.get('p',0), round(sc,1), s.get('cl',50), s.get('vr',1),
         s.get('hsl',0), s.get('dif',0), s.get('wr',50)))
conn.commit()
print(f'✅ 已保存{len(picked)}条到selection_candidates')
conn.close()
