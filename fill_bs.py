#!/usr/bin/env python3
"""用baostock下载 — 更稳定"""
import json, os, time

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# 找需要补的（跳过退市）
need=[]
for fn in [f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]:
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<10: continue
        if recs[-1]["date"]<"2020": continue  # 退市跳过
        if any(r["date"].startswith("2024") for r in recs): continue
        need.append(fn.replace('.json',''))
    except:
        pass

print(f"📊 需下载: {len(need)}只")
batch=need[:500]
print(f"⏳ 本批500只")

import baostock as bs
lg=bs.login()
t0=time.time()
ok=0; fail=0

def to_bs(c):
    if c.startswith('sh'): return 'sh.'+c[2:]
    if c.startswith('sz'): return 'sz.'+c[2:]
    return c

for i,code in enumerate(batch):
    try:
        rs=bs.query_history_k_data_plus(to_bs(code),'date,open,close,high,low,volume',
                                       start_date='2024-01-01',end_date='2026-05-22',
                                       frequency='d',adjustflag='2')
        records=[]
        while rs.next():
            r=rs.get_row_data()
            records.append({"date":r[0],"open":float(r[1]),"close":float(r[2]),
                          "high":float(r[3]),"low":float(r[4]),"volume":float(r[5])})
        if records:
            with open(os.path.join(CACHE_DIR,f"{code}.json"),'w',encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False)
            ok+=1
        else:
            fail+=1
    except:
        fail+=1
    
    if (i+1)%100==0:
        el=time.time()-t0
        print(f"  ✅{ok}/{(i+1)} ❌{fail} ({el:.0f}s)", flush=True)

bs.logout()
print(f"🏁 ✅{ok}成功 ❌{fail}失败 ({(time.time()-t0):.0f}秒)")
