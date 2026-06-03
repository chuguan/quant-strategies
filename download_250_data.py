"""
下载近30天2:50 PM真实数据 — 使用AkShare 5分钟K线
对每个交易日候选股提取：
  - price_2:50 = 14:50 bar收盘价
  - high_2:50, low_2:50 = 截至14:50的当日最高最低
  - p_2:50 = (price_2:50 - prev_close) / prev_close
  - cl_2:50 = (price_2:50 - low_2:50) / (high_2:50 - low_2:50)
  - vol_2:50 = 截至14:50的累计量
输出: 2:50数据字典 + 回测对比
"""
import os, sys, pickle, time
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
sys.path.insert(0, V13_DIR)
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

# 加载big_cache
print('加载缓存...')
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
BIG_DATA, BIG_NAMES = d['data'], d['names']
ALL_DATES = sorted(BIG_DATA.keys())

# 加载策略
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

def filter_close(stocks, levels):
    """用close数据筛选候选股"""
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

# ===== Phase 1: 确定候选股 =====
print('\nPhase 1: 确认候选股...')
# 用akshare找到可用日期
import akshare as ak
test_5 = ak.stock_zh_a_minute(symbol='sh600519', period='5')
avail_dates = sorted(set(test_5[test_5['day'].str.contains('14:50')]['day'].str[:10].unique()))
print(f'可用5分钟日期: {avail_dates[0]}~{avail_dates[-1]} ({len(avail_dates)}天)')

# 最近30天（或全部可用）
bt_dates = [d for d in avail_dates if d in ALL_DATES][-30:]
print(f'将回测: {bt_dates[0]}~{bt_dates[-1]} ({len(bt_dates)}天)')

# 每天候选股
daily_candidates = {}  # {date: [codes]}
unique_codes = set()

for dt in bt_dates:
    stocks = BIG_DATA.get(dt, [])
    if not stocks: continue
    mk = classify(dt, stocks)
    levels, _ = STRATS[mk]
    pool, lvl = filter_close(stocks, levels)
    if pool:
        daily_candidates[dt] = {
            'mk': mk, 'codes': [s['code'] for s in pool],
            'level': lvl, 'pool': pool
        }
        for s in pool:
            unique_codes.add(s['code'])

print(f'候选股总数: {len(unique_codes)}只')

# ===== Phase 2: 下载5分钟数据 =====
print(f'\nPhase 2: 下载 {len(unique_codes)} 只股票5分钟数据...')
MIN5_CACHE = {}
downloaded = 0
failed = 0

for i, code in enumerate(sorted(unique_codes)):
    sym = f"{PREFIX(code)}{code}"
    try:
        df = ak.stock_zh_a_minute(symbol=sym, period='5')
        MIN5_CACHE[code] = df
        downloaded += 1
        if (i+1) % 50 == 0:
            print(f'  [{i+1}/{len(unique_codes)}] 已下载{downloaded}只')
    except Exception as e:
        MIN5_CACHE[code] = None
        failed += 1
    time.sleep(0.25)

print(f'下载完成: {downloaded}只成功, {failed}只失败')

# ===== Phase 3: 提取2:50数据 =====
print('\nPhase 3: 提取2:50指标...')

def get_250(df, date_str):
    """从5分钟df提取2:50指标"""
    day_bars = df[df['day'].str.startswith(date_str)]
    if len(day_bars) == 0: return None
    bars = day_bars[day_bars['day'] <= f"{date_str} 14:50:00"]
    if len(bars) < 3: return None
    h250 = bars.iloc[-1]
    price = float(h250['close'])
    high = float(bars['high'].max())
    low = float(bars['low'].min())
    vol = float(bars['volume'].sum())
    open_p = float(day_bars.iloc[0]['open'])
    return {'price_250': price, 'high_250': high, 'low_250': low,
            'vol_250': vol, 'open': open_p}

# 存储2:50数据
result = {}  # {date: {code: {p_250, cl_250, ...}}}

for dt, info in daily_candidates.items():
    # 前一天的收盘价
    di = ALL_DATES.index(dt)
    prev_close_map = {}
    if di > 0:
        prev_dt = ALL_DATES[di-1]
        for s in BIG_DATA[prev_dt]:
            prev_close_map[s['code']] = s.get('close', 0) or 0
    
    day_250 = {}
    for code in info['codes']:
        df = MIN5_CACHE.get(code)
        if df is None: continue
        
        m5 = get_250(df, dt)
        if m5 is None: continue
        
        prev_c = prev_close_map.get(code, 0)
        p_250 = round((m5['price_250'] - prev_c) / prev_c * 100, 2) if prev_c > 0 else 0
        cl_250 = round((m5['price_250'] - m5['low_250']) / (m5['high_250'] - m5['low_250']) * 100, 2) \
            if (m5['high_250'] - m5['low_250']) > 0 else 50
        
        day_250[code] = {
            'p_250': p_250,
            'cl_250': cl_250,
            'price_250': m5['price_250'],
            'high_250': m5['high_250'],
            'low_250': m5['low_250'],
            'vol_250': m5['vol_250'],
        }
    
    result[dt] = day_250
    if len(day_250) > 0:
        pass  # 有数据

print(f'总数据: {sum(len(v) for v in result.values())}条/天')

# ===== Phase 4: 2:50回测对比 =====
print('\nPhase 4: 2:50回测对比...')

close_wins = 0
q250_wins = 0
close_total = 0
q250_total = 0
champ_same = 0
champ_diff = 0
all_stats = []  # 逐日明细

for dt in bt_dates:
    if dt not in daily_candidates or dt not in result: continue
    info = daily_candidates[dt]
    mk = info['mk']
    _, fn = STRATS[mk]
    pool = info['pool']
    codes_set = set(info['codes'])
    
    # 用2:50数据重算评分
    r250 = result.get(dt, {})
    scored_close = []
    scored_250 = []
    
    for s in pool:
        code = s['code']
        # close评分
        sd = {
            'p': s.get('p',0) or 0,
            'cl': s.get('cl',50) or 50,
            'vr': s.get('vol_ratio',1) or s.get('vr',1) or 1,
            'dif': s.get('dif_val',0) or s.get('dif',0) or 0,
            'wrv': s.get('wr_val',0) or s.get('wrv',50) or 50,
            'jv': s.get('j_val',0) or s.get('jv',50) or 50,
            'pos_in_day': s.get('pos_in_day',50) or 50,
            'nm': s.get('name','') or BIG_NAMES.get(code, ''),
        }
        scored_close.append((fn(sd), s['code'], s))
        
        # 2:50评分
        if code in r250:
            m = r250[code]
            sd2 = dict(sd)
            sd2['p'] = m['p_250']
            sd2['cl'] = m['cl_250']
            sd2['pos_in_day'] = m['cl_250']
            scored_250.append((fn(sd2), code))
    
    if len(scored_250) < 3: continue
    scored_close.sort(key=lambda x: -x[0])
    scored_250.sort(key=lambda x: -x[0])
    
    # D+1
    di = ALL_DATES.index(dt)
    next_dt = ALL_DATES[di+1] if di < len(ALL_DATES)-1 else None
    if not next_dt: continue
    next_map = {s['code']: s for s in BIG_DATA.get(next_dt, [])}
    
    # Close冠军
    champ_c = scored_close[0][1]
    nh_c = float(next_map.get(champ_c, {}).get('n', 0) or 0) if champ_c in next_map else -999
    if nh_c >= 2.5: close_wins += 1
    close_total += 1
    
    # 2:50冠军
    champ_250 = scored_250[0][1]
    nh_250 = float(next_map.get(champ_250, {}).get('n', 0) or 0) if champ_250 in next_map else -999
    if nh_250 >= 2.5: q250_wins += 1
    q250_total += 1
    
    if champ_c == champ_250: champ_same += 1
    else: champ_diff += 1
    
    all_stats.append({
        'date': dt, 'mk': mk, 'pool': len(pool),
        'close_champ': champ_c, 'close_nh': nh_c,
        'q250_champ': champ_250, 'q250_nh': nh_250,
        'same': champ_c == champ_250,
    })

# 结果
print('\n' + '='*65)
print(f'V13 2:50真实回测 ({bt_dates[0]}~{bt_dates[-1]})')
print('='*65)
print(f'\n📊 Close冠军胜率:      {close_wins}/{close_total} = {close_wins/max(close_total,1)*100:.1f}%')
print(f'📊 2:50真实冠军胜率:    {q250_wins}/{q250_total} = {q250_wins/max(q250_total,1)*100:.1f}%')
delta = (q250_wins/max(q250_total,1) - close_wins/max(close_total,1)) * 100
print(f'   差异: {delta:+.1f}%')
print(f'\n🏆 冠军一致性: {champ_same}/{champ_same+champ_diff} = {champ_same/max(champ_same+champ_diff,1)*100:.0f}%')

# 存储2:50数据
output = os.path.join(CACHE_DIR, 'data_250.pkl')
with open(output, 'wb') as f:
    pickle.dump({'result': result, 'stats': all_stats, 'dates': bt_dates}, f)
print(f'\n✅ 2:50数据已保存到: {output}')

# 逐日明细
print(f'\n📋 逐日明细:')
print(f'{"日期":>10} {"行情":>8} {"候选":>4} {"Close冠军":>10} {"C_NH":>5} {"2:50冠军":>10} {"2_NH":>5} {"一致":>4}')
for row in all_stats:
    same = '✅' if row['same'] else '❌'
    mk_disp = {'real_up':'涨日','fake_up':'虚涨','down':'跌日','flat':'横盘'}.get(row['mk'], row['mk'])
    print(f'{row["date"]:>10} {mk_disp:>8} {row["pool"]:>4} {row["close_champ"]:>10} {row["close_nh"]:>+5.1f}% {row["q250_champ"]:>10} {row["q250_nh"]:>+5.1f}% {same:>4}')
