"""验证缓存更新后是否与实时API一致"""
import pickle, os, sys, subprocess, json, random
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR)

PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

def curl_get(url, timeout=8):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url], capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except: return ''

# 实时API
all_codes = []
for i in range(600000, 606000): all_codes.append(str(i))
for i in range(0, 3000): all_codes.append(f'{i:06d}')

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
            api_data[code] = {'name':nm, 'p':pct, 'vol_ratio':vol_r}
        except: pass

# 缓存
d = pickle.load(open('big_cache_full.pkl', 'rb'))
cache_stocks = d['data'].get('2026-05-27', [])
cache_by_code = {s['code']: s for s in cache_stocks}

print(f'实时API: {len(api_data)}只', flush=True)
print(f'缓存(5/27): {len(cache_stocks)}只', flush=True)

common = [c for c in api_data if c in cache_by_code]
print(f'共同: {len(common)}只', flush=True)

# 抽10个随机对比
samples = random.sample(common, min(10, len(common)))
print(f'\n{"代码":>8s} | {"API涨%":>8s} | {"缓存涨%":>8s} | {"匹配":>4s} | {"API量比":>8s} | {"缓存量比":>8s}', flush=True)
print('-' * 60, flush=True)

match_p = 0; match_vr = 0
for code in samples:
    api = api_data[code]
    cache = cache_by_code[code]
    p_ok = '✅' if abs(api['p'] - cache.get('p',0)) < 0.05 else '❌'
    vr_ok = '✅' if abs(api['vol_ratio'] - cache.get('vol_ratio',0)) < 0.05 else '❌'
    if p_ok == '✅': match_p += 1
    if vr_ok == '✅': match_vr += 1
    print(f'{code:>8s} | {api["p"]:>+7.2f}% | {cache.get("p",0):>+7.2f}% | {p_ok:>4s} | {api["vol_ratio"]:>7.2f} | {cache.get("vol_ratio",0):>7.2f}', flush=True)

print(f'\n✅ 涨跌幅匹配: {match_p}/{len(samples)}', flush=True)
print(f'✅ 量比匹配: {match_vr}/{len(samples)}', flush=True)
