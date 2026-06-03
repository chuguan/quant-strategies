#!/usr/bin/env python3
"""分批下载 — 带超时控制"""
import json, os, sys, time, socket, signal

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# 设置全局socket超时
socket.setdefaulttimeout(8)

# 找还没2024数据的
need=[]
total=0
for fn in [f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]:
    total+=1
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        if not any(r["date"].startswith("2024") for r in recs):
            need.append(fn.replace('.json',''))
    except:
        pass

print(f"📊 共{total}只, 需更新: {len(need)}只")

import akshare as ak
batch=need[:500]
print(f"⏳ 本批500只 ({batch[0]}~{batch[-1]})")

t0=time.time()
ok=0; fail=0
for i,code in enumerate(batch):
    try:
        df=ak.stock_zh_a_daily(symbol=code, adjust='qfq')
        records=[{"date":str(r["date"]),"open":float(r["open"]),"close":float(r["close"]),
                  "high":float(r["high"]),"low":float(r["low"]),"volume":float(r["volume"])}
                 for _,r in df.iterrows()]
        if len(records)>100:  # 确认有数据
            with open(os.path.join(CACHE_DIR,f"{code}.json"),'w',encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False)
            ok+=1
    except:
        fail+=1
    
    if (i+1)%100==0:
        print(f"  ✅{ok}/{(i+1)} ❌{fail} ({time.time()-t0:.0f}s)", flush=True)

print(f"🏁 本批: ✅{ok}成功 ❌{fail}失败 ({(time.time()-t0):.0f}秒)")
print(f"   剩余{len(need)-500}只待下一批")
