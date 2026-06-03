#!/usr/bin/env python3
"""检查缓存数据年份分布"""
import json, os, time

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
print(f"总文件: {len(files)}")

import random; random.seed(42)
sample=random.sample(files, min(200, len(files)))

h2024=h2025=h2026=0
min_date="9999-99-99"
max_date="0000-00-00"
earliest_records=9999

for fn in sample:
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        dates=[r['date'] for r in recs]
        if len(recs) < earliest_records: earliest_records = len(recs)
        if any(d.startswith('2024') for d in dates): h2024+=1
        if any(d.startswith('2025') for d in dates): h2025+=1
        if any(d.startswith('2026') for d in dates): h2026+=1
        if dates[0] < min_date: min_date = dates[0]
        if dates[-1] > max_date: max_date = dates[-1]
    except: pass

print(f"\n📊 {len(sample)}只样本统计:")
print(f"  有2024数据: {h2024}/{len(sample)} = {h2024/len(sample)*100:.0f}%")
print(f"  有2025数据: {h2025}/{len(sample)} = {h2025/len(sample)*100:.0f}%")
print(f"  有2026数据: {h2026}/{len(sample)} = {h2026/len(sample)*100:.0f}%")
print(f"  最早日期: {min_date}")
print(f"  最晚日期: {max_date}")
print(f"  最小记录数: {earliest_records}条")
print(f"\n⚠️ 结论: 2024年几乎完全没有数据！最早从{min_date}开始有部分数据")
print(f"   2025年也不是所有股票都有数据")
print(f"   需要重新下载/补充数据才能完整回测")
