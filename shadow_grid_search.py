#!/usr/bin/env python3
"""上影线权重全维度网格搜索 v3 — 保存中间结果"""
import json, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\.cand_cache.json"
OUTPUT_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\shadow_results.json"

# ═══ 加载缓存 ═══
print("📡 加载候选缓存...")
t0 = time.time()
with open(CACHE_FILE, 'rb') as f:
    cache = json.loads(f.read().decode('utf-8'))
cands_2025 = cache['cands_2025']
cands_2026 = cache['cands_2026']
print(f"✅ {len(cands_2025)}条2025 + {len(cands_2026)}条2026, {time.time()-t0:.1f}秒")

# ═══ 按日期分组 ═══
def group_by_date(cands):
    groups = defaultdict(list)
    for c in cands:
        groups[c['d']].append(c)
    return dict(groups)

data_2025 = group_by_date(cands_2025)
data_2026 = group_by_date(cands_2026)
data_2025 = {k: v for k, v in data_2025.items() if len(v) >= 5}
data_2026 = {k: v for k, v in data_2026.items() if len(v) >= 5}
print(f"📅 2025:{len(data_2025)}天 2026:{len(data_2026)}天 (>5候选)")

# 预计算 body+atr 基础分
for yr_data in [data_2025, data_2026]:
    for dt, cands in yr_data.items():
        for c in cands:
            c['ba'] = min(c['b'] * 3, 25) + min(c['a'] * 2, 16)

# ═══ 评分引擎 ═══
def run_backtest(shadow_fn, cands_by_year):
    """返回 {year: {win, total}}"""
    result = {}
    for yr, cbd in cands_by_year.items():
        wins = 0; total = 0
        for dt, cands in cbd.items():
            best_score = -1; best_next = None
            for c in cands:
                sc = shadow_fn(c['s']) + c['ba']
                if sc > best_score:
                    best_score = sc
                    best_next = c['n']
            total += 1
            if best_next and best_next >= 2.5:
                wins += 1
        result[yr] = {"w": wins, "t": total}
    return result

# ═══ v14基线 ═══
def v14_shadow(s):
    return max(0, 35 - s * 1.2) if s < 30 else 0

print(f"\n{'='*90}")
print("🏆 v14基线...")
baseline_yr = run_backtest(v14_shadow, {"2025": data_2025, "2026": data_2026})
baseline_avg = (baseline_yr["2025"]["w"]/baseline_yr["2025"]["t"]*100 + baseline_yr["2026"]["w"]/baseline_yr["2026"]["t"]*100)/2
print(f"  v14(35-1.2x-c30): 2025:{baseline_yr['2025']['w']/baseline_yr['2025']['t']*100:.1f}%/{baseline_yr['2025']['t']}d 2026:{baseline_yr['2026']['w']/baseline_yr['2026']['t']*100:.1f}%/{baseline_yr['2026']['t']}d  平均:{baseline_avg:.2f}%")

# 保存基线
all_results = {
    "baseline": {
        "name": "v14(35-1.2x-c30)",
        "avg": round(baseline_avg, 2),
        "y25": {"w": baseline_yr["2025"]["w"], "t": baseline_yr["2025"]["t"], "pct": round(baseline_yr["2025"]["w"]/baseline_yr["2025"]["t"]*100, 1)},
        "y26": {"w": baseline_yr["2026"]["w"], "t": baseline_yr["2026"]["t"], "pct": round(baseline_yr["2026"]["w"]/baseline_yr["2026"]["t"]*100, 1)}
    },
    "results": []
}

# ═══ 方案A：线性网格 ═══
bases = [20, 22, 24, 26, 28, 30, 32, 34, 35, 36, 38, 40, 42, 45, 48, 50, 55, 60]
mults = [round(x*0.1, 1) for x in range(4, 41)]  # 0.4~4.0 步长0.1
caps = [15, 18, 20, 22, 25, 28, 30, 32, 35, 38, 40]

linear_count = len(bases) * len(mults) * len(caps)
print(f"\n{'='*90}")
print(f"📊 线性方案: {linear_count}种 ({len(bases)}基础×{len(mults)}倍数×{len(caps)}截断)")
t1 = time.time()

batch_size = 200
batches = []
batch = []
for base in bases:
    for mult in mults:
        for cap in caps:
            name = f"L({base}-{mult}x-c{cap})"
            fn = lambda s, b=base, m=mult, c=cap: max(0, b - s * m) if s < c else 0
            batch.append((name, fn))
            if len(batch) >= batch_size:
                batches.append(batch)
                batch = []
if batch:
    batches.append(batch)

for bi, batch in enumerate(batches):
    for name, fn in batch:
        yr_res = run_backtest(fn, {"2025": data_2025, "2026": data_2026})
        avg = (yr_res["2025"]["w"]/yr_res["2025"]["t"]*100 + yr_res["2026"]["w"]/yr_res["2026"]["t"]*100)/2
        change = avg - baseline_avg
        all_results["results"].append({
            "name": name, "avg": round(avg, 2), "change": round(change, 1),
            "y25": {"w": yr_res["2025"]["w"], "t": yr_res["2025"]["t"], "pct": round(yr_res["2025"]["w"]/yr_res["2025"]["t"]*100, 1)},
            "y26": {"w": yr_res["2026"]["w"], "t": yr_res["2026"]["t"], "pct": round(yr_res["2026"]["w"]/yr_res["2026"]["t"]*100, 1)}
        })
    
    done = (bi+1) * batch_size
    el = time.time() - t1
    rate = done/el if el > 0 else 0
    print(f"  {min(done, linear_count)}/{linear_count} ({rate:.0f}方案/秒, {el:.0f}秒)")
    
    # 每批保存一次
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(all_results, f)

lin_time = time.time() - t1
print(f"✅ 线性完成: {lin_time:.0f}秒")

# 已保存到文件
print(f"💾 已保存 {len(all_results['results'])}条结果到 {OUTPUT_FILE}")

# ═══ 方案B：分段 ═══
print(f"\n📊 分段方案...")
piecewise = [
    ("P1(30/20/10/5/0/0)", [30,20,10,5,0,0]),
    ("P2(35/25/15/8/3/0)", [35,25,15,8,3,0]),
    ("P3(40/28/18/10/5/0)", [40,28,18,10,5,0]),
    ("P4(30/22/15/8/0/0)", [30,22,15,8,0,0]),
    ("P5(25/18/12/5/0/0)", [25,18,12,5,0,0]),
    ("P6(35/30/22/15/8/3)", [35,30,22,15,8,3]),
    ("P7(45/35/25/15/8/0)", [45,35,25,15,8,0]),
    ("P8(50/38/25/15/8/0)", [50,38,25,15,8,0]),
    ("P9(20/15/10/5/0/0)", [20,15,10,5,0,0]),
    ("P10(40/30/20/10/5/0)", [40,30,20,10,5,0]),
]
for name, vals in piecewise:
    def fn(s, v=vals):
        bands = [0,5,10,15,20,25,30]
        for bi in range(len(bands)-1):
            if bands[bi] <= s < bands[bi+1]: return v[bi]
        return v[-1] if s >= 30 else 0
    yr_res = run_backtest(fn, {"2025": data_2025, "2026": data_2026})
    avg = (yr_res["2025"]["w"]/yr_res["2025"]["t"]*100 + yr_res["2026"]["w"]/yr_res["2026"]["t"]*100)/2
    change = avg - baseline_avg
    all_results["results"].append({
        "name": name, "avg": round(avg, 2), "change": round(change, 1),
        "y25": {"w": yr_res["2025"]["w"], "t": yr_res["2025"]["t"], "pct": round(yr_res["2025"]["w"]/yr_res["2025"]["t"]*100, 1)},
        "y26": {"w": yr_res["2026"]["w"], "t": yr_res["2026"]["t"], "pct": round(yr_res["2026"]["w"]/yr_res["2026"]["t"]*100, 1)}
    })
    print(f"  {name}: 平均{avg:.2f}% (vs v14:{change:+.1f}%)")

# ═══ 方案C：非线性 ═══
print(f"\n📊 非线性方案...")
nonlinear = [
    ("N1(40-0.02s²)", lambda s: max(0, 40 - s*s*0.02) if s < 35 else 0),
    ("N2(50-0.03s²)", lambda s: max(0, 50 - s*s*0.03) if s < 35 else 0),
    ("N3(35-0.015s²)", lambda s: max(0, 35 - s*s*0.015) if s < 35 else 0),
    ("N4(60-0.05s²)", lambda s: max(0, 60 - s*s*0.05) if s < 30 else 0),
    ("N5(40e^(-s/15))", lambda s: 40 * 2.71828 ** (-s/15) if s < 40 else 0),
    ("N6(50e^(-s/20))", lambda s: 50 * 2.71828 ** (-s/20) if s < 40 else 0),
    ("N7(60e^(-s/25))", lambda s: 60 * 2.71828 ** (-s/25) if s < 40 else 0),
    ("N8(分段5格-7)", lambda s: max(0, 35 - max(0, (s-5)//5)*7) if s < 30 else 0),
    ("N9(分段5格-10)", lambda s: max(0, 40 - max(0, (s-5)//5)*10) if s < 30 else 0),
    ("N10(分段3格-8)", lambda s: max(0, 30 - max(0, (s-3)//3)*8) if s < 27 else 0),
]
for name, fn in nonlinear:
    yr_res = run_backtest(fn, {"2025": data_2025, "2026": data_2026})
    avg = (yr_res["2025"]["w"]/yr_res["2025"]["t"]*100 + yr_res["2026"]["w"]/yr_res["2026"]["t"]*100)/2
    change = avg - baseline_avg
    all_results["results"].append({
        "name": name, "avg": round(avg, 2), "change": round(change, 1),
        "y25": {"w": yr_res["2025"]["w"], "t": yr_res["2025"]["t"], "pct": round(yr_res["2025"]["w"]/yr_res["2025"]["t"]*100, 1)},
        "y26": {"w": yr_res["2026"]["w"], "t": yr_res["2026"]["t"], "pct": round(yr_res["2026"]["w"]/yr_res["2026"]["t"]*100, 1)}
    })
    print(f"  {name}: 平均{avg:.2f}% (vs v14:{change:+.1f}%)")

# ═══ 最终保存 ═══
with open(OUTPUT_FILE, 'w') as f:
    json.dump(all_results, f)

# ═══ 结果排名 ═══
print(f"\n{'='*90}")
print(f"🏆 全部方案排名 (共{len(all_results['results'])}种)")
print(f"{'='*90}")
results_sorted = sorted(all_results["results"], key=lambda x: x["avg"], reverse=True)

# Top 30
print(f"{'排名':<4} {'方案':<25} {'平均':>7} {'vs v14':>8} {'2025胜率':>12} {'2026胜率':>12}")
print("-"*68)
for rank, r in enumerate(results_sorted[:30], 1):
    mk = "🔥" if r["change"] > 0.3 else ("✅" if r["change"] >= -0.3 else "")
    print(f"{rank:<4} {r['name']:<25} {r['avg']:>5.2f}% {r['change']:>+6.1f}% {r['y25']['pct']:>5.1f}%/{r['y25']['t']:>2}d {r['y26']['pct']:>5.1f}%/{r['y26']['t']:>2}d {mk}")

# 有多少方案比v14好
beaters = sum(1 for r in results_sorted if r["change"] > 0.3)
print(f"\n🔥 比v14好0.3%+: {beaters}种")

# v14排名
v14_rank = next((i+1 for i, r in enumerate(results_sorted) if r["name"] == "v14(35-1.2x-c30)" or "v14" in r["name"]), None)
if v14_rank is None:
    # find by baseline avg
    for i, r in enumerate(results_sorted):
        if abs(r["avg"] - baseline_avg) < 0.01:
            v14_rank = i+1
            break
print(f"📊 v14排名: 第{v14_rank}/{len(results_sorted)}" if v14_rank else "")

if beater := results_sorted[0]:
    print(f"\n{'='*90}")
    print(f"🥇 冠军: {beater['name']}")
    print(f"   平均胜率: {beater['avg']:.2f}% (vs v14:{beater['change']:+.1f}%)")
    print(f"   2025: {beater['y25']['pct']}%/{beater['y25']['t']}d  2026: {beater['y26']['pct']}%/{beater['y26']['t']}d")
    
    if beater['change'] > 0.5:
        print(f"\n🔍 进行第二轮局部微调...")
        # Parse parameters
        nm = beater['name']
        parts = nm.replace('L(', '').replace(')', '').split('-')
        best_base, rest = parts[0].split('(')[-1] if '(' in parts[0] else (parts[0], '')
        # Actually parse properly
        import re
        m = re.match(r'L\((\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)x-c(\d+(?:\.\d+)?)\)', nm)
        if m:
            b0, m0, c0 = float(m.group(1)), float(m.group(2)), float(m.group(3))
            fine_results = []
            for base in [b0-2, b0-1, b0, b0+1, b0+2]:
                if base < 10: continue
                for mult in [round(m0 + x*0.1, 1) for x in range(-3, 4)]:
                    if mult <= 0: continue
                    for cap in [c0-2, c0-1, c0, c0+1, c0+2]:
                        if cap < 10: continue
                        name = f"L({base}-{mult}x-c{cap})"
                        fn = lambda s, b=base, m=mult, c=cap: max(0, b - s * m) if s < c else 0
                        yr_res = run_backtest(fn, {"2025": data_2025, "2026": data_2026})
                        avg = (yr_res["2025"]["w"]/yr_res["2025"]["t"]*100 + yr_res["2026"]["w"]/yr_res["2026"]["t"]*100)/2
                        change = avg - baseline_avg
                        all_results["results"].append({
                            "name": name, "avg": round(avg, 2), "change": round(change, 1),
                            "y25": {"w": yr_res["2025"]["w"], "t": yr_res["2025"]["t"], "pct": round(yr_res["2025"]["w"]/yr_res["2025"]["t"]*100, 1)},
                            "y26": {"w": yr_res["2026"]["w"], "t": yr_res["2026"]["t"], "pct": round(yr_res["2026"]["w"]/yr_res["2026"]["t"]*100, 1)}
                        })
                        fine_results.append({"name": name, "avg": round(avg, 2), "change": round(change, 1)})
            
            fine_results.sort(key=lambda x: x["avg"], reverse=True)
            print(f"  局部微调 {len(fine_results)}种方案")
            print(f"  局部冠军: {fine_results[0]['name']} = {fine_results[0]['avg']:.2f}% ({fine_results[0]['change']:+.1f}%)")
            print(f"  Top5:")
            for r in fine_results[:5]:
                print(f"    {r['name']:<25} {r['avg']:>5.2f}% {r['change']:>+6.1f}%")
            
            # 最终保存
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(all_results, f)
            
            if fine_results[0]["change"] > 0:
                final = fine_results[0]
                print(f"\n{'='*90}")
                print(f"🥇 最终冠军: {final['name']} = {final['avg']:.2f}% (+{final['change']:.1f}%)")
                print(f"✅ 建议更新v14上影线公式为: {final['name']}")
            else:
                print(f"\n✅ 第二轮微调后仍无显著提升，v14保持最优")
        else:
            print(f"  无法解析参数，跳过微调")

print(f"\n{'='*90}")
print(f"📋 最终结论")
print(f"{'='*90}")
champ = max(all_results["results"], key=lambda x: x["avg"]) if all_results["results"] else None
if champ and champ["change"] > 0.3:
    print(f"✅ 找到更好的方案: {champ['name']} (+{champ['change']:.1f}%)")
else:
    print(f"❌ 在{len(all_results['results'])}种方案中，无方案显著优于v14")
    print(f"   v14(35-1.2x-c30) = {baseline_avg:.2f}%")
    print(f"   最优 = {champ['name'] if champ else 'N/A'} = {champ['avg'] if champ else 'N/A':.2f}%")
    print(f"\n✅ v14上影线权重 = 已是最优解！")

print(f"\n⏱ 总用时: {time.time()-t0:.0f}秒")
print(f"💾 详细结果已保存到: {OUTPUT_FILE}")
