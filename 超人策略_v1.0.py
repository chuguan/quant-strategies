"""
超人策略 - 完整版：买入价 + 当天涨 + 次日最高/最低
"""
import pickle, os, json, sys

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())

def get_next_day_kline(code, cur_date, next_dates):
    for nd in next_dates:
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        if not os.path.exists(fp): continue
        try:
            with open(fp,'r') as f: k = json.load(f)
        except: continue
        for d in k:
            if d['date'] == nd:
                return d
    return None

date = sys.argv[1] if len(sys.argv) > 1 else dates[-1]
stocks = data.get(date, [])

# 找下一个交易日
next_dates = sorted(d for d in dates if d > date)

cand = []
for s in stocks:
    code, p = s['code'], s['p']
    if p < 5 or p > 8: continue
    if (s.get('vol_ratio',0) or 0) < 1.5: continue
    
    ri = real.get(code)
    if not ri: continue
    hsl = (ri.get('hsl',0) or 0)
    if hsl < 5 or hsl > 15: continue
    sz = (ri.get('shizhi',0) or 0)
    if sz >= 200: continue
    nm = names.get(code,'')
    if 'ST' in nm or '*ST' in nm or '退' in nm: continue
    
    buy_price = s.get('close', 0)
    nf = s.get('n', 0) or 0  # 次日最高涨幅
    nc = s.get('next_close', 0) or 0  # 次日收盘涨幅
    
    # 次日最低价（从K线拿）
    kd = get_next_day_kline(code, date, next_dates)
    nh_price = buy_price * (1 + nf/100) if nf > 0 and buy_price > 0 else 0
    nl_price = kd['low'] if kd else 0
    nl_pct = (nl_price/buy_price - 1) * 100 if nl_price > 0 and buy_price > 0 else 0
    
    # 次日收盘价
    nc_price = kd['close'] if kd else 0
    nc_pct = (nc_price/buy_price - 1) * 100 if nc_price > 0 and buy_price > 0 else 0
    
    # 评分
    sc = 0
    if 7 <= p <= 8: sc += 10
    elif 6 <= p < 7: sc += 8
    elif 5 <= p < 6: sc += 6
    vr = s.get('vol_ratio',0) or 0
    if vr >= 3: sc += 8
    elif vr >= 2: sc += 6
    elif vr >= 1.5: sc += 4
    cl = s.get('cl',0)
    if 70 <= cl <= 85: sc += 5
    elif 85 < cl <= 95: sc += 3
    if 8 <= hsl <= 12: sc += 5
    elif 5 <= hsl < 8: sc += 3
    elif 12 < hsl <= 15: sc += 3
    if sz < 50: sc += 3
    elif sz < 100: sc += 2
    
    cand.append((sc, nm, code, p, vr, cl, hsl, sz, buy_price, 
                 nh_price, nf, nl_price, nl_pct, nc_price, nc_pct))

cand.sort(key=lambda x: (-x[0], -x[3]))

print(f'\n{date}  超人策略')
print(f'条件: 涨5~8% + 量>1.5 + 换5~15% + 市值<200亿 | 候选{len(cand)}只\n')
print(f'{"#":<3} {"名称":<10} {"⬆当天涨%":<9} {"买入价":<8} {"量比":<5} {"收盘位":<5}', end='')
print(f' {"📈次日最高":<10} {"涨幅%":<7} {"📉次日最低":<10} {"跌幅%":<7} {"收盘%":<7} {"评分":<4}')
print('-' * 85)
for i, x in enumerate(cand[:10]):
    nhs = f'{x[9]:.2f}' if x[9] > 0 else 'N/A'
    nf_s = f'{x[10]:.2f}%' if x[10] != 0 else 'N/A'
    nls = f'{x[11]:.2f}' if x[11] > 0 else 'N/A'
    nlp = f'{x[12]:.2f}%' if x[12] != 0 else 'N/A'
    ncp = f'{x[14]:.2f}%' if x[14] != 0 else 'N/A'
    ok = '🔥5%' if x[10] >= 5 else ('✅' if x[10] >= 2.5 else '')
    print(f'{i+1:<3} {x[1][:8]:<10} {x[3]:<+9.1f} {x[8]:<8.2f} {x[4]:<5.2f} {x[5]:<5.0f}', end='')
    print(f' {nhs:<10} {nf_s:<7} {nls:<10} {nlp:<7} {ncp:<7} {x[0]:<4} {ok}')

# 近5日简化版
print(f'\n{"近5日冠军":-^60}')
for dt in ['2026-05-18','2026-05-19','2026-05-20','2026-05-21','2026-05-22']:
    nd = sorted(d for d in dates if d > dt)
    c2 = []
    for s in data.get(dt, []):
        code, p = s['code'], s['p']
        if p < 5 or p > 8: continue
        if (s.get('vol_ratio',0) or 0) < 1.5: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > 15: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= 200: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        bp = s.get('close',0)
        nf = s.get('n',0) or 0
        kd = get_next_day_kline(code, dt, nd)
        nl = kd['low'] if kd else 0
        nlpct = (nl/bp - 1)*100 if nl and bp else 0
        nh = kd['high'] if kd else 0
        nhlpct = (nh/bp - 1)*100 if nh and bp else 0
        c2.append((nm, p, bp, nhlpct, nlpct, nf))
    
    c2.sort(key=lambda x:-x[3])
    if c2:
        x = c2[0]
        nfs = f'{x[5]:.2f}%' if x[5] != 0 else 'N/A'
        nhl = f'{x[3]:+.2f}%' 
        nll = f'{x[4]:+.2f}%'
        print(f'{dt}: 冠军{x[0]} 买{x[2]:.2f} 当天涨{x[1]:+.1f}% 次日最高{x[3]:+.2f}% 最低{x[4]:+.2f}%')
    else:
        print(f'{dt}: 无候选')
