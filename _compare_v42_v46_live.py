#!/usr/bin/env python3
"""V42 vs V46 实时数据源对比"""
import sys, os, importlib
import numpy as np
import sqlite3

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

def load_strats(directory, label):
    strats = {}
    for n in ['真实涨日','虚涨日','跌日','横盘']:
        fp = os.path.join(directory, f'分而治之_V10_{n}_评分策略.py')
        spec = importlib.util.spec_from_file_location(f'{label}_{n}', fp)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        strats[n] = m
    return strats

V42_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V42', '评分策略')
V46_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V46', '评分策略')
v42_strats = load_strats(V42_DIR, 'V42')
v46_strats = load_strats(V46_DIR, 'V46')

MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}

DB = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
conn = sqlite3.connect(DB, timeout=5)
latest_date = conn.execute('SELECT MAX(date) FROM data_cache WHERE close>0').fetchone()[0]
print(f'数据日期: {latest_date}')

rows = conn.execute('''
    SELECT code, name, p, vr, cl, wr_val, dif_val, macd_golden, kdj_golden,
           j_val, k_val, d_val, above_ma5, close
    FROM data_cache WHERE date=? AND close>0 AND p<9 AND p>-7
''', (latest_date,)).fetchall()
print(f'总样本: {len(rows)}')

ps = [r[2] for r in rows if abs(r[2])<15]
vrs = [r[3] for r in rows if r[3]>0 and r[3]<5]
avg_p = sum(ps)/len(ps) if ps else 0
hot = sum(1 for p in ps if 5<=p<=8)
avg_vr = sum(vrs)/len(vrs) if vrs else 0
if avg_p > 0.5: mk = 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
elif avg_p < -0.5: mk = 'down'
else: mk = 'flat'
mk_cn = MK_MAP.get(mk, '横盘')
print(f'行情: {mk_cn} 均涨{avg_p:.2f}% 均量比{avg_vr:.2f}')
print()

v42_picks = []
v46_picks = []
for r in rows:
    code, name, p, vr, cl, wr, dif, mg, kg, jv, kv, dv, a5, close = r
    stock = {
        'p':p or 0,'vr':vr or 0,'cl':cl or 50,'wrv':wr or 50,
        'dif':dif or 0,'mg':mg or 0,'kdj_g':kg or 0,
        'jv':jv or 50,'kv':kv or 50,'dv':dv or 50,
        'a5':a5 or 0,'close':close or 0,'hsl':0,
        'pos_in_day':50,'nm':name,'name':name,
        't4_shadow':0,'slope5':0,'cons_up':0
    }
    s42 = v42_strats[mk_cn].score(stock)
    s46 = v46_strats[mk_cn].score(stock)
    if s42 > 0: v42_picks.append({'name':name,'code':code,'score':s42,'p':p,'vr':vr,'cl':cl})
    if s46 > 0: v46_picks.append({'name':name,'code':code,'score':s46,'p':p,'vr':vr,'cl':cl})

v42_picks.sort(key=lambda x: x['score'], reverse=True)
v46_picks.sort(key=lambda x: x['score'], reverse=True)

print(f'V42通过筛选: {len(v42_picks)}只')
print(f'V46通过筛选: {len(v46_picks)}只')
print()

# TOP10对比表
print(' V42 TOP10                          V46 TOP10')
print(' #  名称         评分   涨%   量比   CL   名称         评分   涨%   量比   CL')
print('-'*75)
for i in range(10):
    v = v42_picks[i] if i < len(v42_picks) else {'name':'','score':0,'p':0,'vr':0,'cl':0}
    w = v46_picks[i] if i < len(v46_picks) else {'name':'','score':0,'p':0,'vr':0,'cl':0}
    print(f'{i+1:>2}  {v["name"]:<6}({v["code"]}) {v["score"]:>5.0f} {v["p"]:>+4.1f} {v["vr"]:>4.1f} {v["cl"]:>4.0f}   {w["name"]:<6}({w["code"]}) {w["score"]:>5.0f} {w["p"]:>+4.1f} {w["vr"]:>4.1f} {w["cl"]:>4.0f}')

# 一致性分析
v42_top = [(p['name'],p['code'],p['score']) for p in v42_picks[:10]]
v46_top = [(p['name'],p['code'],p['score']) for p in v46_picks[:10]]
v42_names = set(p[0] for p in v42_top)
v46_names = set(p[0] for p in v46_top)
same_names = v42_names & v46_names
only_v42 = v42_names - v46_names
only_v46 = v46_names - v42_names

print(f'\n排名一致性:')
print(f'  TOP10完全相同: {len(same_names)}只')
if only_v42:
    print(f'  V42独有: {", ".join(only_v42)}')
if only_v46:
    print(f'  V46独有: {", ".join(only_v46)}')

# 选出但不同排名的
for s in same_names:
    v42_rank = next(i+1 for i,p in enumerate(v42_picks[:10]) if p['name']==s)
    v46_rank = next(i+1 for i,p in enumerate(v46_picks[:10]) if p['name']==s)
    if v42_rank != v46_rank:
        print(f'  {s}: V42#{v42_rank} -> V46#{v46_rank}')

conn.close()
