#!/usr/bin/env python3
"""两年综合最优区间 — 找折中方案"""
import json, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\.cand_cache.json"

print("📡 加载缓存..."); t0=time.time()
with open(CACHE_FILE,'rb') as f: cache=json.loads(f.read().decode('utf-8'))

all_year_data = {}
for yr_name, yr_data in [("2025", cache['cands_2025']), ("2026", cache['cands_2026'])]:
    data = defaultdict(list)
    for c in yr_data:
        data[c['d']].append(c)
    data = {k:v for k,v in data.items() if len(v)>=5}
    for dt,cands in data.items():
        for c in cands:
            c['ba'] = min(c['b']*3,25) + min(c['a']*2,16)
    all_year_data[yr_name] = data

def v14(s,ba): return (max(0,35-s*1.2) if s<30 else 0) + ba

# 跑所有28种组合，记录两年数据
all_results = {}
for lb in range(1,8):
    for ub in range(lb+1,9):
        key = f"{lb}~{ub}"
        all_results[key] = {}
        for yr_name, data in all_year_data.items():
            w=0; t=0
            for dt in sorted(data.keys()):
                cands=[c for c in data[dt] if lb <= c['b'] < ub]
                if len(cands)<5: continue
                best=max(cands, key=lambda c: v14(c['s'],c['ba']))
                t+=1
                if best['n'] and best['n']>=2.5: w+=1
            all_results[key][yr_name] = {"w":w, "t":t, "pct":round(w/t*100,1) if t else 0}

# 计算综合排名
ranked = []
for key, yr_data in all_results.items():
    y25 = yr_data["2025"]["pct"]
    y26 = yr_data["2026"]["pct"]
    avg = round((y25 + y26) / 2, 1)
    t25 = yr_data["2025"]["t"]
    t26 = yr_data["2026"]["t"]
    avg_days = (t25 + t26) // 2
    ranked.append((avg, key, y25, y26, t25, t26, avg_days))

ranked.sort(reverse=True)

# v14基线(无过滤)
def calc_baseline(data):
    w=0; t=0
    for dt in sorted(data.keys()):
        best=max(data[dt], key=lambda c: v14(c['s'],c['ba']))
        t+=1
        if best['n'] and best['n']>=2.5: w+=1
    return w/t*100
b25 = calc_baseline(all_year_data["2025"])
b26 = calc_baseline(all_year_data["2026"])
bavg = round((b25+b26)/2, 1)

print(f"\n{'='*100}")
print(f"📊 全部28种区间 — 两年综合排名")
print(f"{'='*100}")
print(f"v14原版(无涨幅过滤): 2025={b25:.1f}% 2026={b26:.1f}% 平均={bavg:.1f}%")
print(f"\n{'排名':<4} {'区间':<8} {'2年均值':>8} {'2025':>8} {'2026':>8} {'vs原版':>8} {'平均天数':>8}")
print("-"*55)

for rank, (avg, key, y25, y26, t25, t26, ad) in enumerate(ranked, 1):
    diff = round(avg - bavg, 1)
    mk = "🔥" if diff > 0 else ("✅" if diff >= -1 else "")
    print(f"{rank:<4} {key:<8} {avg:>6.1f}%  {y25:>5.1f}% {y26:>5.1f}% {diff:>+6.1f}% {ad:>4}d {mk}")

best = ranked[0]
print(f"\n{'='*100}")
print(f"🥇 综合最优: {best[1]} = {best[0]}% (vs原版{round(best[0]-bavg,1):+.1f}%)")
print(f"   2025: {best[2]}%  2026: {best[3]}%")
print(f"   ⚠️ 但注意是实体%不是真实涨跌幅%")

print(f"\n⏱ {time.time()-t0:.1f}秒")
