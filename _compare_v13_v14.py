#!/usr/bin/env python3
"""V13 vs V14 对比回测 — 同数据源(SQLite) + 各自评分策略"""
import sqlite3, os, sys, importlib
from datetime import datetime, timedelta

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

def load_strats(base_dir):
    """加载4个行情的评分模块"""
    STRATS = {}
    for n in ['真实涨日','虚涨日','跌日','横盘']:
        fp = os.path.join(base_dir, '评分策略', f'分而治之_V10_{n}_评分策略.py')
        spec = importlib.util.spec_from_file_location(n, fp)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        STRATS[n] = m
    return STRATS

MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4']

def mkt_class(ss):
    if not ss: return 'flat'
    ps = [s.get('p',0) or 0 for s in ss]
    vrs = [s.get('vr',0) or 1 for s in ss if s.get('vr',0)]
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

def backtest_version(base_dir, label, data, dates, features, stock_info):
    """对指定版本回测"""
    STRATS = load_strats(base_dir)
    total = 0; wins = 0; mk_s = {'real_up':[0,0],'fake_up':[0,0],'down':[0,0],'flat':[0,0]}
    
    for dt in dates:
        ss = data.get(dt,[])
        ss = [s for s in ss if (s.get('p',0) or 0)<15]
        if not ss: continue
        mk = mkt_class(ss); mk_cn = MK_MAP.get(mk,'横盘')
        mod = STRATS[mk_cn]; levels = mod.LEVELS
        lm = {l['name']:i for i,l in enumerate(levels)}
        pool = None
        for ln in LO:
            if ln not in lm: continue
            i = lm[ln]; lv = levels[i]; cand = []
            for s in ss:
                p = s.get('p',0) or 0
                if p<lv['p_min'] or p>min(lv.get('p_max',10),8): continue
                vr = s.get('vr',0) or s.get('vol_ratio',0) or 0
                if vr<lv['vr_min'] or vr>lv['vr_max']: continue
                si = stock_info.get(s['code'],{}); hsl = si.get('hsl',0) or 0
                if hsl<lv.get('hs_min',0) or hsl>lv.get('hs_max',99): continue
                if (si.get('shizhi',0) or 0)>=lv.get('sz_max',9999): continue
                nm = s.get('name','')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl = s.get('cl',0)
                if cl<lv.get('cl_min',0) or cl>lv.get('cl_max',100): continue
                cand.append(s)
            if len(cand)>=10: pool=cand; break
        if not pool: continue
        
        scored = []
        for s in pool:
            stock = {
                'p': s.get('p',0) or 0,
                'cl': s.get('cl',50),
                'vr': s.get('vr',1) or s.get('vol_ratio',1),
                'dif': s.get('dif_val',0) or s.get('dif',0),
                'mg': s.get('macd_golden',0) or s.get('mg',0),
                'wrv': s.get('wr_val',0) or s.get('wrv',50),
                'jv': s.get('j_val',0) or s.get('jv',50),
                'kv': s.get('k_val',0) or s.get('kv',50),
                'dv': s.get('d_val',0) or s.get('dv',50),
                'a5': s.get('above_ma5',0),
                'kdj_g': s.get('kdj_golden',0) or s.get('kdj_g',0),
                'pos_in_day': s.get('pos_in_day',50),
                'nm': s.get('name','') or '',
                'hsl': stock_info.get(s['code'],{}).get('hsl',0) or 0,
                't4_shadow': 0, 'slope5': 0, 'cons_up': 0,
                'd1': 0, 'd2': 0, 'd3': 0,
            }
            feats = features.get((s['code'], dt), {})
            stock['d1'] = feats.get('d1',0)
            stock['d2'] = feats.get('d2',0)
            stock['d3'] = feats.get('d3',0)
            
            sc = mod.score(stock)
            scored.append((sc, s))
        
        scored.sort(key=lambda x:-x[0])
        champ = scored[0][1]
        nh = champ.get('n',0) or 0
        
        total += 1; mk_s[mk][1] += 1
        if nh >= 2.5:
            wins += 1; mk_s[mk][0] += 1
    
    return wins, total, mk_s

# 主流程
print('▶ 加载数据...')
conn = sqlite3.connect(DB, timeout=30)

# 所有交易日
c = conn.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]
all_dates = [d for d in all_dates if d < '2026-06-01']  # 排除今天(测试数据)
print(f'  {len(all_dates)}个交易日')

# 加载全量数据
data = {}
for dt in all_dates:
    c = conn.execute('SELECT * FROM data_cache WHERE date=?', (dt,))
    cols = [d[0] for d in c.description]
    data[dt] = [dict(zip(cols, row)) for row in c.fetchall()]

# 加载特征
features = {}
for dt in all_dates[-150:]:  # 最近150天有特征数据的
    c = conn.execute('SELECT * FROM features_cache WHERE date=?', (dt,))
    fcols = [d[0] for d in c.description]
    for row in c.fetchall():
        f = dict(zip(fcols, row))
        features[(f['code'], dt)] = f

# 股票信息
c = conn.execute('SELECT code, hsl, shizhi FROM data_stock_info')
stock_info = {r[0]: {'hsl':r[1] or 0, 'shizhi':r[2] or 0} for r in c.fetchall()}
conn.close()

# 按各区间回测
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
V14_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V14')

windows = [30, 50, 100]
print(f'\n▶ 回测对比...')
print(f'{"版本":>10} | {"30天":>15} | {"50天":>15} | {"100天":>15}')
print('-' * 60)

for label, base_dir in [('V13', V13_DIR), ('V14', V14_DIR)]:
    results = []
    for w in windows:
        if len(all_dates) < w:
            dates = all_dates
        else:
            dates = all_dates[-w:]
        wi, ta, mk_s = backtest_version(base_dir, label, data, dates, features, stock_info)
        rate = wi*100/ta if ta else 0
        results.append(f'{wi}/{ta}={rate:.0f}%')
    print(f'{label:>10} | {results[0]:>15} | {results[1]:>15} | {results[2]:>15}')

# 分行情
print(f'\n▶ 分行情详情（最近100天）:')
dates_100 = all_dates[-100:] if len(all_dates) >= 100 else all_dates
results_v13 = backtest_version(V13_DIR, 'V13', data, dates_100, features, stock_info)
results_v14 = backtest_version(V14_DIR, 'V14', data, dates_100, features, stock_info)

mk_names = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
print(f'{"行情":>8} | {"V13":>12} | {"V14":>12} | 差异')
for k, cn in mk_names.items():
    w13, t13 = results_v13[0] if k == 'real_up' else (results_v13[2][k][0], results_v13[2][k][1])
    w14, t14 = results_v14[0] if k == 'real_up' else (results_v14[2][k][0], results_v14[2][k][1])
    
for k, cn in mk_names.items():
    w13 = results_v13[2][k][0]; t13 = results_v13[2][k][1]
    w14 = results_v14[2][k][0]; t14 = results_v14[2][k][1]
    r13 = f'{w13*100//t13}%' if t13 else '-'
    r14 = f'{w14*100//t14}%' if t14 else '-'
    diff = f'{(w14/t14*100 - w13/t13*100):+.0f}%' if t13 and t14 else '-'
    print(f'{cn:>8} | V13 {r13:>6} ({w13}/{t13}) | V14 {r14:>6} ({w14}/{t14}) | {diff}')

print(f'\n{"总计":>8} | V13 {results_v13[0]*100//results_v13[1]}% ({results_v13[0]}/{results_v13[1]}) | V14 {results_v14[0]*100//results_v14[1]}% ({results_v14[0]}/{results_v14[1]}) | {results_v14[0]*100//results_v14[1] - results_v13[0]*100//results_v13[1]:+d}%')
print('✅ 完成')
