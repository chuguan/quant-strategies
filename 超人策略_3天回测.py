"""
超人策略 v2.0 — 3天最大盈利 + 次日下探-3% 回测
条件：涨5~8% + 量比>1 + 换手5~15% + 市值<200亿 + 非ST
评分：分段强度评分（同超人v2）
目标：看3天内最高能赚多少 + 次日最低会不会亏-3%
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

def get_forward_3d(code, buy_date):
    """获取买入后3个交易日的最高和最低涨幅"""
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp):
        return None, None, None, None
    try:
        with open(fp, 'r') as f:
            kdata = json.load(f)
    except:
        return None, None, None, None
    
    # 找到买入日期
    idx = -1
    for i, kd in enumerate(kdata):
        if kd['date'] == buy_date:
            idx = i
            break
    if idx < 0 or idx >= len(kdata) - 1:
        return None, None, None, None
    
    buy_price = kdata[idx]['close']
    if buy_price <= 0:
        return None, None, None, None
    
    # 看未来3天（D+1, D+2, D+3）
    max_high_pct = -999
    min_low_pct = 999
    nxt_day_low_pct = None
    
    for j in range(1, 4):  # D+1, D+2, D+3
        di = idx + j
        if di >= len(kdata):
            break
        kd = kdata[di]
        high_pct = (kd['high'] / buy_price - 1) * 100
        low_pct = (kd['low'] / buy_price - 1) * 100
        if high_pct > max_high_pct:
            max_high_pct = high_pct
        if low_pct < min_low_pct:
            min_low_pct = low_pct
        if j == 1:
            nxt_day_low_pct = low_pct  # 次日最低
    
    if max_high_pct == -999:
        return None, None, None, None
    
    return max_high_pct, min_low_pct, nxt_day_low_pct, buy_price

def superman_v2_score(p, vr, cl):
    sc = 10
    # 涨幅5~6.5%最佳
    if 5 <= p <= 6.5:
        sc += 15
    elif 6.5 < p <= 7:
        sc += 8
    elif 4.5 <= p < 5:
        sc += 5
    # 收盘位70~85%最佳
    if 70 <= cl <= 85:
        sc += 15
    elif 85 < cl <= 90:
        sc += 5
    elif 60 <= cl < 70:
        sc += 3
    # 量比1.2~2.0最佳
    if 1.2 <= vr <= 2.0:
        sc += 10
    elif 2.0 < vr <= 3.0:
        sc += 5
    elif 1.0 <= vr < 1.2:
        sc += 3
    # 扣分
    if cl > 90:
        sc -= 20
    if p > 7:
        sc -= 15
    if vr > 3:
        sc -= 15
    return sc

def get_candidates(date, kline_cache):
    stocks = data.get(date, [])
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
        
        # 用缓存或实时计算3天数据
        n3 = None
        n3_low = None
        nxt_low = None
        buy_c = s.get('close', 0)
        
        if code in kline_cache:
            kd = kline_cache[code]
        else:
            fp = os.path.join(CACHE_DIR, f'{code}.json')
            if os.path.exists(fp):
                try:
                    with open(fp, 'r') as f:
                        kd = json.load(f)
                    kline_cache[code] = kd
                except:
                    kd = []
            else:
                kd = []
        
        if kd:
            idx = -1
            for i, k in enumerate(kd):
                if k['date'] == date:
                    idx = i
                    break
            if idx >= 0 and idx < len(kd) - 1:
                buy_price = kd[idx]['close']
                if buy_price > 0:
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
                    if max_h != -999:
                        n3 = max_h
                        n3_low = min_l
                        nxt_low = nxt_l
                        buy_c = buy_price
        
        if n3 is not None:
            cand.append((sc, nm, code, p, vr, cl, hsl, sz, buy_c, n3, n3_low, nxt_low, jv))
    
    cand.sort(key=lambda x: (-x[0], -x[3]))
    return cand

print("开始回测...", flush=True)
t0 = time.time()

# 按年份跑
all_results = []
kline_cache = {}

for dt in dates:
    if dt.endswith('-22') and '2026' in dt: continue
    cand = get_candidates(dt, kline_cache)
    if not cand: continue
    
    # 冠军数据
    c = cand[0]
    n3_max = c[9]   # 3天最高%
    n3_low = c[10]  # 3天最低%
    nxt_low = c[11] # 次日最低%
    
    # Top3平均
    top3_n3 = [x[9] for x in cand[:3] if x[9] is not None]
    top3_avg = sum(top3_n3)/len(top3_n3) if top3_n3 else 0
    
    # Top3中是否有次日跌超-3%
    top3_nxt_lows = [x[11] for x in cand[:3] if x[11] is not None]
    top3_low3 = [x[10] for x in cand[:3] if x[10] is not None]
    
    # 冠军次日是否下探-3%
    champ_dive = nxt_low <= -3 if nxt_low is not None else False
    # Top3是否有任何一只次日下探-3%
    any_dive = any(l <= -3 for l in top3_nxt_lows) if top3_nxt_lows else False
    
    all_results.append({
        'dt': dt, 'champ': c[1], 'score': c[0],
        'pct': c[3], 'buy': c[8],
        'n3': n3_max, 'n3_low': n3_low,
        'nxt_low': nxt_low, 'champ_dive': champ_dive,
        'top3_avg': top3_avg, 'any_dive': any_dive,
        'cand_count': len(cand)
    })

print(f"\n回测完成：{len(all_results)}天，耗时{time.time()-t0:.1f}s\n", flush=True)

# 按年份统计
for year in ['2025','2026']:
    yr = [r for r in all_results if r['dt'].startswith(year)]
    if not yr:
        print(f"{year}年：无数据", flush=True)
        continue
    
    # 3天达标率
    w5_3d = sum(1 for r in yr if r['n3'] >= 5)
    w25_3d = sum(1 for r in yr if r['n3'] >= 2.5)
    avg_n3 = sum(r['n3'] for r in yr) / len(yr)
    
    # Top3平均
    avg_top3 = sum(r['top3_avg'] for r in yr) / len(yr)
    w5_top3 = sum(1 for r in yr if r['top3_avg'] >= 5)
    
    # 次日下探-3%统计
    dive_count = sum(1 for r in yr if r['champ_dive'])
    any_dive_count = sum(1 for r in yr if r['any_dive'])
    
    # 胜率（n3 > 0）
    win_rate = sum(1 for r in yr if r['n3'] > 0) / len(yr) * 100
    
    print(f"━━━ {year}年（{len(yr)}天）━━━", flush=True)
    print(f"冠军3天最高≥5%: {w5_3d}天（{w5_3d*100/len(yr):.1f}%）", flush=True)
    print(f"冠军3天最高≥2.5%: {w25_3d}天（{w25_3d*100/len(yr):.1f}%）", flush=True)
    print(f"冠军3天平均最高: {avg_n3:.2f}%", flush=True)
    print(f"冠军3天胜率(>0): {win_rate:.0f}%", flush=True)
    print(f"Top3平均最高: {avg_top3:.2f}%", flush=True)
    print(f"Top3平均≥5%: {w5_top3}/{len(yr)} ({w5_top3*100/len(yr):.1f}%)", flush=True)
    print(f"冠军次日下探-3%: {dive_count}天（{dive_count*100/len(yr):.1f}%）", flush=True)
    print(f"Top3有任意下探-3%: {any_dive_count}天（{any_dive_count*100/len(yr):.1f}%）", flush=True)
    
    # 冠军3天平均最低
    avg_low = sum(r['n3_low'] for r in yr) / len(yr)
    print(f"冠军3天平均最低: {avg_low:.2f}%", flush=True)
    print()

# 近5天详情
print("━━━ 近5天冠军详情（3天视角）━━━", flush=True)
for dt in ['2026-05-18','2026-05-19','2026-05-20','2026-05-21','2026-05-22']:
    cand = get_candidates(dt, kline_cache)
    if not cand:
        print(f'{dt}: 无候选', flush=True)
        continue
    c = cand[0]
    n3s = f'{c[9]:.2f}%' if c[9] is not None else 'N/A'
    nls = f'{c[10]:.2f}%' if c[10] is not None else 'N/A'
    nxl = f'{c[11]:.2f}%' if c[11] is not None else 'N/A'
    dive_mark = '⚠️次日下探-3%' if (c[11] is not None and c[11] <= -3) else '✓安全'
    ok = '🔥5%' if c[9] is not None and c[9] >= 5 else ('✅' if c[9] is not None and c[9] >= 2.5 else '❌')
    print(f'{dt}: 冠军{c[1]}(涨{c[3]:.1f}% CL{c[5]:.0f}%) 买{c[8]:.2f} | 3天最高{n3s} 最低{nls} 次日最低{nxl} {dive_mark} {ok}', flush=True)
    for i, x in enumerate(cand[:3]):
        ns = f'{x[9]:.2f}%' if x[9] is not None else 'N/A'
        ls = f'{x[10]:.2f}%' if x[10] is not None else 'N/A'
        nl = f'{x[11]:.2f}%' if x[11] is not None else 'N/A'
        dive2 = '⚠️-3%' if (x[11] is not None and x[11] <= -3) else ''
        ok2 = '🔥' if x[9] is not None and x[9] >= 5 else ('✅' if x[9] is not None and x[9] >= 2.5 else '')
        print(f'  Top{i+1}: {x[1]}(涨{x[3]:.1f}% CL{x[5]:.0f}% J{x[12]:.0f}) 买{x[8]:.2f} → 3天高{ns} 最低{ls} 次日低{nl} {dive2} {ok2}', flush=True)

# 找出冠军次日下探-3%最多的月份
print("\n━━━ 冠军次日下探-3%的失败案例 ━━━", flush=True)
dive_cases = [r for r in all_results if r['champ_dive']]
print(f"共{dive_cases}天冠军次日下探-3%:", flush=True)
for r in dive_cases:
    print(f"{r['dt']}: {r['champ']}({r['pct']:.1f}%)买{r['buy']:.2f} 3天最高{r['n3']:.2f}% 3天最低{r['n3_low']:.2f}% 次日最低{r['nxt_low']:.2f}%", flush=True)
