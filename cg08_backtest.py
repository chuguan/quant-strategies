#!/usr/bin/env python3
"""CG-08 完整回测"""
import pickle, os, sys, time
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)

for yr in ['2025','2026']:
    data=defaultdict(list)
    for dt in cache['data']:
        if not dt.startswith(yr): continue
        for c in cache['data'][dt]:
            if c['code'] in ST: continue
            if not (1 <= c['p'] < 8): continue
            data[dt].append(c)
    data={k:v for k,v in data.items() if len(v)>=5}
    
    # CG-08评分
    def score(c): return c['p']*3 + c['a']*3
    
    w=t=0
    for dt in sorted(data.keys()):
        best=max(data[dt], key=score)
        t+=1
        if best['n'] and best['n']>=2.5: w+=1
    print(f"📅 {yr}: {t}天全勤, 胜率{w/t*100:.1f}% ({w}/{t})")

# 最新选股
print(f"\n{'='*80}")
print(f"🏆 CG-08 最新选股(2026-05-22)")
print(f"{'='*80}")
cands=[c for c in cache['data'].get('2026-05-22',[]) if c['code'] not in ST and 1<=c['p']<8]
for c in cands:
    c['sc']=round(c['p']*3+c['a']*3,1)
cands.sort(key=lambda x:x['sc'], reverse=True)

print(f"{'排名':<4} {'名称':<10} {'代码':<12} {'买入价':>7} {'涨跌幅':>6} {'ATR':>6} {'总分':>5}")
print("-"*55)
for rank,c in enumerate(cands[:10],1):
    print(f"{rank:<4} {cache['names'].get(c['code'],'—'):<10} {c['code']:<12} {c['cl']:>7.2f} {c['p']:>+5.2f}% {c['a']:>5.2f}% {c['sc']:>5.1f}")

print(f"\n✅ 全部涨跌幅<8%，无涨停票！")
