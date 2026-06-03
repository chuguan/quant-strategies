#!/usr/bin/env python3
"""
冠军胜率 vs 前三名胜率
"""
import pickle, os
from collections import defaultdict

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']

MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5
fn=lambda c: c['p']+c['a']

def filter_data(yr):
    by_date=defaultdict(list)
    for dt in data_cache:
        if not dt.startswith(yr): continue
        for c in data_cache[dt]:
            if c['code'] in ST: continue
            p=c['p']; n=c['n']
            if p is None or not (MIN_CHG <= p < MAX_CHG): continue
            if n is None: continue
            by_date[dt].append(c)
    return {k:v for k,v in by_date.items() if len(v)>=5}

print("CG-08 V2（涨跌幅1~8% + 涨跌幅+ATR评分）")
print("="*60)
print(f"{'指标':<20} {'2025':>10} {'2026':>10} {'平均':>10}")
print("-"*60)

for yr in ['2025','2026']:
    data=filter_data(yr)
    
    # 1️⃣ 冠军胜率（第1名）
    w1=t1=0
    # 2️⃣ 前三中最佳（理论上限）
    w3_best=t3=0
    # 3️⃣ 前三中任意一个达标
    w3_any=t3a=0
    
    for dt in sorted(data.keys()):
        cands=sorted(data[dt], key=fn, reverse=True)
        # 冠军
        t1+=1
        if cands[0]['n']>=TARGET: w1+=1
        
        # 前三中最佳
        if len(cands)>=3:
            best3=max(cands[:3], key=lambda c: c['n'])
            t3+=1
            if best3['n']>=TARGET: w3_best+=1
            # 前三任意达标
            t3a+=1
            if any(c['n']>=TARGET for c in cands[:3]): w3_any+=1
    
    wr1=w1/t1*100
    wr3b=w3_best/t3*100
    wr3a=w3_any/t3a*100
    
    print(f"\n{yr}:")
    print(f"{'#1冠军胜率':<20} {wr1:>9.1f}% ({w1}/{t1})")
    print(f"{'#3最佳(上限)':<20} {wr3b:>9.1f}% ({w3_best}/{t3})")
    print(f"{'#3任意达标':<20} {wr3a:>9.1f}% ({w3_any}/{t3a})")

# 汇总
print("\n"+"="*60)
print(f"{'汇总平均':<20} {'2025':>10} {'2026':>10} {'平均':>10}")
print("-"*60)

data25=filter_data('2025')
data26=filter_data('2026')

for label, fn_calc in [
    ('#1冠军', lambda d: sum(1 for dt in sorted(d.keys()) if max(d[dt],key=fn)['n']>=TARGET)/len(d)*100 if d else 0),
    ('#3最佳', lambda d: sum(1 for dt in sorted(d.keys()) for c in [max(sorted(d[dt],key=fn,reverse=True)[:3],key=lambda x:x['n'])] if c['n']>=TARGET)/len(d)*100 if d else 0),
    ('#3任意', lambda d: sum(1 for dt in sorted(d.keys()) if any(c['n']>=TARGET for c in sorted(d[dt],key=fn,reverse=True)[:3]))/len(d)*100 if d else 0),
]:
    w25=fn_calc(data25)
    w26=fn_calc(data26)
    avg=(w25+w26)/2
    print(f"{label:<20} {w25:>9.1f}% {w26:>9.1f}% {avg:>9.1f}%")
