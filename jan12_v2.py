#!/usr/bin/env python3
"""1月12日 — 正确涨跌幅1~7%过滤"""
import pickle, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"

with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']; names=cache['names']

ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

target="2026-01-12"
cands=data[target]

filt=[]
for c in cands:
    if c['code'] in ST: continue
    p=c['p']
    if not (1 <= p < 7): continue  # 涨跌幅1~7%
    sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
    c['total']=round(sh+min(c['b']*3,25)+min(c['a']*2,16),1)
    filt.append(c)

filt.sort(key=lambda x:x['total'], reverse=True)
print(f"📅 {target}  原始: {len(cands)}只  涨跌幅1~7%过滤: {len(filt)}只")

print(f"\n{'='*85}")
print(f"🏆 TOP10")
print(f"{'='*85}")
print(f"{'排名':<4} {'名称':<10} {'代码':<12} {'买入价':>7} {'涨跌幅':>7} {'总分':>5} {'次日最高':>8}")
print("-"*60)

for rank,c in enumerate(filt[:10],1):
    nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
    print(f"{rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['cl']:>7.2f} {c['p']:>+6.2f}% {c['total']:>5.1f} {nh:>8}")

# 对比实体%过滤版本
old=[c for c in cands if c['code'] not in ST and 1<=c['b']<7]
print(f"\n📊 对比")
print(f"  实体%过滤: {len(old)}只")
print(f"  涨跌幅%过滤: {len(filt)}只")
removed=set(c['code'] for c in old)-set(c['code'] for c in filt)
print(f"  被排除的(涨跌幅>7%但实体<7%): {len(removed)}只")
for code in list(removed)[:5]:
    c=next(c for c in old if c['code']==code)
    print(f"    {names.get(code,'?')}({code}) 涨跌幅{c['p']:+.2f}% 实体{c['b']:.2f}%")
