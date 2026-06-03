#!/usr/bin/env python3
"""涨跌幅1~8% 回测"""
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
    
    # v14原版评分
    def v14(c): return (max(0,35-c['s']*1.2) if c['s']<30 else 0) + min(c['b']*3,25) + min(c['a']*2,16)
    
    w=0; t=0
    for dt in sorted(data.keys()):
        best=max(data[dt], key=v14)
        t+=1
        if best['n'] and best['n']>=2.5: w+=1
    print(f"📅 {yr}: {t}天, 胜率{w/t*100:.1f}% ({w}/{t})")

# 最新一天选股 — 确认没有9%+
print(f"\n{'='*80}")
print(f"📋 最新选股(2026-05-22) — 确认无9%+")
print(f"{'='*80}")
cands=[c for c in cache['data'].get('2026-05-22',[]) 
       if c['code'] not in ST and 1 <= c['p'] < 8]

for c in cands:
    c['sc']=round((max(0,35-c['s']*1.2) if c['s']<30 else 0) + min(c['b']*3,25) + min(c['a']*2,16), 1)
cands.sort(key=lambda x:x['sc'], reverse=True)

print(f"{'排名':<4} {'名称':<10} {'代码':<12} {'买入价':>7} {'涨跌幅':>6} {'总分':>5}")
print("-"*50)
for rank,c in enumerate(cands[:10],1):
    name=cache['names'].get(c['code'],'—')
    cl=c['cl']; p=c['p']
    # 确保没有>8%的
    assert p < 8, f"❌ {c['code']} 涨跌幅{p}% > 8%"
    print(f"{rank:<4} {name:<10} {c['code']:<12} {cl:>7.2f} {p:>+5.2f}% {c['sc']:>5.1f}")

print(f"\n✅ 全部涨跌幅<8%，无涨停票！")
