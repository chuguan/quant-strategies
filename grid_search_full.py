#!/usr/bin/env python3
"""
全面网格搜索 — 涨跌幅1~8%过滤下，所有评分公式的胜率
评分用今天数据(p=涨跌幅%, b=实体%, s=上影%, a=ATR%, cl=收盘位置)
验证用n=次日最高%
"""
import pickle, os, sys, time
from collections import defaultdict
from itertools import product
import math

sys.stdout.reconfigure(line_buffering=True)

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']

TARGET=2.5  # 次日最高≥2.5%算赢
MIN_CHG=1.0
MAX_CHG=8.0

def filter_data(yr):
    """按年份过滤数据，应用涨跌幅1~8%硬过滤"""
    by_date=defaultdict(list)
    for dt in data_cache:
        if not dt.startswith(yr): continue
        for c in data_cache[dt]:
            if c['code'] in ST: continue
            p=c['p']  # 涨跌幅%
            if p is None or not (MIN_CHG <= p < MAX_CHG): continue
            if c['n'] is None: continue  # 没有次日数据
            by_date[dt].append(c)
    # 只保留≥5只候选的日期
    by_date={k:v for k,v in by_date.items() if len(v)>=5}
    return by_date

def test_score(data, score_fn, name):
    """测试一个评分公式在全年数据上的表现"""
    wins=0; total=0
    for dt in sorted(data.keys()):
        best=max(data[dt], key=score_fn)
        total+=1
        if best['n'] >= TARGET:
            wins+=1
    wr=wins/total*100 if total>0 else 0
    return wr, wins, total

# ═══════════════════════════════════
# 网格 1: 线性组合 w1*p + w2*a + w3*b + w4*s + w5*cl
# p=涨跌幅, a=ATR, b=实体, s=上影, cl=收盘位置
# ═══════════════════════════════════
print("="*80)
print("🏁 第1轮：5维线性组合网格搜索")
print("="*80)

weights=[0,0.5,1,2,3,5,8]
results=[]

data_2025=filter_data('2025')
data_2026=filter_data('2026')
print(f"📅 2025: {len(data_2025)}天, 2026: {len(data_2026)}天")

t0=time.time()
count=0

# Limit to reasonable combinations - we don't want all 7^5 = 16807
# Try combinations of 2-3 factors first
for w_p in [0, 0.5, 1, 2, 3, 5]:
    for w_a in [0, 0.5, 1, 2, 3, 5]:
        for w_b in [0, 0.5, 1, 2, 3]:
            for w_s in [0, -0.5, -1, -2]:
                for w_cl in [0, 0.5, 1, 2]:
                    if w_p==0 and w_a==0 and w_b==0 and w_s==0 and w_cl==0:
                        continue
                    score_fn=lambda c,wp=w_p,wa=w_a,wb=w_b,ws=w_s,wcl=w_cl: (
                        (c['p']*wp if wp else 0) +
                        (c['a']*wa if wa else 0) +
                        (c['b']*wb if wb else 0) +
                        (c['s']*ws if ws else 0) +
                        (c['cl']*wcl if wcl else 0)
                    )
                    wr25, w25, t25 = test_score(data_2025, score_fn, "")
                    wr26, w26, t26 = test_score(data_2026, score_fn, "")
                    avg=(wr25+wr26)/2
                    results.append((avg, wr25, wr26, w25, t25, w26, t26, f"({w_p})p+({w_a})a+({w_b})b+({w_s})s+({w_cl})cl"))
                    count+=1

results.sort(key=lambda x: x[0], reverse=True)

print(f"\n🔬 共测试{count}种组合，耗时{time.time()-t0:.0f}秒")
print(f"\n{'='*80}")
print(f"🏆 TOP 20 线性组合")
print(f"{'='*80}")
print(f"{'排名':<4} {'两年均':>7} {'2025':>7} {'2026':>7} {'公式':<45}")
print("-"*80)
for i,(avg,w25,w26,wc25,t25,wc26,t26,formula) in enumerate(results[:20],1):
    print(f"{i:<4} {avg:>6.1f}% {w25:>6.1f}% {w26:>6.1f}% {formula}")

print(f"\n✅ 第1轮完成，最优: {results[0][0]:.1f}% — {results[0][7]}")
