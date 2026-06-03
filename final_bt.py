#!/usr/bin/env python3
"""全量回测：第一名胜率 + 前三名均价"""
import pickle, os
from collections import defaultdict

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: c=pickle.load(f)
dc=c['data']; nm=c['names']

MIN=1.0; MAX=8.0; TARGET=2.5

def ok(e):
    if e['code'] in ST: return False
    if e['p'] is None or not (MIN<=e['p']<MAX): return False
    if e['n'] is None: return False
    if e.get('is_yang',0)!=1 or e.get('above_ma5',0)!=1 or e.get('a',0)<=3: return False
    return True

def sc(e):
    return e['p']+e['a']*1.5+(e.get('dif_val',0) or 0)*0.5+e.get('cl',0)*0.02-(3 if e.get('s',0)>40 else 0)

print("📊 全量回测：冠军胜率 + 前三均涨")
print()

for yr in ['2025','2026']:
    bd=defaultdict(list)
    for dt in dc:
        if not dt.startswith(yr): continue
        for e in dc[dt]:
            if ok(e): bd[dt].append(e)
    bd={k:v for k,v in bd.items() if len(v)>=5}
    
    w1=t1=0; sum1=0; sum3=0
    for dt in sorted(bd.keys()):
        cs=sorted(bd[dt], key=sc, reverse=True)
        t1+=1
        # 第一名
        c1=cs[0]
        sum1+=c1['n']
        if c1['n']>=TARGET: w1+=1
        # 前三名
        for c in cs[:3]:
            sum3+=c['n']
    
    avg1=sum1/len(bd)
    avg3=sum3/(len(bd)*3)
    print(f"📅 {yr} ({len(bd)}天):")
    print(f"  🥇 冠军胜率: {w1/t1*100:.1f}% ({w1}/{t1})")
    print(f"  🥇 冠军均涨: {avg1:+.1f}%")
    print(f"  🥇🥈🥉 前三均涨: {avg3:+.1f}%")
    print()
