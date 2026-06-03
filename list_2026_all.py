#!/usr/bin/env python3
"""2026年全89天数据：每日冠军+次日涨幅+评分"""
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

bd=defaultdict(list)
for dt in dc:
    if not dt.startswith('2026'): continue
    for e in dc[dt]:
        if ok(e): bd[dt].append(e)
bd={k:v for k,v in bd.items() if len(v)>=5}

print("2026年每日冠军数据")
print("日期      名称       代码              涨跌幅  ATR  收盘位 上影  DIF   评分  次日高")
print("-"*105)

win=0; total=0
for dt in sorted(bd.keys()):
    best=max(bd[dt], key=sc)
    total+=1
    name=nm.get(best['code'],'?')
    res=''  # hide result flag, just show data
    if best['n']>=TARGET: win+=1
    print(f"{dt} {name:<8} {best['code']:<16} {best['p']:+.1f}% {best['a']:4.1f}% {best.get('cl',0):3.0f}% {best.get('s',0):4.1f}% {best.get('dif_val',0) or 0:5.2f} {sc(best):5.1f} {best['n']:+5.1f}%")

print(f"\n总天数: {total}  胜率: {win/total*100:.1f}%")
