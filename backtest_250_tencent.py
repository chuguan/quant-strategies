"""
V13 2:50真实回测 — 腾讯5分钟数据（11天真实2:50）
"""
import os, sys, pickle, subprocess, json, time
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
sys.path.insert(0, V13_DIR)

print('加载数据...')
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
BIG_DATA, BIG_NAMES = d['data'], d['names']
ALL_DATES = sorted(BIG_DATA.keys())

import importlib
def load_strat(mk):
    info = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}[mk]
    spec = importlib.util.spec_from_file_location('s',
        os.path.join(V13_DIR,'评分策略',f'分而治之_V10_{info}_评分策略.py'))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    lvs = mod.LEVELS
    renamed = []
    for lv in lvs:
        renamed.append({**lv, 'name': 'L' if lv['name']=='L0' else lv['name']})
    last = lvs[-1]
    renamed.append({"name":"L5","p_min":last["p_min"]-3,"p_max":last["p_max"],
        "vr_min":max(0.1,last["vr_min"]-0.2),"vr_max":last["vr_max"]+2,
        "hs_min":max(0.1,last["hs_min"]-1),"hs_max":last["hs_max"]+15,
        "sz_max":last["sz_max"]+200,"cl_min":max(0,last["cl_min"]-15),"cl_max":100})
    return renamed, mod.score
STRATS = {k: load_strat(k) for k in ['real_up','fake_up','down','flat']}
LEVEL_NAMES = ['L', 'L1', 'L2', 'L3', 'L4', 'L5']
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

def classify(dt, stocks):
    ps = [s.get('p',0) or 0 for s in stocks]
    avg_p = sum(ps)/len(ps) if ps else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    vrs = [s.get('vol_ratio',1) or 1 for s in stocks if s.get('vol_ratio')]
    avg_vr = sum(vrs)/len(vrs) if vrs else 0
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

def filter_pool(stocks, levels):
    lm = {l['name']:i for i,l in enumerate(levels)}
    for ln in LEVEL_NAMES:
        if ln not in lm: continue
        i = lm[ln]; lv = levels[i]; pool = []
        for s in stocks:
            p = s.get('p',0) or 0
            if p < lv['p_min'] or p > min(lv.get('p_max',10),8): continue
            vr = s.get('vol_ratio',0) or s.get('vr',0) or 0
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            nm = s.get('name','') or BIG_NAMES.get(s['code'],'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl = s.get('cl',0) or 50
            if cl < lv.get('cl_min',0) or cl > lv.get('cl_max',100): continue
            pool.append(s)
        if len(pool) >= 10: return pool, ln
    return pool if len(pool)>=10 else [], '无'

# Tencent 5分钟数据
MIN5_CACHE = {}
def get_min5(code):
    if code in MIN5_CACHE:
        return MIN5_CACHE[code]
    pref = PREFIX(code)
    url = f"http://ifzq.gtimg.cn/appstock/app/kline/mkline?param={pref}{code},m5,,,500"
    try:
        r = subprocess.run(['curl','-sL','--max-time','10',url,
            '-H','User-Agent: Mozilla/5.0'], capture_output=True, timeout=15)
        d = json.loads(r.stdout)
        m5 = d.get('data',{}).get(f'{pref}{code}',{}).get('m5',[])
        MIN5_CACHE[code] = m5
        return m5
    except:
        MIN5_CACHE[code] = []
        return []

def extract_250(m5, date_str):
    """从5分钟数据提取2:50指标"""
    date8 = date_str.replace('-', '')
    # 所有当天的bars
    day_bars = [x for x in m5 if x[0].startswith(date8)]
    if len(day_bars) < 5: return None
    # 到14:50为止
    bars = [x for x in day_bars if x[0][:10] <= f"{date8}1455"]
    if len(bars) < 3: return None
    h250 = bars[-1]  # 14:50 bar
    prices = [float(x[3]) for x in bars]  # high
    lows = [float(x[4]) for x in bars]    # low
    vols = [float(x[5]) for x in bars]    # volume
    return {
        'price': float(h250[2]),  # close of 14:50 bar
        'high': max(prices) if prices else 0,
        'low': min(lows) if lows else 0,
        'vol': sum(vols) if vols else 0,
    }

# 可用日期
test_m5 = get_min5('600519')
avail_raw = sorted(set(x[0][:8] for x in test_m5 if x[0].endswith('1455')))
avail_dates = [f"{d[:4]}-{d[4:6]}-{d[6:8]}" for d in avail_raw]
print(f'可用2:50天数: {len(avail_dates)}')
print(f'日期: {avail_dates[0]}~{avail_dates[-1]}')

bt_dates = [d for d in avail_dates if d in ALL_DATES]
print(f'回测: {len(bt_dates)}天')

# ===== 主回测 =====
close_wins = 0; q250_wins = 0; close_t = 0; q250_t = 0
champ_same = 0; champ_diff = 0
details = []

for idx, dt in enumerate(bt_dates):
    stocks = BIG_DATA.get(dt, [])
    if not stocks: continue
    mk = classify(dt, stocks)
    levels, fn = STRATS[mk]
    pool, lvl = filter_pool(stocks, levels)
    if not pool: continue
    
    # D+1
    di = ALL_DATES.index(dt)
    next_dt = ALL_DATES[di+1] if di < len(ALL_DATES)-1 else None
    if not next_dt: continue
    next_map = {s['code']: s for s in BIG_DATA.get(next_dt, [])}
    
    # 前一天close
    prev_map = {}
    if di > 0:
        for s in BIG_DATA[ALL_DATES[di-1]]:
            prev_map[s['code']] = s.get('close', 0) or 0
    
    # Close评分
    sc_close = [(fn({
        'p': s.get('p',0) or 0,
        'cl': s.get('cl',50) or 50,
        'vr': s.get('vol_ratio',1) or s.get('vr',1) or 1,
        'dif': s.get('dif_val',0) or s.get('dif',0) or 0,
        'wrv': s.get('wr_val',0) or s.get('wrv',50) or 50,
        'jv': s.get('j_val',0) or s.get('jv',50) or 50,
        'pos_in_day': s.get('pos_in_day',50) or 50,
        'nm': s.get('name','') or BIG_NAMES.get(s['code'], '')
    }), s['code']) for s in pool]
    sc_close.sort(key=lambda x: -x[0])
    
    # 2:50评分 — 对候选股下载5分钟数据
    sc_250 = []
    for _, code in sc_close[:30]:
        m5 = get_min5(code)
        if not m5: continue
        m = extract_250(m5, dt)
        if m is None: continue
        prev_c = prev_map.get(code, 0)
        p_250 = round((m['price'] - prev_c) / prev_c * 100, 2) if prev_c > 0 else 0
        cl_250 = round((m['price'] - m['low']) / (m['high'] - m['low']) * 100, 2) \
            if (m['high'] - m['low']) > 0 else 50
        
        s = next((ss for ss in pool if ss['code'] == code), None)
        if not s: continue
        
        sd2 = {'p': p_250, 'cl': cl_250,
               'vr': s.get('vol_ratio',1) or s.get('vr',1) or 1,
               'dif': s.get('dif_val',0) or s.get('dif',0) or 0,
               'wrv': s.get('wr_val',0) or s.get('wrv',50) or 50,
               'jv': s.get('j_val',0) or s.get('jv',50) or 50,
               'pos_in_day': cl_250,
               'nm': s.get('name','') or BIG_NAMES.get(code, '')}
        sc_250.append((fn(sd2), code))
    
    if len(sc_250) < 3: continue
    sc_250.sort(key=lambda x: -x[0])
    
    # 统计
    champ_c = sc_close[0][1]
    champ_250 = sc_250[0][1]
    nh_c = float(next_map.get(champ_c, {}).get('n',0) or 0) if champ_c in next_map else -99
    nh_250 = float(next_map.get(champ_250, {}).get('n',0) or 0) if champ_250 in next_map else -99
    
    if nh_c >= 2.5: close_wins += 1; close_t += 1
    else: close_t += 1
    if nh_250 >= 2.5: q250_wins += 1; q250_t += 1
    else: q250_t += 1
    if champ_c == champ_250: champ_same += 1
    else: champ_diff += 1
    
    mk_disp = {'real_up':'涨日','fake_up':'虚涨','down':'跌日','flat':'横盘'}.get(mk, mk)
    same = '✅' if champ_c == champ_250 else '❌'
    details.append(f'{dt} | {mk_disp:>4} | {len(pool):>3}只 | close={champ_c}({nh_c:+.1f}%) | 2:50={champ_250}({nh_250:+.1f}%) | {same}')

# 结果
print(f'\n缓存了{len(MIN5_CACHE)}只股票的5分钟数据')
print()
print('='*65)
print(f'V13 2:50真实回测（腾讯5分钟数据）')
print('='*65)
print(f'📊 Close冠军胜率:      {close_wins}/{close_t} = {close_wins/max(close_t,1)*100:.1f}%')
print(f'📊 2:50真实冠军胜率:    {q250_wins}/{q250_t} = {q250_wins/max(q250_t,1)*100:.1f}%')
delta = (q250_wins/max(q250_t,1) - close_wins/max(close_t,1)) * 100
print(f'   差异: {delta:+.1f}%')
print(f'🏆 冠军一致性: {champ_same}/{champ_same+champ_diff} = {champ_same/max(champ_same+champ_diff,1)*100:.0f}%')
print()
print('📋 逐日明细:')
for r in details:
    print(f'  {r}')
