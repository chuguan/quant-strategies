#!/usr/bin/env python3
"""26天冠军跌日统计：买Top3的整体收益"""
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

# 收集所有2026年数据
bd=defaultdict(list)
for dt in dc:
    if not dt.startswith('2026'): continue
    for e in dc[dt]:
        if ok(e): bd[dt].append(e)
bd={k:v for k,v in bd.items() if len(v)>=5}

fails=[]; all_days=[]
for dt in sorted(bd.keys()):
    top3=sorted(bd[dt], key=sc, reverse=True)[:3]
    champ=top3[0]
    all_days.append((dt, top3))
    if champ['n']<TARGET:
        fails.append((dt, top3))

print("="*100)
print("2026年 冠军跌的日子（26天）— 买Top3的表现")
print("="*100)
print(f"{'日期':<12}{'#1冠军':<20}{'次日':>6}{'#2亚军':<20}{'次日':>6}{'#3季军':<20}{'次日':>6}{'3只总涨':>8}")
print("-"*100)

total_3=0; fail_3_any_win=0
for dt,top3 in fails:
    name1=nm.get(top3[0]['code'],'?')
    name2=nm.get(top3[1]['code'],'?')
    name3=nm.get(top3[2]['code'],'?')
    n1=top3[0]['n']; n2=top3[1]['n']; n3=top3[2]['n']
    total=n1+n2+n3
    total_3+=total
    any_win="✅" if any(x['n']>=TARGET for x in top3) else "❌"
    if any(x['n']>=TARGET for x in top3): fail_3_any_win+=1
    print(f"{dt:<12}{name1+str(top3[0]['code'])[-6:]:<20}{n1:>+5.1f}%{name2+str(top3[1]['code'])[-6:]:<20}{n2:>+5.1f}%{name3+str(top3[2]['code'])[-6:]:<20}{n3:>+5.1f}%{total:>+7.1f}%{any_win}")

print("-"*100)

# 整体统计
print(f"\n📊 冠军跌的26天统计：")
print(f"  冠军均次日: {sum(t[0]['n'] for _,t in fails)/len(fails):+.1f}%")
print(f"  亚军均次日: {sum(t[1]['n'] for _,t in fails)/len(fails):+.1f}%")
print(f"  季军均次日: {sum(t[2]['n'] for _,t in fails)/len(fails):+.1f}%")
print(f"  3只总涨平均: {total_3/len(fails):+.1f}%")
print(f"  3只中至少1只达标: {fail_3_any_win}/{len(fails)} = {fail_3_any_win/len(fails)*100:.1f}%")

# 全场统计
all_any_win=sum(1 for _,t3 in all_days if any(x['n']>=TARGET for x in t3))
print(f"\n📊 全89天统计（买Top3）：")
print(f"  日均3只总涨: {sum(sum(x['n'] for x in t3) for _,t3 in all_days)/len(all_days):+.1f}%")
print(f"  日均\$1: {sum(t3[0]['n'] for _,t3 in all_days)/len(all_days):+.1f}%")
print(f"  日均\$2: {sum(t3[1]['n'] for _,t3 in all_days)/len(all_days):+.1f}%")
print(f"  日均\$3: {sum(t3[2]['n'] for _,t3 in all_days)/len(all_days):+.1f}%")
print(f"  至少1只达标: {all_any_win}/89 = {all_any_win/89*100:.1f}%")
