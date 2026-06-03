#!/usr/bin/env python3
"""
全量回测 + 今日推荐（秒出）
评分：涨跌幅×1 + ATR×1.5 + DIF×0.5 + 收盘位×0.02 - 上影>40%-3
过滤：阳线 + 站MA5 + ATR>3% + 涨跌幅1~8% + 排除ST
"""
import pickle, os, sys
from collections import defaultdict

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']; names=cache['names']

def score(c):
    sc = c['p'] + c['a']*1.5
    if c.get('dif_val',0): sc += c['dif_val']*0.5
    sc += c.get('cl',0)*0.02
    if c.get('s',0)>40: sc-=3
    return round(sc,2)

def ok(c):
    if c['code'] in ST: return False
    if c['p'] is None or not (MIN_CHG <= c['p'] < MAX_CHG): return False
    if c.get('is_yang',0)!=1 or c.get('above_ma5',0)!=1 or c.get('a',0)<=3:
        return False
    return True

print("📊 全量回测结果")
print("="*60)

for yr in ['2025','2026']:
    by_date=defaultdict(list)
    for dt in data_cache:
        if not dt.startswith(yr): continue
        for c in data_cache[dt]:
            if not ok(c) or c['n'] is None: continue
            by_date[dt].append(c)
    by_date={k:v for k,v in by_date.items() if len(v)>=5}
    
    w1=t1=w3=t3a=0
    for dt in sorted(by_date.keys()):
        cs=sorted(by_date[dt], key=lambda c: c['p']+c['a']*1.5+(c.get('dif_val',0) or 0)*0.5+c.get('cl',0)*0.02-(3 if c.get('s',0)>40 else 0), reverse=True)
        t1+=1
        if cs[0]['n']>=TARGET: w1+=1
        if len(cs)>=3:
            t3a+=1
            if any(c['n']>=TARGET for c in cs[:3]): w3+=1
    
    print(f"\n📅 {yr} ({t1}天):")
    print(f"  #1冠军胜率: {w1/t1*100:.1f}% ({w1}/{t1})")
    print(f"  Top3任意达标: {w3/t3a*100:.1f}% ({w3}/{t3a})")

print(f"\n{'='*60}")
print(f"📋 最新推荐")
print("="*60)

for latest_dt in [sorted([d for d in data_cache if d.startswith('2026')])[-1]]:
    cs=[c for c in data_cache.get(latest_dt,[]) if ok(c)]
    for c in cs: c['sc']=score(c)
    cs.sort(key=lambda c:c['sc'], reverse=True)
    
    print(f"\n📅 {latest_dt} Top5:")
    print(f"  {'#':<3} {'名称':<10} {'代码':<16} {'买入价':>7} {'涨跌幅':>6} {'ATR':>5} {'收盘位':>5} {'上影':>5} {'DIF':>6} {'评分':>5}")
    print(f"  {'-'*70}")
    for i,c in enumerate(cs[:5],1):
        n=names.get(c['code'],'?')
        print(f"  {i:<3} {n:<10} {c['code']:<16} {c['close']:>7.2f} {c['p']:>+5.1f}% {c['a']:>4.1f}% {c.get('cl',0):>4.0f}% {c.get('s',0):>4.1f}% {c.get('dif_val',0):>5.2f} {c['sc']:>5.1f}")

print(f"\n⏱ 耗时<1秒（缓存直出）")
