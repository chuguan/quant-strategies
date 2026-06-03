#!/usr/bin/env python3
"""1~8全部组合扫描 — 找最优涨幅区间"""
import json, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\.cand_cache.json"

print("📡 加载缓存..."); t0=time.time()
with open(CACHE_FILE,'rb') as f: cache=json.loads(f.read().decode('utf-8'))

for yr_name, yr_data in [("2025", cache['cands_2025']), ("2026", cache['cands_2026'])]:
    data = defaultdict(list)
    for c in yr_data:
        data[c['d']].append(c)
    data = {k:v for k,v in data.items() if len(v)>=5}
    
    for dt,cands in data.items():
        for c in cands:
            c['ba'] = min(c['b']*3,25) + min(c['a']*2,16)
    
    def v14(s,ba): return (max(0,35-s*1.2) if s<30 else 0) + ba
    
    print(f"\n{'='*90}")
    print(f"📅 {yr_name}年 — 1%~8%全部组合")
    print(f"{'='*90}")
    print(f"{'下限~上限':<12} {'胜率':>7} {'天数':>5} {'vs原版':>8} {'冠军平均':>10}")
    print("-"*50)
    
    baseline_w=0; baseline_t=0
    for dt in sorted(data.keys()):
        best=max(data[dt], key=lambda c: v14(c['s'],c['ba']))
        baseline_t+=1
        if best['n'] and best['n']>=2.5: baseline_w+=1
    baseline_pct=baseline_w/baseline_t*100
    
    results=[]
    # 下限 1~7, 上限 2~8, 下限<上限
    for lb in range(1,8):
        for ub in range(lb+1,9):
            w=0; t=0
            for dt in sorted(data.keys()):
                cands=[c for c in data[dt] if lb <= c['b'] < ub]
                if len(cands)<5: continue
                best=max(cands, key=lambda c: v14(c['s'],c['ba']))
                t+=1
                if best['n'] and best['n']>=2.5: w+=1
            rate=w/t*100 if t else 0
            diff=rate-baseline_pct
            results.append((rate, diff, lb, ub, w, t))
    
    results.sort(reverse=True)
    
    for rate, diff, lb, ub, w, t in results[:15]:
        mk="🔥" if diff>0 else ("✅" if diff>=-2 else "")
        print(f"{lb}%~{ub}%    {rate:>5.1f}%  {t:>3}d  {diff:>+6.1f}% {mk}")
    
    # 最佳
    best=results[0]
    print(f"\n🥇 最优区间: {best[2]}%~{best[3]}% = {best[0]:.1f}% (vs原版{best[1]:+.1f}%)")

print(f"\n⏱ {time.time()-t0:.1f}秒")
