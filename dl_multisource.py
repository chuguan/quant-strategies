#!/usr/bin/env python3
"""多源下载 — 通达信/东方财富/腾讯 三源轮换"""
import json, os, time, random, urllib.request, urllib.error
CACHE_DIR=r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# 找需要2024数据的（跳过退市）
files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
print(f"📊 共{len(files)}只文件", flush=True)

need=[]
for fn in files:
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<10: continue
        if recs[-1]["date"]<"2020": continue
        if not any(r["date"].startswith("2024") for r in recs):
            need.append(fn.replace('.json',''))
    except:
        need.append(fn.replace('.json',''))

print(f"📥 需下载: {len(need)}只", flush=True)
random.shuffle(need)  # 随机顺序避免连续请求被封

# ── 三种下载源 ──
def dl_tdx(code):
    """源1: 通达信(akshare)"""
    import akshare as ak
    df=ak.stock_zh_a_daily(symbol=code, adjust='qfq')
    return [{"date":str(r["date"]),"open":float(r["open"]),"close":float(r["close"]),
             "high":float(r["high"]),"low":float(r["low"]),"volume":float(r["volume"])}
            for _,r in df.iterrows()]

def dl_em(code):
    """源2: 东方财富"""
    import akshare as ak
    symbol=code.replace('sh','').replace('sz','')
    df=ak.stock_zh_a_hist(symbol=symbol, start_date='20240101', end_date='20260522', adjust='qfq')
    return [{"date":str(r["日期"]),"open":float(r["开盘"]),"close":float(r["收盘"]),
             "high":float(r["最高"]),"low":float(r["最低"]),"volume":float(r["成交量"])}
            for _,r in df.iterrows()]

def dl_tencent(code):
    """源3: 腾讯财经"""
    # 转格式: sh600000 -> sh600000
    url=f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,2024-01-01,,700,qfq"
    req=urllib.request.urlopen(url, timeout=10)
    data=json.loads(req.read().decode('gbk'))
    if data.get("code")!=0: return None
    sd=data.get("data",{}).get(code,{})
    day=sd.get("qfqday") or sd.get("day") or sd.get("qfq")
    if not day: return None
    return [{"date":r[0],"open":float(r[1]),"close":float(r[2]),
             "high":float(r[3]),"low":float(r[4]),"volume":float(r[5])} for r in day]

sources=[("通达信",dl_tdx),("东方财富",dl_em),("腾讯",dl_tencent)]

# ── 下载 ──
t0=time.time(); ok=0; fail=0
for i,code in enumerate(need):
    records=None; used_src=""
    for src_name, src_fn in sources:
        try:
            r=src_fn(code)
            if r and len(r)>100:
                records=r; used_src=src_name; break
        except: continue
    
    if records:
        with open(os.path.join(CACHE_DIR,f"{code}.json"),'w',encoding='utf-8') as f:
            json.dump(records,f,ensure_ascii=False)
        ok+=1
    else:
        fail+=1
    
    if (i+1)%100==0:
        el=time.time()-t0
        rate=(i+1)/el if el>0 else 0
        rem=(len(need)-i-1)/rate if rate>0 else 0
        print(f"  ✅{ok}/{(i+1)} ❌{fail} ({el:.0f}s ETA:{rem:.0f}s)", flush=True)
    
    time.sleep(random.uniform(0.5,1.5))  # 随机延迟

print(f"\n🏁 ✅{ok}成功 ❌{fail}失败 ⏱{time.time()-t0:.0f}秒")
