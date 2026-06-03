#!/usr/bin/env python3
"""后台下载2024数据"""
import json, os, time, sys, baostock as bs
CACHE_DIR=r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# 找需要补的
need=[]; scanned=0
for fn in os.listdir(CACHE_DIR):
    if not fn.endswith('.json'): continue
    if not (fn.startswith('sh6') or fn.startswith('sz0') or fn.startswith('sz2')): continue
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<10: continue
        if recs[-1]["date"]<"2020": continue
        if not any(r["date"].startswith("2024") for r in recs):
            need.append(fn.replace('.json',''))
    except: pass
    scanned+=1

print(f"扫描{scanned}只, 需下载{len(need)}只", flush=True)

def to_bs(c):
    return ('sh.'+c[2:]) if c.startswith('sh') else ('sz.'+c[2:]) if c.startswith('sz') else c

lg=bs.login()
t0=time.time(); ok=0; fail=0; last_report=0
for i,code in enumerate(need):
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
                json.dump(records,f,ensure_ascii=False)
            ok+=1
        else: fail+=1
    except: fail+=1
    
    elapsed=time.time()-t0
    if elapsed-last_report>=30:
        last_report=elapsed
        rate=(i+1)/elapsed if elapsed>0 else 0
        rem=(len(need)-i-1)/rate if rate>0 else 0
        print(f"✅{ok}/{(i+1)} ❌{fail} ({elapsed:.0f}s ETA:{rem:.0f}s)", flush=True)

bs.logout()
print(f"🏁 完成! ✅{ok}成功 ❌{fail}失败 ⏱{time.time()-t0:.0f}秒", flush=True)
