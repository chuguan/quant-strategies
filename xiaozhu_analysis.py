#!/usr/bin/env python3
"""小猪策略 — 尾盘选股特征分析：第二天涨2.5%+的票有什么特征"""
import json, os, sys, time
from collections import Counter, defaultdict
import math

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# ═══ 技术指标 ═══
def ma(d, pd):
    r = []
    for i in range(len(d)):
        if i < pd-1: r.append(None)
        else: r.append(sum(d[i-pd+1:i+1])/pd)
    return r

def macd_full(ps):
    n = len(ps)
    if n < 26: return None, None, None
    e12 = [ps[0]]; e26 = [ps[0]]
    dif = [None]*n; dea = [None]*n; macd = [None]*n
    for i in range(1, n):
        e12.append(e12[-1]*11/13+ps[i]*2/13)
        e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i] = e12[i] - e26[i]
    dea[0] = dif[0] if dif[0] else 0
    for i in range(1, n):
        dea[i] = dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    for i in range(n):
        if dif[i] is not None and dea[i] is not None:
            macd[i] = dif[i] - dea[i]
    return dif, dea, macd

def kdj_calc(highs, lows, closes, n=9):
    L = len(closes)
    if L < n: return None, None, None
    k = [50.0]*L; d = [50.0]*L; j = [50.0]*L
    for i in range(n-1, L):
        hh = max(highs[i-n+1:i+1]); ll = min(lows[i-n+1:i+1])
        rsv = 50.0 if hh == ll else (closes[i]-ll)/(hh-ll)*100
        if i == n-1: k[i] = 50.0
        else: k[i] = 2/3*k[i-1] + 1/3*rsv
        d[i] = 2/3*d[i-1] + 1/3*k[i]
        j[i] = 3*k[i] - 2*d[i]
    return k, d, j

def atr_calc(highs, lows, closes, n=14):
    """计算ATR(14) - 波动率"""
    L = len(closes)
    if L < n+1: return [None]*L
    tr = [None]*L
    for i in range(1, L):
        tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
    atr = [None]*L
    for i in range(n, L):
        atr[i] = sum(tr[i-n+1:i+1])/n
    return atr

def load_all_stocks():
    """加载所有股票数据"""
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
    all_data = {}
    loaded = 0
    skipped = 0
    for fn in files:
        fp = os.path.join(CACHE_DIR, fn)
        try:
            with open(fp, 'rb') as f:
                raw = f.read()
            recs = json.loads(raw.decode('utf-8'))
            if not isinstance(recs, list) or len(recs) < 80:
                skipped += 1
                continue
            code = fn.replace('.json', '')
            all_data[code] = recs
            loaded += 1
            if loaded % 500 == 0:
                print(f"  已加载 {loaded} / {len(files)}...")
        except:
            skipped += 1
    print(f"✅ 加载完成：{loaded}只股票（跳过{skipped}只）")
    return all_data

# ═══ 特征提取 ═══
def extract_features(code, recs, i):
    """提取第i天的所有特征"""
    r = recs[i]
    close = r['close']; open_p = r['open']; high = r['high']; low = r['low']; vol = r['volume']
    date = r['date']
    
    # 收盘价在当日范围的位置
    day_range = high - low
    close_pos_day = (close - low) / day_range * 100 if day_range > 0 else 50
    
    # 当日涨跌幅
    if i > 0:
        pct_chg = (close - recs[i-1]['close']) / recs[i-1]['close'] * 100
    else:
        pct_chg = 0
    
    # 前一日涨跌幅
    pre_pct = (recs[i-1]['close'] - recs[i-2]['close']) / recs[i-2]['close'] * 100 if i >= 2 else 0
    
    # 实体
    body = abs(close - open_p)
    body_pct = body / open_p * 100
    is_yang = close > open_p  # 阳线
    upper_shadow = high - max(close, open_p)
    lower_shadow = min(close, open_p) - low
    shadow_ratio = upper_shadow / (upper_shadow + lower_shadow + 1) * 100  # 上影线占比
    
    # --- 均线 ---
    closes = [x['close'] for x in recs[:i+1]]
    highs = [x['high'] for x in recs[:i+1]]
    lows = [x['low'] for x in recs[:i+1]]
    opens = [x['open'] for x in recs[:i+1]]
    volumes = [x['volume'] for x in recs[:i+1]]
    
    ma5 = ma(closes, 5); ma10 = ma(closes, 10); ma20 = ma(closes, 20); ma60 = ma(closes, 60)
    
    # MA5斜率（5日）
    ma5_slope = None
    if i >= 4 and ma5[i] and ma5[i-4]:
        ma5_slope = (ma5[i] - ma5[i-4]) / ma5[i-4] * 100
    
    # MA5斜率（3日）
    ma5_slope_3 = None
    if i >= 2 and ma5[i] and ma5[i-2]:
        ma5_slope_3 = (ma5[i] - ma5[i-2]) / ma5[i-2] * 100
    
    # 收盘价在MA5/MA10/MA20/MA60的位置
    close_pos_ma5 = (close - ma5[i]) / ma5[i] * 100 if ma5[i] and ma5[i] > 0 else None
    close_pos_ma10 = (close - ma10[i]) / ma10[i] * 100 if ma10[i] and ma10[i] > 0 else None
    close_pos_ma20 = (close - ma20[i]) / ma20[i] * 100 if ma20[i] and ma20[i] > 0 else None
    close_pos_ma60 = (close - ma60[i]) / ma60[i] * 100 if ma60[i] and ma60[i] > 0 else None
    
    # 站上均线
    above_ma5 = close > ma5[i] if ma5[i] else None
    above_ma10 = close > ma10[i] if ma10[i] else None
    above_ma20 = close > ma20[i] if ma20[i] else None
    above_ma60 = close > ma60[i] if ma60[i] else None
    
    # 均线多头排列
    bullish_ma = None
    if ma5[i] and ma10[i] and ma20[i]:
        bullish_ma = ma5[i] > ma10[i] > ma20[i]
    
    # 均线发散（MA5 - MA10的差距）
    ma5_ma10_gap = None
    if ma5[i] and ma10[i]:
        ma5_ma10_gap = (ma5[i] - ma10[i]) / ma10[i] * 100
    
    # --- MACD ---
    dif, dea, macd = macd_full(closes)
    macd_val = macd[i] if macd and macd[i] is not None else None
    dif_v = dif[i] if dif and dif[i] is not None else None
    dea_v = dea[i] if dea and dea[i] is not None else None
    
    macd_golden = None  # 金叉
    if i >= 1 and dif and dea and dif[i] and dea[i] and dif[i-1] and dea[i-1]:
        macd_golden = dif[i-1] <= dea[i-1] and dif[i] > dea[i]
    
    # MACD柱斜率
    macd_slope = None
    if i >= 2 and macd and macd[i] and macd[i-1] and macd[i-2] and macd[i-1] and macd[i-2]:
        if macd[i] is not None and macd[i-1] is not None and macd[i-2] is not None:
            macd_slope = (macd[i] - macd[i-2]) / (abs(macd[i-2]) + 0.001)
    
    # MACD在零轴上下
    macd_above_zero = dif_v > 0 if dif_v is not None else None
    
    # --- KDJ ---
    k, d, j = kdj_calc(highs, lows, closes)
    k_v = k[i] if k else None
    d_v = d[i] if d else None
    j_v = j[i] if j else None
    
    kdj_golden = None
    if i >= 1 and k and d and k[i] and d[i] and k[i-1] and d[i-1]:
        kdj_golden = k[i-1] <= d[i-1] and k[i] > d[i]
    
    # J值上升
    j_rising = None
    if i >= 1 and j and j[i] is not None and j[i-1] is not None:
        j_rising = j[i] > j[i-1]
    
    # --- 量价 ---
    if i >= 5:
        avg_vol_5 = sum(volumes[i-4:i+1]) / 5
        avg_vol_10 = sum(volumes[i-9:i+1]) / 10 if len(volumes) >= i+1-9 else volumes[0]
    else:
        avg_vol_5 = sum(volumes) / len(volumes)
        avg_vol_10 = sum(volumes) / len(volumes)
    
    # 量比（当日成交量 / 5日均量）
    vol_ratio_5 = vol / avg_vol_5 if avg_vol_5 > 0 else None
    
    # 量比（当日成交量 / 10日均量）
    vol_ratio_10 = vol / avg_vol_10 if avg_vol_10 > 0 else None
    
    # --- 波动率 (ATR) ---
    atr = atr_calc(highs, lows, closes)
    atr_val = atr[i] if atr and atr[i] else None
    atr_pct = atr_val / close * 100 if atr_val and close > 0 else None  # ATR百分比
    
    # --- 位置分析 ---
    # 在近20日/60日高低点中的位置
    if i >= 19:
        high20 = max(highs[i-19:i+1])
        low20 = min(lows[i-19:i+1])
    else:
        high20 = max(highs); low20 = min(lows)
    pos20 = (close - low20) / (high20 - low20) * 100 if high20 > low20 else 50
    
    if i >= 59:
        high60 = max(highs[i-59:i+1])
        low60 = min(lows[i-59:i+1])
    else:
        high60 = max(highs); low60 = min(lows)
    pos60 = (close - low60) / (high60 - low60) * 100 if high60 > low60 else 50
    
    # --- 换手率（以量代替，无流通盘数据）---
    # 用成交量变化来代替
    
    # --- 次日表现 ---
    next_open = recs[i+1]['open'] if i+1 < len(recs) else None
    next_close = recs[i+1]['close'] if i+1 < len(recs) else None
    next_high = recs[i+1]['high'] if i+1 < len(recs) else None
    next_low = recs[i+1]['low'] if i+1 < len(recs) else None
    
    if next_close and close > 0:
        next_day_pct = (next_close - close) / close * 100
        next_day_high_pct = (next_high - close) / close * 100 if next_high else 0
        next_day_open_pct = (next_open - close) / close * 100 if next_open else 0
    else:
        next_day_pct = None
        next_day_high_pct = None
        next_day_open_pct = None
    
    # 次日能否涨2.5%以上（盘中最高）
    next_win_25 = next_day_high_pct >= 2.5 if next_day_high_pct is not None else None
    
    # 次日收盘能否涨2.5%以上
    next_close_win_25 = next_day_pct >= 2.5 if next_day_pct is not None else None
    
    features = {
        'code': code, 'date': date,
        'close': close, 'open': open_p, 'high': high, 'low': low, 'vol': vol,
        'pct_chg': pct_chg,           # 当日涨跌幅
        'pre_pct': pre_pct,           # 前日涨跌幅
        'body_pct': body_pct,         # 实体%
        'is_yang': is_yang,           # 是否阳线
        'close_pos_day': close_pos_day,  # 收盘在当日范围位置
        'shadow_ratio': shadow_ratio,    # 上影线占比
        'ma5_slope': ma5_slope,        # MA5斜率(5日)
        'ma5_slope_3': ma5_slope_3,    # MA5斜率(3日)
        'close_pos_ma5': close_pos_ma5,
        'close_pos_ma10': close_pos_ma10,
        'close_pos_ma20': close_pos_ma20,
        'close_pos_ma60': close_pos_ma60,
        'above_ma5': above_ma5,
        'above_ma10': above_ma10,
        'above_ma20': above_ma20,
        'above_ma60': above_ma60,
        'bullish_ma': bullish_ma,      # 均线多头
        'ma5_ma10_gap': ma5_ma10_gap,  # 5-10日线差距
        'macd_val': macd_val,
        'dif_val': dif_v,
        'dea_val': dea_v,
        'macd_golden': macd_golden,    # MACD金叉
        'macd_slope': macd_slope,      # MACD柱斜率
        'macd_above_zero': macd_above_zero,  # DIF在零轴上
        'k_val': k_v, 'd_val': d_v, 'j_val': j_v,
        'kdj_golden': kdj_golden,      # KDJ金叉
        'j_rising': j_rising,          # J值上升
        'vol_ratio_5': vol_ratio_5,    # 量比(5日均量)
        'vol_ratio_10': vol_ratio_10,  # 量比(10日均量)
        'atr_pct': atr_pct,            # ATR波动率%
        'pos20': pos20,                # 20日位置
        'pos60': pos60,                # 60日位置
        # 次日表现（用于分类）
        'next_day_pct': next_day_pct,
        'next_day_high_pct': next_day_high_pct,
        'next_day_open_pct': next_day_open_pct,
        'next_win_25': next_win_25,      # 次日最高涨2.5%+
        'next_close_win_25': next_close_win_25,  # 次日收盘涨2.5%+
    }
    return features

# ═══ 统计比较 ═══
def analyze_feature(feat_name, win_vals, lose_vals, feat_type='numeric'):
    """比较成功组和失败组的特征分布"""
    if feat_type == 'numeric':
        win_valid = [v for v in win_vals if v is not None]
        lose_valid = [v for v in lose_vals if v is not None]
        
        if not win_valid or not lose_valid:
            return None
        
        win_avg = sum(win_valid) / len(win_valid)
        lose_avg = sum(lose_valid) / len(lose_valid)
        
        # 简单区分度
        diff = win_avg - lose_avg
        # 用T值衡量（简化版）
        win_std = (sum((v-win_avg)**2 for v in win_valid) / len(win_valid))**0.5 if len(win_valid) > 1 else 0
        lose_std = (sum((v-lose_avg)**2 for v in lose_valid) / len(lose_valid))**0.5 if len(lose_valid) > 1 else 0
        
        # 计算一个简单的区分指标
        pooled_std = ((win_std**2 + lose_std**2)/2)**0.5
        t_value = diff / (pooled_std + 0.0001) if pooled_std > 0 else 0
        
        # 百分位数比较
        win_sorted = sorted(win_valid)
        lose_sorted = sorted(lose_valid)
        win_p25 = win_sorted[int(len(win_sorted)*0.25)]
        win_p50 = win_sorted[int(len(win_sorted)*0.5)]
        win_p75 = win_sorted[int(len(win_sorted)*0.75)]
        lose_p25 = lose_sorted[int(len(lose_sorted)*0.25)]
        lose_p50 = lose_sorted[int(len(lose_sorted)*0.5)]
        lose_p75 = lose_sorted[int(len(lose_sorted)*0.75)]
        
        # 最优分界点（两个分布重叠最少的位置）
        # 简单方法：用中点
        best_threshold = (win_avg + lose_avg) / 2
        # 在这个阈值下的准确率
        win_above = sum(1 for v in win_valid if v >= best_threshold) / len(win_valid) * 100
        lose_below = sum(1 for v in lose_valid if v < best_threshold) / len(lose_valid) * 100
        accuracy = (win_above * len(win_valid) + lose_below * len(lose_valid)) / (len(win_valid) + len(lose_valid))
        
        return {
            'win_avg': round(win_avg, 2), 'lose_avg': round(lose_avg, 2),
            'diff': round(diff, 2),
            'win_p25': round(win_p25, 2), 'win_p50': round(win_p50, 2), 'win_p75': round(win_p75, 2),
            'lose_p25': round(lose_p25, 2), 'lose_p50': round(lose_p50, 2), 'lose_p75': round(lose_p75, 2),
            't_value': round(t_value, 3),
            'win_n': len(win_valid), 'lose_n': len(lose_valid),
            'best_threshold': round(best_threshold, 2),
            'accuracy': round(accuracy, 1),
        }
    elif feat_type == 'bool':
        win_true = sum(1 for v in win_vals if v is True)
        win_total = len(win_vals)
        lose_true = sum(1 for v in lose_vals if v is True)
        lose_total = len(lose_vals)
        if win_total == 0 or lose_total == 0:
            return None
        win_rate = win_true / win_total * 100
        lose_rate = lose_true / lose_total * 100
        lift = win_rate / (lose_rate + 0.001)
        return {
            'win_rate': round(win_rate, 1), 'lose_rate': round(lose_rate, 1),
            'lift': round(lift, 2), 'win_n': win_total, 'lose_n': lose_total
        }

# ═══ 主分析 ═══
def main():
    print("=" * 60)
    print("🐷 小猪策略 — 特征分析")
    print(f"⏰ {time.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    print("\n📡 加载数据...")
    all_data = load_all_stocks()
    
    print("\n🔍 提取特征（每只股票逐日计算）...")
    all_features = []
    win_features = []   # 次日高开/盘中达到2.5%+的
    lose_features = []  # 没达到的
    total_days = 0
    stock_cnt = 0
    
    for code, recs in all_data.items():
        stock_cnt += 1
        if stock_cnt % 1000 == 0:
            print(f"  已分析 {stock_cnt}/{len(all_data)} 只股票，{total_days}个交易日")
        
        for i in range(60, len(recs)-1):  # 跳过前60天（技术指标预热），留后一天
            feats = extract_features(code, recs, i)
            if feats['next_win_25'] is None:
                continue
            total_days += 1
            all_features.append(feats)
            if feats['next_win_25']:
                win_features.append(feats)
            else:
                lose_features.append(feats)
    
    print(f"\n📊 共分析 {total_days} 个交易日（{len(all_data)}只股票）")
    print(f"✅ 次日涨2.5%+（盘中）：{len(win_features)} 次 ({len(win_features)/total_days*100:.1f}%)")
    print(f"❌ 未达2.5%：{len(lose_features)} 次")
    
    # ═══ 分析各特征 ═══
    print("\n" + "=" * 60)
    print("📈 数值型特征对比（赢家 vs 输家）")
    print("=" * 60)
    
    numeric_feats = [
        ('pct_chg', '当日涨跌幅%'),
        ('pre_pct', '前日涨跌幅%'),
        ('body_pct', '实体%'),
        ('close_pos_day', '收盘在当日位置%'),
        ('shadow_ratio', '上影线占比%'),
        ('close_pos_ma5', '收盘在MA5上方%'),
        ('close_pos_ma10', '收盘在MA10上方%'),
        ('close_pos_ma20', '收盘在MA20上方%'),
        ('close_pos_ma60', '收盘在MA60上方%'),
        ('ma5_slope', 'MA5斜率(5日)%'),
        ('ma5_slope_3', 'MA5斜率(3日)%'),
        ('ma5_ma10_gap', 'MA5-MA10差距%'),
        ('k_val', 'K值'),
        ('d_val', 'D值'),
        ('j_val', 'J值'),
        ('vol_ratio_5', '量比(5日均量)'),
        ('vol_ratio_10', '量比(10日均量)'),
        ('atr_pct', 'ATR波动率%'),
        ('pos20', '20日位置%'),
        ('pos60', '60日位置%'),
        ('macd_val', 'MACD柱值'),
        ('dif_val', 'DIF值'),
        ('macd_slope', 'MACD柱斜率'),
    ]
    
    results = []
    for key, name in numeric_feats:
        win_vals = [f[key] for f in win_features]
        lose_vals = [f[key] for f in lose_features]
        r = analyze_feature(key, win_vals, lose_vals)
        if r:
            results.append((key, name, r))
    
    # 按t值绝对值排序（区分度）
    results.sort(key=lambda x: abs(x[2]['t_value']), reverse=True)
    
    print(f"\n{'特征':<24} {'赢家中值':>10} {'输家中值':>10} {'差值':>8} {'T值':>8} {'阈值':>8} {'准确率':>8}")
    print("-" * 80)
    for key, name, r in results[:15]:
        print(f"{name:<24} {r['win_p50']:>8.1f}% {r['lose_p50']:>8.1f}% {r['diff']:>+7.1f} {r['t_value']:>+7.3f} {r['best_threshold']:>7.1f} {r['accuracy']:>6.1f}%")
    
    # ═══ 布尔型特征分析 ═══
    print("\n" + "=" * 60)
    print("🎯 布尔型特征对比（赢家率 vs 输家率）")
    print("=" * 60)
    
    bool_feats = [
        ('is_yang', '阳线'),
        ('above_ma5', '站上MA5'),
        ('above_ma10', '站上MA10'),
        ('above_ma20', '站上MA20'),
        ('above_ma60', '站上MA60'),
        ('bullish_ma', '均线多头'),
        ('macd_golden', 'MACD金叉'),
        ('macd_above_zero', 'DIF零轴上'),
        ('kdj_golden', 'KDJ金叉'),
        ('j_rising', 'J值上升'),
    ]
    
    print(f"\n{'特征':<24} {'赢家率':>10} {'输家率':>10} {'提升':>8}")
    print("-" * 54)
    for key, name in bool_feats:
        win_vals = [f[key] for f in win_features]
        lose_vals = [f[key] for f in lose_features]
        r = analyze_feature(key, win_vals, lose_vals, 'bool')
        if r:
            print(f"{name:<24} {r['win_rate']:>8.1f}% {r['lose_rate']:>8.1f}% {r['lift']:>+7.2f}x")
    
    # ═══ 多条件组合分析 ═══
    print("\n" + "=" * 60)
    print("🧩 条件组合胜率分析")
    print("=" * 60)
    
    # 测试常见组合
    combos = [
        ("均线多头", lambda f: f['bullish_ma'] == True),
        ("站上MA5+MA10+MA20", lambda f: f['above_ma5'] == True and f['above_ma10'] == True and f['above_ma20'] == True),
        ("均线多头+MACD金叉", lambda f: f['bullish_ma'] == True and f['macd_golden'] == True),
        ("均线多头+量比>1", lambda f: f['bullish_ma'] == True and (f['vol_ratio_5'] or 0) > 1),
        ("均线多头+量比<3", lambda f: f['bullish_ma'] == True and (f['vol_ratio_5'] or 99) < 3),
        ("阳线+均线多头", lambda f: f['is_yang'] == True and f['bullish_ma'] == True),
        ("J值上升+均线多头", lambda f: f['j_rising'] == True and f['bullish_ma'] == True),
        ("J值>50+均线多头", lambda f: (f['j_val'] or 0) > 50 and f['bullish_ma'] == True),
        ("MACD金叉+均线多头+阳线", lambda f: f['macd_golden'] == True and f['bullish_ma'] == True and f['is_yang'] == True),
        ("站上MA20+MACD金叉", lambda f: f['above_ma20'] == True and f['macd_golden'] == True),
        ("20日位>40%+均线多头", lambda f: (f['pos20'] or 0) > 40 and f['bullish_ma'] == True),
        ("20日位<80%+均线多头", lambda f: (f['pos20'] or 100) < 80 and f['bullish_ma'] == True),
        ("位置40~80%+均线多头+阳线", lambda f: 40 <= (f['pos20'] or 0) <= 80 and f['bullish_ma'] == True and f['is_yang'] == True),
        ("位置40~80%+均线多头+量比<3", lambda f: 40 <= (f['pos20'] or 0) <= 80 and f['bullish_ma'] == True and (f['vol_ratio_5'] or 99) < 3),
        # 更宽松的组合（针对2024）
        ("位置<80%+均线多头+J值上升", lambda f: (f['pos20'] or 100) < 80 and f['bullish_ma'] == True and f['j_rising'] == True),
        ("位置<80%+站上MA20+阳线", lambda f: (f['pos20'] or 100) < 80 and f['above_ma20'] == True and f['is_yang'] == True),
        ("MA5斜率>0+均线多头", lambda f: (f['ma5_slope'] or 0) > 0 and f['bullish_ma'] == True),
        ("DIF零轴上+均线多头", lambda f: f['macd_above_zero'] == True and f['bullish_ma'] == True),
    ]
    
    print(f"\n{'组合条件':<30} {'样本数':>8} {'次日2.5%+':>12} {'胜率':>8}")
    print("-" * 60)
    
    for name, condition in combos:
        win_cnt = sum(1 for f in win_features if condition(f))
        lose_cnt = sum(1 for f in lose_features if condition(f))
        total = win_cnt + lose_cnt
        rate = win_cnt / total * 100 if total > 0 else 0
        # 总体占比
        total_win = len(win_features)
        coverage = win_cnt / total_win * 100 if total_win > 0 else 0
        print(f"{name:<30} {total:>8} {win_cnt:>8}/{total:<4} {rate:>6.1f}% (覆盖{coverage:.0f}%)")
    
    # ═══ 各个特征的最优阈值 ═══
    print("\n" + "=" * 60)
    print("🔑 各特征最优阈值（最大化准确率）")
    print("=" * 60)
    print(f"\n{'特征':<24} {'阈值':>8} {'赢家≥阈值':>12} {'输家<阈值':>12} {'准确率':>8}")
    print("-" * 66)
    for key, name, r in results[:12]:
        print(f"{name:<24} {r['best_threshold']:>7.1f} {r['accuracy']:>20.1f}%")
    
    # ═══ 保存结果 ═══
    print("\n💾 保存分析结果...")
    out = {
        'total_days': total_days,
        'win_cnt': len(win_features),
        'lose_cnt': len(lose_features),
        'win_rate': round(len(win_features)/total_days*100, 1),
    }
    print(f"\n✅ 分析完成！基础数据：{total_days}日，赢家{len(win_features)}次({out['win_rate']}%)")

if __name__ == '__main__':
    main()
