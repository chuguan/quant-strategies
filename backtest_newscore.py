"""
全量回测：原版评分 + 前一天涨幅扣分
扣分规则：前日涨>6%→-5, >7%→-8, ≥8%→-15
输出格式含：评分列、前日涨跌幅
"""
import pickle, json, os, time, sys
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
BIG_CACHE = 'big_cache.pkl'

# 加载大缓存
print('加载大缓存...')
t0 = time.time()
with open(BIG_CACHE, 'rb') as f:
    cache = pickle.load(f)
names = cache['names']
real = cache['real']
data = cache['data']
dates = sorted(data.keys())
print(f'已加载 {len(dates)} 天数据 ({time.time()-t0:.1f}s)')

# 构建日期索引
date_index = {d: i for i, d in enumerate(dates)}

# K线数据缓存（按需加载）
kline_cache = {}  # code -> {date: close}

def load_kline(code):
    """加载一只股票的K线数据，返回date->close字典"""
    if code in kline_cache:
        return kline_cache[code]
    
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp):
        kline_cache[code] = None
        return None
    
    try:
        with open(fp, 'r') as f:
            kdata = json.load(f)
        result = {d['date']: d['close'] for d in kdata}
        kline_cache[code] = result
        return result
    except:
        kline_cache[code] = None
        return None

def get_prev_gain(code, cur_date):
    """
    获取前一天涨幅 = (前日收盘/前前天收盘 - 1) * 100
    优先用缓存，没有则用K线
    """
    idx = date_index.get(cur_date)
    if idx is None or idx == 0:
        return None
    prev_date = dates[idx - 1]
    
    # 方案1：从大缓存取（快）
    prev_stocks = data.get(prev_date, [])
    for s in prev_stocks:
        if s['code'] == code:
            return s['p']  # p = (prev_close / prev_prev_close - 1) * 100
    
    # 方案2：从K线取（慢但全）
    kline = load_kline(code)
    if kline is None:
        return None
    
    prev_close = kline.get(prev_date)
    if prev_close is None:
        return None
    
    # 找前前天
    if idx >= 2:
        prev_prev_date = dates[idx - 2]
        prev_prev_close = kline.get(prev_prev_date)
        if prev_prev_close:
            return (prev_close / prev_prev_close - 1) * 100
    
    return None

def calc_old_score(s):
    """原版评分"""
    p = s.get('p', 0)
    a = s.get('a', 0)
    dif = s.get('dif_val', 0)
    cl = s.get('cl', 50)
    score = p * 1 + a * 1.5 + dif * 0.5 + cl * 0.02
    if cl < 60:
        score -= 3
    return score

def calc_new_score(s, prev_gain):
    """新评分 = 原版 + 前一天涨幅扣分"""
    p = s.get('p', 0)
    a = s.get('a', 0)
    dif = s.get('dif_val', 0)
    cl = s.get('cl', 50)
    
    score = p * 1 + a * 1.5 + dif * 0.5 + cl * 0.02
    if cl < 60:
        score -= 3
    
    # 前一天涨幅扣分（不叠加，取最大）
    if prev_gain is not None:
        if prev_gain >= 8:
            score -= 15
        elif prev_gain > 7:
            score -= 8
        elif prev_gain > 6:
            score -= 5
    
    return score

def m1_filter(s, real, code):
    """M1硬过滤"""
    p = s.get('p', -999)
    if p < 1 or p > 8:
        return False
    if s.get('is_yang', 0) != 1:
        return False
    if s.get('above_ma5', 0) != 1:
        return False
    if (s.get('vol_ratio', 0) or 0) <= 1:
        return False
    ri = real.get(code)
    if not ri:
        return False
    hsl = (ri.get('hsl', 0) or 0)
    if hsl < 3 or hsl > 15:
        return False
    pe = (ri.get('pe', 0) or 0)
    if pe <= 0:
        return False
    sz = (ri.get('shizhi', 0) or 0)
    if sz >= 200:
        return False
    return True

# 回测循环
print('\n开始回测...')
t0 = time.time()
total = 0
old_wins = 0
new_wins = 0
old_avg_n = 0
new_avg_n = 0
new_champion_changed = 0  # 冠军改变的次数
new_better_champion = 0  # 新冠军比旧冠军好的次数

# 详细记录
detail_old = []
detail_new = []

for date in dates:
    stocks = data[date]
    filtered = []
    
    for s in stocks:
        code = s['code']
        if not m1_filter(s, real, code):
            continue
        prev_gain = get_prev_gain(code, date)
        old_score = calc_old_score(s)
        new_score = calc_new_score(s, prev_gain)
        n = s.get('n', 0) or 0
        name = names.get(code, code)
        filtered.append({
            'code': code, 'name': name, 's': s,
            'old_score': old_score, 'new_score': new_score,
            'prev_gain': prev_gain, 'n': n
        })
    
    if not filtered:
        continue
    
    total += 1
    
    # 旧版冠军
    filtered.sort(key=lambda x: -x['old_score'])
    old_champ = filtered[0]
    
    # 新版冠军
    filtered.sort(key=lambda x: -x['new_score'])
    new_champ = filtered[0]
    
    old_ok = old_champ['n'] >= 2.5
    new_ok = new_champ['n'] >= 2.5
    
    if old_ok: old_wins += 1
    if new_ok: new_wins += 1
    old_avg_n += old_champ['n']
    new_avg_n += new_champ['n']
    
    # 冠军变化检测
    if old_champ['code'] != new_champ['code']:
        new_champion_changed += 1
        if new_ok and not old_ok:
            new_better_champion += 1
        elif new_ok and old_ok:
            if new_champ['n'] > old_champ['n']:
                new_better_champion += 1
    
    detail_old.append({
        'date': date, 'code': old_champ['code'], 'name': old_champ['name'],
        'score': old_champ['old_score'], 'p': old_champ['s']['p'], 'n': old_champ['n'], 'ok': old_ok
    })
    detail_new.append({
        'date': date, 'code': new_champ['code'], 'name': new_champ['name'],
        'score': new_champ['new_score'], 'p': new_champ['s']['p'], 'n': new_champ['n'], 'ok': new_ok,
        'prev_gain': new_champ['prev_gain']
    })

# 统计结果
elapsed = time.time() - t0
print(f'\n回测完成 ({elapsed:.1f}s)')
print(f'总回测天数: {total}')
print()
print('=' * 50)
print(f'原版冠军: {old_wins}/{total} = {old_wins*100/total:.1f}%  均涨幅={old_avg_n/total:.2f}%')
print(f'新版冠军: {new_wins}/{total} = {new_wins*100/total:.1f}%  均涨幅={new_avg_n/total:.2f}%')
print(f'差异: {new_wins-old_wins:+d}天 ({new_wins*100/total-old_wins*100/total:+.1f}%)')
print(f'冠军变化: {new_champion_changed}次, 新更优: {new_better_champion}次')
print()

# 分年
for year in ['2025', '2026']:
    ny = [r for r in detail_new if r['date'].startswith(year)]
    oy = [r for r in detail_old if r['date'].startswith(year)]
    if ny and oy:
        nw = sum(1 for r in ny if r['ok'])
        ow = sum(1 for r in oy if r['ok'])
        print(f'{year}年: 新版={nw}/{len(ny)}={nw*100/len(ny):.1f}%  原版={ow}/{len(oy)}={ow*100/len(oy):.1f}%')

print()

# 找出冠军不同的日子
changed_days = []
for o, n in zip(detail_old, detail_new):
    if o['code'] != n['code']:
        changed_days.append({
            'date': n['date'],
            'old_name': o['name'], 'old_n': o['n'], 'old_score': o['score'],
            'new_name': n['name'], 'new_n': n['n'], 'new_score': n['score'],
            'better': n['ok'] and not o['ok']
        })

print(f'冠军改变天数: {len(changed_days)}')
# 统计旧版失败→新版成功的次数
old_fail_new_ok = sum(1 for d in changed_days if d['better'])
old_ok_new_fail = sum(1 for d in changed_days if not d['better'] and d['old_n'] >= 2.5 and d['new_n'] < 2.5)
print(f'  新版翻盘(旧败→新胜): {old_fail_new_ok}次')
print(f'  新版翻车(旧胜→新败): {old_ok_new_fail}次')
