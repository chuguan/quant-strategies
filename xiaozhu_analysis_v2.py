#!/usr/bin/env python3
"""小猪策略 — 尾盘选股特征分析（优化版：采样+批量计算）"""
import json, os, sys, time
from collections import Counter, defaultdict

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# ═══ 技术指标 ═══
def calc_ma(series, periods):
    """批量计算多个均线"""
    n = len(series)
    result = {}
    for p in periods:
        ma = [None] * n
        for i in range(p-1, n):
            ma[i] = sum(series[i-p+1:i+1]) / p
        result[p] = ma
    return result

def calc_macd(ps):
    n = len(ps)
    dif = [None]*n; dea = [None]*n; macd = [None]*n
    if n < 26: return dif, dea, macd
    e12 = [ps[0]]; e26 = [ps[0]]
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

def calc_kdj(highs, lows, closes, n=9):
    L = len(closes)
    k = [50.0]*L; d = [50.0]*L; j = [50.0]*L
    if L < n: return k, d, j
    for i in range(n-1, L):
        hh = max(highs[i-n+1:i+1]); ll = min(lows[i-n+1:i+1])
        rsv = 50.0 if hh == ll else (closes[i]-ll)/(hh-ll)*100
        if i > n-1:
            k[i] = 2/3*k[i-1] + 1/3*rsv
            d[i] = 2/3*d[i-1] + 1/3*k[i]
        j[i] = 3*k[i] - 2*d[i]
    return k, d, j

def calc_atr(highs, lows, closes, n=14):
    L = len(closes)
    atr = [None]*L
    if L < n+1: return atr
    tr = [None]*L
    for i in range(1, L):
        tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
    for i in range(n, L):
        atr[i] = sum(tr[i-n+1:i+1])/n
    return atr

# ═══ 批量分析函数 ═══
def analyze_stock(code, recs):
    """分析一只股票的所有交易日，返回特征列表"""
    n = len(recs)
    if n < 80: return []
    
    closes = [r['close'] for r in recs]
    highs = [r['high'] for r in recs]
    lows = [r['low'] for r in recs]
    opens = [r['open'] for r in recs]
    volumes = [r['volume'] for r in recs]
    
    # 批量计算指标
    mas = calc_ma(closes, [5, 10, 20, 60])
    ma5, ma10, ma20, ma60 = mas[5], mas[10], mas[20], mas[60]
    dif, dea, macd = calc_macd(closes)
    k, d, j = calc_kdj(highs, lows, closes)
    atr = calc_atr(highs, lows, closes)
    
    features = []
    
    for i in range(60, n-1):  # 跳过预热，留1天做次日判断
        r = recs[i]
        close = r['close']; open_p = r['open']; high = r['high']; low = r['low']; vol = r['volume']
        date = r['date']
        
        # 当日涨跌幅
        if i > 0:
            pct_chg = (close - closes[i-1]) / closes[i-1] * 100
        else:
            pct_chg = 0
        
        # 前日涨跌幅
        pre_pct = (closes[i-1] - closes[i-2]) / closes[i-2] * 100 if i >= 2 else 0
        
        # 实体
        body = abs(close - open_p)
        body_pct = body / open_p * 100
        is_yang = close > open_p
        day_range = high - low
        close_pos_day = (close - low) / day_range * 100 if day_range > 0 else 50
        
        # 上影线
        upper_shadow = high - max(close, open_p)
        lower_shadow = min(close, open_p) - low
        shadow_ratio = upper_shadow / (upper_shadow + lower_shadow + 0.001) * 100
        
        # MA5斜率
        ma5_slope = None
        if i >= 4 and ma5[i] and ma5[i-4]:
            ma5_slope = (ma5[i] - ma5[i-4]) / ma5[i-4] * 100
        
        ma5_slope_3 = None
        if i >= 2 and ma5[i] and ma5[i-2]:
            ma5_slope_3 = (ma5[i] - ma5[i-2]) / ma5[i-2] * 100
        
        # 收盘在均线上方%
        def pos_above(val, ma_v):
            return (val - ma_v) / ma_v * 100 if ma_v and ma_v > 0 else None
        
        cps = [pos_above(close, ma5[i]), pos_above(close, ma10[i]), pos_above(close, ma20[i]), pos_above(close, ma60[i])]
        
        # 站上均线
        above = [close > ma5[i] if ma5[i] else None,
                 close > ma10[i] if ma10[i] else None,
                 close > ma20[i] if ma20[i] else None,
                 close > ma60[i] if ma60[i] else None]
        
        # 均线多头
        bullish_ma = None
        if ma5[i] and ma10[i] and ma20[i]:
            bullish_ma = ma5[i] > ma10[i] > ma20[i]
        
        # MA5-MA10差距
        ma5_ma10_gap = (ma5[i] - ma10[i]) / ma10[i] * 100 if ma5[i] and ma10[i] else None
        
        # MACD
        macd_v = macd[i] if macd and macd[i] is not None else None
        dif_v = dif[i] if dif and dif[i] is not None else None
        dea_v = dea[i] if dea and dea[i] is not None else None
        
        macd_golden = None
        if i >= 1 and dif and dea and dif[i] and dea[i] and dif[i-1] and dea[i-1]:
            macd_golden = dif[i-1] <= dea[i-1] and dif[i] > dea[i]
        
        macd_slope = None
        if i >= 2 and macd and macd[i] is not None and macd[i-1] is not None and macd[i-2] is not None:
            denom = abs(macd[i-2]) + 0.001
            macd_slope = (macd[i] - macd[i-2]) / denom
        
        macd_above_zero = dif_v > 0 if dif_v is not None else None
        
        # KDJ
        k_v, d_v, j_v = (k[i] if k else None), (d[i] if d else None), (j[i] if j else None)
        
        kdj_golden = None
        if i >= 1 and k and d and k[i] and d[i] and k[i-1] and d[i-1]:
            kdj_golden = k[i-1] <= d[i-1] and k[i] > d[i]
        
        j_rising = None
        if i >= 1 and j and j[i] is not None and j[i-1] is not None:
            j_rising = j[i] > j[i-1]
        
        # 量比
        if i >= 5:
            avg_vol5 = sum(volumes[i-4:i+1]) / 5
        else:
            avg_vol5 = sum(volumes[:i+1]) / (i+1)
        vol_ratio5 = vol / avg_vol5 if avg_vol5 > 0 else None
        
        if i >= 10:
            avg_vol10 = sum(volumes[i-9:i+1]) / 10
        else:
            avg_vol10 = sum(volumes[:i+1]) / (i+1)
        vol_ratio10 = vol / avg_vol10 if avg_vol10 > 0 else None
        
        # 位置
        if i >= 19:
            high20 = max(highs[i-19:i+1]); low20 = min(lows[i-19:i+1])
        else:
            high20 = max(highs[:i+1]); low20 = min(lows[:i+1])
        pos20 = (close - low20) / (high20 - low20) * 100 if high20 > low20 else 50
        
        if i >= 59:
            high60 = max(highs[i-59:i+1]); low60 = min(lows[i-59:i+1])
        else:
            high60 = max(highs[:i+1]); low60 = min(lows[:i+1])
        pos60 = (close - low60) / (high60 - low60) * 100 if high60 > low60 else 50
        
        # ATR
        atr_v = atr[i] if atr and atr[i] else None
        atr_pct = atr_v / close * 100 if atr_v and close > 0 else None
        
        # 次日表现
        nr = recs[i+1]
        next_day_pct = (nr['close'] - close) / close * 100
        next_day_high_pct = (nr['high'] - close) / close * 100
        next_day_open_pct = (nr['open'] - close) / close * 100
        next_win_25 = next_day_high_pct >= 2.5
        
        features.append({
            'date': date, 'code': code,
            # 次日
            'next_win': next_win_25,
            'next_pct': round(next_day_pct, 2),
            'next_high': round(next_day_high_pct, 2),
            'next_open': round(next_day_open_pct, 2),
            # 当日特征
            'pct_chg': round(pct_chg, 2),
            'pre_pct': round(pre_pct, 2),
            'body_pct': round(body_pct, 2),
            'is_yang': is_yang,
            'close_pos_day': round(close_pos_day, 1),
            'shadow_ratio': round(shadow_ratio, 1),
            'ma5_slope': round(ma5_slope, 2) if ma5_slope else None,
            'ma5_slope_3': round(ma5_slope_3, 2) if ma5_slope_3 else None,
            'close_pos_ma5': round(cps[0], 2) if cps[0] else None,
            'close_pos_ma10': round(cps[1], 2) if cps[1] else None,
            'close_pos_ma20': round(cps[2], 2) if cps[2] else None,
            'close_pos_ma60': round(cps[3], 3) if cps[3] else None,
            'above_ma5': above[0], 'above_ma10': above[1],
            'above_ma20': above[2], 'above_ma60': above[3],
            'bullish_ma': bullish_ma,
            'ma5_ma10_gap': round(ma5_ma10_gap, 2) if ma5_ma10_gap else None,
            'macd_val': round(macd_v, 4) if macd_v is not None else None,
            'dif_val': round(dif_v, 4) if dif_v is not None else None,
            'dea_val': round(dea_v, 4) if dea_v is not None else None,
            'macd_golden': macd_golden,
            'macd_slope': round(macd_slope, 3) if macd_slope is not None else None,
            'macd_above_zero': macd_above_zero,
            'k_val': round(k_v, 1) if k_v is not None else None,
            'd_val': round(d_v, 1) if d_v is not None else None,
            'j_val': round(j_v, 1) if j_v is not None else None,
            'kdj_golden': kdj_golden,
            'j_rising': j_rising,
            'vol_ratio_5': round(vol_ratio5, 2) if vol_ratio5 else None,
            'vol_ratio_10': round(vol_ratio10, 2) if vol_ratio10 else None,
            'atr_pct': round(atr_pct, 2) if atr_pct else None,
            'pos20': round(pos20, 1),
            'pos60': round(pos60, 1),
        })
    
    return features

def percentile(data, p):
    """计算百分位数"""
    if not data: return None
    s = sorted(data)
    idx = int(len(s) * p / 100)
    return s[idx]

def main():
    print("=" * 60)
    print("🐷 小猪策略 — 特征分析（优化版）")
    print(f"⏰ {time.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
    # 采样策略：用全部股票，但限制为60开头和000/002开头的（沪深主板）
    # 并且随机采样50%
    import random
    random.seed(42)
    
    # 筛选沪深主板股（60/000/002）
    main_files = [f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
    # 随机采样30%
    sample_files = sorted(random.sample(main_files, max(500, int(len(main_files)*0.3))))
    print(f"📊 沪深主板股票：{len(main_files)}只，采样{len(sample_files)}只进行测试")
    
    # 还要加上过去策略选中的强势股
    extra_codes = []
    
    all_features = []
    processed = 0
    
    for fn in sample_files:
        fp = os.path.join(CACHE_DIR, fn)
        try:
            with open(fp, 'rb') as f:
                recs = json.loads(f.read().decode('utf-8'))
            if len(recs) < 80:
                continue
            code = fn.replace('.json', '')
            feats = analyze_stock(code, recs)
            all_features.extend(feats)
            processed += 1
            if processed % 200 == 0:
                print(f"  已处理 {processed}/{len(sample_files)} 只股票，收集 {len(all_features)} 条记录")
        except Exception as e:
            continue
    
    print(f"\n📊 共处理 {processed} 只股票，{len(all_features)} 个交易日样本")
    
    # 分离成功/失败
    win = [f for f in all_features if f['next_win']]
    lose = [f for f in all_features if not f['next_win']]
    print(f"✅ 次日涨2.5%+（盘中）：{len(win)} 次 ({len(win)/len(all_features)*100:.1f}%)")
    print(f"❌ 未达2.5%：{len(lose)} 次 ({len(lose)/len(all_features)*100:.1f}%)")
    
    # ═══ 数值型特征 ═══
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
        ('k_val', 'K值'), ('d_val', 'D值'), ('j_val', 'J值'),
        ('vol_ratio_5', '量比(5日均量)'),
        ('vol_ratio_10', '量比(10日均量)'),
        ('atr_pct', 'ATR波动率%'),
        ('pos20', '20日位置%'),
        ('pos60', '60日位置%'),
        ('macd_val', 'MACD柱'),
        ('dif_val', 'DIF值'),
        ('macd_slope', 'MACD柱斜率'),
        ('next_open', '次日高开%'),
        ('next_pct', '次日收盘涨幅'),
    ]
    
    print("\n" + "=" * 60)
    print("📈 数值型特征（赢家 vs 输家 中位数对比）")
    print("=" * 60)
    print(f"{'特征':<24} {'赢家中位':>10} {'输家中位':>10} {'差值':>8} {'区分度':>8}")
    print("-" * 62)
    
    # 按区分度排序（差值绝对值 / 输家std近似）
    results = []
    for key, name in numeric_feats:
        wv = [f[key] for f in win if f[key] is not None]
        lv = [f[key] for f in lose if f[key] is not None]
        if not wv or not lv: continue
        
        wp = percentile(wv, 50)
        lp = percentile(lv, 50)
        
        # 简单区分度：25%分位差 / 全距
        wp25 = percentile(wv, 25); wp75 = percentile(wv, 75)
        lp25 = percentile(lv, 25); lp75 = percentile(lv, 75)
        
        # 重叠度评估：赢家25%分位 - 输家75%分位
        overlap = max(0, min(wp75, lp75) - max(wp25, lp25))
        total_range = max(wp75, lp75) - min(wp25, lp25)
        overlap_ratio = overlap / total_range if total_range > 0 else 1
        
        discrim = round((1 - overlap_ratio) * 100, 1)
        results.append((key, name, wp, lp, round(wp-lp, 2), discrim))
    
    results.sort(key=lambda x: x[5], reverse=True)
    
    for key, name, wp, lp, diff, disc in results:
        print(f"{name:<24} {wp:>9.1f}% {lp:>9.1f}% {diff:>+7.1f} {disc:>7.1f}%")
    
    # ═══ 布尔特征 ═══
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
    
    print("\n" + "=" * 60)
    print("🎯 布尔特征（赢家率 vs 输家率）")
    print("=" * 60)
    print(f"{'特征':<24} {'赢家率':>10} {'输家率':>10} {'提升比':>8}")
    print("-" * 54)
    
    for key, name in bool_feats:
        wr = sum(1 for f in win if f[key] == True) / len(win) * 100 if win else 0
        lr = sum(1 for f in lose if f[key] == True) / len(lose) * 100 if lose else 0
        lift = wr / lr if lr > 0 else 0
        print(f"{name:<24} {wr:>8.1f}% {lr:>8.1f}% {lift:>+7.2f}x")
    
    # ═══ 条件组合 ═══
    print("\n" + "=" * 60)
    print("🧩 条件组合胜率（样本筛选后，赚2.5%+比例）")
    print("=" * 60)
    
    def eval_condition(cond_name, condition):
        w = sum(1 for f in win if condition(f))
        l = sum(1 for f in lose if condition(f))
        t = w + l
        rate = w / t * 100 if t > 0 else 0
        return w, l, t, rate
    
    combos = [
        ("均线多头", lambda f: f['bullish_ma'] == True),
        ("站上MA5+MA10+MA20", lambda f: f['above_ma5'] and f['above_ma10'] and f['above_ma20']),
        ("均线多头+MACD金叉", lambda f: f['bullish_ma'] and f['macd_golden']),
        ("均线多头+阳线", lambda f: f['bullish_ma'] and f['is_yang']),
        ("均线多头+J值上升", lambda f: f['bullish_ma'] and f['j_rising']),
        ("均线多头+量比1~3", lambda f: f['bullish_ma'] and (f['vol_ratio_5'] or 0) >= 1 and (f['vol_ratio_5'] or 99) <= 3),
        ("均线多头+J值>50", lambda f: f['bullish_ma'] and (f['j_val'] or 0) > 50),
        ("均线多头+位置40~80%", lambda f: f['bullish_ma'] and 40 <= (f['pos20'] or 0) <= 80),
        ("位置40~80%+阳线+均线多头", lambda f: 40 <= (f['pos20'] or 0) <= 80 and f['is_yang'] and f['bullish_ma']),
        ("位置40~80%+均线多头+量比<3", lambda f: 40 <= (f['pos20'] or 0) <= 80 and f['bullish_ma'] and (f['vol_ratio_5'] or 99) < 3),
        ("位置40~80%+均线多头+MA5斜>0", lambda f: 40 <= (f['pos20'] or 0) <= 80 and f['bullish_ma'] and (f['ma5_slope'] or 0) > 0),
        ("DIF零轴上+均线多头", lambda f: f['macd_above_zero'] and f['bullish_ma']),
        ("位置<80%+均线多头+J值上升", lambda f: (f['pos20'] or 100) < 80 and f['bullish_ma'] and f['j_rising']),
        ("位置<80%+站上MA20+阳线", lambda f: (f['pos20'] or 100) < 80 and f['above_ma20'] and f['is_yang']),
        ("当日涨0~4%+均线多头", lambda f: 0 <= (f['pct_chg'] or 0) <= 4 and f['bullish_ma']),
        ("当日跌0~2%+均线多头", lambda f: -2 <= (f['pct_chg'] or 0) <= 0 and f['bullish_ma']),
        ("当日涨0~4%+位置<70%+均线多头", lambda f: 0 <= (f['pct_chg'] or 0) <= 4 and (f['pos20'] or 100) < 70 and f['bullish_ma']),
        ("站上MA60+均线多头", lambda f: f['above_ma60'] and f['bullish_ma']),
        ("均线多头+MACD零轴上+K>D", lambda f: f['bullish_ma'] and f['macd_above_zero'] and (f['k_val'] or 0) > (f['d_val'] or 0)),
        ("无过滤（基准）", lambda f: True),
    ]
    
    print(f"{'组合条件':<30} {'命中/总数':>12} {'胜率':>8} {'覆盖':>8}")
    print("-" * 60)
    
    for name, cond in combos:
        w, l, t, rate = eval_condition(name, cond)
        cov = w / len(win) * 100 if win else 0
        print(f"{name:<30} {w:>5}/{t:<6} {rate:>6.1f}% {cov:>6.0f}%")
    
    # ═══ 最优单条件阈值 ═══
    print("\n" + "=" * 60)
    print("🔑 各特征最优过滤阈值")
    print("=" * 60)
    
    def find_best_threshold(key, steps=40):
        """找到使得胜率+覆盖平衡最好的阈值"""
        all_vals = [(f[key], f['next_win']) for f in all_features if f[key] is not None]
        if len(all_vals) < 100: return None
        
        vals = sorted(set(v[0] for v in all_vals))
        if len(vals) < 5: return None
        
        step = max(1, len(vals) // steps)
        best = None
        best_score = 0
        
        for idx in range(0, len(vals), step):
            t = vals[idx]
            w = sum(1 for v, n in all_vals if v >= t and n)
            l = sum(1 for v, n in all_vals if v >= t and not n)
            total = w + l
            if total < 50: continue
            rate = w / total * 100
            cov = w / len(win) * 100 if win else 0
            # 综合评分：胜率 + 覆盖/2
            score = rate + cov * 0.5
            if score > best_score:
                best_score = score
                best = (t, rate, cov, total)
        return best
    
    print(f"{'特征':<24} {'阈值':>8} {'胜率':>8} {'覆盖':>8} {'样本':>6}")
    print("-" * 56)
    
    top_keys = results[:10]
    for key, name, wp, lp, diff, disc in top_keys:
        r = find_best_threshold(key)
        if r:
            t, rate, cov, n = r
            print(f"{name:<24} {t:>7.1f} {rate:>6.1f}% {cov:>6.0f}% {n:>5}")
    
    print("\n✅ 分析完成！")

if __name__ == '__main__':
    main()
