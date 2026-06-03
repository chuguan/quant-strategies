#!/usr/bin/env python3
"""
第3轮：放宽条件 + 不同目标胜率分布分析
看看把条件放宽到什么程度能达到高胜率
"""
import pickle, os, sys, math
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']

MIN_CHG=1.0; MAX_CHG=8.0

# 不再使用ST过滤，只关注涨跌幅范围

# ═══ 分析1: 不同目标下的最优评分 ═══
print("═══ 分析1: 不同目标下的最优评分（涨跌幅1~8%） ═══")
for TARGET in [1.5, 2.0, 2.5, 3.0, 4.0, 5.0]:
    for yr in ['2025','2026']:
        by_date=defaultdict(list)
        for dt in data_cache:
            if not dt.startswith(yr): continue
            for c in data_cache[dt]:
                p=c['p']
                if p is None or not (MIN_CHG <= p < MAX_CHG): continue
                if c['n'] is None: continue
                by_date[dt].append(c)
        by_date={k:v for k,v in by_date.items() if len(v)>=5}
        
        def test(fn):
            w=t=0
            for dt in sorted(by_date.keys()):
                best=max(by_date[dt], key=fn)
                t+=1
                if best['n']>=TARGET: w+=1
            return w/t*100 if t>0 else 0
        
        p_a = test(lambda c: c['p']+c['a'])
        p_2a = test(lambda c: c['p']*2+c['a'])
        p_a2 = test(lambda c: c['p']+c['a']*c['a'])
        max3_a = test(lambda c: max(c['p'],3)+c['a'])
        p_times_a = test(lambda c: c['p']*c['a'])
        
        print(f"  {yr} 目标≥{TARGET}%:  p+a={p_a:.1f}%  2p+a={p_2a:.1f}%  p+a²={p_a2:.1f}%  max(p,3)+a={max3_a:.1f}%  p×a={p_times_a:.1f}%")

# ═══ 分析2: 放宽ATR下限 ═══
print("\n═══ 分析2: 放宽ATR下限（涨跌幅1~8%，目标2.5%，p+a评分） ═══")
for min_atr in [0, 1, 2, 3, 4, 5]:
    for yr in ['2025','2026']:
        by_date=defaultdict(list)
        for dt in data_cache:
            if not dt.startswith(yr): continue
            for c in data_cache[dt]:
                p=c['p']; a=c['a']
                if p is None or not (MIN_CHG <= p < MAX_CHG): continue
                if c['n'] is None: continue
                if a < min_atr: continue
                by_date[dt].append(c)
        by_date={k:v for k,v in by_date.items() if len(v)>=5}
        wr=0; w=t=0
        for dt in sorted(by_date.keys()):
            best=max(by_date[dt], key=lambda c: c['p']+c['a'])
            t+=1
            if best['n']>=2.5: w+=1
        wr=w/t*100 if t>0 else 0
        print(f"  ATR>{min_atr}%  {yr}: {wr:.1f}% ({t}天, {w}胜)")
    print()

# ═══ 分析3: 不同涨幅区间的最优评分 ═══
print("═══ 分析3: 不同涨跌幅区间的胜率（p+a评分，目标2.5%） ═══")
ranges=[(1,3),(3,5),(5,7),(1,5),(1,7),(1,8)]
for lo,hi in ranges:
    for yr in ['2025','2026']:
        by_date=defaultdict(list)
        for dt in data_cache:
            if not dt.startswith(yr): continue
            for c in data_cache[dt]:
                p=c['p']; a=c['a']
                if p is None or not (lo <= p < hi): continue
                if c['n'] is None: continue
                by_date[dt].append(c)
        by_date={k:v for k,v in by_date.items() if len(v)>=5}
        wr=0; w=t=0
        for dt in sorted(by_date.keys()):
            best=max(by_date[dt], key=lambda c: c['p']+c['a'])
            t+=1
            if best['n']>=2.5: w+=1
        wr=w/t*100 if t>0 else 0
        print(f"  {lo}~{hi}% {yr}: {wr:.1f}% ({t}天)")
    print()

# ═══ 分析4：2026最佳公式深度分析 ═══
print("═══ 分析4: 2026年 p×a² 公式为什么好 ═══")
# 对比两个公式在2026每月的表现
by_date=defaultdict(list)
for dt in data_cache:
    if not dt.startswith('2026'): continue
    for c in data_cache[dt]:
        p=c['p']
        if p is None or not (MIN_CHG <= p < MAX_CHG): continue
        if c['n'] is None: continue
        by_date[dt].append(c)
by_date={k:v for k,v in by_date.items() if len(v)>=5}

months=defaultdict(lambda: {'p_a':[0,0], 'p_a2':[0,0]})
fn1=lambda c: c['p']+c['a']
fn2=lambda c: c['p']+c['a']*c['a']
for dt in sorted(by_date.keys()):
    m=dt[:7]
    best1=max(by_date[dt], key=fn1)
    best2=max(by_date[dt], key=fn2)
    months[m]['p_a'][0]+=1
    months[m]['p_a'][1]+=1 if best1['n']>=2.5 else 0
    months[m]['p_a2'][0]+=1
    months[m]['p_a2'][1]+=1 if best2['n']>=2.5 else 0

print(f"{'月份':<8} {'p+a胜率':>8} {'p+a²胜率':>10}")
for m in sorted(months.keys()):
    v1=months[m]['p_a']
    v2=months[m]['p_a2']
    print(f"{m:<8} {v1[1]/v1[0]*100:>7.1f}% ({v1[1]}/{v1[0]})  {v2[1]/v2[0]*100:>7.1f}% ({v2[1]}/{v2[0]})")
