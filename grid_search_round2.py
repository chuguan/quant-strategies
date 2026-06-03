#!/usr/bin/env python3
"""
第2轮：非线性组合 — 乘积、比率、阈值、平方
"""
import pickle, os, sys, time, math
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']

TARGET=2.5
MIN_CHG=1.0
MAX_CHG=8.0

def filter_data(yr):
    by_date=defaultdict(list)
    for dt in data_cache:
        if not dt.startswith(yr): continue
        for c in data_cache[dt]:
            if c['code'] in ST: continue
            p=c['p']
            if p is None or not (MIN_CHG <= p < MAX_CHG): continue
            if c['n'] is None: continue
            by_date[dt].append(c)
    return {k:v for k,v in by_date.items() if len(v)>=5}

def test(data, fn):
    w=t=0
    for dt in sorted(data.keys()):
        best=max(data[dt], key=fn)
        t+=1
        if best['n']>=TARGET: w+=1
    return w/t*100 if t>0 else 0, w, t

data25=filter_data('2025')
data26=filter_data('2026')
print(f"📅 2025: {len(data25)}天, 2026: {len(data26)}天")
print()

Results=[]
def add(name, fn):
    w25,_,_=test(data25,fn)
    w26,_,_=test(data26,fn)
    avg=(w25+w26)/2
    Results.append((avg,w25,w26,name))
    return avg

# ═══ 乘积组合 ═══
print("═══ 乘积组合 ═══")
add("p×a(涨跌幅×ATR)",       lambda c: c['p']*c['a'])
add("p×b(涨跌幅×实体)",      lambda c: c['p']*c['b'])
add("a×b(ATR×实体)",        lambda c: c['a']*c['b'])
add("p×a×b(三乘积)",        lambda c: c['p']*c['a']*c['b'])
add("p×cl(涨跌幅×收盘位)",   lambda c: c['p']*c['cl'])
add("a×cl(ATR×收盘位)",     lambda c: c['a']*c['cl'])
add("p^2×a",                lambda c: c['p']*c['p']*c['a'])
add("p×a^2",                lambda c: c['p']*c['a']*c['a'])

# ═══ 比率组合 ═══
print("═══ 比率组合 ═══")
add("p/a(涨跌幅÷ATR)",       lambda c: c['p']/(c['a']+0.01))
add("a/p(ATR÷涨跌幅)",       lambda c: c['a']/(c['p']+0.01))
add("b/a(实体÷ATR)",        lambda c: c['b']/(c['a']+0.01))
add("p/b(涨跌幅÷实体)",      lambda c: c['p']/(c['b']+0.01))
add("(p³/a)",               lambda c: c['p']**3/(c['a']+0.01))

# ═══ 平方组合 ═══
print("═══ 平方组合 ═══")
add("p²(涨跌幅²)",           lambda c: c['p']**2)
add("a²(ATR²)",             lambda c: c['a']**2)
add("b²(实体²)",            lambda c: c['b']**2)
add("√p(涨跌幅开方)",        lambda c: math.sqrt(max(0.01,c['p'])))

# ═══ 阈值组合 ═══
print("═══ 阈值/封顶组合 ═══")
add("p+min(a,6)",           lambda c: c['p']+min(c['a'],6))
add("min(p,5)+min(a,5)",    lambda c: min(c['p'],5)+min(c['a'],5))
add("p-max(b-5,0)",         lambda c: c['p']-max(c['b']-5,0))
add("max(p,3)+a",           lambda c: max(c['p'],3)+c['a'])

# ═══ 多因子组合 ═══
print("═══ 多因子复合组合 ═══")
add("p+a+p*a/10",           lambda c: c['p']+c['a']+c['p']*c['a']/10)
add("p+a+b/3",              lambda c: c['p']+c['a']+c['b']/3)
add("p+a+b/5+s/10",         lambda c: c['p']+c['a']+c['b']/5+max(0,c['s'])/10)
add("p+a+p/d",              lambda c: c['p']+c['a']+10/(c['p']+0.1))

# ═══ 特征组合（涨停边界效应）═══
print("═══ 边界效应组合 ═══")
add("(8-p)*p*a(接近涨停加分)",   lambda c: (8-c['p'])*c['p']*c['a']/10)
add("p×p×a(涨跌幅²×ATR)",       lambda c: c['p']*c['p']*c['a'])
add("p×a×b(三者乘积)",          lambda c: c['p']*c['a']*c['b'])

# ═══ 排名 ═══
Results.sort(key=lambda x: x[0], reverse=True)
print(f"\n{'='*80}")
print(f"🏆 非线性组合 TOP 20")
print(f"{'='*80}")
print(f"{'排名':<4} {'两年均':>7} {'2025':>7} {'2026':>7} {'公式':<45}")
print("-"*80)
for i,(avg,w25,w26,name) in enumerate(Results[:20],1):
    print(f"{i:<4} {avg:>6.1f}% {w25:>6.1f}% {w26:>6.1f}% {name}")
