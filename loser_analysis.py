#!/usr/bin/env python3
"""输家冠军分析 — 用现成缓存，秒出结果"""
import json, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\.cand_cache.json"

print("📡 加载缓存..."); t0=time.time()
with open(CACHE_FILE,'rb') as f: cache=json.loads(f.read().decode('utf-8'))
cands_2026 = cache['cands_2026']
print(f"✅ {len(cands_2026)}条2026候选, {time.time()-t0:.1f}秒")

data = defaultdict(list)
for c in cands_2026:
    data[c['d']].append(c)
data = {k:v for k,v in data.items() if len(v)>=5}
print(f"📅 2026: {len(data)}天 (≥5候选)")

for dt,cands in data.items():
    for c in cands:
        c['ba'] = min(c['b']*3,25) + min(c['a']*2,16)

def v14_total(s, ba):
    sh = max(0, 35 - s * 1.2) if s < 30 else 0
    return sh + ba

wins=0; losses=0; total=0
losing_champs=[]; winning_champs=[]

for dt in sorted(data.keys()):
    cands = data[dt]
    best = max(cands, key=lambda c: v14_total(c['s'], c['ba']))
    total += 1
    if best['n'] and best['n'] >= 2.5:
        wins += 1
        winning_champs.append(best)
    else:
        losses += 1
        losing_champs.append(best)

print(f"📊 {total}天: 赢{wins}({wins/total*100:.1f}%) 输{losses}({losses/total*100:.1f}%)")

print(f"\n{'='*100}")
print(f"❌ 输家冠军列表 ({losses}天)")
print(f"{'='*100}")
print(f"{'日期':<12} {'上影%':>6} {'实体%':>7} {'ATR%':>6} {'总分':>5} {'次日高':>7}")
print("-"*50)
losing_champs.sort(key=lambda x: x['n'] if x['n'] else -999)
for c in losing_champs:
    sh = max(0,35-c['s']*1.2) if c['s']<30 else 0
    sc = sh + c['ba']
    nh = f"{c['n']:+.1f}%" if c['n'] else "N/A"
    print(f"{c['d']:<12} {c['s']:>5.1f}% {c['b']:>6.2f}% {c['a']:>5.2f}% {sc:>5.1f} {nh:>7}")

print(f"\n{'='*100}")
print(f"📊 输家 vs 赢家 特征对比")
print(f"{'='*100}")
def avg(lst,key): return round(sum(c[key] for c in lst if c[key] is not None)/len(lst),2)

for key,f in [('s','上影%'),('b','实体%'),('a','ATR%')]:
    lv=avg(losing_champs,key)
    wv=avg(winning_champs,key)
    diff=lv-wv
    mk=" ⚠️" if abs(diff)>1 else ""
    print(f"  {f:<8} 输家均值={lv:>6.2f}%  赢家均值={wv:>6.2f}%  差值={diff:>+6.2f}%{mk}")

print(f"\n💡 输家死亡模式")
over_shadow = [c for c in losing_champs if c['s']>15]
print(f"  上影>15%: {len(over_shadow)}/{losses} ({len(over_shadow)/losses*100:.0f}%)")
for c in over_shadow[:5]:
    print(f"    {c['d']} 上影{c['s']:.1f}% → 次日{c['n']:+.1f}%")

both = [c for c in losing_champs if c['s']>10 and c['b']<1.5]
print(f"  上影>10%+实体<1.5%: {len(both)}/{losses} ({len(both)/losses*100:.0f}%)")
for c in both[:5]:
    print(f"    {c['d']} 上影{c['s']:.1f}% 实体{c['b']:.2f}% → 次日{c['n']:+.1f}%")

print(f"\n⏱ {time.time()-t0:.1f}秒")
