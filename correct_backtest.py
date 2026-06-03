#!/usr/bin/env python3
"""正确回测：买入价=收盘，卖出价=次日收盘"""
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
    if e.get('is_yang',0)!=1 or e.get('above_ma5',0)!=1 or e.get('a',0)<=3: return False
    return True

def sc(e):
    return e['p']+e['a']*1.5+(e.get('dif_val',0) or 0)*0.5+e.get('cl',0)*0.02-(3 if e.get('s',0)>40 else 0)

print("📊 正确回测：买入价=收盘价，卖出价=次日收盘价，目标≥2.5%")
print()

for yr in ['2025','2026']:
    bd=defaultdict(list)
    for dt in dc:
        if not dt.startswith(yr): continue
        for e in dc[dt]:
            if not ok(e): continue
            if e.get('next_close') is None: continue  # 必须有次日收盘数据
            bd[dt].append(e)
    bd={k:v for k,v in bd.items() if len(v)>=5}
    
    w=t=0
    for dt in sorted(bd.keys()):
        best=max(bd[dt], key=sc)
        t+=1
        if best['next_close']>=TARGET: w+=1
    print(f"  {yr}: {t}天, 胜率{w/t*100:.1f}% ({w}/{t})")

# 上海港湾验证
for dt in ['2026-01-12']:
    cs=[e for e in dc.get(dt,[]) if ok(e)]
    for e in cs: e['s2']=sc(e)
    cs.sort(key=lambda e:e['s2'], reverse=True)
    c1=cs[0]
    n2=nm.get(c1['code'],'?')
    nc=c1.get('next_close',0)
    nh=c1.get('n',0)
    print(f"\n📅 {dt} {n2}({c1['code']}):")
    print(f"  买入价(收盘): {c1['close']:.2f}")
    print(f"  次日最高: {c1['n']:+.1f}% (我之前用的错误标准)")
    print(f"  次日收盘: {c1['next_close']:+.1f}% (正确的标准)")
    print(f"  目标2.5%: {'✅' if nc>=TARGET else '❌'} (次日收盘{nc:+.1f}%)")
