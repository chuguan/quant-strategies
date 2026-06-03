#!/usr/bin/env python3
"""通达信数据批量下载 — 补齐2024-2026年K线数据"""
import json, os, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

def needs_update(fp):
    """检查是否需要下载"""
    try:
        with open(fp,'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        dates=[r["date"] for r in recs]
        has_2024=any(d.startswith("2024") for d in dates)
        has_full_2025=sum(1 for d in dates if d.startswith("2025")) >= 200
        return not has_2024, recs
    except:
        return True, []

def download_one(code):
    """下载一只股票的历史数据"""
    import akshare as ak
    try:
        df=ak.stock_zh_a_daily(symbol=code, adjust='qfq')
        records=[]
        for _, row in df.iterrows():
            records.append({
                "date": row["date"],
                "open": float(row["open"]),
                "close": float(row["close"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "volume": float(row["volume"])
            })
        return records
    except Exception as e:
        return None

# 扫描全部文件
files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
print(f"📊 共{len(files)}只主板股")

# 检查哪些需要更新
to_download=[]
for fn in files:
    fp=os.path.join(CACHE_DIR,fn)
    missing_2024, existing_recs = needs_update(fp)
    if missing_2024:
        to_download.append((fn.replace('.json',''), existing_recs))

print(f"📥 需下载2024年数据: {len(to_download)}只")
if len(to_download)==0:
    print("✅ 全部已有2024数据，无需下载")
    exit(0)

# 多线程下载
downloaded=0; errors=0; skipped=0
lock=threading.Lock()
t0=time.time()

def worker(code, existing_recs):
    global downloaded, errors
    records=download_one(code)
    if records is None:
        with lock: errors+=1
        return False
    
    # 合并(新数据在后)
    date_set=set(r["date"] for r in existing_recs)
    merged=list(existing_recs)
    for r in records:
        if r["date"] not in date_set:
            merged.append(r)
    merged.sort(key=lambda x:x["date"])
    
    # 保存
    fp=os.path.join(CACHE_DIR,f"{code}.json")
    with open(fp,'w',encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False)
    
    with lock:
        downloaded+=1
        if downloaded%100==0:
            elapsed=time.time()-t0
            rate=downloaded/elapsed
            remaining=(len(to_download)-downloaded)/rate
            print(f"  ✅ {downloaded}/{len(to_download)}  ({elapsed:.0f}秒, 剩余{remaining:.0f}秒)")
    return True

print(f"\n⏳ 开始下载 (8线程并发)...")

with ThreadPoolExecutor(max_workers=8) as executor:
    futures=[executor.submit(worker, code, recs) for code, recs in to_download]
    for f in as_completed(futures):
        pass

elapsed=time.time()-t0
print(f"\n📊 完成!")
print(f"  ✅ 成功更新: {downloaded}只")
print(f"  ❌ 失败: {errors}只")
print(f"  ⏱ 总用时: {elapsed:.0f}秒 ({elapsed/60:.1f}分)")
