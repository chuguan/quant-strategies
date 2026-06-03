#!/usr/bin/env python3
"""
逐个失败案例分析 —— 对每个失败冠军找"唯一特征"
目标是找到能精准抓住失败票但不误伤好票的条件
"""
import pickle, os, sys, importlib
import numpy as np
from collections import defaultdict

BASE = os.path.expanduser(r'~/AppData/Local/hermes/scripts')
V13_DIR = os.path.join(BASE, 'release', 'V13')
V45_DIR = os.path.join(BASE, 'release', 'V45')

with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d['real'], d['names']
with open(os.path.join(V13_DIR, 'features_30d.pkl'), 'rb') as f:
    precomputed = pickle.load(f)
all_dates = sorted(k for k in data.keys() if '2025-01-01' <= k <= '2026-05-28')[-200:]

def load_mod(fp):
    spec = importlib.util.spec_from_file_location(f'm_{os.path.basename(fp)}', fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

MODS={}
for cn in ['真实涨日','虚涨日','跌日','横盘']:
    fp=os.path.join(V45_DIR,'评分策略',f'分而治之_V10_{cn}_评分策略.py')
    if os.path.exists(fp): MODS[cn]=load_mod(fp)

def mkt_class(stocks):
    if not stocks: return 'flat'
    ps=[s.get('p',0) or 0 for s in stocks]
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'
MK_MAP={'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO=['L0','L1','L2','L3','L4']

# 跑200天回测，记录每日冠军特征
all_champs = []  # [{date, mk, code, name, score, n, p, cl, vr, dif, hsl, pos, wrv, slope5, t4s, ...}]

for dt in all_dates:
    stocks=data.get(dt,[])
    if not stocks: continue
    stocks=[s for s in stocks if (s.get('p',0) or 0)<15]
    if not stocks: continue
    mt=mkt_class(stocks); mk_cn=MK_MAP.get(mt,'横盘')
    mod=MODS.get(mk_cn)
    if not mod: continue
    LEVELS=mod.LEVELS; lm={l['name']:i for i,l in enumerate(LEVELS)}
    pool=None
    for ln in LO:
        if ln not in lm: continue
        i=lm[ln]; lv=LEVELS[i]; cand=[]
        for s in stocks:
            p=s.get('p',0) or 0
            if p<lv['p_min'] or p>min(lv.get('p_max',10),8): continue
            vr=s.get('vol_ratio',0) or 0
            if vr<lv['vr_min'] or vr>lv['vr_max']: continue
            ri=real.get(s['code'],{}); hsl=ri.get('hsl',0) or 0
            if hsl<lv.get('hs_min',0) or hsl>lv.get('hs_max',99): continue
            if (ri.get('shizhi',0) or 0)>=lv.get('sz_max',9999): continue
            nm=names.get(s['code'],'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl=s.get('cl',0)
            if cl<lv.get('cl_min',0) or cl>lv.get('cl_max',100): continue
            cand.append(s)
        if len(cand)>=10: pool=cand; break
    if not pool: continue
    
    scored=[]
    for s in pool:
        code=s.get('code','')
        feats=precomputed.get((code,dt),{})
        stock={
            'p':s.get('p',0) or 0,'cl':s.get('cl',50),
            'vr':s.get('vol_ratio',1) or s.get('vr',1),
            'dif':s.get('dif_val',0) or s.get('dif',0),
            'mg':s.get('macd_golden',0) or s.get('mg',0),
            'wrv':s.get('wr_val',0) or s.get('wrv',50),
            'jv':s.get('j_val',0) or s.get('jv',50),
            'kv':s.get('k_val',0) or s.get('kv',50),
            'dv':s.get('d_val',0) or s.get('dv',50),
            'a5':s.get('above_ma5',0),
            'kdj_g':s.get('kdj_golden',0) or s.get('kdj_g',0),
            'pos_in_day':s.get('pos_in_day',50),
            'nm':s.get('nm','') or s.get('name','') or names.get(code,''),
            'hsl':real.get(code,{}).get('hsl',0) or 0,
            'buy_c':s.get('close',0) or 0,
            't4_shadow':feats.get('t4_shadow',0),'slope5':feats.get('slope5',0),
            'cons_up':feats.get('cons_up',0),
        }
        sc=mod.score(stock)
        if sc>0: scored.append((sc,stock,s.get('n',0) or 0))
    if not scored: continue
    scored.sort(key=lambda x:-x[0])
    
    sc,stock,n=scored[0]
    all_champs.append({
        'date':dt,'market':mk_cn,'name':stock['nm'],'code':stock.get('nm',''),
        'score':round(sc,1),'n':round(n,1),
        'p':stock['p'],'cl':stock['cl'],'vr':stock['vr'],
        'dif':stock['dif'],'wrv':stock['wrv'],'hsl':stock['hsl'],
        'pos':stock['pos_in_day'],'t4s':stock['t4_shadow'],
        'sl5':stock['slope5'],'cons_up':stock['cons_up'],
        'passed':n>=2.5
    })

fails=[c for c in all_champs if not c['passed']]
wins=[c for c in all_champs if c['passed']]

print(f"总天数: {len(all_champs)}")
print(f"胜利: {len(wins)}, 失败: {len(fails)}")
print()

# 对每个失败案例，检查各种可能的"过滤条件"能不能抓住它
# 同时检查会不会误伤胜利的票
print("="*70)
print("  候选条件效果测试")
print("  目标：抓住失败票，少伤胜利票")
print("="*70)

# 各种候选条件
candidates = [
    ("cl>90", lambda c: c['cl'] > 90),
    ("cl>92", lambda c: c['cl'] > 92),
    ("p>5", lambda c: c['p'] > 5),
    ("p>5.5", lambda c: c['p'] > 5.5),
    ("p>6", lambda c: c['p'] > 6),
    ("cl>85,p>5", lambda c: c['cl'] > 85 and c['p'] > 5),
    ("cl>88,p>4.5", lambda c: c['cl'] > 88 and c['p'] > 4.5),
    ("cl>90,p>4.5", lambda c: c['cl'] > 90 and c['p'] > 4.5),
    ("hsl>15", lambda c: c['hsl'] > 15),
    ("hsl>18", lambda c: c['hsl'] > 18),
    ("p>5,hsl>12", lambda c: c['p'] > 5 and c['hsl'] > 12),
    ("p>5,hsl>15", lambda c: c['p'] > 5 and c['hsl'] > 15),
    ("pos<35", lambda c: c['pos'] < 35),
    ("pos>80,p>5", lambda c: c['pos'] > 80 and c['p'] > 5),
    ("dif<0,p>5", lambda c: c['dif'] < 0 and c['p'] > 5),
    ("vr<0.7", lambda c: c['vr'] < 0.7),
    ("vr<0.6", lambda c: c['vr'] < 0.6),
    ("wrv<10", lambda c: c['wrv'] < 10),  # 极度超买
    ("cl>85,wrv<15", lambda c: c['cl'] > 85 and c['wrv'] < 15),  # 高位超买
    ("sl5>15", lambda c: c['sl5'] > 15),
    ("sl5>12,t4s>20", lambda c: c['sl5'] > 12 and c['t4s'] > 20),
    ("cons_up>=4", lambda c: c['cons_up'] >= 4),
]

print(f"\n{'条件':>22} | {'抓失败':>10} | {'抓胜率':>10} | {'误伤胜利':>10} | {'净效果':>10}")
print("-"*70)

best = []
for name, func in candidates:
    caught_fails = sum(1 for c in fails if func(c))
    caught_wins = sum(1 for c in wins if func(c))
    fail_rate = caught_fails/len(fails)*100 if fails else 0
    win_rate = caught_wins/len(wins)*100 if wins else 0
    
    # 性价比 = 抓到的失败% - 误伤的胜利%
    # 净效果 = 抓到的失败数 - 误伤的胜利数
    net = caught_fails - caught_wins
    efficiency = fail_rate - win_rate
    
    mark = '✅' if net > 0 else '❌'
    print(f"  {name:>20} | {caught_fails:>3}/{len(fails):>3}({fail_rate:>4.0f}%) | {caught_wins:>3}/{len(wins):>3}({win_rate:>4.0f}%) | -{caught_wins:>3}胜 | {net:+3d} {mark}")
    best.append((net, name, caught_fails, caught_wins, fail_rate, win_rate, efficiency))

# 排序输出最佳条件
best.sort(key=lambda x:-x[0])
print(f"\n\n{'='*70}")
print(f"  🏆 最佳过滤条件排名（按净效果）")
print(f"{'='*70}")
print(f"\n{'排名':>4} | {'条件':>22} | {'抓失败':>8} | {'误伤胜利':>8} | {'净效果':>8} | {'性价比':>10}")
print("-"*60)
for i,(net,name,cf,cw,fr,wr,eff) in enumerate(best[:10]):
    print(f"  {i+1:>2}  | {name:>20} | {cf:>3}次 | -{cw:>3}次 | {net:>+3d}次 | {eff:>+7.1f}%")

print(f"\n{'='*70}")
print(f"  📊 解读")
print(f"{'='*70}")
print(f"""
  净效果 = 抓住的失败票 - 误伤的胜利票
  正数 = 这个条件抓到更多失败票而非误伤好票 → 有用
  负数 = 误伤太多好票 → 别用

  性价比 = 抓失败率% - 误伤胜率%
  反映这个条件是否"精准"
""")
