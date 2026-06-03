#!/usr/bin/env python3
"""找最优涨幅区间 — 实体%替代涨跌幅，扫描1%~8%全部组合"""
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
    
    print(f"\n{'='*80}")
    print(f"📅 {yr_name}年 — 扫描涨幅上限(实体%)")
    print(f"{'='*80}")
    
    # 测试不同的实体%上限 (min_body = 0，max_body = 3~8%)
    results = []
    for max_body in range(30, 81, 5):  # 3.0%~8.0%, 步长0.5%
        max_body_pct = max_body / 10
        w=0; t=0
        for dt in sorted(data.keys()):
            cands=[c for c in data[dt] if c['b']<max_body_pct]
            if len(cands)<5: continue
            best=max(cands, key=lambda c: v14(c['s'],c['ba']))
            t+=1
            if best['n'] and best['n']>=2.5: w+=1
        rate = w/t*100 if t else 0
        results.append((rate, max_body_pct, w, t))
    
    results.sort(reverse=True)
    
    print(f"{'上限':<8} {'胜率':>7} {'天数':>5} {'vs原版':>8}")
    print("-"*35)
    baseline = 77.8 if yr_name=="2025" else 87.6
    for rate, mb, w, t in results[:10]:
        diff = rate - baseline
        mk="🔥" if diff>0 else ("✅" if diff>=-1 else "")
        print(f"<{mb:.1f}%    {rate:>5.1f}%  {t:>3}d  {diff:>+6.1f}% {mk}")
    
    # 新加入涨幅下限测试
    print(f"\n📊 涨幅下限(买方安全垫)")
    results2 = []
    for min_body in range(5, 31, 5):  # 0.5%~3.0%
        min_body_pct = min_body / 10
        max_body_pct = 8.0
        w=0; t=0
        for dt in sorted(data.keys()):
            cands=[c for c in data[dt] if min_body_pct <= c['b'] < max_body_pct]
            if len(cands)<5: continue
            best=max(cands, key=lambda c: v14(c['s'],c['ba']))
            t+=1
            if best['n'] and best['n']>=2.5: w+=1
        rate2 = w/t*100 if t else 0
        results2.append((rate2, min_body_pct, w, t))
    
    results2.sort(reverse=True)
    print(f"{'下限~8%':<10} {'胜率':>7} {'天数':>5}")
    print("-"*30)
    for rate, mb, w, t in results2[:5]:
        print(f"{mb:.1f}%~8%  {rate:>5.1f}%  {t:>3}d")

    # 双维度扫描
    print(f"\n📊 双维度扫描（下限×上限）")
    print(f"下限→上限:{'':>2}", end="")
    for ub in [40,50,60,70,80]:
        print(f" <{ub/10:.0f}%  ", end="")
    print()
    
    for lb in [5,10,15,20,25]:
        print(f"{lb/10:.1f}%     ", end="")
        for ub in [40,50,60,70,80]:
            w=0; t=0
            for dt in sorted(data.keys()):
                cands=[c for c in data[dt] if lb/10 <= c['b'] < ub/10]
                if len(cands)<5: continue
                best=max(cands, key=lambda c: v14(c['s'],c['ba']))
                t+=1
                if best['n'] and best['n']>=2.5: w+=1
            rate3 = w/t*100 if t else 0
            mk="★" if rate3>80 else ""
            print(f"{rate3:>5.1f}%{mk:<2}", end="")
        print()

print(f"\n⏱ {time.time()-t0:.1f}秒")
