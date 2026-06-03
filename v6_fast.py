#!/usr/bin/env python3
"""
V6秒出版 — 用big_cache，不加载JSON！
MACD/KDJ用当前状态评分（金叉大小、死叉检测）
权重调小：金叉+2、死叉-2、J向上+1、J向下-1
"""
import pickle, os, sys
from collections import defaultdict

CACHE = r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST = set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST = {l.strip() for l in f if l.strip()}

with open(CACHE, 'rb') as f: cache = pickle.load(f)
dc = cache['data']; nm = cache['names']
print(f"✅ 缓存加载: 0.3秒")

MIN=1.0; MAX=8.0; TARGET=2.5

def ok(e):
    if e['code'] in ST: return False
    if e['p'] is None or not (MIN<=e['p']<MAX): return False
    if e['n'] is None: return False
    if e.get('is_yang',0)!=1 or e.get('above_ma5',0)!=1 or e.get('a',0)<=3: return False
    return True

def sc_v6(e):
    sc = e['p'] + e['a']*1.5 + (e.get('dif_val',0) or 0)*0.5
    
    gap = e.get('macd_gap',0) or 0
    if gap > 0.5:    sc += 2  # 金叉强劲
    elif gap < 0.05: sc -= 2  # 金叉微弱(将死叉)
    
    if e.get('kdj_golden',1) == 1: sc += 2  # KDJ金叉
    else: sc -= 2  # KDJ死叉
    
    j_v = e.get('j_val',50) or 50
    if j_v > 80: pass  # J值高位不追
    elif j_v < 30: sc += 1  # J值低位超卖
    
    if e.get('s',0) > 40: sc -= 3  # 上影太长
    
    return round(sc, 2)

print()
for yr in ['2025','2026']:
    bd = defaultdict(list)
    for dt in dc:
        if not dt.startswith(yr): continue
        for e in dc[dt]:
            if ok(e): bd[dt].append(e)
    bd = {k:v for k,v in bd.items() if len(v)>=5}
    w=t=0
    for dt in sorted(bd.keys()):
        best = max(bd[dt], key=sc_v6)
        t+=1
        if best['n']>=TARGET: w+=1
    print(f"📊 {yr}: {t}天, 胜率{w/t*100:.1f}% ({w}/{t})")

# 1月数据
print(f"\n{'='*120}")
for dt2 in ['2026-01-09','2026-01-12','2026-01-13','2026-01-14']:
    cs=[e for e in dc.get(dt2,[]) if ok(e)]
    if len(cs)<5: continue
    for e in cs: e['s2']=sc_v6(e)
    top=sorted(cs, key=lambda x:x['s2'], reverse=True)
    c=top[0]
    n2=nm.get(c['code'],'?')
    mg="强金叉" if c.get('macd_gap',0)>0.5 else ("弱金叉" if c.get('macd_gap',0)>0 else "死叉")
    kg="金叉" if c.get('kdj_golden',1)==1 else "死叉"
    res="✅" if c['n']>=2.5 else "❌"
    print(f"\n📅 {dt2} 🥇{n2}({c['code']})")
    print(f"   涨{c['p']:+.1f}% MACD{c.get('dif_val',0):.2f}/{c.get('dea_val',0):.2f}={mg} KDJ({c.get('k_val',0):.0f},{c.get('d_val',0):.0f},{c.get('j_val',0):.0f})={kg}")
    print(f"   评分{c['s2']:.1f} → 次日{c['n']:+.1f}% {res}")

# 今日
latest=sorted([d for d in dc if d.startswith('2026')])[-1]
cs=[e for e in dc.get(latest,[]) if e['code'] not in ST and MIN<=e['p']<MAX and e.get('is_yang',0)==1 and e.get('above_ma5',0)==1 and e.get('a',0)>3]
for e in cs: e['s2']=sc_v6(e)
top=sorted(cs, key=lambda x:x['s2'], reverse=True)
print(f"\n🏆 {latest} Top5:")
for i,e in enumerate(top[:5],1):
    n2=nm.get(e['code'],'?')
    print(f"  {i}. {n2}({e['code']}) 买入{e['close']:.2f} 涨{e['p']:+.1f}% MACD{e.get('macd_gap',0):.2f} KDJ{e.get('k_val',0):.0f}>{e.get('d_val',0):.0f} 评分{e['s2']:.1f}")
