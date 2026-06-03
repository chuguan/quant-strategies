#!/usr/bin/env python3
"""多线程akshare批量下载"""
import json, os, time, threading, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# 扫描需要补的
need=[]
for fn in [f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]:
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        if not any(r["date"].startswith("2024") for r in recs):
            need.append(fn.replace('.json',''))
    except:
        need.append(fn.replace('.json',''))

print(f"📊 需补数据: {len(need)}只")

import akshare as ak
ok=0; fail=0; lock=threading.Lock()
t0=time.time()

def dl(code):
    global ok, fail
    try:
        df=ak.stock_zh_a_daily(symbol=code, adjust='qfq')
        records=[{"date":str(r["date"]),"open":float(r["open"]),"close":float(r["close"]),
                  "high":float(r["high"]),"low":float(r["low"]),"volume":float(r["volume"])}
                 for _,r in df.iterrows()]
        with open(os.path.join(CACHE_DIR,f"{code}.json"),'w',encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False)
        with lock: ok+=1
    except:
        with lock: fail+=1

print(f"⏳ 5线程下载...")
with ThreadPoolExecutor(max_workers=5) as ex:
    futs=[ex.submit(dl, c) for c in need]
    done=0; last=0
    for f in as_completed(futs):
        with lock: done+=1
        if done-last>=50:
            last=done
            eta=(time.time()-t0)/done*(len(need)-done)
            print(f"  ✅{ok}/{done} ❌{fail} ({time.time()-t0:.0f}s ETA:{eta:.0f}s)")

print(f"\n🏁 ✅{ok}成功 ❌{fail}失败 ⏱{time.time()-t0:.0f}秒")
