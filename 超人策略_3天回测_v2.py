"""
超人策略 v2.0 — 3天回测，聚焦2.5%胜率
条件：涨5~8% + 量比>1 + 换手5~15% + 市值<200亿 + 非ST
评分：分段强度评分（同超人v2）
目标：看冠军和Top3中3日内最高≥2.5%的胜率
"""
import pickle, os, json, sys, time
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR)

print("加载缓存...", flush=True)
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, names = cache['data'], cache['names']
dates = sorted(data.keys())

def get_forward_3d(code, buy_date, kline_cache):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if code in kline_cache:
        kd = kline_cache[code]
    else:
        if not os.path.exists(fp):
            return None, None, None, None
        try:
            with open(fp, 'r') as f:
                kd = json.load(f)
            kline_cache[code] = kd
        except:
            return None, None, None, None
    
    idx = -1
    for i, k in enumerate(kd):
        if k['date'] == buy_date:
            idx = i
            break
    if idx < 0 or idx >= len(kd) - 1:
        return None, None, None, None
    
    buy_price = kd[idx]['close']
    if buy_price <= 0:
        return None, None, None, None
    
    max_h, min_l = -999, 999
    nxt_l = None
    for j in range(1, 4):
        di = idx + j
        if di >= len(kd):
            break
        k = kd[di]
        hp = (k['high'] / buy_price - 1) * 100
        lp = (k['low'] / buy_price - 1) * 100
        if hp > max_h: max_h = hp
        if lp < min_l: min_l = lp
        if j == 1: nxt_l = lp
    if max_h == -999:
        return None, None, None, None
    return max_h, min_l, nxt_l, buy_price

def superman_v2_score(p, vr, cl):
    sc = 10
    if 5 <= p <= 6.5: sc += 15
    elif 6.5 < p <= 7: sc += 8
    elif 4.5 <= p < 5: sc += 5
    if 70 <= cl <= 85: sc += 15
    elif 85 < cl <= 90: sc += 5
    elif 60 <= cl < 70: sc += 3
    if 1.2 <= vr <= 2.0: sc += 10
    elif 2.0 < vr <= 3.0: sc += 5
    elif 1.0 <= vr < 1.2: sc += 3
    if cl > 90: sc -= 20
    if p > 7: sc -= 15
    if vr > 3: sc -= 15
    return sc

print("开始回测...", flush=True)
t0 = time.time()
kline_cache = {}
all_results = []

for dt in dates:
    if dt.endswith('-22') and '2026' in dt: continue
    
    stocks = data.get(dt, [])
    cand = []
    for s in stocks:
        code, p = s['code'], s['p']
        if p < 5 or p > 8: continue
        if (s.get('vol_ratio',0) or 0) < 1.0: continue
        
        ri = cache['real'].get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > 15: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= 200: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        
        jv = s.get('j_val',0) or 0
        if jv > 100: continue
        
        vr = s.get('vol_ratio',0) or 0
        cl = s.get('cl', 0)
        sc = superman_v2_score(p, vr, cl)
        
        n3, n3_low, nxt_low, buy_c = get_forward_3d(code, dt, kline_cache)
        if n3 is None: continue
        
        cand.append((sc, nm, code, p, vr, cl, hsl, sz, buy_c, n3, n3_low, nxt_low, jv))
    
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[3]))
    
    c = cand[0]
    top3_n3 = [x[9] for x in cand[:3] if x[9] is not None]
    
    all_results.append({
        'dt': dt, 'champ': c[1], 'champ_n3': c[9],
        'top3_n3_list': top3_n3,
        'cand_count': len(cand)
    })

print(f"完成：{len(all_results)}天，{time.time()-t0:.1f}s\n", flush=True)

# 统计
for year in ['2025','2026']:
    yr = [r for r in all_results if r['dt'].startswith(year)]
    if not yr:
        print(f"{year}：无数据", flush=True)
        continue
    
    n = len(yr)
    
    # 冠军2.5%
    champ_ge_25 = sum(1 for r in yr if r['champ_n3'] >= 2.5)
    champ_ge_5 = sum(1 for r in yr if r['champ_n3'] >= 5)
    champ_avg = sum(r['champ_n3'] for r in yr) / n
    
    # Top3: 任意一只≥2.5%
    top3_any_25 = sum(1 for r in yr if any(x >= 2.5 for x in r['top3_n3_list']))
    top3_any_5 = sum(1 for r in yr if any(x >= 5 for x in r['top3_n3_list']))
    top3_avg = sum(sum(r['top3_n3_list'])/len(r['top3_n3_list']) for r in yr) / n
    
    # Top3: 全部≥2.5%
    top3_all_25 = sum(1 for r in yr if all(x >= 2.5 for x in r['top3_n3_list']))
    
    print(f"━━━ {year}年（{n}天）━━━", flush=True)
    print(f"冠军 ≥2.5%: {champ_ge_25}天  {champ_ge_25*100/n:.1f}%", flush=True)
    print(f"冠军 ≥5%:   {champ_ge_5}天  {champ_ge_5*100/n:.1f}%", flush=True)
    print(f"冠军平均:   {champ_avg:.2f}%", flush=True)
    print(f"", flush=True)
    print(f"Top3任意≥2.5%: {top3_any_25}天  {top3_any_25*100/n:.1f}%", flush=True)
    print(f"Top3任意≥5%:   {top3_any_5}天  {top3_any_5*100/n:.1f}%", flush=True)
    print(f"Top3全部≥2.5%: {top3_all_25}天  {top3_all_25*100/n:.1f}%", flush=True)
    print(f"Top3平均:       {top3_avg:.2f}%", flush=True)
    print()
    
    # 近5天
    if year == '2026':
        print(f"━━━ 近5天详情━━━", flush=True)
        for dt in ['2026-05-18','2026-05-19','2026-05-20','2026-05-21','2026-05-22']:
            r = next((x for x in yr if x['dt'] == dt), None)
            if not r:
                print(f"{dt}: 无候选", flush=True)
                continue
            ok = '🔥' if r['champ_n3'] >= 5 else ('✅' if r['champ_n3'] >= 2.5 else '❌')
            top3_str = '/'.join([f"{x:.1f}%" for x in r['top3_n3_list']])
            any25 = any(x >= 2.5 for x in r['top3_n3_list'])
            any5 = any(x >= 5 for x in r['top3_n3_list'])
            extra = ''
            if any5: extra = '🔥有5%'
            elif any25: extra = '✅有2.5%'
            else: extra = '❌全亏'
            print(f"{dt}: {r['champ']} 冠军+{r['champ_n3']:.2f}% {ok} | Top3: [{top3_str}] {extra}", flush=True)
