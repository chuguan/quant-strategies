#!/usr/bin/env python3
"""核实上海港湾1月12日数据"""
import json, os

fp = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache\sh605598.json"
with open(fp, 'rb') as f: recs = json.loads(f.read().decode('utf-8'))

print(f"总记录数: {len(recs)}")
print()

# 找1月9日-1月13日的数据
for r in recs:
    if r['date'] in ['2026-01-09','2026-01-12','2026-01-13','2026-01-14','2026-01-08','2026-01-06']:
        print(f"{r['date']}: 开{r['open']:.2f} 高{r['high']:.2f} 低{r['low']:.2f} 收{r['close']:.2f}")

# 计算涨跌幅
for i,r in enumerate(recs):
    if r['date'] in ['2026-01-09','2026-01-12','2026-01-13']:
        idx = i
for j in range(max(0,idx-2), min(len(recs), idx+3)):
    r = recs[j]
    pct = (r['close']/recs[j-1]['close']-1)*100 if j>0 else 0
    print(f"{r['date']}: 收{r['close']:.2f} 涨跌幅{pct:+.2f}% 第{j}条")

# 1月12日->1月13日
cl_12 = recs[idx]['close']
hi_13 = recs[idx+1]['high']
nxt_pct = (hi_13/cl_12 - 1)*100
print(f"\n1月12日收盘: {cl_12:.2f}")
print(f"1月13日最高: {hi_13:.2f}")
print(f"次日最高涨幅: {nxt_pct:+.2f}%")
