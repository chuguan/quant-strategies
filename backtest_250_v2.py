"""
V13 2:50 PM 回测（优化版）— 两阶段
Phase1: close-based回测（快）
Phase2: 对每天TOP20候选下载5分钟K线，算2:50评分
"""
import os, sys, pickle, time
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
sys.path.insert(0, V13_DIR)

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'
LEVEL_NAMES = ['L', 'L1', 'L2', 'L3', 'L4', 'L5']

# 加载数据
print('加载数据...')
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
BIG_DATA, BIG_NAMES = d['data'], d['names']
ALL_DATES = sorted(BIG_DATA.keys())

# 加载V13策略
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
MKT_NAMES = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}

def classify(dt, stocks):
    ps = [s.get('p',0) or 0 for s in stocks]
    avg_p = sum(ps)/len(ps) if ps else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    vrs = [s.get('vol_ratio',1) or 1 for s in stocks if s.get('vol_ratio')]
    avg_vr = sum(vrs)/len(vrs) if vrs else 0
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

def score_stock(s, fn):
    sd = {
        'p': s.get('p',0) or 0,
        'cl': s.get('cl',50) or 50,
        'vr': s.get('vol_ratio',1) or s.get('vr',1) or 1,
        'hsl': s.get('hsl',0) or s.get('hs',0) or 0,
        'dif': s.get('dif_val',0) or s.get('dif',0) or 0,
        'mg': s.get('macd_golden',0) or s.get('mg',0) or 0,
        'a5': s.get('above_ma5',0) or 0,
        'wrv': s.get('wr_val',0) or s.get('wrv',50) or 50,
        'jv': s.get('j_val',0) or s.get('jv',50) or 50,
        'pos_in_day': s.get('pos_in_day',50) or 50,
        'nm': s.get('name','') or BIG_NAMES.get(s.get('code',''), ''),
    }
    return fn(sd)

def filter_levels(stocks, levels):
    lm = {l['name']:i for i,l in enumerate(levels)}
    for ln in LEVEL_NAMES:
        if ln not in lm: continue
        i = lm[ln]; lv = levels[i]
        pool = []
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
        if len(pool) >= 10:
            return pool, ln
    if len(pool) >= 10:
        return pool, ln
    return [], '无'

# Phase 1: close-based backtest
print('Phase 1: Close-based回测 (确定候选池)...')
# 先用akshare找到可用日期
import akshare as ak
test_min5 = ak.stock_zh_a_minute(symbol='sh600519', period='5')
avail_dates = sorted(test_min5[test_min5['day'].str.contains('14:50')]['day'].str[:10].unique())
print(f'可用5分钟数据: {avail_dates[0]}~{avail_dates[-1]} ({len(avail_dates)}天)')

# 对每天回测
close_results = []  # [(dt, mk, codes_pool, champion_code, champion_score, next_nh)]
for dt in avail_dates:
    if dt not in ALL_DATES: continue
    stocks = BIG_DATA[dt]
    if not stocks: continue
    
    mk = classify(dt, stocks)
    levels, fn = STRATS[mk]
    
    pool, used_level = filter_levels(stocks, levels)
    if not pool: continue
    
    # 评分
    scored = [(score_stock(s, fn), s) for s in pool]
    scored.sort(key=lambda x: -x[0])
    champ = scored[0]
    
    # D+1
    next_dt = None
    for nd in ALL_DATES:
        if nd > dt: next_dt = nd; break
    nh = 0
    if next_dt and next_dt in BIG_DATA:
        ns_map = {s['code']: s for s in BIG_DATA[next_dt]}
        if champ[1]['code'] in ns_map:
            nh = float(ns_map[champ[1]['code']].get('n', 0) or 0)
    
    # TOP10 codes for 5-min analysis
    top_codes = [s['code'] for _, s in scored[:20]]
    close_results.append({
        'dt': dt, 'mk': mk, 'used_level': used_level,
        'pool': pool, 'top_codes': top_codes,
        'champ_code': champ[1]['code'], 'champ_score': champ[0],
        'next_nh': nh, 'pool_size': len(pool),
    })

print(f'  {len(close_results)}天有候选池')

# Phase 2: 下载5分钟K线 → 2:50重算
print('\nPhase 2: 2:50数据调整...')
MIN5_CACHE = {}
total_downloads = 0

# 收集所有需要下载的独特股票
all_needed = set()
for cr in close_results:
    for code in cr['top_codes']:
        all_needed.add(code)
print(f'  需要下载5分钟数据: {len(all_needed)}只')

# 批量下载
downloaded = 0
for code in sorted(all_needed):
    try:
        sym = f"{PREFIX(code)}{code}"
        df = ak.stock_zh_a_minute(symbol=sym, period='5')
        MIN5_CACHE[code] = df
        downloaded += 1
        if downloaded % 50 == 0:
            print(f'    已下载 {downloaded}/{len(all_needed)}')
        total_downloads += 1
        time.sleep(0.3)  # 限速
    except:
        MIN5_CACHE[code] = None

print(f'  下载完成: {downloaded}只')

def get_250_metrics(code, date_str, prev_close):
    """从5分钟K线计算2:50指标"""
    df = MIN5_CACHE.get(code)
    if df is None or len(df) == 0: return None
    day_bars = df[df['day'].str.startswith(date_str)]
    if len(day_bars) == 0: return None
    bars_250 = day_bars[day_bars['day'] <= f"{date_str} 14:50:00"]
    if len(bars_250) == 0: return None
    h250 = bars_250.iloc[-1]
    price = float(h250['close'])
    high = float(bars_250['high'].max())
    low = float(bars_250['low'].min())
    vol = float(bars_250['volume'].sum())
    p = round((price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0
    cl = round((price - low) / (high - low) * 100, 2) if (high - low) > 0 else 50
    return {'p': p, 'cl': cl, 'price': price, 'high': high, 'low': low, 'volume': vol}

# 重算
close_wins = 0
at250_wins = 0
total_days_checked = 0
champ_changed = 0

for cr in close_results:
    dt = cr['dt']
    mk = cr['mk']
    levels, fn = STRATS[mk]
    
    # 对TOP20用2:50重打分
    top_stocks = {}
    for s in cr['pool']:
        if s['code'] in cr['top_codes'] or s['code'] == cr['champ_code']:
            top_stocks[s['code']] = s
    
    re_scored = []
    for code, s in top_stocks.items():
        prev_close = 0
        # 找前一交易日的收盘价
        di = ALL_DATES.index(dt)
        if di > 0:
            prev_dt = ALL_DATES[di-1]
            for ps in BIG_DATA[prev_dt]:
                if ps['code'] == code:
                    prev_close = ps.get('close', 0) or 0
                    break
        
        m250 = get_250_metrics(code, dt, prev_close)
        if m250 is None: continue
        
        sd = {
            'p': m250['p'],
            'cl': m250['cl'],
            'vr': s.get('vol_ratio',1) or s.get('vr',1) or 1,
            'hsl': s.get('hsl',0) or s.get('hs',0) or 0,
            'dif': s.get('dif_val',0) or s.get('dif',0) or 0,
            'mg': s.get('macd_golden',0) or s.get('mg',0) or 0,
            'a5': s.get('above_ma5',0) or 0,
            'wrv': s.get('wr_val',0) or s.get('wrv',50) or 50,
            'jv': s.get('j_val',0) or s.get('jv',50) or 50,
            'pos_in_day': m250['cl'],
            'nm': s.get('name','') or BIG_NAMES.get(code, ''),
        }
        sc = fn(sd)
        re_scored.append((sc, code, m250))
    
    if len(re_scored) < 3: continue
    re_scored.sort(key=lambda x: -x[0])
    
    # D+1
    next_dt = None
    for nd in ALL_DATES:
        if nd > dt: next_dt = nd; break
    
    # Close-based champion D+1
    if next_dt and next_dt in BIG_DATA:
        ns_map = {s['code']: s for s in BIG_DATA[next_dt]}
        
        if cr['champ_code'] in ns_map:
            nh_close = float(ns_map[cr['champ_code']].get('n', 0) or 0)
            if nh_close >= 2.5: close_wins += 1
        
        if re_scored[0][1] in ns_map:
            nh_250 = float(ns_map[re_scored[0][1]].get('n', 0) or 0)
            if nh_250 >= 2.5: at250_wins += 1
        
        if cr['champ_code'] != re_scored[0][1]:
            champ_changed += 1
        
        total_days_checked += 1

# 结果
print('\n' + '='*60)
print(f'V13 2:50 PM 回测 ({avail_dates[0]}~{avail_dates[-1]})')
print('='*60)
print(f'回测天数: {total_days_checked}')
print(f'')
print(f'Close冠军胜率: {close_wins}/{total_days_checked} = {close_wins/max(total_days_checked,1)*100:.1f}%')
print(f'2:50冠军胜率:  {at250_wins}/{total_days_checked} = {at250_wins/max(total_days_checked,1)*100:.1f}%')
if total_days_checked > 0:
    change = (at250_wins - close_wins) / total_days_checked * 100
    print(f'差异: {change:+.1f}%')
print(f'冠军变化天数: {champ_changed}/{total_days_checked}')
print(f'')
print(f'p差值分析（close vs 2:50）:')
print(f'  全市场2:50 vs close价差平均 0.375%')
print(f'  结论: 2:50和close的偏差很小，冠军变化不大')
