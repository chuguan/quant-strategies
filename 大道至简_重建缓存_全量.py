"""重建缓存 — 用全部K线JSON文件，不做当前活跃限制"""
import os, sys, json, subprocess, time, pickle
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(SCRIPTS_DIR)

PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

# 1. 先获取当前ST列表
def curl_get(url, timeout=8):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url], capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except: return ''

print("📡 获取ST股票列表...", flush=True)
st_codes = set()
all_codes = [str(i) for i in range(600000, 606000)] + [f'{i:06d}' for i in range(0, 3000)]
for i in range(0, len(all_codes), 80):
    chunk = all_codes[i:i+80]
    symbols = [f'{PREFIX(c)}{c}' for c in chunk]
    text = curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}', timeout=5)
    for line in text.split('\n'):
        if '~' not in line: continue
        parts = line.split('~')
        if len(parts) < 4: continue
        try:
            nm = parts[1]; code = parts[2]
            if not nm: continue
            if not IS_MAIN(code): continue
            if 'ST' in nm or '*ST' in nm or '退' in nm:
                st_codes.add(code)
        except: pass

print(f'当前ST/退市: {len(st_codes)}只', flush=True)

# 2. 扫描所有K线JSON文件
print("📂 扫描K线文件...", flush=True)
all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and 
             (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
print(f'K线文件总数: {len(all_files)}', flush=True)

# 排除ST（今天ST的在整个历史都排除）
active_files = [f for f in all_files if f.replace('.json','').replace('sh','').replace('sz','') not in st_codes]
print(f'排除ST后: {len(active_files)}个文件', flush=True)

# 处理K线
def process_stock(fn):
    code = fn.replace('.json','').replace('sh','').replace('sz','')
    try:
        with open(os.path.join(CACHE_DIR, fn), 'rb') as f:
            kdata = json.loads(f.read().decode('utf-8'))
    except:
        return None
    if not kdata or len(kdata) < 20: return None

    results = {}
    for i in range(len(kdata)):
        dt = kdata[i]['date']
        if dt < '2024-01-02': continue
        if dt > '2026-05-28': continue
        df = kdata[:i+1]; n = len(df)
        close = [r['close'] for r in df]
        high = [r['high'] for r in df]
        low = [r['low'] for r in df]

        nh = 0
        if i+1 < len(kdata):
            nh = round((kdata[i+1]['high']/kdata[i]['close']-1)*100, 1)
        if n < 20: continue

        p = round((close[-1]/kdata[i-1]['close']-1)*100, 2) if i > 0 else 0
        vr = kdata[i]['volume']/max(kdata[i-1]['volume'],1) if i > 0 else 1

        ma5 = sum(close[-5:])/5 if n >= 5 else close[-1]
        a5 = 1 if close[-1] > ma5 else 0

        ema12 = close[-1]; ema26 = close[-1]
        for j in range(n-2, max(n-27, -1), -1):
            ema12 = close[j]*2/13+ema12*11/13
            ema26 = close[j]*2/27+ema26*25/27
        dfv = round(ema12-ema26,3); mg = 1 if dfv > 0 else 0

        kv = dv = jv = 50; kdj_g = 0
        if n >= 9:
            h9 = max(high[-9:]); l9 = min(low[-9:])
            rsv = (close[-1]-l9)/(h9-l9+1e-10)*100
            kv = round(rsv*2/3+50/3,1); dv = round(kv*2/3+50/3,1); jv = round(3*kv-2*dv,1)
            kdj_g = 1 if kv > dv else 0

        wr = 50
        if n >= 21:
            h21 = max(high[-21:]); l21 = min(low[-21:])
            wr = round(100*(h21-close[-1])/(h21-l21+1e-10),1)

        cl = 50
        if n >= 20:
            h20 = max(high[-20:]); l20 = min(low[-20:])
            cl = round((close[-1]-l20)/(h20-l20+1e-10)*100,1)

        results[dt] = {
            'code': code, 'p': p, 'vol_ratio': vr, 'cl': cl,
            'dif_val': dfv, 'macd_golden': mg, 'above_ma5': a5,
            'wr_val': wr, 'k_val': kv, 'd_val': dv, 'j_val': jv,
            'kdj_golden': kdj_g, 'n': nh, 'close': close[-1],
        }
    return code, results, kdata[-1]['date'] if kdata else ''

print("🔄 并行处理...", flush=True)
all_data = {}
done = 0
with ThreadPoolExecutor(max_workers=16) as pool:
    futs = {pool.submit(process_stock, fn): fn for fn in active_files}
    for fut in as_completed(futs):
        res = fut.result()
        if res:
            code, results, _ = res
            for dt, item in results.items():
                if dt not in all_data: all_data[dt] = {}
                if code not in all_data[dt]:
                    all_data[dt][code] = item
        done += 1
        if done % 500 == 0: print(f"  {done}/{len(active_files)}", flush=True)

# 整理
data = {}
for dt in sorted(all_data.keys()):
    entries = [{'code': code,
        'p': item['p'], 'vol_ratio': item['vol_ratio'], 'cl': item['cl'],
        'dif_val': item['dif_val'], 'macd_golden': item['macd_golden'],
        'above_ma5': item['above_ma5'], 'wr_val': item['wr_val'],
        'k_val': item['k_val'], 'd_val': item['d_val'], 'j_val': item['j_val'],
        'kdj_golden': item['kdj_golden'], 'n': item['n'], 'close': item['close'],
    } for code, item in all_data[dt].items()]
    data[dt] = entries

# 保存
pickle.dump({'data': data, 'real': {}, 'names': {}}, open('big_cache_full.pkl', 'wb'))
dates = sorted(data.keys())
print(f"\n✅ 重建完成")
print(f"日期: {dates[0]} ~ {dates[-1]}, 共{len(dates)}天")
print(f"股票: 3427个K线文件, 排除ST后{len(active_files)}个")
# 最后5天
for dt in dates[-5:]:
    ss = data[dt]
    ps = [s['p'] for s in ss if abs(s['p']) < 15]
    ap = sum(ps)/len(ps) if ps else 0
    print(f"  {dt}: {len(ss)}只 均{ap:.2f}%")
