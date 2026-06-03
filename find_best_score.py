#!/usr/bin/env python3
"""涨跌幅1~8%的票 — 新评分规则测试"""
import pickle, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)

def build(yr):
    data=defaultdict(list)
    for dt in cache['data']:
        if not dt.startswith(yr): continue
        for c in cache['data'][dt]:
            if c['code'] in ST: continue
            if not (1 <= c['p'] < 8): continue
            data[dt].append(c)
    return {k:v for k,v in data.items() if len(v)>=5}

d25=build('2025'); d26=build('2026')

def test(data, fn):
    w=t=0
    for dt in sorted(data.keys()):
        best=max(data[dt], key=fn)
        t+=1
        if best['n'] and best['n']>=2.5: w+=1
    return w/t*100 if t else 0, w, t

# ── 15种评分方案 ──
schemes = [
    ("v14原版", lambda c: (max(0,35-c['s']*1.2) if c['s']<30 else 0)+min(c['b']*3,25)+min(c['a']*2,16)),
    ("A:上影越长越好", lambda c: c['s']*1.5 + c['b']*2 + c['a']*2),
    ("B:无上影(实体+ATR)", lambda c: min(c['b']*3,25)+min(c['a']*2,16)),
    ("C:涨跌幅+ATR", lambda c: c['p']*3 + c['a']*3),
    ("D:实体×ATR", lambda c: min(c['b'],10)*min(c['a'],8)),
    ("E:上影+ATR", lambda c: c['s']*1 + c['a']*4),
    ("F:等权混合", lambda c: c['p']+c['b']+c['s']+c['a']),
    ("G:涨跌幅3~5分+10", lambda c: (10 if 3<=c['p']<5 else 0)+c['a']*3+c['b']*2),
    ("H:仅ATR", lambda c: c['a']),
    ("I:仅实体", lambda c: c['b']),
    ("J:仅涨跌幅", lambda c: c['p']),
    ("K:实体+涨跌幅", lambda c: c['b']*2 + c['p']*2),
    ("L:上影+实体(反包)", lambda c: c['s']*2 + c['b']*1 + c['a']*1),
    ("M:下影(100-上影)", lambda c: max(0,100-c['s'])*1 + c['a']*4),
    ("N:实体/上影比", lambda c: c['b']/(c['s']+0.1)*10 + c['a']*2),
]

print(f"📊 涨跌幅1~8% — 15种评分规则测试")
print(f"{'='*90}")
print(f"{'方案':<25} {'两年均':>7} {'2025':>10} {'2026':>10}")
print("-"*55)

res=[]
for name, fn in schemes:
    r25,_,_=test(d25,fn); r26,_,_=test(d26,fn)
    avg=(r25+r26)/2
    res.append((avg,name,r25,r26))

res.sort(reverse=True)
for rank,(avg,name,r25,r26) in enumerate(res,1):
    mk="🔥" if rank==1 else ""
    print(f"  {rank}. {name:<25} {avg:>5.1f}% {r25:>5.1f}% {r26:>5.1f}% {mk}")

print(f"\n⏱ {time.time()-0:.1f}秒")
