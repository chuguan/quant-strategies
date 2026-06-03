#!/usr/bin/env python3
"""回测v14+涨跌幅过滤版 — 排除涨>8%的票"""
import json, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\.cand_cache.json"

print("📡 加载缓存..."); t0=time.time()
with open(CACHE_FILE,'rb') as f: cache=json.loads(f.read().decode('utf-8'))

# 分别跑2025和2026
for yr_name, yr_data in [("2025", cache['cands_2025']), ("2026", cache['cands_2026'])]:
    data = defaultdict(list)
    for c in yr_data:
        data[c['d']].append(c)
    data = {k:v for k,v in data.items() if len(v)>=5}
    
    for dt,cands in data.items():
        for c in cands:
            c['ba'] = min(c['b']*3,25) + min(c['a']*2,16)
    
    def v14(s,ba): return (max(0,35-s*1.2) if s<30 else 0) + ba
    
    print(f"\n{'='*80}")
    print(f"📅 {yr_name}年")
    print(f"{'='*80}")
    
    # 原版v14
    w1=0; t1=0
    for dt in sorted(data.keys()):
        cands=data[dt]
        best=max(cands, key=lambda c: v14(c['s'],c['ba']))
        t1+=1
        if best['n'] and best['n']>=2.5: w1+=1
    print(f"原版v14: {w1}/{t1} = {w1/t1*100:.1f}%")
    
    # v14 + 涨跌幅过滤(body% < 8%作为涨停排除)
    w2=0; t2=0
    for dt in sorted(data.keys()):
        cands=[c for c in data[dt] if c['b']<8]  # 排除涨停(实体>8%)
        if len(cands)<5: continue
        best=max(cands, key=lambda c: v14(c['s'],c['ba']))
        t2+=1
        if best['n'] and best['n']>=2.5: w2+=1
    print(f"v14+排除涨停(实体<8%): {w2}/{t2} = {w2/t2*100:.1f}%")
    
    # v14 + 涨跌幅过滤(body% < 7%)
    w3=0; t3=0
    for dt in sorted(data.keys()):
        cands=[c for c in data[dt] if c['b']<7]
        if len(cands)<5: continue
        best=max(cands, key=lambda c: v14(c['s'],c['ba']))
        t3+=1
        if best['n'] and best['n']>=2.5: w3+=1
    print(f"v14+排除大涨(实体<7%): {w3}/{t3} = {w3/t3*100:.1f}%")
    
    # v14 + 涨跌幅过滤(body% < 6%)
    w4=0; t4=0
    for dt in sorted(data.keys()):
        cands=[c for c in data[dt] if c['b']<6]
        if len(cands)<5: continue
        best=max(cands, key=lambda c: v14(c['s'],c['ba']))
        t4+=1
        if best['n'] and best['n']>=2.5: w4+=1
    print(f"v14+排除大涨(实体<6%): {w4}/{t4} = {w4/t4*100:.1f}%")
    
    # 出票天数变化
    print(f"  出票天数: 原版{t1}天 → 实体<8%:{t2}天 → <7%:{t3}天 → <6%:{t4}天")

print(f"\n⏱ {time.time()-t0:.1f}秒")
