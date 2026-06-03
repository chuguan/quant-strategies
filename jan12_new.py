#!/usr/bin/env python3
"""1月12日 1~7%过滤版 — 精确缓存"""
import pickle, os, time, sys
sys.stdout.reconfigure(line_buffering=True)

CACHE = r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"

print("📡 加载..."); t0=time.time()
with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']; names=cache['names']

target="2026-01-12"
cands=data.get(target,[])
print(f"📅 {target}: {len(cands)}只")

# v14评分
for c in cands:
    sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
    c['total']=round(sh+min(c['b']*3,25)+min(c['a']*2,16),1)

# 1~7%过滤
filt=[c for c in cands if 1<=c['b']<7]
filt.sort(key=lambda x:x['total'], reverse=True)
print(f"  1~7%过滤: {len(filt)}只")

# 冠军对比
orig_best=max(cands, key=lambda c: c['total'])
onh=f"{orig_best['n']:+.1f}%" if orig_best['n'] else "N/A"
print(f"\n❌ 原版冠军: {names.get(orig_best['code'],'?')}({orig_best['code']})")
print(f"  实体{orig_best['b']:.2f}% 涨幅{orig_best['p']:+.2f}% → 次日{onh}")

if filt:
    nb=filt[0]; nnh=f"{nb['n']:+.1f}%" if nb['n'] else "N/A"
    print(f"✅ 新版冠军: {names.get(nb['code'],'?')}({nb['code']})")
    print(f"  实体{nb['b']:.2f}% 涨幅{nb['p']:+.2f}% → 次日{nnh}")

# 详细表
print(f"\n{'='*95}")
print(f"🏆 1~7%过滤后排名")
print(f"{'='*95}")
print(f"{'排名':<4} {'名称':<10} {'代码':<12} {'涨跌幅':>7} {'收盘':>7} {'实体':>6} {'上影':>6} {'上影分':>6} {'实体分':>6} {'ATR分':>5} {'总分':>5} {'次日':>6}")
print("-"*82)

for rank,c in enumerate(filt[:30],1):
    sh_sc=round(max(0,35-c['s']*1.2) if c['s']<30 else 0,1)
    bd_sc=round(min(c['b']*3,25),1)
    at_sc=round(min(c['a']*2,16),1)
    nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
    mk="🏆" if rank==1 else ""
    print(f"{rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['p']:>+6.2f}% {c['cl']:>7.2f} {c['b']:>5.2f}% {c['s']:>5.1f}% {sh_sc:>5.1f} {bd_sc:>5.1f} {at_sc:>4.1f} {c['total']:>5.1f} {nh:>6} {mk}")

# 前5统计
top5=filt[:5]
w5=sum(1 for c in top5 if c['n'] and c['n']>=2.5)
print(f"\n📊 前5中 {w5}/5 赢")

print(f"\n⏱ {time.time()-t0:.2f}秒")
