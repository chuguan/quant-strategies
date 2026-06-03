#!/usr/bin/env python3
"""评分调优：尝试新维度和组合"""
import pickle, os
from collections import defaultdict

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}
with open(CACHE,'rb') as f: c=pickle.load(f)
dc=c['data']; nm=c['names']
MIN=1.0; MAX=8.0; TARGET=2.5

def ok(e):
    if e['code'] in ST: return False
    if e['p'] is None or not (MIN<=e['p']<MAX): return False
    if e['n'] is None: return False
    if e.get('is_yang',0)!=1 or e.get('above_ma5',0)!=1 or e.get('a',0)<=3: return False
    return True

data25=defaultdict(list); data26=defaultdict(list)
for dt in dc:
    for e in dc[dt]:
        if not ok(e): continue
        if dt.startswith('2025'): data25[dt].append(e)
        elif dt.startswith('2026'): data26[dt].append(e)
data25={k:v for k,v in data25.items() if len(v)>=5}
data26={k:v for k,v in data26.items() if len(v)>=5}

def backtest(data, fn):
    w=t=0
    for dt in sorted(data.keys()):
        best=max(data[dt], key=fn); t+=1
        if best['n']>=TARGET: w+=1
    return w/t*100 if t>0 else 0

print("═══ 第1组：非线性变换 ═══")
tests=[]
for name,fn in [
    ("p^0.5+a", lambda c: (c['p']**0.5)+c['a']),
    ("log(p)+a", lambda c: __import__('math').log(c['p']+1)+c['a']),
    ("p/(a+1)+a", lambda c: c['p']/(c['a']+1)+c['a']),
    ("(p-3)^2+a", lambda c: (c['p']-3)**2+c['a']),
    ("(p-5)^2+a", lambda c: (c['p']-5)**2+c['a']),
    ("p*cl/100", lambda c: c['p']*c.get('cl',50)/100),
    ("a*cl/100", lambda c: c['a']*c.get('cl',50)/100),
]:
    w25=backtest(data25, fn); w26=backtest(data26, fn)
    avg=(w25+w26)/2; tests.append((avg,w25,w26,name))
tests.sort(key=lambda x:x[0],reverse=True)
for i,(a,w25,w26,n) in enumerate(tests[:8],1):
    print(f"  {i}. {n}: {a:.1f}% (25={w25:.1f}%, 26={w26:.1f}%)")

print("\n═══ 第2组：排名法（多维度分排名后求和） ═══")
def rank_sum(data, keys_and_dirs):
    """keys_and_dirs: [(key, direction), ...] direction: 1=升序, -1=降序"""
    for dt in data:
        cs=data[dt]; n=len(cs)
        for key,dr in keys_and_dirs:
            sorted_cs=sorted(cs, key=lambda c: c.get(key,0), reverse=(dr>0))
            rank_map={c['code']:i+1 for i,c in enumerate(sorted_cs) if c.get(key) is not None}
            # 简化：直接用值，不排序了
        # Actually let me just use normalized values
        for c in cs:
            c['_rs']=sum(c.get(key,0)*dr for key,dr in keys_and_dirs)
    w=t=0
    for dt in sorted(data.keys()):
        best=max(data[dt], key=lambda c:c.get('_rs',0)); t+=1
        if best['n']>=TARGET: w+=1
    return w/t*100 if t>0 else 0

# 简单排名组合
for name,keys in [
    ("p+a", [('p',1),('a',1)]),
    ("p+a+cl/50", [('p',1),('a',1),('cl',0.02)]),
    ("p+a-cl/100", [('p',1),('a',1),('cl',-0.01)]),
]:
    w25=rank_sum(data25, keys); w26=rank_sum(data26, keys)
    print(f"  {name}: {(w25+w26)/2:.1f}% (25={w25:.1f}%, 26={w26:.1f}%)")

print("\n═══ 第3组：基准+新维度搜索 ═══")
# 用p+a+dif*0.5+cl*0.02为基准
fn_base=lambda c: c['p']+c['a']*1.5+(c.get('dif_val',0) or 0)*0.5+c.get('cl',0)*0.02-(3 if c.get('s',0)>40 else 0)
w25b=backtest(data25, fn_base); w26b=backtest(data26, fn_base)
print(f"  基准: {(w25b+w26b)/2:.1f}% (25={w25b:.1f}%, 26={w26b:.1f}%)")

# 加J值/量比/MA5斜率等
for name,fn in [
    ("+j_val*0.05", lambda c: c['p']+c['a']*1.5+(c.get('dif_val',0)or 0)*0.5+c.get('cl',0)*0.02-(3 if c.get('s',0)>40 else 0)+c.get('j_val',50)*0.05),
    ("-j_val*0.05", lambda c: c['p']+c['a']*1.5+(c.get('dif_val',0)or 0)*0.5+c.get('cl',0)*0.02-(3 if c.get('s',0)>40 else 0)-c.get('j_val',50)*0.05),
    ("+ma5_slope*0.1", lambda c: c['p']+c['a']*1.5+(c.get('dif_val',0)or 0)*0.5+c.get('cl',0)*0.02-(3 if c.get('s',0)>40 else 0)+c.get('ma5_slope',0)*0.1),
]:
    w25=backtest(data25, fn); w26=backtest(data26, fn)
    avg=(w25+w26)/2
    print(f"  {name}: {avg:.1f}% (25={w25:.1f}%, 26={w26:.1f}%)")
