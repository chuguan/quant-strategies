#!/usr/bin/env python3
"""2026-01-12 全部候选股票"""
import pickle, os
CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}
with open(CACHE,'rb') as f: c=pickle.load(f)
dc=c['data']; nm=c['names']
MIN=1.0; MAX=8.0
def ok(e):
    if e['code'] in ST: return False
    if e['p'] is None or not (MIN<=e['p']<MAX): return False
    if e.get('is_yang',0)!=1 or e.get('above_ma5',0)!=1 or e.get('a',0)<=3: return False
    return True
def sc(e):
    return e['p']+e['a']*1.5+(e.get('dif_val',0) or 0)*0.5+e.get('cl',0)*0.02-(3 if e.get('s',0)>40 else 0)

target_dt='2026-01-12'
cs=[e for e in dc.get(target_dt,[]) if ok(e)]
for e in cs: e['s2']=round(sc(e),2)
cs.sort(key=lambda e:e['s2'], reverse=True)

print("2026-01-12 全部%d只候选" % len(cs))
print("#   名称      代码              买入价  涨跌  ATR   位  上影  DIF    DEA    MACD  K    D    J    评分   次日")
print("-"*130)
for i,e in enumerate(cs,1):
    n2=nm.get(e['code'],'?')
    nxt="%.1f%%"%e['n'] if e['n'] is not None else "N/A"
    mg=e.get('macd_gap',0)
    print("%-3d %-8s %-16s %7.2f %+.1f%% %5.1f%% %3.0f%% %5.1f%% %5.2f %5.2f %5.2f %3.0f %3.0f %3.0f %5.1f %s"%(i,n2,e['code'],e['close'],e['p'],e['a'],e.get('cl',0),e.get('s',0),e.get('dif_val',0)or 0,e.get('dea_val',0)or 0,mg,e.get('k_val',0)or 0,e.get('d_val',0)or 0,e.get('j_val',0)or 0,e['s2'],nxt))
