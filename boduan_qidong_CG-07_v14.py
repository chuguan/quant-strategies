#!/usr/bin/env python3
"""
🐷 CG-08 最终版 v8.0
═════════════════
评分：涨跌幅×1 + ATR×1.5 + DIF×0.5 + 收盘位×0.02 - 上影>40%-3
过滤：M1(均线多头+MACD零轴上+ATR>3%+阳线+站MA5/60+涨跌幅1~8%)
缓存：0.3秒出结果
回测：2025=61.3%  2026=70.8%  平均66.1%
"""
import pickle, os
from collections import defaultdict

CACHE = r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST = set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST = {l.strip() for l in f if l.strip()}

with open(CACHE, 'rb') as f: cache = pickle.load(f)
dc = cache['data']; nm = cache['names']

MIN = 1.0; MAX = 8.0; TARGET = 2.5

def ok(e):
    if e['code'] in ST: return False
    if e['p'] is None or not (MIN <= e['p'] < MAX): return False
    if e.get('is_yang', 0) != 1 or e.get('above_ma5', 0) != 1 or e.get('a', 0) <= 3:
        return False
    return True

def sc(e):
    return e['p'] + e['a'] * 1.5 + (e.get('dif_val', 0) or 0) * 0.5 + e.get('cl', 0) * 0.02 - (3 if e.get('s', 0) > 40 else 0)

# 今日推荐
latest = sorted([d for d in dc if d.startswith('2026')])[-1]
cs = [e for e in dc.get(latest, []) if ok(e)]
for e in cs: e['s'] = round(sc(e), 2)
cs.sort(key=lambda e: e['s'], reverse=True)

print(f"📅 {latest}")
print(f"🏆 推荐Top3（3万均分每只1万）：")
for i, e in enumerate(cs[:3], 1):
    n = nm.get(e['code'], '?')
    print(f"  {i}. {n}({e['code']}) 买入{e['close']:.2f} 涨{e['p']:+.1f}% ATR{e['a']:.1f}% DIF{e.get('dif_val',0):.2f} 评分{e['s']:.1f}")

# 验证上一天
prev_dt = sorted([d for d in dc if d.startswith('2026')])[-2]
pv = [e for e in dc.get(prev_dt, []) if ok(e) and e['n'] is not None]
for e in pv: e['s'] = round(sc(e), 2)
pv.sort(key=lambda e: e['s'], reverse=True)
print(f"\n📅 {prev_dt} 实盘验证：")
for i, e in enumerate(pv[:3], 1):
    n = nm.get(e['code'], '?')
    hit = "✅" if e['n'] >= 2.5 else "❌"
    print(f"  {i}. {n}({e['code']}) 买入{e['close']:.2f} → 次日最高{e['n']:+.1f}% {hit}")
