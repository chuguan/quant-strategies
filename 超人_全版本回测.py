"""
全版本回测对比 — 次日最高概率分布
"""
import pickle, os, json, sys, statistics
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
all_days = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
KLINE_CACHE = {}

def get_kline(code):
    if code not in KLINE_CACHE:
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    KLINE_CACHE[code] = json.load(f)
            except:
                KLINE_CACHE[code] = None
        else:
            KLINE_CACHE[code] = None
    return KLINE_CACHE[code]

import statistics as stats

# ===== 各版本评分函数 =====
def score_original(p, vr, cl):
    sc = 10
    if 5 <= p <= 6.5: sc += 15
    elif 6.5 < p <= 7: sc += 8
    elif 4.5 <= p < 5: sc += 5
    elif p > 7: sc -= 15
    if 70 <= cl <= 85: sc += 15
    elif 85 < cl <= 90: sc += 5
    elif 60 <= cl < 70: sc += 3
    elif cl > 90: sc -= 20
    if 1.2 <= vr <= 2.0: sc += 10
    elif 2.0 < vr <= 3.0: sc += 5
    elif 1.0 <= vr < 1.2: sc += 3
    elif vr > 3: sc -= 15
    return sc

def score_v22(p, vr, cl):
    sc = 10
    if 5 <= p <= 6.5: sc += 15
    elif 6.5 < p <= 7: sc += 8
    elif 4.5 <= p < 5: sc += 5
    elif p > 7: sc -= 15
    if 60 <= cl <= 85: sc += 10
    elif cl > 90: sc -= 15
    if 0.8 <= vr <= 1.5: sc += 10
    elif 1.5 < vr <= 3.0: sc += 0
    elif vr > 3: sc -= 10
    return sc

def score_v4(p, vr, cl):
    sc = 10
    if 5 <= p <= 6.5: sc += 15
    elif 6.5 < p <= 7: sc += 8
    elif 4.5 <= p < 5: sc += 5
    elif p > 7: sc -= 15
    if 60 <= cl <= 85: sc += 10
    elif 85 < cl <= 90: sc += 0
    elif cl > 90: sc -= 15
    if 0.8 <= vr <= 1.5: sc += 10
    elif 1.5 < vr <= 2.0: sc += 5
    elif vr > 2: sc -= 8
    return sc

def score_v5_kline(p, vr, cl, code, date, buy_c):
    sc = score_v4(p, vr, cl)
    kd = get_kline(code)
    if kd is None: return sc
    
    today_idx = None
    for i, d in enumerate(kd):
        if d['date'] == date:
            today_idx = i
            break
    if today_idx is None or today_idx < 20: return sc
    
    td = kd[today_idx]
    close = td['close']
    volume = td['volume']
    
    ma5 = stats.mean([kd[i]['close'] for i in range(today_idx-4, today_idx+1)])
    ma10 = stats.mean([kd[i]['close'] for i in range(today_idx-9, today_idx+1)])
    ma20 = stats.mean([kd[i]['close'] for i in range(today_idx-19, today_idx+1)])
    
    sc += 5 if ma10 >= ma20 else 0                    # 多头
    sc += 2 if close >= ma5 else 0                     # 站上5日线
    sc += 2 if close >= ma10 else 0                    # 站上10日线
    sc += 3 if close >= ma20 else 0                    # 站上20日线
    
    prev_pct = (kd[today_idx-1]['close']/kd[today_idx-2]['close']-1)*100 if today_idx >= 2 else 0
    today_pct = (close/kd[today_idx-1]['close']-1)*100
    accel = today_pct - prev_pct
    
    sc += 3 if accel < 7 else 0                        # 加速度<7
    
    vol_ma5 = stats.mean([kd[i]['volume'] for i in range(today_idx-4, today_idx+1)])
    vol_ratio = volume/vol_ma5 if vol_ma5 > 0 else 0
    sc += 2 if vol_ratio < 2 else (-3 if vol_ratio > 3 else 0)
    
    candle_range = td['high'] - td['low']
    lower_shadow = (min(td['close'],td['open'])-td['low'])/candle_range*100 if candle_range>0 else 0
    sc += 2 if lower_shadow < 10 else 0
    
    h20 = max([kd[i]['high'] for i in range(today_idx-19, today_idx+1)])
    l20 = min([kd[i]['low'] for i in range(today_idx-19, today_idx+1)])
    near20 = (close-l20)/(h20-l20)*100 if h20>l20 else 50
    sc += 3 if 40 <= near20 <= 80 else (-3 if near20 > 90 else 0)
    
    return sc

def get_champion(dt, score_fn, extra=None):
    """取某天冠军（次日最高涨幅）"""
    stocks = data.get(dt, [])
    best_nv = 0
    best_sc = -999
    best_code = None
    
    for s in stocks:
        code, p = s['code'], s['p']
        if p < 5 or p > 8: continue
        if (s.get('vol_ratio',0) or 0) < 0.8: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > 15: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= 150: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > 80: continue
        
        vr = s.get('vol_ratio',0) or 0
        cl = s.get('cl',0)
        
        if extra == 'v5':
            buy_c = s.get('close', 0)
            sc = score_v5_kline(p, vr, cl, code, dt, buy_c)
        else:
            sc = score_fn(p, vr, cl)
        
        nv = s.get('n',0) or 0
        
        if sc > best_sc:
            best_sc = sc
            best_nv = nv
            best_code = code
    
    return best_nv

# ===== 跑所有版本 =====
versions = [
    ('原版', score_original, None),
    ('v2.2', score_v22, None),
    ('v4(伯乐)', score_v4, None),
    ('v5(K线+分)', score_v4, 'v5'),  # uses score_v4 as base + kline
]

print(f'2026年 {len(all_days)}天 各版本次日最高概率分布')
print(f'{"版本":<14}', end='')
for pct in [0, 1, 2, 2.5, 3, 4, 5, 7, 10]:
    print(f' ≥{pct}%'.rjust(8), end='')
print(f' {"均涨%":>6}', end='')
print()

for vname, sfn, extra in versions:
    results = [get_champion(dt, sfn, extra) for dt in all_days]
    results = [r for r in results if r is not None]
    n = len(results)
    
    print(f'{vname:<14}', end='')
    for pct in [0, 1, 2, 2.5, 3, 4, 5, 7, 10]:
        cnt = sum(1 for r in results if r >= pct)
        p = cnt*100/n
        print(f' {p:>6.1f}%', end='')
    
    avg = sum(results)/n
    print(f' {avg:>6.2f}%')

# ===== 按月分 =====
print(f'\n--- v5按月分解 ---')
for month in ['2026-01','2026-02','2026-03','2026-04','2026-05']:
    md = [dt for dt in all_days if dt.startswith(month)]
    if not md: continue
    results = [get_champion(dt, score_v4, 'v5') for dt in md]
    results = [r for r in results if r is not None]
    n = len(results)
    w25 = sum(1 for r in results if r >= 2.5)
    w5 = sum(1 for r in results if r >= 5)
    avg = sum(results)/n
    print(f'{month:<10} {n:>2}天 达2.5%:{w25}({w25*100/n:.1f}%) 达5%:{w5}({w5*100/n:.1f}%) 均{avg:.2f}%')

# ===== 全部版本按月 =====
print(f'\n--- 各版本按月对比 达2.5%率 ---')
print(f'{"月份":<10} {"原版":>8} {"v2.2":>8} {"v4伯乐":>8} {"v5K线":>8}')
for month in ['2026-01','2026-02','2026-03','2026-04','2026-05']:
    md = [dt for dt in all_days if dt.startswith(month)]
    if not md: continue
    print(f'{month:<10}', end='')
    for vname, sfn, extra in versions:
        results = []
        for dt in md:
            if extra == 'v5':
                r = get_champion(dt, sfn, 'v5')
            else:
                r = get_champion(dt, sfn, extra)
            if r is not None:
                results.append(r)
        if not results:
            print(f' {"N/A":>8}', end='')
        else:
            w25 = sum(1 for r in results if r >= 2.5)*100/len(results)
            print(f' {w25:>7.1f}%', end='')
    print()

# ===== 概率密度 =====
print(f'\n--- 概率密度（每1%一档）v5 ---')
bins = [(i, i+1) for i in range(-5, 11)]
v5_results = [get_champion(dt, score_v4, 'v5') for dt in all_days]
v5_results = [r for r in v5_results if r is not None]
n = len(v5_results)

print(f'{"区间":<10} {"天数":<6} {"占比":<8} {"累计":<8}')
cum = 0
for lo, hi in bins:
    cnt = sum(1 for r in v5_results if lo <= r < hi)
    p = cnt*100/n
    cum += p
    bar = '█' * int(p/2)
    print(f'{lo:+.0f}~{hi:+.0f}%  {cnt:<6} {p:<8.1f}% {cum:<8.1f}% {bar}')

print(f'\n2026年 v5: {n}天 | 正收益:{sum(1 for r in v5_results if r>=0)*100/n:.1f}% | 达2.5%:{sum(1 for r in v5_results if r>=2.5)*100/n:.1f}% | 达5%:{sum(1 for r in v5_results if r>=5)*100/n:.1f}%')
