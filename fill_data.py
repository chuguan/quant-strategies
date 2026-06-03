#!/usr/bin/env python3
"""通达信数据批量下载 — 补齐2024-2026年K线 (简化版)"""
import json, os, sys, time, akshare as ak

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# 扫描全部文件
files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
print(f"📊 共{len(files)}只主板股")

# 检查哪些需要更新
to_download=[]
for fn in files:
    fp=os.path.join(CACHE_DIR,fn)
    try:
        with open(fp,'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        dates=[r["date"] for r in recs]
        has_2024=any(d.startswith("2024") for d in dates)
        if not has_2024:
            to_download.append((fn.replace('.json',''), recs))
    except:
        to_download.append((fn.replace('.json',''), []))

print(f"📥 需下载2024年数据: {len(to_download)}只")
if not to_download:
    print("✅ 全部已有2024年数据！")
    sys.exit(0)

# 批量下载
downloaded=0; errors=0; t0=time.time()
batch_size=min(100, len(to_download))
to_process=to_download[:batch_size]

print(f"\n⏳ 先下载{batch_size}只测试...")
for code, existing in to_process:
    try:
        df=ak.stock_zh_a_daily(symbol=code, adjust='qfq')
        records=[]
        for _,row in df.iterrows():
            records.append({"date":row["date"],"open":float(row["open"]),
                          "close":float(row["close"]),"high":float(row["high"]),
                          "low":float(row["low"]),"volume":float(row["volume"])})
        
        # 合并
        date_set=set(r["date"] for r in existing)
        merged=list(existing)
        for r in records:
            if r["date"] not in date_set: merged.append(r)
        merged.sort(key=lambda x:x["date"])
        
        fp=os.path.join(CACHE_DIR,f"{code}.json")
        with open(fp,'w',encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False)
        downloaded+=1
    except Exception as e:
        errors+=1
        if errors<=5: print(f"  ❌ {code}: {e}")
    
    if downloaded%20==0:
        elapsed=time.time()-t0
        rate=downloaded/elapsed if elapsed>0 else 0
        remaining=(len(to_process)-downloaded)/rate if rate>0 else 0
        print(f"  ✅ {downloaded}/{len(to_process)} ({elapsed:.0f}秒, 剩余{remaining:.0f}秒)")

print(f"\n📊 首批完成: {downloaded}只成功, {errors}只失败")
print(f"   用时: {time.time()-t0:.0f}秒")

# 如果首批成功，继续下载剩余
if downloaded>0 and len(to_download)>batch_size:
    remaining_list=to_download[batch_size:]
    print(f"\n⏳ 继续下载剩余{len(remaining_list)}只...")
    t0=time.time()
    
    for i,(code,existing) in enumerate(remaining_list):
        try:
            df=ak.stock_zh_a_daily(symbol=code, adjust='qfq')
            records=[]
            for _,row in df.iterrows():
                records.append({"date":row["date"],"open":float(row["open"]),
                              "close":float(row["close"]),"high":float(row["high"]),
                              "low":float(row["low"]),"volume":float(row["volume"])})
            date_set=set(r["date"] for r in existing)
            merged=list(existing)
            for r in records:
                if r["date"] not in date_set: merged.append(r)
            merged.sort(key=lambda x:x["date"])
            fp=os.path.join(CACHE_DIR,f"{code}.json")
            with open(fp,'w',encoding='utf-8') as f:
                json.dump(merged, f, ensure_ascii=False)
            downloaded+=1
            errors-=1  # 不计入之前的失败
        except Exception as e:
            errors+=1
            if errors%50==0: print(f"  ❌ 已失败{errors}次")
        
        if (i+1)%100==0:
            elapsed=time.time()-t0
            rate=(i+1)/elapsed if elapsed>0 else 0
            remaining=(len(remaining_list)-i-1)/rate if rate>0 else 0
            print(f"  ✅ {downloaded}/{len(to_download)} (批量{i+1}, {elapsed:.0f}秒, 剩余{remaining:.0f}秒)")
        
        time.sleep(0.2)

print(f"\n{'='*60}")
print(f"🏁 全部完成!")
print(f"  ✅ 成功更新: {downloaded}只")
print(f"  ❌ 失败: {errors}只")
print(f"  ⏱ 总用时: {time.time()-t0:.0f}秒")
