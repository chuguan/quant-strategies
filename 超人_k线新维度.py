"""
🚀 打破规则！从K线挖20+全新维度
不受限于缓存字段，直接从5125只JSON全量计算
"""
import pickle, os, json, sys, time
from collections import defaultdict
import statistics
import math

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
t0 = time.time()

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
all_days = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]

print(f'[{time.time()-t0:.1f}s] 缓存加载完成 | {len(data)}天 {len(real)}只', flush=True)

# ===== 读取K线 for one stock (快速) =====
kline_cache = {}
def get_kline(code):
    if code in kline_cache:
        return kline_cache[code]
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp):
        kline_cache[code] = None
        return None
    try:
        with open(fp) as f:
            kd = json.load(f)
        kline_cache[code] = kd
        return kd
    except:
        kline_cache[code] = None
        return None

# ===== 特征提取 =====
def extract_features(code, dt, kd, buy_c):
    """从K线数据中提取多维特征"""
    feats = {}
    
    # 找今天在K线中的位置
    today_idx = None
    for i, d in enumerate(kd):
        if d['date'] == dt:
            today_idx = i
            break
    if today_idx is None or today_idx < 20:  # 至少需要20天数据
        return None
    
    td = kd[today_idx]  # 今天K线
    yd = kd[today_idx - 1]  # 昨天K线
    
    close = td['close']
    high = td['high']
    low = td['low']
    open_p = td['open']
    volume = td['volume']
    
    # ---- 均线距离 ----
    closes_5 = [kd[i]['close'] for i in range(today_idx-4, today_idx+1)]
    closes_10 = [kd[i]['close'] for i in range(today_idx-9, today_idx+1)]
    closes_20 = [kd[i]['close'] for i in range(today_idx-19, today_idx+1)]
    
    ma5 = statistics.mean(closes_5)
    ma10 = statistics.mean(closes_10)
    ma20 = statistics.mean(closes_20)
    
    feats['ma5_dist'] = (close/ma5 - 1) * 100          # 距5日线%
    feats['ma10_dist'] = (close/ma10 - 1) * 100        # 距10日线%
    feats['ma20_dist'] = (close/ma20 - 1) * 100         # 距20日线%
    feats['above_ma5'] = 1 if close >= ma5 else 0       # 站上5日线
    feats['above_ma10'] = 1 if close >= ma10 else 0     # 站上10日线
    feats['above_ma20'] = 1 if close >= ma20 else 0     # 站上20日线
    feats['ma5_ma10_cross'] = 1 if ma5 >= ma10 else 0   # 5日线上穿10日线
    feats['ma10_ma20_cross'] = 1 if ma10 >= ma20 else 0 # 多头排列
    
    # ---- 量能分析 ----
    volumes_5 = [kd[i]['volume'] for i in range(today_idx-4, today_idx+1)]
    volumes_10 = [kd[i]['volume'] for i in range(today_idx-9, today_idx+1)]
    vol_ma5 = statistics.mean(volumes_5)
    vol_ma10 = statistics.mean(volumes_10)
    
    feats['vol_ma5_ratio'] = volume / vol_ma5 if vol_ma5 > 0 else 0       # 量/5日均量
    feats['vol_ma10_ratio'] = volume / vol_ma10 if vol_ma10 > 0 else 0     # 量/10日均量
    feats['vol_trend_1d'] = volume / yd['volume'] if yd['volume'] > 0 else 0  # 量比昨日
    feats['vol_trend_3d'] = volume / vol_ma5 if vol_ma5 > 0 else 0  # 量比5日均量
    
    # 量价背离: 价涨但量缩
    price_up = close > yd['close']
    vol_up = volume > yd['volume']
    feats['vol_price_div'] = 1 if (price_up and not vol_up) else 0
    
    # ---- K线形态 ----
    candle_range = high - low
    body = abs(close - open_p)
    
    feats['upper_shadow'] = (high - max(close, open_p)) / candle_range * 100 if candle_range > 0 else 0  # 上影线%
    feats['lower_shadow'] = (min(close, open_p) - low) / candle_range * 100 if candle_range > 0 else 0   # 下影线%
    feats['body_pct'] = body / candle_range * 100 if candle_range > 0 else 0                              # 实体%
    feats['is_red'] = 1 if close > open_p else 0                                                          # 阳线
    
    # ---- 缺口分析 ----
    prev_close = yd['close']
    gap = (open_p / prev_close - 1) * 100 if prev_close > 0 else 0
    feats['gap_pct'] = gap
    feats['has_gap_up'] = 1 if gap > 0.5 else 0        # 跳空高开>0.5%
    feats['gap_fill'] = 1 if (gap > 0.5 and low <= prev_close) else 0  # 跳空后回补缺口
    
    # ---- 连涨/连跌 ----
    up_days = 0
    for i in range(today_idx-1, max(today_idx-10, -1), -1):
        if kd[i]['close'] > kd[i-1]['close']:
            up_days += 1
        else:
            break
    feats['consecutive_up'] = up_days  # 连涨天数(不含今日)
    
    # ---- 波动率 ----
    atr14 = statistics.mean([
        abs(kd[i]['high'] - kd[i]['low']) for i in range(today_idx-13, today_idx+1)
    ])
    feats['range_atr_ratio'] = candle_range / atr14 if atr14 > 0 else 0
    
    # ---- 近20日位置 ----
    highs_20 = [kd[i]['high'] for i in range(today_idx-19, today_idx+1)]
    lows_20 = [kd[i]['low'] for i in range(today_idx-19, today_idx+1)]
    h20_max = max(highs_20)
    h20_min = min(lows_20)
    feats['near_20d_high'] = (close - h20_min) / (h20_max - h20_min) * 100 if h20_max > h20_min else 50
    feats['is_20d_high'] = 1 if close >= h20_max * 0.98 else 0  # 接近20日高点
    
    # ---- 加速/减速 ----
    today_pct = (close / prev_close - 1) * 100
    prev_pct = (prev_close / kd[today_idx-2]['close'] - 1) * 100 if today_idx >= 2 else 0
    feats['price_accel'] = today_pct - prev_pct  # 加速度（今日涨幅-昨日涨幅）
    
    # ---- 量价加速 ----
    # 量在涨
    vol_3d_avg = statistics.mean([kd[i]['volume'] for i in range(today_idx-3, today_idx)])
    feats['vol_3d_trend'] = volume / vol_3d_avg if vol_3d_avg > 0 else 0
    
    # ---- ATR百分比 ----
    close_pct = close
    atr_pct = (atr14 / close_pct) * 100 if close_pct > 0 else 0
    feats['atr_pct'] = atr_pct
    
    # ---- RSI(6) ----
    gains, losses = [], []
    for i in range(today_idx-5, today_idx+1):
        chg = (kd[i]['close'] - kd[i-1]['close']) / kd[i-1]['close'] * 100 if kd[i-1]['close'] > 0 else 0
        gains.append(max(chg, 0))
        losses.append(abs(min(chg, 0)))
    avg_gain = statistics.mean(gains) if gains else 0
    avg_loss = statistics.mean(losses) if losses else 0
    feats['rsi6'] = 100 - (100 / (1 + avg_gain/avg_loss)) if avg_loss > 0 else 100
    
    # ---- 价格动量(5天) ----
    close_5d_ago = kd[today_idx-5]['close']
    feats['momentum_5d'] = (close / close_5d_ago - 1) * 100 if close_5d_ago > 0 else 0
    
    return feats

# ===== 主循环：提取特征 → 对比达标/不达标 =====
print(f'开始K线特征提取...', flush=True)

pass_feats = defaultdict(list)
fail_feats = defaultdict(list)
total_scanned = 0

# 只取伯乐v4通过的股票
def bole_v4_check(s, ri):
    p = s['p']
    if p < 5 or p > 8: return False
    vr = s.get('vol_ratio',0) or 0
    if vr < 0.8: return False
    if not ri: return False
    hsl = (ri.get('hsl',0) or 0)
    if hsl < 5 or hsl > 15: return False
    sz = (ri.get('shizhi',0) or 0)
    if sz >= 150: return False
    nm = names.get(s['code'],'')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return False
    jv = s.get('j_val',0) or 0
    if jv > 80: return False
    return True

pass_days, fail_days = 0, 0
kline_reads = 0

for dt in all_days:
    stocks = data.get(dt, [])
    best_stock = None
    best_nv = 0
    
    for s in stocks:
        ri = real.get(s['code'])
        if not bole_v4_check(s, ri): continue
        
        code = s['code']
        kd = get_kline(code)
        if kd is None: continue
        kline_reads += 1
        
        buy_c = s.get('close', 0)
        feats = extract_features(code, dt, kd, buy_c)
        if feats is None: continue
        
        nv = s.get('n', 0) or 0
        sc = 10  # 基础分，简化
        if 5 <= s['p'] <= 6.5: sc += 15
        elif 6.5 < s['p'] <= 7: sc += 8
        elif 4.5 <= s['p'] < 5: sc += 5
        if 60 <= s['cl'] <= 85: sc += 10
        if 0.8 <= s['vol_ratio'] <= 1.5: sc += 10
        
        if best_stock is None or sc > best_stock[0]:
            best_stock = (sc, code, nv, feats, s['p'], s.get('cl',0), s.get('vol_ratio',0))
    
    if best_stock is None: continue
    _, code, nv, feats, p, cl, vr = best_stock
    target = pass_feats if nv >= 2.5 else fail_feats
    
    for k, v in feats.items():
        target[k].append(v)
    target['p'].append(p)
    target['cl'].append(cl)
    target['vr'].append(vr)
    target['nv'].append(nv)
    
    if nv >= 2.5:
        pass_days += 1
    else:
        fail_days += 1

total = pass_days + fail_days
print(f'\n经过伯乐v4+K线筛选: {total}天 | 达标{pass_days}({pass_days*100/total:.1f}%) 不达标{fail_days}({fail_days*100/total:.1f}%)', flush=True)
print(f'K线读取: {kline_reads}次', flush=True)

# ===== 特征对比 =====
print(f'\n{"="*80}')
print(f'  🔬 20+新维度特征对比：达标 vs 不达标')
print(f'{"="*80}', flush=True)

# 定义特征名称和方向
FEATURE_NAMES = {
    'ma5_dist': '距5日线%', 'ma10_dist': '距10日线%', 'ma20_dist': '距20日线%',
    'above_ma5': '站上5日线', 'above_ma10': '站上10日线', 'above_ma20': '站上20日线',
    'ma5_ma10_cross': '5穿10', 'ma10_ma20_cross': '10穿20(多头)',
    'vol_ma5_ratio': '量/5均量', 'vol_ma10_ratio': '量/10均量',
    'vol_trend_1d': '量/昨量', 'vol_trend_3d': '量/3日均量',
    'vol_price_div': '量价背离', 'upper_shadow': '上影线%', 'lower_shadow': '下影线%',
    'body_pct': '实体%', 'is_red': '阳线',
    'gap_pct': '跳空%', 'has_gap_up': '跳空高开', 'gap_fill': '缺口回补',
    'consecutive_up': '连涨天数', 'range_atr_ratio': '波动/ATR',
    'near_20d_high': '20日位置%', 'is_20d_high': '近20日高点',
    'price_accel': '加速度', 'vol_3d_trend': '量/3日均量2',
    'atr_pct': 'ATR%', 'rsi6': 'RSI6', 'momentum_5d': '5日动量%',
}

for feat_key, feat_name in sorted(FEATURE_NAMES.items(), key=lambda x: abs(
    (statistics.mean(pass_feats.get(x[0], [0])) if pass_feats.get(x[0]) else 0) -
    (statistics.mean(fail_feats.get(x[0], [0])) if fail_feats.get(x[0]) else 0)
), reverse=True):
    pv = pass_feats.get(feat_key, [])
    fv = fail_feats.get(feat_key, [])
    if not pv or not fv: continue
    
    p_avg = statistics.mean(pv)
    f_avg = statistics.mean(fv)
    p_med = statistics.median(pv)
    f_med = statistics.median(fv)
    p_std = statistics.stdev(pv) if len(pv) > 1 else 0
    f_std = statistics.stdev(fv) if len(fv) > 1 else 0
    diff = p_avg - f_avg
    pooled_std = math.sqrt(p_std**2 + f_std**2) if (p_std or f_std) else 1
    sep = abs(diff) / max(pooled_std, 0.001)
    
    # 显示信号
    if sep >= 0.3:
        sig = '🔥' if sep >= 0.5 else '✅'
    elif sep >= 0.2:
        sig = '📊'
    else:
        sig = ''
    
    print(f'{sig} {feat_name:<14} 达标avg={p_avg:>10.3f} med={p_med:>8.3f} | 不达标avg={f_avg:>10.3f} med={f_med:>8.3f} | Δ={diff:>+8.3f} 分离度={sep:.2f}σ', flush=True)

# ===== 最佳条件 =====
print(f'\n{"="*80}')
print(f'  最佳新条件穿透率测试')
print(f'{"="*80}', flush=True)

# 从特征中选最有希望的做条件组合
best_conditions = []

# 测试每个特征的最优阈值
for feat_key, feat_name in FEATURE_NAMES.items():
    pv = pass_feats.get(feat_key, [])
    fv = fail_feats.get(feat_key, [])
    all_v = pv + fv
    if not all_v: continue
    
    # 找最佳阈值
    sorted_v = sorted(all_v)
    best_rate = 0
    best_threshold = None
    best_direction = None
    
    for threshold in sorted_v[::max(1, len(sorted_v)//20)]:  # 采样
        for direction in ['gt', 'lt']:
            wins, total = 0, 0
            for dt in all_days:
                stocks = data.get(dt, [])
                best_nv = 0
                best_val = None
                
                for s in stocks:
                    ri = real.get(s['code'])
                    if not bole_v4_check(s, ri): continue
                    code = s['code']
                    kd = get_kline(code)
                    if kd is None: continue
                    buy_c = s.get('close', 0)
                    feats = extract_features(code, dt, kd, buy_c)
                    if feats is None: continue
                    val = feats.get(feat_key)
                    if val is None: continue
                    
                    if best_val is None or val > best_val:
                        best_val = val
                        best_nv = s.get('n', 0) or 0
                
                if best_val is None: continue
                ok = (direction == 'gt' and best_val >= threshold) or (direction == 'lt' and best_val <= threshold)
                if ok:
                    total += 1
                    if best_nv >= 2.5: wins += 1
            
            if total >= 3:
                rate = wins*100/total
                if rate > best_rate:
                    best_rate = rate
                    best_threshold = threshold
                    best_direction = direction
    
    if best_threshold is not None and total >= 5:
        dir_symbol = '≥' if best_direction == 'gt' else '≤'
        print(f'{feat_name:<14} {dir_symbol} {best_threshold:<8.2f} → {wins}/{total} = {best_rate:.1f}% | 基准{pass_days*100/total:.1f}%', flush=True)
        best_conditions.append((best_rate, total, feat_name, dir_symbol, best_threshold, wins))

# ===== 多条件组合 =====
print(f'\n{"="*80}')
print(f'  多条件黄金组合')
print(f'{"="*80}', flush=True)

# 手动测试有希望的组合
combos = [
    # (名称, 条件函数)
    ('距5日线>0(站上MA5)', lambda f: f['ma5_dist'] > 0),
    ('距5日线0~5%', lambda f: 0 <= f['ma5_dist'] <= 5),
    ('距5日线2~8%', lambda f: 2 <= f['ma5_dist'] <= 8),
    ('多头排列(5>10>20)', lambda f: f['above_ma5'] and f['above_ma10'] and f['above_ma20'] and f['ma5_ma10_cross']),
    ('跳空高开+未回补', lambda f: f['has_gap_up'] and not f['gap_fill']),
    ('上影线<30%+阳线', lambda f: f['upper_shadow'] < 30 and f['is_red']),
    ('连涨<3天', lambda f: f['consecutive_up'] < 3),
    ('RSI6<70', lambda f: f['rsi6'] < 70),
    ('RSI6 40~65', lambda f: 40 <= f['rsi6'] <= 65),
    ('量/5均量<2.5', lambda f: f['vol_ma5_ratio'] < 2.5),
    ('近20日位置>70%', lambda f: f['near_20d_high'] > 70),
    ('近20日位置40~80%', lambda f: 40 <= f['near_20d_high'] <= 80),
    ('站上5日线+RSI<70', lambda f: f['above_ma5'] and f['rsi6'] < 70),
    ('站上5日线+RSI40~65', lambda f: f['above_ma5'] and 40 <= f['rsi6'] <= 65),
    ('站上MA5+量<2.5倍', lambda f: f['above_ma5'] and f['vol_ma5_ratio'] < 2.5),
    ('站上MA5+连涨<3+RSI<70', lambda f: f['above_ma5'] and f['consecutive_up'] < 3 and f['rsi6'] < 70),
    ('MA5上方+无跳空+阳线', lambda f: f['above_ma5'] and not f['has_gap_up'] and f['is_red']),
    ('多头排列+量比<2.5', lambda f: f['above_ma5'] and f['above_ma10'] and f['above_ma20'] and f['vol_ma5_ratio'] < 2.5),
    ('站上MA5+实体>50%', lambda f: f['above_ma5'] and f['body_pct'] > 50),
    ('站上MA5+上影<30%+RSI<70', lambda f: f['above_ma5'] and f['upper_shadow'] < 30 and f['rsi6'] < 70),
    ('站上MA5+量价配合', lambda f: f['above_ma5'] and not f['vol_price_div'] and f['vol_ma5_ratio'] < 2.5),
]

for name, cond in combos:
    wins, total = 0, 0
    for dt in all_days:
        stocks = data.get(dt, [])
        best_nv = 0
        found = False
        
        for s in stocks:
            ri = real.get(s['code'])
            if not bole_v4_check(s, ri): continue
            code = s['code']
            kd = get_kline(code)
            if kd is None: continue
            buy_c = s.get('close', 0)
            feats = extract_features(code, dt, kd, buy_c)
            if feats is None: continue
            
            if cond(feats):
                nv = s.get('n', 0) or 0
                if nv > best_nv:
                    best_nv = nv
                found = True
                break  # 只取第一只符合条件的
        
        if not found: continue
        total += 1
        if best_nv >= 2.5: wins += 1
    
    if total > 0:
        rate = wins*100/total
        diff_rate = rate - pass_days*100/max(total, 1)
        sig = '🔥' if diff_rate > 10 else ('✅' if diff_rate > 5 else '')
        print(f'{sig} {name:<30} {wins}/{total} = {rate:.1f}% (差距{diff_rate:+.1f}%)', flush=True)

print(f'\n{"="*80}')
print(f'  🚀 最终结论')
print(f'{"="*80}', flush=True)
print(f'1. 基准伯乐v4: {pass_days}/{total} = {pass_days*100/total:.1f}%', flush=True)
print(f'2. K线新维度特征中分离度>0.3σ的值得关注', flush=True)
print(f'3. 最佳条件组合能提升多少看上面结果', flush=True)
print(f'耗时: {time.time()-t0:.1f}秒', flush=True)
