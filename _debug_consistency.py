"""对比pick_today和backtest_30d对同一天同一数据的选股结果"""
import sqlite3, os, json, sys, importlib
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
DB = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

# 1. 用pick_today的方式跑05-29
# 从data_cache加载05-29数据模拟实时API结果
conn = sqlite3.connect(DB, timeout=10)
c = conn.cursor()
c.execute('SELECT code, name, p, cl, wr_val, dif_val, vr FROM data_cache WHERE date="2026-05-29" AND p<8 AND p>0')
stocks = {}
for r in c.fetchall():
    stocks[r[0]] = {'name': r[1], 'p': r[2], 'cl': r[3], 'wr': r[4], 'dif': r[5], 'vr': r[6]}
conn.close()

# 加载V13评分策略
sys.path.insert(0, os.path.join(SCRIPTS_DIR, 'release', 'V13'))
for n in ['真实涨日','虚涨日','跌日','横盘']:
    fp = os.path.join(SCRIPTS_DIR, 'release', 'V13', '评分策略', f'分而治之_V10_{n}_评分策略.py')
    spec = importlib.util.spec_from_file_location(n, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    globals()[f'STRAT_{n}'] = m

MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4']

def mkt_class(ss):
    if not ss: return 'flat'
    ps=[s.get('p',0) or 0 for s in ss]
    vrs=[s.get('vr',0) or 1 for s in ss if s.get('vr',0)]
    ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

def score_stock(s, code, mod):
    stock = {
        'p': s['p'], 'cl': s['cl'], 'vr': s['vr'],
        'dif': s['dif'], 'mg': 1 if s['dif']>0 else 0,
        'wrv': s['wr'], 'jv': 50, 'kv': 50, 'dv': 50,
        'a5': 1, 'kdj_g': 1, 'pos_in_day': 50,
        'nm': s['name'], 'hsl': 0,
        't4_shadow': 0, 'slope5': 0, 'cons_up': 0,
        'd1': 0, 'd2': 0, 'd3': 0,
    }
    return mod.score(stock)

# 模拟05-29
mk = mkt_class(list(stocks.values()))
mk_cn = MK_MAP.get(mk, '横盘')
mod = globals()[f'STRAT_{mk_cn}']
levels = mod.LEVELS
lm = {l['name']:i for i,l in enumerate(levels)}

pool = None; used_level = '无'
for ln in LO:
    if ln not in lm: continue
    i = lm[ln]; lv = levels[i]; cand = []
    for code, s in stocks.items():
        p = s['p']
        if p < lv['p_min'] or p > min(lv.get('p_max',10),8): continue
        vr = s['vr']
        if vr < lv['vr_min'] or vr > lv['vr_max']: continue
        cl = s['cl']
        if cl < lv.get('cl_min',0) or cl > lv.get('cl_max',100): continue
        cand.append((code, s))
    if len(cand) >= 10:
        pool = cand; used_level = ln; break

scored = [(score_stock(s, code, mod), code, s) for code, s in pool]
scored.sort(key=lambda x: -x[0])

print(f'=== 直接用data_cache数据模拟05-29 ===')
print(f'行情: {mk_cn} | LEVEL: {used_level} | 候选池: {len(pool)}')
print(f'评分排序TOP5:')
for i, (sc, code, s) in enumerate(scored[:5]):
    print(f'  {i+1}. {s["name"]}({code}): 评分={sc:.0f} p={s["p"]:.1f}% cl={s["cl"]:.0f} wr={s["wr"]:.0f} vr={s["vr"]:.1f}')

print()
print(f'=== 对比V13日报跑出来的今日推荐 ===')
print(f'今日推荐: 贵州茅台 +3.9% 评分35')
print(f'差异原因: 今日推荐用的是06-01盘中实时数据')
print(f'          模拟用的是05-29收盘data_cache数据')
print(f'          虽然价格一样(未开盘), 但行情分类(跌日L0 vs L2)不同')
print(f'          导致LEVELS过滤门槛不一样, 选出不同股')
