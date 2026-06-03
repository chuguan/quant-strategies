"""
多策略量化测试 — 从K线中验证10+种经典A股策略
策略来源：涨停回马枪、N字突破、箱体突破、均线粘合、MACD金叉等
"""
import pickle, os, json, sys, statistics, itertools, math, time
from collections import defaultdict, Counter

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
KLINE_CACHE = {}
t0 = time.time()

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
all_days = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]
all_days_set = set(all_days)

print(f'2026年 {len(all_days)}天 | 加载{time.time()-t0:.1f}s', flush=True)

def get_kline(code):
    if code not in KLINE_CACHE:
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        if os.path.exists(fp):
            try:
                KLINE_CACHE[code] = json.load(open(fp))
            except: KLINE_CACHE[code] = None
        else: KLINE_CACHE[code] = None
    return KLINE_CACHE[code]

# ===== 基础过滤（最佳参数） =====
BEST_P = {'p_min':5.0, 'p_max':7.5, 'vr_min':1.0, 'vr_max':1.5, 
          'hsl_min':5, 'hsl_max':12, 'sz_max':100, 'j_max':100, 'cl_min':0, 'cl_max':100}

def basic_filter(s):
    code, p = s['code'], s['p']
    if p < BEST_P['p_min'] or p > BEST_P['p_max']: return False, ''
    vr = s.get('vol_ratio',0) or 0
    if vr < BEST_P['vr_min'] or vr > BEST_P['vr_max']: return False, ''
    ri = real.get(code)
    if not ri: return False, ''
    hsl = (ri.get('hsl',0) or 0)
    if hsl < BEST_P['hsl_min'] or hsl > BEST_P['hsl_max']: return False, ''
    if (ri.get('shizhi',0) or 0) > BEST_P['sz_max']: return False, ''
    nm = names.get(code,'')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return False, ''
    jv = s.get('j_val',0) or 0
    if jv > BEST_P['j_max']: return False, ''
    cl = s.get('cl',0)
    if cl < BEST_P['cl_min'] or cl > BEST_P['cl_max']: return False, ''
    return True, nm

def get_kline_at(code, dt):
    """获取某只股票在指定日期的K线及前20天数据"""
    kd = get_kline(code)
    if kd is None: return None, None
    for i, d in enumerate(kd):
        if d['date'] == dt:
            if i < 20: return None, None
            return kd[i-20:i+1], kd[i-20:i+1]  # 返回20天数据+今天
    return None, None

# ===== 策略定义 =====
strategies = {}

# 策略1: N字突破（涨→回调→再涨）
def strategy_n_break(kd_20, today):
    """N字形态：前5天内有高点→回调2~3天→今天再涨"""
    if len(kd_20) < 10: return False
    p5d = kd_20[-10:-1]  # 前9天（不含今天）
    today_close = today['close']
    today_high = today['high']
    
    # 找前9天的最高点
    highs = [d['high'] for d in p5d]
    max_high = max(highs)
    max_idx = highs.index(max_high)
    
    # 条件：高点在第3~7天出现，之后回调，今天突破
    if 3 <= max_idx <= 7:
        # 回调幅度：从高点回落至少1%
        after_high = p5d[max_idx:]
        lows_after = [d['low'] for d in after_high]
        min_low = min(lows_after)
        pullback = (max_high - min_low) / max_high * 100
        if pullback >= 1.0 and pullback <= 8.0:
            # 今天突破前高
            if today_close >= max_high * 0.98:
                return True
    return False
strategies['N字突破'] = strategy_n_break

# 策略2: 箱体突破（横盘→放量突破）
def strategy_box_break(kd_20, today):
    """箱体：前15天在一个区间内震荡，今天放量突破"""
    if len(kd_20) < 18: return False
    box = kd_20[:-1]  # 不含今天
    box_highs = [d['high'] for d in box]
    box_lows = [d['low'] for d in box]
    box_volumes = [d['volume'] for d in box]
    
    box_range = (max(box_highs) - min(box_lows)) / min(box_lows) * 100
    avg_vol = statistics.mean(box_volumes)
    
    # 横盘：箱体宽度<15%
    if box_range < 15:
        # 今天突破箱体上沿
        if today['close'] >= max(box_highs) * 0.99:
            # 放量
            if today['volume'] >= avg_vol * 1.3:
                return True
    return False
strategies['箱体突破'] = strategy_box_break

# 策略3: 涨停回马枪（大涨→缩量回调→再涨）
def strategy_limit_pullback(kd_20, today):
    """涨停回马枪：前1~3天大涨>6%，然后缩量回调，今天再启动"""
    if len(kd_20) < 8: return False
    p5d = kd_20[-6:-1]  # 前5天不含今天
    today_v = today['volume']
    
    big_up_days = []
    for i, d in enumerate(p5d):
        prev = kd_20[-7+i]  # 前一天
        pct = (d['close'] - prev['close']) / prev['close'] * 100
        if pct >= 6:
            big_up_days.append((i, pct, d['volume']))
    
    if not big_up_days: return False
    
    # 取最近一次大涨
    last_up = big_up_days[-1]
    idx, up_pct, up_vol = last_up
    
    # 大涨后回调天数
    retreat_days = len(p5d) - idx - 1
    if retreat_days < 1 or retreat_days > 4: return False
    
    # 缩量回调：回调日成交量小于大涨日
    retreat_vols = [d['volume'] for d in p5d[idx+1:]]
    if retreat_vols and max(retreat_vols) <= up_vol * 1.2:
        # 今天放量启动
        if today_v >= statistics.mean(retreat_vols) * 1.2:
            if today['close'] > today['open']:  # 阳线
                return True
    return False
strategies['涨停回马枪'] = strategy_limit_pullback

# 策略4: 均线粘合突破
def strategy_ma_stick(kd_20, today):
    """均线粘合：MA5,MA10,MA20靠拢后向上发散"""
    if len(kd_20) < 20: return False
    ma5 = statistics.mean([kd_20[-5+i]['close'] for i in range(-5,0)]) if len(kd_20)>=5 else 0
    ma10 = statistics.mean([kd_20[-10+i]['close'] for i in range(-10,0)])
    ma20 = statistics.mean([d['close'] for d in kd_20])
    
    if ma5 <= 0 or ma10 <= 0 or ma20 <= 0: return False
    
    # 粘合：三条均线差距<3%
    spread = max(ma5,ma10,ma20) / min(ma5,ma10,ma20) - 1
    if spread * 100 < 3:
        # 今天价格站上所有均线
        if today['close'] > max(ma5, ma10, ma20):
            return True
    return False
strategies['均线粘合'] = strategy_ma_stick

# 策略5: 缩量涨停（强庄）
def strategy_shrink_limit(kd_20, today):
    """缩量涨停/大涨：涨幅大但成交量减少"""
    if len(kd_20) < 6: return False
    prev_vol = statistics.mean([kd_20[-6+i]['volume'] for i in range(0,5)])
    today_vol = today['volume']
    today_pct = (today['close'] - kd_20[-2]['close']) / kd_20[-2]['close'] * 100
    
    if today_pct >= 6 and today_vol < prev_vol * 0.8:
        return True
    return False
strategies['缩量大涨'] = strategy_shrink_limit

# 策略6: 倍量突破
def strategy_double_vol(kd_20, today):
    """成交量是昨天的2倍以上，且上涨"""
    if len(kd_20) < 3: return False
    vol_yesterday = kd_20[-3]['volume']
    if vol_yesterday <= 0: return False
    today_vol = today['volume']
    today_pct = (today['close'] - kd_20[-2]['close']) / kd_20[-2]['close'] * 100
    if today_vol >= vol_yesterday * 2 and today_pct > 0:
        return True
    return False
strategies['倍量突破'] = strategy_double_vol

# 策略7: 连续阳线推升
def strategy_consecutive_up(kd_20, today):
    """连续3~7根阳线推升"""
    if len(kd_20) < 8: return False
    up_count = 0
    for i in range(-8, -1):  # 前7天
        if kd_20[i]['close'] > kd_20[i]['open']:
            up_count += 1
        else:
            up_count = 0
        if up_count >= 3:
            break
    if 3 <= up_count <= 7:
        if today['close'] > kd_20[-2]['close']:  # 今天继续涨
            return True
    return False
strategies['连续阳线'] = strategy_consecutive_up

# 策略8: MACD零轴上方金叉（用DIF近似）
def strategy_macd_golden(kd_20, today):
    """DIF在零轴上方"""
    pass  # 已有J/DIF数据，后面单独测

# ===== 测试每个策略 =====
print(f'\n{"="*80}')
print(f'10+策略回测（基础过滤+策略条件）')
print(f'{"="*80}', flush=True)

KLINE_READS = 0

def test_strategy(dt, code, p, vr, cl):
    """测试股票是否满足各策略"""
    kd, _ = get_kline_at(code, dt)
    if kd is None or len(kd) < 20: return {}
    
    global KLINE_READS
    KLINE_READS += 1
    today = kd[-1]
    kd_20 = kd  # 20天数据
    
    results = {}
    for sname, sfn in strategies.items():
        try:
            results[sname] = sfn(kd_20, today)
        except:
            results[sname] = False
    return results

# 收集策略数据
strategy_stats = defaultdict(lambda: {'pass':0, 'total':0, 'nvs':[]})

for dt in all_days:
    stocks = data.get(dt, [])
    best_stock, best_nv = None, 0
    best_strats = {}
    
    for s in stocks:
        ok, nm = basic_filter(s)
        if not ok: continue
        
        code = s['code']
        nv = s.get('n',0) or 0
        
        strats = test_strategy(dt, code, s['p'], 
            s.get('vol_ratio',0), s.get('cl',0))
        
        # 取冠军（涨幅最高）
        if best_stock is None or s['p'] > best_stock['p']:
            best_stock = s
            best_nv = nv
            best_strats = strats
    
    if best_stock is None: continue
    
    # 记录策略命中
    for sname, hit in best_strats.items():
        strategy_stats[sname]['total'] += 1
        strategy_stats[sname]['nvs'].append(best_nv)
        if hit:
            strategy_stats[sname]['pass'] += 1

# 输出结果
print(f'K线读取: {KLINE_READS}次', flush=True)
print(f'\n{"策略名":<16} {"命中天数":<8} {"命中率":<10} {"达2.5%":<8} {"达标率":<10} {"均次日%":<10}')
print(f'{"-":<65}')
for sname, stats in sorted(strategy_stats.items(), key=lambda x: -sum(1 for v in x[1]['nvs'] if v >= 2.5)/len(x[1]['nvs']) if x[1]['nvs'] else 0):
    nvs = stats['nvs']
    total = len(nvs)
    hits = stats['pass']
    hit_rate = hits*100/total
    w25 = sum(1 for v in nvs if v >= 2.5)
    w25_rate = w25*100/total
    avg = statistics.mean(nvs) if nvs else 0
    bar = '█' * int(w25_rate/3)
    print(f'{sname:<16} {total:<8} {hit_rate:<10.1f}% {w25:<8} {w25_rate:<10.1f}% {avg:<+10.2f}% {bar}', flush=True)

# ===== 策略组合 =====
print(f'\n{"="*80}')
print(f'策略组合测试')
print(f'{"="*80}', flush=True)

# 收集所有策略命中的冠军数据
strategy_days = defaultdict(list)
for dt in all_days:
    stocks = data.get(dt, [])
    for s in stocks:
        ok, nm = basic_filter(s)
        if not ok: continue
        code = s['code']
        nv = s.get('n',0) or 0
        strats = test_strategy(dt, code, s['p'], s.get('vol_ratio',0), s.get('cl',0))
        
        for sname, hit in strats.items():
            if hit:
                strategy_days[sname].append((dt, code, nv))

# 双策略组合
from itertools import combinations
snames = list(strategies.keys())
print(f'{"组合1":<16} {"组合2":<16} {"天数":<6} {"达2.5%":<10}')
for s1, s2 in combinations(snames, 2):
    set1 = set(dt for dt,_,_ in strategy_days[s1])
    set2 = set(dt for dt,_,_ in strategy_days[s2])
    common = set1 & set2
    if not common: continue
    
    nvs = [nv for dt,_,nv in strategy_days[s1] if dt in common]
    nvs += [nv for dt,_,nv in strategy_days[s2] if dt in common]
    common_nvs = []
    for dt in common:
        for sname in [s1, s2]:
            for d, c, n in strategy_days[sname]:
                if d == dt:
                    common_nvs.append(n)
                    break
    
    if common_nvs:
        w25 = sum(1 for v in common_nvs if v >= 2.5)*100/len(common_nvs)
        if w25 >= 60:
            print(f'{s1:<16} {s2:<16} {len(common):<6} {w25:<10.1f}%')

print(f'\n总耗时: {time.time()-t0:.1f}s', flush=True)
