#!/usr/bin/env python3
"""通达信数据批量补齐—简化版"""
import json, os, time, akshare as ak

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# 扫描需要补的
need_fix=[]
for fn in [f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]:
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        if not any(r["date"].startswith("2024") for r in recs):
            need_fix.append(fn.replace('.json',''))
    except:
        need_fix.append(fn.replace('.json',''))

print(f"📊 共{len(need_fix)+len([f for f in os.listdir(CACHE_DIR) if f.endswith('.json')])}只, 需补2024: {len(need_fix)}只")

t0=time.time()
ok=0; fail=0
for i,code in enumerate(need_fix):
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
        if fail<=3: print(f"  ❌ {code}: {str(e)[:80]}")
    
    if (i+1)%50==0:
        eta=(time.time()-t0)/(i+1)*(len(need_fix)-i-1)
        print(f"  ✅{ok}/{i+1} ❌{fail} ({time.time()-t0:.0f}s ETA:{eta:.0f}s)")
    time.sleep(0.15)

print(f"\n✅{ok}成功 ❌{fail}失败 ⏱{time.time()-t0:.0f}秒")
