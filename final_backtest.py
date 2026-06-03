#!/usr/bin/env python3
"""2025-2026 精确回测 — 涨跌幅1~7%过滤+排除ST+v14评分"""
import pickle, os, time, sys
sys.stdout.reconfigure(line_buffering=True)

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"

ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

print("📡 加载..."); t0=time.time()
with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']

for yr in ["2025","2026"]:
    dates=sorted(d for d in data if d.startswith(yr))
    
    wins=0; total=0
    for dt in dates:
        cands=[]
        for c in data[dt]:
            if c['code'] in ST: continue
            p=c['p']
            if not (1 <= p < 7): continue  # 涨跌幅1~7%
            sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
            sc=round(sh+min(c['b']*3,25)+min(c['a']*2,16),1)
            cands.append((sc, c))
        
        if len(cands)<5: continue
        cands.sort(key=lambda x:x[0], reverse=True)
        champ=cands[0][1]
        total+=1
        if champ['n'] and champ['n']>=2.5: wins+=1
    
    rate=wins/total*100 if total else 0
    print(f"\n{'='*60}")
    print(f"📅 {yr}年 — 涨跌幅1~7%+排除ST+v14")
    print(f"{'='*60}")
    print(f"  胜率: {wins}/{total} = {rate:.1f}%")

print(f"\n⏱ {time.time()-t0:.2f}秒")
