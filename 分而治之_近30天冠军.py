"""分而治之 V5 近30天冠军验证"""
import pickle, os, sys, json, importlib
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
IDX_FILE = os.path.join(SCRIPTS_DIR, '分而治之_日期索引.pkl')
sys.path.insert(0, SCRIPTS_DIR)

with open(IDX_FILE, 'rb') as f: di = pickle.load(f)
daily = di['daily']; kline = di['kline']

strat_names = {'real_up': '分而治之_真实涨日_评分策略', 'fake_up': '分而治之_虚涨日_评分策略',
               'down': '分而治之_跌日_评分策略', 'flat': '分而治之_横盘_评分策略'}
score_fn_names = {'real_up': '真实涨日_评分', 'fake_up': '虚涨日_评分',
                  'down': '跌日_评分', 'flat': '横盘_评分'}
mkt_names = {'real_up': '涨', 'fake_up': '虚涨', 'down': '跌', 'flat': '横'}
mkt_emoji = {'real_up': '📈', 'fake_up': '🎭', 'down': '📉', 'flat': '➡️'}

def get_nd_high(code, dt, kline):
    kd = kline.get(code)
    if not kd: return None
    d8 = dt.replace('-', '')
    ads = sorted([d for d in kd.keys() if len(d) == 8 and d.isdigit()])
    try: idx = ads.index(d8)
    except: return None
    if idx + 1 >= len(ads): return None
    bc = kd.get(d8, {}).get('c', 0)
    if bc <= 0: return None
    return round((kd[ads[idx+1]]['h'] / bc - 1) * 100, 2)

def get_nd_close(code, dt, kline):
    kd = kline.get(code)
    if not kd: return None
    d8 = dt.replace('-', '')
    ads = sorted([d for d in kd.keys() if len(d) == 8 and d.isdigit()])
    try: idx = ads.index(d8)
    except: return None
    if idx + 1 >= len(ads): return None
    bc = kd.get(d8, {}).get('c', 0)
    if bc <= 0: return None
    return round((kd[ads[idx+1]]['c'] / bc - 1) * 100, 2)

def classify(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) for s in stocks]; vrs = [s.get('vr', 0) for s in stocks if s.get('vr', 0)]
    if not ps: return 'flat'
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

def prepare(s):
    return {
        'p': s.get('p',0) or 0, 'cl': s.get('cl',0) or 0,
        'vr': s.get('vr',0) or 0, 'hsl': s.get('hs',0) or 0,
        'dif': s.get('dif_val',0) or 0, 'mg': s.get('macd_golden',0) or 0,
        'a5': s.get('above_ma5',0) or 0, 'wrv': s.get('wr',50) or 50,
        'jv': s.get('j_val',50) or 50, 'kv': s.get('k_val',50) or 50,
        'dv': s.get('d_val',50) or 50, 'kdj_g': s.get('kdj_golden',0) or 0,
        'buy_c': s.get('close',0) or 0,
    }

dates = sorted([d for d in daily.keys() if '2025-01-01' <= d <= '2026-06-01'])[-30:]
print(f"📊 近30天冠军验证 ({dates[0]} ~ {dates[-1]})\n")

all_wins = 0; all_total = 0
regime_stats = {}

for dt in dates:
    stocks = [s for s in daily.get(dt, []) if abs(s.get('p',0) or 0) < 9.98]
    if not stocks:
        print(f"  {dt} ❌ 无数据")
        continue
    
    mkt = classify(stocks)
    mod = importlib.import_module(strat_names[mkt])
    importlib.reload(mod)
    levels = getattr(mod, 'LEVELS')
    score_fn = getattr(mod, score_fn_names[mkt])
    
    # 分级筛选
    pool = None
    used_lv = '-'
    for lv in levels:
        pool = []
        for s in stocks:
            p = s.get('p',0) or 0
            if p < lv.get('p_min',-10) or p > lv.get('p_max',8): continue
            if p >= 8: continue
            vr = s.get('vr',0) or 0
            if vr < lv.get('vr_min',0.1) or vr > lv.get('vr_max',10): continue
            cl = s.get('cl',0) or 0
            if cl < lv.get('cl_min',0) or cl > lv.get('cl_max',100): continue
            pool.append(s)
        if len(pool) > 8:
            used_lv = lv.get('name','L')
            break
        pool = None
    
    if not pool or len(pool) <= 8:
        print(f"  {dt} {mkt_emoji[mkt]} {mkt_names[mkt]} ❌ 候选不足({len(pool) if pool else 0}只)")
        continue
    
    scored = []
    for s in pool:
        sd = prepare(s)
        sc = score_fn(sd)
        nh = get_nd_high(s['code'], dt, kline)
        scored.append({'sc':sc, 'code':s['code'], 'nh':nh, 'nm':s.get('nm','?'), 'p':s.get('p',0)})
    
    scored.sort(key=lambda x: -x['sc'])
    champ = scored[0]
    nh = champ['nh']
    win = '✅' if nh is not None and nh >= 2.5 else ('❌' if nh is not None else '🟡')
    
    all_total += 1
    if nh is not None and nh >= 2.5: all_wins += 1
    
    regime_stats.setdefault(mkt, {'w':0,'t':0})
    regime_stats[mkt]['t'] += 1
    if nh is not None and nh >= 2.5: regime_stats[mkt]['w'] += 1
    
    print(f"  {dt} {mkt_emoji[mkt]}{mkt_names[mkt]} L{used_lv} | 🥇 {champ['nm']}({champ['code']}) p={champ['p']:.1f}% 次日最高={nh if nh else '—'}% {win}")

print(f"\n{'='*50}")
print(f"🏆 近30天总胜率: {all_wins}/{all_total} = {round(all_wins*100/all_total,1)}%")
print(f"\n📊 分行情:")
for reg in ['real_up','fake_up','down','flat']:
    s = regime_stats.get(reg, {'w':0,'t':0})
    rate = round(s['w']*100/s['t'],1) if s['t'] else 0
    print(f"  {mkt_emoji[reg]} {mkt_names[reg]}: {s['w']}/{s['t']} = {rate}%")
