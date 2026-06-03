#!/usr/bin/env python3
"""下载 — 跳过退市股"""
import json, os, time, socket
socket.setdefaulttimeout(10)

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

need=[]; skip_delisted=0
for fn in [f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]:
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<10: continue
        last_date=recs[-1]["date"]
        # 如果最新数据在2020年以前→退市股跳过
        if last_date<"2020":
            skip_delisted+=1
            continue
        # 如果已经有2024数据→跳过
        if any(r["date"].startswith("2024") for r in recs):
            continue
        need.append(fn.replace('.json',''))
    except:
        pass

print(f"📊 退市跳过: {skip_delisted}只, 需下载: {len(need)}只")

import akshare as ak
batch=need[:500]
print(f"⏳ 本批500只")

t0=time.time()
ok=0; fail=0
for i,code in enumerate(batch):
    try:
        df=ak.stock_zh_a_daily(symbol=code, adjust='qfq')
        records=[{"date":str(r["date"]),"open":float(r["open"]),"close":float(r["close"]),
                  "high":float(r["high"]),"low":float(r["low"]),"volume":float(r["volume"])}
                 for _,r in df.iterrows()]
        with open(os.path.join(CACHE_DIR,f"{code}.json"),'w',encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False)
        ok+=1
    except:
        fail+=1
    if (i+1)%100==0:
        print(f"  ✅{ok}/{(i+1)} ❌{fail} ({time.time()-t0:.0f}s)", flush=True)

print(f"🏁 ✅{ok}成功 ❌{fail}失败 ({(time.time()-t0):.0f}秒)")
print(f"剩余{len(need)-500}只待下一批")
