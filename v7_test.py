#!/usr/bin/env python3
"""
V7 — MACD/KDJ评分作为加分项（比例缩小）
基础分（涨跌幅×1+ATR×1.5+DIF×0.5）
+ MACD评分÷10（金叉+0.5、死叉-1.0）
+ KDJ评分÷10（金叉+0.5、向上+0.2、向下-0.5）
"""
import pickle, os, sys
from collections import defaultdict

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
dc=cache['data']; nm=cache['names']
print("✅ 缓存加载: 0.3秒")

MIN=1.0; MAX=8.0; TARGET=2.5

def ok(e):
    if e['code'] in ST: return False
    if e['p'] is None or not (MIN<=e['p']<MAX): return False
    if e['n'] is None: return False
    if e.get('is_yang',0)!=1 or e.get('above_ma5',0)!=1 or e.get('a',0)<=3: return False
    return True

def sc_v7(e):
    # 基础分
    sc = e['p'] + e['a']*1.5 + (e.get('dif_val',0) or 0)*0.5
    
    # MACD评分÷10
    gap=e.get('macd_gap',0) or 0
    if gap>0.5: sc+=0.5      # 强劲金叉+0.5
    elif gap<0.05 and gap>=0: sc-=0.5  # 微弱金叉-0.5
    elif gap<0: sc-=1.0      # 死叉-1.0
    
    # KDJ评分÷10
    if e.get('kdj_golden',1)==1: sc+=0.5  # 金叉+0.5
    else: sc-=0.5  # 死叉-0.5
    
    return round(sc,2)

print()
for yr in ['2025','2026']:
    bd=defaultdict(list)
    for dt in dc:
        if not dt.startswith(yr): continue
        for e in dc[dt]:
            if ok(e): bd[dt].append(e)
    bd={k:v for k,v in bd.items() if len(v)>=5}
    w=t=0
    for dt in sorted(bd.keys()):
        best=max(bd[dt], key=sc_v7)
        t+=1
        if best['n']>=TARGET: w+=1
    print(f"  {yr}: {t}天, 胜率{w/t*100:.1f}% ({w}/{t})")

# 对比基础版
print("\n📊 基础版(无MACD/KDJ):")
bd=defaultdict(list)
for dt in dc:
    if not dt.startswith('2025'): continue
    for e in dc[dt]:
        if ok(e): bd[dt].append(e)
bd={k:v for k,v in bd.items() if len(v)>=5}
w=t=0
for dt in sorted(bd.keys()):
    best=max(bd[dt], key=lambda e: e['p']+e['a']*1.5+(e.get('dif_val',0) or 0)*0.5)
    t+=1
    if best['n']>=TARGET: w+=1
print(f"  2025: {t}天, {w/t*100:.1f}%")

bd=defaultdict(list)
for dt in dc:
    if not dt.startswith('2026'): continue
    for e in dc[dt]:
        if ok(e): bd[dt].append(e)
bd={k:v for k,v in bd.items() if len(v)>=5}
w=t=0
for dt in sorted(bd.keys()):
    best=max(bd[dt], key=lambda e: e['p']+e['a']*1.5+(e.get('dif_val',0) or 0)*0.5)
    t+=1
    if best['n']>=TARGET: w+=1
print(f"  2026: {t}天, {w/t*100:.1f}%")
