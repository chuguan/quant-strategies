#!/usr/bin/env python3
"""多线程批量补全2024年数据 — akshare + baostock双重保障"""
import json, os, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# 扫描需要补的股票
need_fix=[]
for fn in [f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]:
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        if not any(r["date"].startswith("2024") for r in recs):
            need_fix.append(fn.replace('.json',''))
    except:
        need_fix.append(fn.replace('.json',''))

print(f"📊 需补2024数据: {len(need_fix)}只")

# 转换代码格式
def to_bs(code):
    if code.startswith('sh'): return 'sh.'+code[2:]
    if code.startswith('sz'): return 'sz.'+code[2:]
    return code

# 下载函数
global_ok=0; global_fail=0; global_lock=threading.Lock()
t0=time.time()

def download_stock(code):
    global global_ok, global_fail
    try:
        # 先用akshare（速度快）
        import akshare as ak
        df=ak.stock_zh_a_daily(symbol=code, adjust='qfq')
        records=[{"date":str(r["date"]),"open":float(r["open"]),"close":float(r["close"]),
                  "high":float(r["high"]),"low":float(r["low"]),"volume":float(r["volume"])}
                 for _,r in df.iterrows() if r["date"]>="2024-01-01"]
        # 只需2024年起
        with open(os.path.join(CACHE_DIR,f"{code}.json"),'w',encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False)
        with global_lock: global_ok+=1
        return True
    except:
        # 备用baostock
        try:
            import baostock as bs
            bs_code=to_bs(code)
            rs=bs.query_history_k_data_plus(bs_code,'date,open,close,high,low,volume',
                                           start_date='2024-01-01',end_date='2026-05-22',
                                           frequency='d',adjustflag='2')
            records=[]
            while rs.next():
                r=rs.get_row_data()
                records.append({"date":r[0],"open":float(r[1]),"close":float(r[2]),
                               "high":float(r[3]),"low":float(r[4]),"volume":float(r[5])})
            with open(os.path.join(CACHE_DIR,f"{code}.json"),'w',encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False)
            with global_lock: global_ok+=1
            return True
        except:
            with global_lock: global_fail+=1
            return False

# 多线程下载
print(f"⏳ 开始下载 (5线程)...")

# 先baostock登录
import baostock as bs
bs.login()

with ThreadPoolExecutor(max_workers=5) as ex:
    futs=[ex.submit(download_stock, c) for c in need_fix]
    done=0; last_report=0
    for f in as_completed(futs):
        done+=1
        if done-last_report>=50:
            last_report=done
            with global_lock:
                eta=(time.time()-t0)/done*(len(need_fix)-done)
            print(f"  ✅{global_ok}/{done} ❌{global_fail} ({time.time()-t0:.0f}s ETA:{eta:.0f}s)")

bs.logout()
print(f"\n🏁 完成! ✅{global_ok}只成功 ❌{global_fail}只失败 ⏱{time.time()-t0:.0f}秒")
