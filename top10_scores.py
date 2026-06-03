#!/usr/bin/env python3
"""1月6日 Top10 评分明细"""
import pickle, os, sys, time
sys.stdout.reconfigure(line_buffering=True)
CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"

with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']; names=cache['names']

cands=data["2026-01-06"]
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

filt=[]
for c in cands:
    if c['code'] in ST: continue
    b=c['b']
    if b<1 or b>=7: continue
    sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
    bd=min(b*3,25)
    at=min(c['a']*2,16)
    c['total']=round(sh+bd+at,1)
    c['sh_sc']=round(sh,1)
    c['bd_sc']=round(bd,1)
    c['at_sc']=round(at,1)
    filt.append(c)

filt.sort(key=lambda x:x['total'], reverse=True)

print(f"{'排名':<4} {'名称':<10} {'代码':<12} {'涨跌幅':>7} {'次日':>6} {'实体':>6} {'上影':>6} {'ATR':>6} {'上影分':>6} {'实体分':>6} {'ATR分':>5} {'总分':>5}")
print("-"*90)

for rank,c in enumerate(filt[:10],1):
    nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
    print(f"{rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['p']:>+6.2f}% {nh:>6} {c['b']:>5.2f}% {c['s']:>5.1f}% {c['a']:>5.2f}% {c['sh_sc']:>5.1f} {c['bd_sc']:>5.1f} {c['at_sc']:>4.1f} {c['total']:>5.1f}")
