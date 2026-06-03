#!/usr/bin/env python3
"""某天详细 — 能买到的票"""
import pickle, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"

ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']; names=cache['names']

target="2026-01-06"
cands=data[target]

# 原版冠军(无过滤)
orig_best=max(cands, key=lambda c: max(0,35-c['s']*1.2) if c['s']<30 else 0 + min(c['b']*3,25)+min(c['a']*2,16))

print(f"📅 {target}")
print(f"{'='*80}")

# 原版冠军：买不进的涨停票
print(f"\n❌ 原版冠军(涨停买不进): {names.get(orig_best['code'],'?')}({orig_best['code']})")
print(f"   买入价: {orig_best['cl']:.2f}  涨跌幅: {orig_best['p']:+.2f}%  总分: {max(0,35-orig_best['s']*1.2) if orig_best['s']<30 else 0 + min(orig_best['b']*3,25)+min(orig_best['a']*2,16):.1f}")
print(f"   次日最高: {orig_best['n']:+.1f}%" if orig_best['n'] else "   次日最高: N/A")

# 新版：涨跌幅1~7%+排除ST
filt=[]
for c in cands:
    if c['code'] in ST: continue
    if not (1 <= c['p'] < 7): continue
    sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
    c['total']=round(sh+min(c['b']*3,25)+min(c['a']*2,16),1)
    filt.append(c)

filt.sort(key=lambda x:x['total'], reverse=True)

print(f"\n✅ 新版(可买入) — {len(filt)}只候选")
print(f"{'='*80}")
print(f"{'排名':<4} {'名称':<10} {'代码':<12} {'买入价':>7} {'涨跌幅':>6} {'总分':>5} {'次日最高':>8} {'次日收盘':>8}")
print("-"*65)

for rank,c in enumerate(filt[:10],1):
    nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
    nc_r=round((c['n'] if c['n'] else 0),1)
    mk="🏆" if rank==1 else ""
    print(f"{rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['cl']:>7.2f} {c['p']:>+5.2f}% {c['total']:>5.1f} {nh:>8}  {'N/A':>8} {mk}")

# 统计
wins=sum(1 for c in filt[:10] if c['n'] and c['n']>=2.5)
print(f"\n📊 前10中 {wins}/10 赢了")

print(f"\n⏱ 0.0秒")
