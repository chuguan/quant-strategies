#!/usr/bin/env python3
"""检查下载进度"""
import json, os, time
CACHE_DIR=r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
h2024=0; active=0; delisted=0; recent=[]
for fn in files:
    fp=os.path.join(CACHE_DIR,fn)
    t=os.path.getmtime(fp); recent.append((t,fn))
    try:
        r=json.loads(open(fp,'rb').read().decode('utf-8'))
        if len(r)<10: continue
        if r[-1]['date']<'2020': delisted+=1; continue
        active+=1
        if any(d['date'].startswith('2024') for d in r): h2024+=1
    except: pass
recent.sort(reverse=True)
print(f"活跃:{active}只, 退市:{delisted}")
print(f"有2024:{h2024}({h2024/active*100:.0f}%), 缺{active-h2024}只")
print(f"\n最近修改的文件:")
for t,fn in recent[:8]:
    print(f"  {fn}: {time.ctime(t)}")
