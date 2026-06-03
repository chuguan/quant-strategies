#!/usr/bin/env python3
"""全量回测+今日推荐 秒出版"""
import pickle, os
from collections import defaultdict

CACHE = r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST = set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST = {l.strip() for l in f if l.strip()}

with open(CACHE, 'rb') as f: c = pickle.load(f)
data = c['data']; names = c['names']
MIN = 1.0; MAX = 8.0; TARGET = 2.5

def ok(e):
    if e['code'] in ST: return False
    if e['p'] is None or not (MIN <= e['p'] < MAX): return False
    if e['n'] is None: return False
    if e.get('is_yang', 0) != 1 or e.get('above_ma5', 0) != 1 or e.get('a', 0) <= 3:
        return False
    return True

def sc(e):
    return (e['p'] + e['a'] * 1.5 + (e.get('dif_val', 0) or 0) * 0.5
            + e.get('cl', 0) * 0.02 - (3 if e.get('s', 0) > 40 else 0))

for yr in ['2025', '2026']:
    by_date = defaultdict(list)
    for dt in data:
        if not dt.startswith(yr): continue
        for e in data[dt]:
            if ok(e): by_date[dt].append(e)
    by_date = {k: v for k, v in by_date.items() if len(v) >= 5}

    win = 0; total = 0
    print()
    print("=" * 130)
    print("  %s年 回测 (%d天)" % (yr, len(by_date)))
    print("=" * 130)
    print("日期        名称      代码             买入价  涨跌幅  ATR  收盘位 上影   DIF   评分  次日高  次日收  结果")
    print("-" * 130)

    for dt in sorted(by_date.keys()):
        best = max(by_date[dt], key=sc)
        total += 1
        nh = best['n']
        name = names.get(best['code'], '?')
        res = "OK" if nh >= TARGET else "XX"
        if nh >= TARGET: win += 1
        nc = best.get('next_close')
        nc_s = "%+.1f%%" % nc if nc is not None else "  N/A "
        print("%s %-8s %-14s %7.2f %+.1f%% %5.1f%% %4.0f%% %5.1f%% %5.2f %5.1f %+5.1f%% %s %s" % (
            dt, name, best['code'], best['close'], best['p'], best['a'],
            best.get('cl', 0), best.get('s', 0), best.get('dif_val', 0) or 0,
            sc(best), nh, nc_s, res))

    print("-" * 130)
    print("  总计: %d天  胜率: %.1f%% (%d/%d)" % (total, win / total * 100, win, total))

print()
print("=" * 130)
latest = sorted([d for d in data if d.startswith('2026')])[-1]
cs = [e for e in data[latest] if e['code'] not in ST
      and MIN <= e['p'] < MAX
      and e.get('is_yang', 0) == 1
      and e.get('above_ma5', 0) == 1
      and e.get('a', 0) > 3]
for e in cs: e['s2'] = sc(e)
cs.sort(key=lambda e: e['s2'], reverse=True)
print("  今日推荐(%s) Top5:" % latest)
print("#  名称      代码             买入价  涨跌幅  ATR  收盘位 上影   DIF   评分")
print("-" * 70)
for i, e in enumerate(cs[:5], 1):
    n = names.get(e['code'], '?')
    print("%d  %-8s %-14s %7.2f %+.1f%% %5.1f%% %4.0f%% %5.1f%% %5.2f %5.1f" % (
        i, n, e['code'], e['close'], e['p'], e['a'],
        e.get('cl', 0), e.get('s', 0), e.get('dif_val', 0) or 0, sc(e)))
