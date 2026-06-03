"""验证2026年缓存数据准确性 — 对比实时API"""
import pickle, os, sys, subprocess, json
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR)

PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

def curl_get(url, timeout=8):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url], capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except: return ''

# 1. 从实时API获取今天(2026-05-27)的股票数据
print("=== 实时API 今天(5/27) 数据 ===", flush=True)
all_codes = []
for i in range(600000, 606000): all_codes.append(str(i))
for i in range(0, 3000): all_codes.append(f'{i:06d}')

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

api_data = {}
for i in range(0, len(all_codes), 80):
    chunk = all_codes[i:i+80]
    symbols = [f'{PREFIX(c)}{c}' for c in chunk]
    text = curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}', timeout=6)
    for line in text.split('\n'):
        if '~' not in line: continue
        parts = line.split('~')
        if len(parts) < 40: continue
        try:
            nm = parts[1]; code = parts[2]
            if not nm or 'ST' in nm or '*ST' in nm or '退' in nm: continue
            if not IS_MAIN(code): continue
            price = float(parts[3]); prev_c = float(parts[4])
            pct = round((price/prev_c-1)*100, 2) if prev_c else 0
            vol_r = float(parts[38]) if parts[38] else 0
            api_data[code] = {'name':nm, 'p':pct, 'vol_ratio':vol_r, 'price':price}
        except: pass

print(f"实时API: {len(api_data)}只", flush=True)

# 2. 从缓存获取今天的数据
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, names = d['data'], d['names']
cache_stocks = data.get('2026-05-27', [])
print(f"缓存: {len(cache_stocks)}只", flush=True)

# 3. 对比：取实时API和缓存共同有的前10个code
common = list(set(api_data.keys()) & set(s['code'] for s in cache_stocks))
print(f"\n共同股票: {len(common)}只", flush=True)

# 抽10个随机对比
import random
samples = random.sample(common, min(10, len(common)))
print(f"\n=== 对比抽样（实时API vs 缓存）===", flush=True)
print(f"{'代码':>8s} | {'名称':>8s} | {'API涨%':>8s} | {'缓存涨%':>8s} | {'匹配':>4s} | {'API量比':>8s} | {'缓存量比':>8s}", flush=True)
print("-" * 70)

match_p = 0; match_vr = 0
for code in samples:
    api = api_data[code]
    cache = next(s for s in cache_stocks if s['code'] == code)
    api_p = api['p']; cache_p = cache.get('p', 0) or 0
    api_vr = api['vol_ratio']; cache_vr = cache.get('vol_ratio', 0) or 0
    p_match = '✅' if abs(api_p - cache_p) < 0.05 else '❌'
    vr_match = '✅' if abs(api_vr - cache_vr) < 0.05 else '❌'
    if p_match == '✅': match_p += 1
    if vr_match == '✅': match_vr += 1
    nm = api['name'][:8]
    print(f"{code:>8s} | {nm:>8s} | {api_p:>+7.2f}% | {cache_p:>+7.2f}% | {p_match:>4s} | {api_vr:>7.2f} | {cache_vr:>7.2f}", flush=True)

print(f"\n涨跌幅匹配率: {match_p}/{len(samples)}", flush=True)
print(f"量比匹配率: {match_vr}/{len(samples)}", flush=True)

# 4. 检查2026年缓存各日期的股票数量趋势
print(f"\n=== 2026年每月平均股票数 ===", flush=True)
from collections import defaultdict
monthly = defaultdict(list)
for dt, stocks in data.items():
    if dt.startswith('2026'):
        month = dt[:7]
        monthly[month].append(len(stocks))
for m in sorted(monthly.keys()):
    avg = sum(monthly[m]) / len(monthly[m])
    print(f"  {m}: 平均{avg:.0f}只/天 (范围{min(monthly[m])}~{max(monthly[m])})", flush=True)
