#!/usr/bin/env python3
"""尾盘K线缓存预热 — 14:30执行
提前拉取所有活跃股的K线数据到本地缓存(1h过期)
确保14:48/14:50 V13/V42选股时秒读缓存"""
import os, json, subprocess, time
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.makedirs(CACHE_DIR, exist_ok=True)
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

# 获取活跃股票列表（主板：600xxx,601xxx,603xxx,605xxx,000xxx,001xxx,002xxx）
active_codes = [str(i) for i in range(600000, 606000)] + \
               [f'{i:06d}' for i in range(3000)]

# 过滤掉ST和STAR
import sqlite3
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
try:
    db = sqlite3.connect(DB_PATH)
    excluded = set(r[0] for r in db.execute('SELECT code FROM excluded_stocks WHERE active=1'))
    db.close()
except: excluded = set()

def curl_get(url, timeout=8):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url],capture_output=True,timeout=timeout+3)
        return r.stdout.decode('gbk',errors='replace')
    except: return ''

def fetch_kline(code):
    if code in excluded: return
    mkt = PREFIX(code)
    kf = os.path.join(CACHE_DIR, f'{mkt}{code}.json')
    if os.path.exists(kf) and time.time()-os.path.getmtime(kf)<3600*2:
        return  # 缓存有效（2小时窗口避免反复拉）
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt}{code},day,,,300,qfq'
    text = curl_get(url, timeout=6)
    if text and text.strip().startswith('{'):
        try:
            d = json.loads(text)
            sd = d.get('data',{}).get(f'{mkt}{code}',{})
            k = sd.get('qfqday',[])
            if not k:
                for key in sd:
                    if isinstance(sd[key],list) and sd[key] and isinstance(sd[key][0],list): k=sd[key]; break
            if k and len(k)>=80:
                recs=[{'date':x[0],'open':float(x[1]),'close':float(x[2]),'high':float(x[3]),'low':float(x[4]),'volume':float(x[5])} for x in k]
                with open(kf,'w') as f: json.dump(recs,f)
                return 1  # 成功拉取
        except: pass
    return None

print('🚀 K线缓存预热启动...', flush=True)
t0 = time.time()
total = len(active_codes)
fetched = 0
cached = 0
failed = 0
errors = 0

with ThreadPoolExecutor(max_workers=15) as ex:
    futures = {ex.submit(fetch_kline, c): c for c in active_codes}
    for f in as_completed(futures):
        try:
            r = f.result()
            if r == 1: fetched += 1
            elif r is None: errors += 1
            else: cached += 1
        except: errors += 1
        total_done = fetched + errors
        if total_done % 500 == 0 and total_done > 0:
            pct = total_done * 100 // len(active_codes)
            print(f'⏳ {total_done}/{len(active_codes)} ({pct}%) 已拉{fetched}条新K线', flush=True)

elapsed = time.time()-t0
print(f'✅ K线预热完成: 新拉{fetched}条, 失败{errors}条, 耗时{elapsed:.0f}s', flush=True)
