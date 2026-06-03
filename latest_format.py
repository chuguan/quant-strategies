#!/usr/bin/env python3
"""最新选股 — 新格式展示（次日放第一列）"""
import pickle, os, sys, time
sys.stdout.reconfigure(line_buffering=True)
CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"

ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']; names=cache['names']

dates_2026=sorted([d for d in data if d.startswith("2026")], reverse=True)
target=dates_2026[0]
cands=data[target]
print(f"📅 {target} — 原始: {len(cands)}只")

filt=[]
for c in cands:
    if c['code'] in ST: continue
    b=c['b']
    if b<1 or b>=7: continue
    sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
    c['total']=round(sh+min(b*3,25)+min(c['a']*2,16),1)
    filt.append(c)

filt.sort(key=lambda x:x['total'], reverse=True)
print(f"  过滤后: {len(filt)}只")

if not filt:
    print("❌ 无候选")
    sys.exit(0)

print(f"\n{'='*75}")
print(f"🏆 TOP10 详情")
print(f"{'='*75}")
print(f"{'排名':<4} {'代码':<12} {'次日':>6} {'总分':>5} {'实体%':>6} {'上影%':>6} {'ATR%':>6} {'涨跌幅':>7}")
print("-"*55)

for rank,c in enumerate(filt[:10],1):
    nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
    mk="🏆" if rank==1 else ""
    print(f"{rank:<4} {c['code']:<12} {nh:>6} {c['total']:>5.1f} {c['b']:>5.2f}% {c['s']:>5.1f}% {c['a']:>5.2f}% {c['p']:>+6.2f}% {mk}")

print(f"\n🥇 冠军: {names.get(filt[0]['code'],'?')}({filt[0]['code']})  评分: {filt[0]['total']:.1f}")
print(f"⏱ {time.time()-0:.3f}秒")
