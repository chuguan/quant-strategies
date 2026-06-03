"""验证缓存更新后，实时API和缓存是否一致"""
import pickle, os, sys, subprocess, random
os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

def curl_get(url, timeout=8):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url], capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except: return ''

# 1. 实时API
all_codes = [str(i) for i in range(600000, 606000)] + [f'{i:06d}' for i in range(0, 3000)]
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
            try: hsl = float(parts[46]) if parts[46] and float(parts[46]) < 100 else 0
            except: hsl = 0
            try: sz = float(parts[44])/1e8 if parts[44] else 0
            except: sz = 0
            try: pe = float(parts[39]) if parts[39] else 0
            except: pe = 0
            api_data[code] = {'p':pct, 'vol_ratio':vol_r, 'hsl':hsl, 'sz':sz, 'pe':pe}
        except: pass

print(f'📡 实时API: {len(api_data)}只', flush=True)

# 2. 缓存
d = pickle.load(open('big_cache_full.pkl', 'rb'))
cache_stocks = d['data'].get('2026-05-27', [])
cache_by_code = {s['code']: s for s in cache_stocks}
cache_real = d['real']

print(f'💾 缓存: {len(cache_stocks)}只', flush=True)

common = [c for c in api_data if c in cache_by_code]
print(f'共同: {len(common)}只', flush=True)

# 3. 对比
samples = random.sample(common, min(15, len(common)))
match_p = match_vr = match_hsl = match_sz = 0
print(f'\n{"代码":>8s} | {"API涨%":>8s} | {"缓存涨%":>8s} | {"匹配":>4s} | {"量比API":>7s} | {"缓存":>7s} | {"HSL":>7s}', flush=True)
print('-' * 75, flush=True)

for code in samples:
    a = api_data[code]; c = cache_by_code[code]
    p_ok = abs(a['p'] - c.get('p',0) or 0) < 0.05
    vr_ok = abs(a['vol_ratio'] - c.get('vol_ratio',0) or 0) < 0.05
    if p_ok: match_p += 1
    if vr_ok: match_vr += 1
    p_tag = '✅' if p_ok else '❌'
    vr_tag = '✅' if vr_ok else '❌'
    print(f'{code:>8s} | {a["p"]:>+7.2f}% | {c.get("p",0):>+7.2f}% | {p_tag:>4s} | {a["vol_ratio"]:>6.2f} | {c.get("vol_ratio",0):>5.2f} | {a["hsl"]:>4.1f}%❓', flush=True)

print(f'\n📊 汇总:', flush=True)
print(f'  涨跌幅匹配: {match_p}/{len(samples)}', flush=True)
print(f'  量比匹配:   {match_vr}/{len(samples)}', flush=True)

# 4. 统计不匹配的原因
bad_p = sum(1 for c in common if abs(api_data[c]['p'] - cache_by_code[c].get('p',0)) >= 0.05)
bad_vr = sum(1 for c in common if abs(api_data[c]['vol_ratio'] - cache_by_code[c].get('vol_ratio',0)) >= 0.05)
print(f'\n🔍 全量统计:', flush=True)
print(f'  涨跌幅不一致: {bad_p}/{len(common)} = {bad_p*100/len(common):.1f}%', flush=True)
print(f'  量比不一致:   {bad_vr}/{len(common)} = {bad_vr*100/len(common):.1f}%', flush=True)
