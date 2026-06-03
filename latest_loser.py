#!/usr/bin/env python3
"""找2026年最新的输家日，跑1~7%过滤分析"""
import pickle, os, time, sys
sys.stdout.reconfigure(line_buffering=True)

CACHE = r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
print("📡 加载..."); t0=time.time()
with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']; names=cache['names']

# 只找2026年的
dates_2026=sorted(d for d in data if d.startswith("2026"))

# Find the latest losing champion day  
losers=[]
for dt in reversed(dates_2026):
    cands=data[dt]
    if len(cands)<5: continue
    for c in cands:
        sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
        c['total']=round(sh+min(c['b']*3,25)+min(c['a']*2,16),1)
    best=max(cands, key=lambda x:x['total'])
    if best['n'] is not None and best['n']<0:  # 负的 = 跌了
        losers.append((dt, best))
        if len(losers)>=3: break

if not losers:
    print("❌ 无输家日")
    sys.exit(1)

for dt, champ in losers:
    print(f"\n{'='*80}")
    print(f"❌ 输家日: {dt} — 冠军{names.get(champ['code'],'?')}({champ['code']}) → 次日{champ['n']:+.1f}%")
    print(f"{'='*80}")
    print(f"  实体{champ['b']:.2f}% 涨幅{champ['p']:+.2f}% 上影{champ['s']:.1f}%")
    
    # 1~7%过滤后的新冠军
    cands=data[dt]
    for c in cands:
        sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
        c['total']=round(sh+min(c['b']*3,25)+min(c['a']*2,16),1)
    
    filt=[c for c in cands if 1<=c['b']<7]
    filt.sort(key=lambda x:x['total'], reverse=True)
    
    print(f"\n  🔍 1~7%过滤后:")
    print(f"  {'排名':<4} {'名称':<10} {'代码':<12} {'涨跌幅':>7} {'实体':>6} {'上影':>6} {'总分':>5} {'次日':>6}")
    print(f"  {'-'*55}")
    
    for rank,c in enumerate(filt[:10],1):
        nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
        print(f"  {rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['p']:>+6.2f}% {c['b']:>5.2f}% {c['s']:>5.1f}% {c['total']:>5.1f} {nh:>6}")
    
    w5=sum(1 for c in filt[:5] if c['n'] and c['n']>=2.5)
    print(f"\n  📊 前5: {w5}/5 赢")

print(f"\n⏱ {time.time()-t0:.2f}秒")
