#!/usr/bin/env python3
"""
关键修复：加收盘位因子的新评分
假设：p+a+cl*w 公式中，收盘位(cl)到底该占多少权重？
"""
import pickle, os
from collections import defaultdict

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']

MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5

def filter_data(yr):
    by_date=defaultdict(list)
    for dt in data_cache:
        if not dt.startswith(yr): continue
        for c in data_cache[dt]:
            if c['code'] in ST: continue
            p=c['p']; n=c['n']
            if p is None or not (MIN_CHG <= p < MAX_CHG): continue
            if n is None: continue
            by_date[dt].append(c)
    return {k:v for k,v in by_date.items() if len(v)>=5}

data25=filter_data('2025')
data26=filter_data('2026')
print(f"📅 2025: {len(data25)}天, 2026: {len(data26)}天")

# 各种收盘位权重测试
# 核心公式: p + a + cl * w_cl
print("\n═══ 加收盘位权重 ═══")
print(f"{'cl权重':<8} {'2025':>8} {'2026':>8} {'平均':>8}")
print("-"*35)

results=[]
for w_cl in [0, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.50]:
    fn=lambda c, w=w_cl: c['p']+c['a']+c['cl']*w
    w25=sum(1 for dt in sorted(data25.keys()) if max(data25[dt], key=fn)['n']>=TARGET)/max(len(data25),1)*100
    w26=sum(1 for dt in sorted(data26.keys()) if max(data26[dt], key=fn)['n']>=TARGET)/max(len(data26),1)*100
    avg=(w25+w26)/2
    results.append((avg, w25, w26, w_cl))
    print(f"{w_cl:<8.2f} {w25:>7.1f}% {w26:>7.1f}% {avg:>7.1f}%")

results.sort(key=lambda x:x[0], reverse=True)
best=results[0]
print(f"\n🏆 最优: cl权重={best[3]:.2f}, 两年均{best[0]:.1f}%")

# ═══ 现在试：收盘位 + 实体 + 上影 多维度 ═══
print("\n═══ 多维搜索：p+a+cl*w_cl+b*w_b+s*w_s ═══")
results2=[]
for w_cl in [0, 0.01, 0.02, 0.03, 0.05, 0.10, 0.20]:
    for w_b in [0, -0.02, -0.05, -0.10, 0.02, 0.05]:
        for w_s in [0, 0.01, 0.02, 0.03, 0.05, 0.10, -0.02]:
            if w_cl==0 and w_b==0 and w_s==0: continue
            fn=lambda c, w1=w_cl, w2=w_b, w3=w_s: c['p']+c['a']+c['cl']*w1+c['b']*w2+c['s']*w3
            w25=sum(1 for dt in sorted(data25.keys()) if max(data25[dt], key=fn)['n']>=TARGET)/max(len(data25),1)*100
            w26=sum(1 for dt in sorted(data26.keys()) if max(data26[dt], key=fn)['n']>=TARGET)/max(len(data26),1)*100
            avg=(w25+w26)/2
            results2.append((avg, w25, w26, f"p+a+cl×{w_cl}+b×{w_b}+s×{w_s}"))

results2.sort(key=lambda x:x[0], reverse=True)
print(f"{'排名':<4} {'两年均':>7} {'2025':>7} {'2026':>7} {'公式':<40}")
print("-"*65)
for i,(avg,w25,w26,formula) in enumerate(results2[:10],1):
    print(f"{i:<4} {avg:>6.1f}% {w25:>6.1f}% {w26:>6.1f}% {formula}")
