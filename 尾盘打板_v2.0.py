"""
小猪策略 尾盘打板 v2.0
评分公式：涨跌幅×1 + ATR×1.5 + DIF×0.5 + 收盘位×0.02 - 上影(位<60)-3 + 连涨≥3天+1
硬过滤：M1(价/阳/MA5/量比/换手/PE/市值) + 排除ST
"""
import os, pickle, json, time, sys
from datetime import datetime

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
BIG_CACHE = 'big_cache.pkl'

# 加载数据
with open(BIG_CACHE, 'rb') as f:
    cache = pickle.load(f)
names = cache['names']
real = cache['real']
data = cache['data']
dates = sorted(data.keys())
di = {d: i for i, d in enumerate(dates)}
last_date = dates[-1]

kline_cache = {}

def load_kline_recent(code, cur_date):
    key = f'kl_{code}_{cur_date[:7]}'
    if key in kline_cache:
        return kline_cache[key]
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp):
        return None
    try:
        with open(fp, 'r') as f:
            kdata = json.load(f)
    except:
        return None
    idx = next((i for i, d in enumerate(kdata) if d['date'] == cur_date), -1)
    if idx < 0:
        return None
    result = kdata[max(0, idx - 80):idx + 1]
    kline_cache[key] = result
    return result

def m1_filter(s, ri):
    if not ri:
        return False
    p = s.get('p', -999)
    if p < 1 or p > 8:
        return False
    if s.get('is_yang', 0) != 1:
        return False
    if s.get('above_ma5', 0) != 1:
        return False
    if (s.get('vol_ratio', 0) or 0) <= 1:
        return False
    hsl = ri.get('hsl', 0) or 0
    if hsl < 3 or hsl > 15:
        return False
    pe = ri.get('pe', 0) or 0
    if pe <= 0:
        return False
    sz = ri.get('shizhi', 0) or 0
    if sz >= 200:
        return False
    name = names.get(s['code'], '')
    if 'ST' in name or '*ST' in name or '退' in name:
        return False
    return True

def get_prev_gain(code, cur_date):
    idx = di.get(cur_date)
    if idx is None or idx == 0:
        return None
    prev_date = dates[idx - 1]
    for s in data.get(prev_date, []):
        if s['code'] == code:
            return s['p']
    recent = load_kline_recent(code, cur_date)
    if not recent:
        return None
    for i, d in enumerate(recent):
        if d['date'] == prev_date and i > 0:
            return (d['close'] / recent[i - 1]['close'] - 1) * 100
    return None

def get_gains(code, cur_date):
    """计算连续小涨天数（每日涨0~4%为碎阳）"""
    recent = load_kline_recent(code, cur_date)
    if not recent or len(recent) < 10:
        return 0
    idx = len(recent) - 1
    gains = 0
    for j in range(idx, max(1, idx - 12), -1):
        pg = (recent[j]['close'] / recent[j - 1]['close'] - 1) * 100
        if 0 < pg < 4:
            gains += 1
        else:
            break
    return gains

if __name__ == '__main__':
    date = sys.argv[1] if len(sys.argv) > 1 else last_date
    stocks = data.get(date, [])
    
    results = []
    for s in stocks:
        code = s['code']
        ri = real.get(code)
        if not m1_filter(s, ri):
            continue
        
        pg = get_prev_gain(code, date)
        gains = get_gains(code, date)
        
        p, a, dif, cl = s['p'], s['a'], s['dif_val'], s['cl']
        score = p * 1 + a * 1.5 + dif * 0.5 + cl * 0.02
        if cl < 60:
            score -= 3
        if gains >= 3:
            score += 1
        
        name = names.get(code, code)
        vol = s.get('vol_ratio', 0)
        ri_data = ri or {}
        hsl = ri_data.get('hsl', 0) or 0
        pe = ri_data.get('pe', 0) or 0
        sz = ri_data.get('shizhi', 0) or 0
        n = s.get('n', 0) or 0
        j = s.get('j_val', 0)
        dif_v = s.get('dif_val', 0)
        
        results.append((score, code, name, p, a, cl, vol, hsl, pe, sz, gains, pg, n, j, dif_v))
    
    results.sort(key=lambda x: -x[0])
    
    print(f'\n{date}  小猪策略 尾盘打板 v2.0 （共{len(results)}只）')
    print('="""')
    cols = [('#',3),('名称',10),('代码',11),('评分',5),('涨%',4),('ATR',4),('位%',3),('量',3),('换%',4),('PE',5),('市值',5),('碎阳',3),('前日%',6),('次日%',6),('J',4),('DIF',5)]
    header = ''.join(f'{k:<{w}}' for k,w in cols)
    print(header)
    print('-' * 88)
    for i, (sc, code, name, p, a, cl, vol, hsl, pe, sz, gains, pg, n, j, dif_v) in enumerate(results[:30]):
        pg_str = f'{pg:.2f}' if pg is not None else 'N/A'
        n_str = f'{n:.2f}' if n > 0 else 'N/A'
        gains_str = f'{gains}🔥' if gains >= 3 else str(gains)
        name_disp = name[:8]
        print(f'{i+1:<3} {name_disp:<10} {code:<11} {sc:<5.1f} {p:<4.1f} {a:<4.1f} {cl:<3.0f} {vol:<3.2f} {hsl:<4.1f} {pe:<5.1f} {sz:<5.0f} {gains_str:<3} {pg_str:<6} {n_str:<6} {j:<4.1f} {dif_v:<5.3f}')
    print('="""')
