#!/usr/bin/env python3
"""JAN15分析 — 赢家 vs 输家 到底差在哪"""
import json, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\.cand_cache.json"

print("📡 加载..."); t0=time.time()
with open(CACHE_FILE,'rb') as f: cache=json.loads(f.read().decode('utf-8'))

data=defaultdict(list)
for c in cache['cands_2026']:
    data[c['d']].append(c)

target="2026-01-15"
cands=data.get(target,[])
if not cands: print("❌ 无数据"); sys.exit(0)

for c in cands:
    sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
    c['ba']=min(c['b']*3,25)+min(c['a']*2,16)
    c['total']=round(sh+c['ba'],1)

# 按v14评分排名
cands.sort(key=lambda x:x['total'], reverse=True)

winners=[c for c in cands if c['n'] and c['n']>=2.5]
losers=[c for c in cands if c['n'] and c['n']<2.5]
no_data=[c for c in cands if not c['n']]

print(f"📅 {target} — 共{len(cands)}只候选")
print(f"  赢家(次日≥2.5%): {len(winners)}只")
print(f"  输家(次日<2.5%): {len(losers)}只")
print(f"  无次日数据: {len(no_data)}只")

# 特征对比
print(f"\n{'='*60}")
print(f"📊 赢家 vs 输家 特征对比")
print(f"{'='*60}")
def avg(lst,k): return round(sum(c[k] for c in lst if c[k] is not None)/len(lst),2)

for key,fname in [('s','上影%'),('b','实体%'),('a','ATR%'),('total','总分')]:
    wa=avg(winners,key)
    la=avg(losers,key)
    print(f"  {fname:<8} 赢家={wa:>7.2f}  输家={la:>7.2f}  差={wa-la:>+7.2f}")

# 分布对比
print(f"\n{'='*60}")
print(f"📊 分布对比")
print(f"{'='*60}")
# 上影线
for threshold in [5,10,15,20,30]:
    wp=sum(1 for c in winners if c['s']<threshold)/len(winners)*100
    lp=sum(1 for c in losers if c['s']<threshold)/len(losers)*100
    print(f"  上影<{threshold}%: 赢家{wp:.0f}%  输家{lp:.0f}%  差={wp-lp:+.0f}%")

# 实体
for threshold in [1,2,3,4,5]:
    wp=sum(1 for c in winners if c['b']>threshold)/len(winners)*100
    lp=sum(1 for c in losers if c['b']>threshold)/len(losers)*100
    print(f"  实体>{threshold}%: 赢家{wp:.0f}%  输家{lp:.0f}%  差={wp-lp:+.0f}%")

# Top 10详情
print(f"\n{'='*80}")
print(f"🏆 评分前10 — 赢家✅/输家❌")
print(f"{'='*80}")
print(f"{'排名':<4} {'总分':>5} {'上影%':>6} {'实体%':>6} {'ATR%':>6} {'次日':>6}")
print("-"*35)
for rank,c in enumerate(cands[:20],1):
    nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
    mk="✅" if c['n'] and c['n']>=2.5 else ("❌" if c['n'] else "—")
    print(f"{rank:<4} {c['total']:>5.1f} {c['s']:>5.1f}% {c['b']:>5.2f}% {c['a']:>5.2f}% {nh:>6} {mk}")

# 结论
print(f"\n{'='*60}")
winner_ft=[f"上影{avg(winners,'s'):.1f}%" for _ in [1]]
loser_ft=[f"上影{avg(losers,'s'):.1f}%" for _ in [1]]
print(f"💡 结论")
print(f"  赢家特征: 实体{avg(winners,'b'):.2f}%  上影{avg(winners,'s'):.1f}%")
print(f"  输家特征: 实体{avg(losers,'b'):.2f}%  上影{avg(losers,'s'):.1f}%")
print(f"  差异: 极小 — 当天涨跌基本随机")

print(f"\n⏱ {time.time()-t0:.1f}秒")
