#!/usr/bin/env python3
"""通达信数据补齐 — 逐个下载并保存"""
import akshare as ak, json, os, sys, time

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
print(f"📊 {len(files)}只主板股")

# 统计现状
has2024=0; has2025=0; total=0
for fn in files:
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        total+=1
        dates=[r['date'] for r in recs]
        if any(d.startswith('2024') for d in dates): has2024+=1
        if any(d.startswith('2025') for d in dates): has2025+=1
    except: pass
print(f"扫描{total}只: 有2024={has2024}({has2024/total*100:.0f}%), 有2025={has2025}({has2025/total*100:.0f}%)")

# 先从缺少2024的股票开始补
need_fix=[fn.replace('.json','') for fn in files 
          if not any(d.startswith('2024') for d in 
                     json.loads(open(os.path.join(CACHE_DIR,fn),'rb').read().decode('utf-8'))
                     if isinstance(d, str) for d in ...)]
# 太复杂，直接逐个文件检查
need_fix=[]
for fn in files:
    fp=os.path.join(CACHE_DIR,fn)
    try:
        with open(fp,'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        dates=[r['date'] for r in recs]
        if not any(d.startswith('2024') for d in dates):
            need_fix.append(fn.replace('.json',''))
    except:
        need_fix.append(fn.replace('.json',''))

print(f"📥 需要补2024数据: {len(need_fix)}只")

# 下载并保存
t0=time.time()
ok=0; fail=0
for i,code in enumerate(need_fix):
    try:
        df=ak.stock_zh_a_daily(symbol=code, adjust='qfq')
        # 转为标准格式
        records=[]
        for _,row in df.iterrows():
            records.append({"date":row["date"],"open":float(row["open"]),
                          "close":float(row["close"]),"high":float(row["high"]),
                          "low":float(row["low"]),"volume":float(row["volume"])})
        
        fp=os.path.join(CACHE_DIR,f"{code}.json")
        with open(fp,'w',encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False)
        
        ok+=1
        if ok%50==0:
            eta=(time.time()-t0)/ok*(len(need_fix)-ok)
            print(f"  ✅ {ok}/{len(need_fix)} ({time.time()-t0:.0f}秒, ETA:{eta:.0f}秒)")
    except Exception as e:
        fail+=1
        if fail<=3:
            print(f"  ❌ {code}: {e}")
    
    time.sleep(0.15)  # 限速

print(f"\n📊 完成: ✅{ok}只成功, ❌{fail}只失败, ⏱{time.time()-t0:.0f}秒")
