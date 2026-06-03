#!/usr/bin/env python3
"""最新日选股 — v14+1~7%过滤，保存全部结果"""
import pickle, os, time, sys
sys.stdout.reconfigure(line_buffering=True)

CACHE = r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
OUTPUT = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\latest_picks.txt"
TARGET = "2026-05-22"

print("📡 加载..."); t0=time.time()
with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']; names=cache['names']

cands=data.get(TARGET,[])
if not cands: print("❌ 无数据"); exit(1)

# v14评分
for c in cands:
    sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
    c['sh_sc']=round(sh,1)
    c['bd_sc']=round(min(c['b']*3,25),1)
    c['at_sc']=round(min(c['a']*2,16),1)
    c['total']=round(sh+c['bd_sc']+c['at_sc'],1)

# 1~7%过滤
filt=[c for c in cands if 1<=c['b']<7]
filt.sort(key=lambda x:x['total'], reverse=True)

lines=[]
lines.append(f"📅 {TARGET} CG-07 v14 + 实体1%~7%过滤")
lines.append(f"={'='*80}")
lines.append(f"原始候选: {len(cands)}只  过滤后: {len(filt)}只")
lines.append("")

# 冠军对比
orig_best=max(cands, key=lambda c: c['total'])
onh=f"{orig_best['n']:+.1f}%" if orig_best['n'] else "N/A"
lines.append(f"❌ 原版冠军: {names.get(orig_best['code'],'?')}({orig_best['code']}) 实体{orig_best['b']:.2f}% 涨幅{orig_best['p']:+.2f}% → 次日{onh}")

if filt:
    nb=filt[0]
    nnh=f"{nb['n']:+.1f}%" if nb['n'] else "N/A"
    lines.append(f"✅ 新版冠军: {names.get(nb['code'],'?')}({nb['code']}) 实体{nb['b']:.2f}% 涨幅{nb['p']:+.2f}% → 次日{nnh}")

lines.append("")

# 全量候选表
lines.append(f"🏆 全部候选排名 ({len(filt)}只)")
lines.append(f"{'排名':<4} {'名称':<10} {'代码':<12} {'涨跌幅':>7} {'收盘':>7} {'实体':>6} {'上影':>6} {'上影分':>6} {'实体分':>6} {'ATR分':>5} {'总分':>5} {'次日':>6}")
lines.append("-"*80)

for rank,c in enumerate(filt,1):
    nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
    mk="🏆" if rank==1 else ""
    lines.append(f"{rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['p']:>+6.2f}% {c['cl']:>7.2f} {c['b']:>5.2f}% {c['s']:>5.1f}% {c['sh_sc']:>5.1f} {c['bd_sc']:>5.1f} {c['at_sc']:>4.1f} {c['total']:>5.1f} {nh:>6} {mk}")

# 统计
w5=sum(1 for c in filt[:5] if c['n'] and c['n']>=2.5)
lines.append(f"\n📊 前5: {w5}/5 赢")

text="\n".join(lines)
with open(OUTPUT,'w',encoding='utf-8') as f:
    f.write(text)

print(text)
print(f"\n💾 已保存: {OUTPUT}")
print(f"⏱ {time.time()-t0:.2f}秒")
