#!/usr/bin/env python3
"""2026年冠军跌的日子"""
import pickle, os
from collections import defaultdict

C = r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST = set()
if os.path.exists(r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"):
    with open(r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt") as f:
        ST = {l.strip() for l in f if l.strip()}

with open(C, 'rb') as f:
    cache = pickle.load(f)
dc = cache['data']
nm = cache['names']

MIN=1.0; MAX=8.0; T=2.5

def ok(e):
    if e['code'] in ST: return False
    if e['p'] is None or not (MIN<=e['p']<MAX): return False
    if e['n'] is None: return False
    if e.get('is_yang',0)!=1 or e.get('above_ma5',0)!=1 or e.get('a',0)<=3: return False
    return True

def sc(e):
    return e['p']+e['a']*1.5+(e.get('dif_val',0) or 0)*0.5+e.get('cl',0)*0.02-(3 if e.get('s',0)>40 else 0)

bd = defaultdict(list)
for dt in dc:
    if not dt.startswith('2026'): continue
    for e in dc[dt]:
        if ok(e): bd[dt].append(e)
bd = {k:v for k,v in bd.items() if len(v)>=5}

fails = []
for dt in sorted(bd.keys()):
    best = max(bd[dt], key=sc)
    if best['n'] < T:
        fails.append((dt, best))

print("2026年冠军跌的日子（共%d天）" % len(fails))
print()
for dt, best in fails:
    n2 = nm.get(best['code'], '?')
    print("%s %-8s %-14s 买入%6.2f 涨%+.1f%% ATR%.1f%% 位%3.0f%% 影%4.1f%% DIF%5.2f 评%4.1f → 次日%+.1f%% XX" % (
        dt, n2, best['code'], best['close'], best['p'], best['a'],
        best.get('cl',0), best.get('s',0), best.get('dif_val',0) or 0,
        sc(best), best['n']))
