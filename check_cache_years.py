#!/usr/bin/env python3
"""检查缓存数据完整性 — 看各年份数据是否齐全"""
import json, os

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files=[f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
print(f"📊 共{len(main_files)}只主板股缓存文件")

# 检查每个文件的日期覆盖范围
year_stats = {"2024": {"files":0, "dates":set(), "min_dates_per_file":[], "avg_recs":0},
              "2025": {"files":0, "dates":set(), "min_dates_per_file":[], "avg_recs":0},
              "2026": {"files":0, "dates":set(), "min_dates_per_file":[], "avg_recs":0}}

files_with_2024=0; files_with_2025=0; files_with_2026=0
total_recs=0

for i, fn in enumerate(main_files[:200]):  # 取样200只
    fp=os.path.join(CACHE_DIR,fn)
    try:
        with open(fp,'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        dates=[r["date"] for r in recs]
        has_2024=any(d.startswith("2024") for d in dates)
        has_2025=any(d.startswith("2025") for d in dates)
        has_2026=any(d.startswith("2026") for d in dates)
        if has_2024: files_with_2024+=1
        if has_2025: files_with_2025+=1
        if has_2026: files_with_2026+=1
        total_recs+=len(recs)
        
        for yr in ["2024","2025","2026"]:
            yr_dates=[d for d in dates if d.startswith(yr)]
            if yr_dates:
                year_stats[yr]["files"]+=1
                year_stats[yr]["dates"].update(yr_dates)
                year_stats[yr]["min_dates_per_file"].append(len(yr_dates))
    except: pass

print(f"\n📅 各年份数据覆盖（200只样本）")
print(f"{'年份':>6} {'有数据文件':>12} {'交易日':>10} {'最少条/文件':>12} {'最多条/文件':>12}")
print("-"*52)
for yr in ["2024","2025","2026"]:
    s=year_stats[yr]
    dates_sorted=sorted(s["dates"])
    if dates_sorted:
        print(f"{yr:>6} {s['files']:>8}/200 {len(dates_sorted):>5}天 {min(s['min_dates_per_file']):>5}~{max(s['min_dates_per_file']):>5}条")
        print(f"           日期范围: {dates_sorted[0]} ~ {dates_sorted[-1]}")
    else:
        print(f"{yr:>6} 无数据")

# 看5月份各年的交易日数
print(f"\n📅 5月份交易日统计")
for yr in ["2024","2025","2026"]:
    s=year_stats[yr]
    may_dates=sorted([d for d in s["dates"] if d.startswith(f"{yr}-05")])
    print(f"  {yr}年5月: {len(may_dates)}天 ({may_dates[0] if may_dates else '无'} ~ {may_dates[-1] if may_dates else '无'})")

# 看最后一笔数据日期
print(f"\n💾 数据时效性")
print(f"  总记录数(200只): {total_recs}条")
print(f"  均每只: {total_recs/200:.0f}条")
