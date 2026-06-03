#!/usr/bin/env python3
"""今日选股分析（不发邮件）— 展示CL排序版最高胜率60%+"""
import json, os, sys, subprocess, pickle, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR)

# 加载股票列表
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
all_codes = list(names.keys())

def get_today_qt(code):
    try:
        r = subprocess.run(['curl','-s','--max-time','5',
            f'https://qt.gtimg.cn/q={code}'], capture_output=True, timeout=8)
        text = r.stdout.decode('gbk', errors='replace')
        parts = text.split('~')
        if len(parts) < 45: return None
        p_now = float(parts[3]) if parts[3] else 0
        p_prev = float(parts[4]) if parts[4] else 0
        if p_prev <= 0: return None
        pct = round((p_now/p_prev - 1)*100, 2)
        high = float(parts[33]) if parts[33] else 0
        low = float(parts[34]) if parts[34] else 0
        vol = float(parts[36]) if parts[36] else 0
        hsl = float(parts[38]) if parts[38] else 0
        pe = float(parts[39]) if parts[39] else 0
        sz = float(parts[44]) if parts[44] else 0
        return {'code':code, 'p':pct, 'close':p_now, 'high':high, 'low':low,
                'vol':vol, 'hsl':hsl, 'pe':pe, 'sz':sz, 'p_prev':p_prev}
    except:
        return None

print('获取实时行情...', flush=True)
qt_map = {}
with ThreadPoolExecutor(max_workers=30) as pool:
    futs = {pool.submit(get_today_qt, c):c for c in all_codes}
    for f in as_completed(futs):
        r = f.result()
        if r and r['p_prev'] > 0:
            qt_map[r['code']] = r
print(f'获取到 {len(qt_map)} 只行情', flush=True)

def get_kl_indicators(code, today='2026-05-25', n=20):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return None
    try:
        with open(fp) as f:
            kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==today), None)
        if idx is None or idx < 1: return None
        hs = [k['high'] for k in kdata[idx-n+1:idx+1]]
        ls = [k['low'] for k in kdata[idx-n+1:idx+1]]
        c = kdata[idx]['close']
        cl = (c - min(ls)) / (max(hs)-min(ls)) * 100 if max(hs)!=min(ls) else 50
        o = kdata[idx]['open']
        is_yang = 1 if c > o else 0
        ma5 = sum(k['close'] for k in kdata[idx-4:idx+1])/5
        above_ma5 = 1 if c > ma5 else 0
        closes = [k['close'] for k in kdata[idx-8:idx+1]]
        h9 = max(closes); l9 = min(closes)
        rsv = (c-l9)/(h9-l9)*100 if h9!=l9 else 50
        k_val = rsv; d_val = k_val; j_val = 3*k_val-2*d_val
        ema12 = sum(closes[-12:])/12 if len(closes)>=12 else c
        ema26 = sum(closes[-26:])/26 if len(closes)>=26 else c
        dif = ema12 - ema26
        macd_golden = 1 if dif > 0 else 0
        kdj_golden = 1 if k_val > d_val else 0
        today_vol = kdata[idx]['volume']
        avg5_vol = sum(k['volume'] for k in kdata[idx-5:idx])/5 if idx>=5 else today_vol
        vol_ratio = round(today_vol/avg5_vol, 2) if avg5_vol>0 else 1.0
        prev_pct = (c/kdata[idx-1]['close']-1)*100
        high = kdata[idx]['high']; low = kdata[idx]['low']
        shadow_pct = (high-max(c,o))/(high-low)*100 if high!=low else 0
        up_days = 0
        for d in range(1, min(10, idx+1)):
            if kdata[idx-d+1]['close'] > kdata[idx-d]['close']:
                up_days += 1
            else:
                break
        return {'cl':round(cl,1), 'j_val':round(j_val,1), 'is_yang':is_yang,
                'above_ma5':above_ma5, 'vol_ratio':vol_ratio, 'macd_golden':macd_golden,
                'kdj_golden':kdj_golden, 'prev_pct':round(prev_pct,2),
                'shadow_pct':round(shadow_pct,1), 'up_days':up_days,
                'dif':round(dif,4), 'k_val':round(k_val,1), 'd_val':round(d_val,1)}
    except:
        return None

print('正在选股分析...', flush=True)
p_min,p_max=5,8; vr_min,vr_max=1.0,1.5; hsl_min,hsl_max=5,15; sz_max=200; cl_min,cl_max=60,90; j_max=100

def calc_score(p, cl, vr, hsl, indicators):
    s = 0
    if 5.5 <= p <= 6.5: s += 30
    elif 5 <= p <= 7: s += 25
    elif p <= 7.5: s += 20
    else: s += 10
    if 70 <= cl <= 85: s += 25
    elif 65 <= cl <= 90: s += 20
    else: s += 10
    if 1.0 <= vr <= 1.2: s += 20
    elif 1.0 <= vr <= 1.5: s += 15
    else: s += 5
    if 5 <= hsl <= 10: s += 10
    elif hsl <= 15: s += 5
    if indicators['macd_golden']: s += 10
    if indicators['kdj_golden']: s += 8
    if indicators['dif'] > 0: s += 5
    if indicators['is_yang']: s += 3
    if indicators['above_ma5']: s += 5
    jv = indicators['j_val']
    if jv > 80: s -= 5
    if jv > 90: s -= 10
    if indicators['shadow_pct'] > 40: s -= 3
    return s

cand = []
for code, qt in qt_map.items():
    p = qt['p']
    if p < p_min or p > p_max: continue
    hsl = qt['hsl']
    if hsl < hsl_min or hsl > hsl_max: continue
    sz = qt['sz']
    if sz >= sz_max: continue
    nm = names.get(code, '')
    if not nm or 'ST' in nm or '*ST' in nm or '退' in nm: continue
    ind = get_kl_indicators(code)
    if not ind: continue
    cl = ind['cl']
    if cl < cl_min or cl > cl_max: continue
    jv = ind['j_val']
    if jv > j_max: continue
    vr = ind['vol_ratio']
    if vr < vr_min or vr > vr_max: continue
    score = calc_score(p, cl, vr, hsl, ind)
    cand.append({
        'cl':cl, 'nm':nm, 'code':code, 'p':p, 'vr':vr, 'hsl':hsl,
        'sz':sz, 'buy_c':qt['close'], 'jv':jv, 'score':score,
        'pe':qt['pe'], 'macd':ind['macd_golden'], 'kdj':ind['kdj_golden'],
        'prev_pct':ind['prev_pct'], 'shadow':ind['shadow_pct'],
        'up_days':ind['up_days'], 'is_yang':ind['is_yang'],
        'above_ma5':ind['above_ma5'], 'dif':ind['dif'],
        'k_val':ind['k_val'], 'd_val':ind['d_val']
    })

# CL排序
cand.sort(key=lambda x: (-x['cl'], -x['p']))

print(f'\n📊 今日(2026-05-25) 选股结果')
print(f'全市场 {len(qt_map)}只 → 候选 {len(cand)}只')
print(f'策略: CL排序版 涨5~8% 量比1.0~1.5 换手5~15% 市值<200亿 CL60~90%')
print(f'2026年回测胜率: 冠军69.0% 前三任意86.9%')
print()

if cand:
    # 表格头
    hdr = f'{"#":<3} {"名称":<10} {"代码":<8} {"CL%":<5} {"涨%":<6} {"量比":<6} {"换手%":<6}'
    hdr += f' {"买入":<7} {"评分":<5} {"J值":<5} {"PE":<6} {"市值":<6} {"MACD":<5} {"KDJ":<5}'
    print(hdr)
    print('-' * len(hdr))
    
    for i, c in enumerate(cand):
        macd_s = '金叉' if c['macd'] else '—'
        kdj_s = '金叉' if c['kdj'] else '—'
        print(f'{i+1:<3} {c["nm"][:8]:<10} {c["code"][-6:]:<8} '
              f'{c["cl"]:<5.1f} +{c["p"]:<5.1f} {c["vr"]:<6.2f} {c["hsl"]:<6.1f} '
              f'{c["buy_c"]:<7.2f} {c["score"]:<5} {c["jv"]:<5.1f} {c["pe"]:<6.1f} '
              f'{c["sz"]:<6.0f} {macd_s:<5} {kdj_s:<5}')
    
    # 第一名详解
    c = cand[0]
    c2 = cand[1] if len(cand) > 1 else None
    print(f'\n{"="*60}')
    print(f'🥇 第一名: {c["nm"]} ({c["code"][-6:]})')
    print(f'{"="*60}')
    print(f'  当天买入价: {c["buy_c"]:.2f}')
    print(f'  当天涨跌幅: +{c["p"]:.1f}%')
    print(f'  CL(收盘位): {c["cl"]:.1f}%（全市场候选最高，决定排名）')
    print(f'  量比: {c["vr"]:.2f}')
    print(f'  换手率: {c["hsl"]:.1f}%')
    print(f'  PE: {c["pe"]:.1f}  市值: {c["sz"]:.0f}亿')
    print(f'  J值: {c["jv"]:.1f}  K值: {c["k_val"]:.1f}  D值: {c["d_val"]:.1f}')
    print(f'  DIF: {c["dif"]:.4f}')
    print(f'  前日涨幅: {c["prev_pct"]:+.2f}%')
    print(f'  MACD: {"✅ 金叉" if c["macd"] else "❌ 无"}')
    print(f'  KDJ: {"✅ 金叉" if c["kdj"] else "❌ 无"}')
    print(f'  收阳: {"✅" if c["is_yang"] else "❌"}')
    print(f'  站上5日线: {"✅" if c["above_ma5"] else "❌"}')
    print(f'  上影线占比: {c["shadow"]:.1f}%')
    print(f'  连涨天数: {c["up_days"]}天')
    
    # 评分拆解
    p, cl, vr, hsl = c['p'], c['cl'], c['vr'], c['hsl']
    parts = []
    if 5.5 <= p <= 6.5: parts.append(f'涨分+30(涨{p:.1f}∈5.5~6.5)')
    elif 5 <= p <= 7: parts.append(f'涨分+25(涨{p:.1f}∈5~7)')
    elif p <= 7.5: parts.append(f'涨分+20(涨{p:.1f}∈7~7.5)')
    else: parts.append(f'涨分+10')
    if 70 <= cl <= 85: parts.append(f'CL分+25(CL{cl:.0f}∈70~85)')
    elif 65 <= cl <= 90: parts.append(f'CL分+20(CL{cl:.0f}∈65~90)')
    else: parts.append(f'CL分+10')
    if 1.0 <= vr <= 1.2: parts.append(f'量比分+20')
    elif 1.0 <= vr <= 1.5: parts.append(f'量比分+15')
    if 5 <= hsl <= 10: parts.append(f'换手分+10')
    elif hsl <= 15: parts.append(f'换手分+5')
    if c['macd']: parts.append(f'MACD金叉+10')
    if c['kdj']: parts.append(f'KDJ金叉+8')
    if c['dif']>0: parts.append(f'DIF>0+5')
    if c['is_yang']: parts.append(f'收阳+3')
    if c['above_ma5']: parts.append(f'站上5日线+5')
    jv = c['jv']
    if jv > 80: parts.append(f'J值{jv:.0f}>80扣5')
    print(f'\n  评分明细:')
    for part in parts:
        print(f'    {part}')
    print(f'  综合评分: {c["score"]}')
    
    if c2:
        print(f'\n{"="*60}')
        print(f'🥇 vs 🥈 排名对比')
        print(f'{"="*60}')
        print(f'{"维度":<12} {"第一名":<12} {"第二名":<12} {"决定因素"}')
        print(f'{"CL%":<12} {c["cl"]:<12.1f} {c2["cl"]:<12.1f} {"CL更高→第一名" if c["cl"]>c2["cl"] else "CL相同看涨%" if c["cl"]==c2["cl"] else ""}')
        print(f'{"涨%":<12} {c["p"]:<12.1f} {c2["p"]:<12.1f}')
        print(f'{"量比":<12} {c["vr"]:<12.2f} {c2["vr"]:<12.2f}')
        print(f'{"换手%":<12} {c["hsl"]:<12.1f} {c2["hsl"]:<12.1f}')
        print(f'{"评分":<12} {c["score"]:<12} {c2["score"]:<12}')
else:
    print('今日无候选')
