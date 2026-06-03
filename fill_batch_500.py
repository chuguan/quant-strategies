#!/usr/bin/env python3
"""分批下载 — 一次跑500只"""
import json, os, sys, time, akshare as ak

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# 找还没2024数据的
need=[]
for fn in [f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]:
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        if not any(r["date"].startswith("2024") for r in recs):
            need.append(fn.replace('.json',''))
    except:
        need.append(fn.replace('.json',''))

print(f"📊 还需更新: {len(need)}只")

# 取前500只
batch=need[:500]
print(f"⏳ 本批下载{batch[0]}~{batch[-1]} ({len(batch)}只)")

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
    except Exception as e:
        fail+=1
        if fail<=3: print(f"  ❌ {code}")
    if (i+1)%100==0:
        print(f"  ✅{ok}/{(i+1)} ❌{fail} ({time.time()-t0:.0f}s)")

print(f"✅本批: {ok}成功 {fail}失败 ({(time.time()-t0):.0f}秒)")
print(f"总进度: {len(need)-len(batch)}只还在等")
