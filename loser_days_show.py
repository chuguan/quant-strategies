#!/usr/bin/env python3
"""找2026年冠军次日跌的天，显示Top10"""
import pickle, os, sys, time
sys.stdout.reconfigure(line_buffering=True)
CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"

with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']; names=cache['names']
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

# 找出所有次日跌的交易日
loser_days=[]
for dt in sorted(data):
    if not dt.startswith("2026"): continue
    cands=data[dt]
    if len(cands)<5: continue
    # 原版冠军
    orig_best=max(cands, key=lambda c: max(0,35-c['s']*1.2) if c['s']<30 else 0 + min(c['b']*3,25)+min(c['a']*2,16))
    if orig_best['n'] is not None and orig_best['n']<0:
        loser_days.append((dt, orig_best['n']))

loser_days.sort(key=lambda x:x[1])
print(f"📅 2026年冠军次日跌的天: {len(loser_days)}天")

for dt, loss in loser_days:
    cands=data[dt]
    # 1~7%过滤
    filt=[]
    for c in cands:
        if c['code'] in ST: continue
        if c['b']<1 or c['b']>=7: continue
        sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
        c['total']=round(sh+min(c['b']*3,25)+min(c['a']*2,16),1)
        filt.append(c)
    filt.sort(key=lambda x:x['total'], reverse=True)
    
    # 原版冠军信息
    orig_best=max(cands, key=lambda c: max(0,35-c['s']*1.2) if c['s']<30 else 0 + min(c['b']*3,25)+min(c['a']*2,16))
    onh=f"{orig_best['n']:+.1f}%" if orig_best['n'] else "N/A"
    
    print(f"\n{'='*85}")
    print(f"❌ {dt}  原版冠军: {names.get(orig_best['code'],'?')}({orig_best['code']}) 涨{orig_best['p']:+.2f}% → 次日{onh}")
    print(f"{'='*85}")
    print(f"  {'排名':<4} {'名称':<10} {'代码':<12} {'买入价':>7} {'涨跌幅':>7} {'总分':>5}")
    print(f"  {'-'*48}")
    
    for rank, c in enumerate(filt[:10], 1):
        print(f"  {rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['cl']:>7.2f} {c['p']:>+6.2f}% {c['total']:>5.1f}")

print(f"\n⏱ 0.03秒")
