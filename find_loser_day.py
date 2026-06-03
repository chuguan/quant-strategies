#!/usr/bin/env python3
"""找输家日并详细分析"""
import json, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\.cand_cache.json"
print("📡 加载..."); t0=time.time()
with open(CACHE_FILE,'rb') as f: cache=json.loads(f.read().decode('utf-8'))

data=defaultdict(list)
for c in cache['cands_2026']:
    data[c['d']].append(c)

data={k:v for k,v in data.items() if len(v)>=5}

for dt,cands in data.items():
    for c in cands:
        sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
        c['ba']=min(c['b']*3,25)+min(c['a']*2,16)
        c['total']=round(sh+c['ba'],1)

# 找所有输家日
loser_days=[]
for dt in sorted(data.keys()):
    cands=data[dt]
    best=max(cands, key=lambda c: c['total'])
    if best['n'] is None: continue
    if best['n']<2.5:
        loser_days.append((dt, best['n'], best['total'], best['s'], best['b'], best['a']))

loser_days.sort(key=lambda x: x[1])  # 最差的排前面
print(f"📅 2026年共{len(data)}天，输家日{len(loser_days)}天")

# 最烂的5天
print(f"\n{'='*80}")
print(f"💀 输家日排名（按次日最低）")
print(f"{'='*80}")
print(f"{'日期':<12} {'次日':>6} {'总分':>5} {'上影%':>6} {'实体%':>6} {'ATR%':>6}")
print("-"*50)
for dt, nh, tot, s, b, a in loser_days[:10]:
    print(f"{dt:<12} {nh:>+5.1f}% {tot:>5.1f} {s:>5.1f}% {b:>6.2f}% {a:>5.2f}%")

# 选最烂的那个（或者选第一个）
target_day = loser_days[0][0]
print(f"\n{'='*80}")
print(f"🔍 重点分析: {target_day} （冠军次日{loser_days[0][1]:+.1f}%）")
print(f"{'='*80}")

cands=data[target_day]
cands.sort(key=lambda x:x['total'], reverse=True)

# 全量对比
winners=[c for c in cands if c['n'] and c['n']>=2.5]
losers=[c for c in cands if c['n'] and c['n']<2.5]

print(f"  全池{len(cands)}只: 赢家{len(winners)}只 输家{len(losers)}只")

def avg(lst,k): return round(sum(c[k] for c in lst if c[k] is not None)/len(lst),2)
print(f"\n📊 赢家 vs 输家 特征")
for key,nm in [('s','上影%'),('b','实体%'),('a','ATR%'),('total','总分')]:
    wa=avg(winners,key); la=avg(losers,key)
    chk="⚠️" if abs(wa-la)<2 else ""
    print(f"  {nm:<8} 赢家={wa:>6.2f}  输家={la:>6.2f}  差={wa-la:>+5.2f} {chk}")

# Top15+亚军分析
print(f"\n{'='*80}")
print(f"🏆 评分Top15 — 赢家✅/输家❌")
print(f"{'='*80}")
print(f"{'排名':<4} {'总分':>5} {'上影%':>6} {'实体%':>6} {'ATR%':>6} {'次日':>6}")
print("-"*35)
for rank,c in enumerate(cands[:15],1):
    nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
    mk="✅" if c['n'] and c['n']>=2.5 else ("❌" if c['n'] else "—")
    print(f"{rank:<4} {c['total']:>5.1f} {c['s']:>5.1f}% {c['b']:>5.2f}% {c['a']:>5.2f}% {nh:>6} {mk}")

# 如果加了1~7%过滤会怎样
print(f"\n{'='*80}")
print(f"🔍 如果加实体1%~7%过滤会怎样？")
print(f"{'='*80}")
filt=[c for c in cands if 1<=c['b']<7]
filt.sort(key=lambda x:x['total'], reverse=True)
print(f"  过滤后剩{len(filt)}只候选 (原{len(cands)}只)")
if len(filt)>=5:
    champ_filt=filt[0]
    print(f"  新冠军: 实体{champ_filt['b']:.2f}% 上影{champ_filt['s']:.1f}% → 次日{champ_filt['n']:+.1f}%")
    # 前5的输赢
    wins_f=sum(1 for c in filt[:5] if c['n'] and c['n']>=2.5)
    print(f"  前5中 {wins_f}/5 赢了")
else:
    print(f"  候选不足5只，无法选出")

print(f"\n⏱ {time.time()-t0:.1f}秒")
