"""
全维度评分策略（用于尾盘打板/小猪策略）
从K线数据提取：多头排列、周线上涨、月线上涨、连续小涨、量能趋势
加权组合找最优
"""
import pickle, json, os, time, sys
from datetime import datetime
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

date_index = {d: i for i, d in enumerate(dates)}
kline_cache = {}  # code -> full kline list

def wait_until_complete(all_kline_loaded):
    """不再加载K线，等待完成"""
    pass

def load_kline_full(code):
    """加载完整K线数据"""
    if code in kline_cache:
        return kline_cache[code]
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp):
        kline_cache[code] = None
        return None
    try:
        with open(fp, 'r') as f:
            kdata = json.load(f)
        kline_cache[code] = kdata
        return kdata
    except:
        kline_cache[code] = None
        return None

def ma(data_list, period):
    """简单移动平均"""
    if len(data_list) < period:
        return None
    return sum(data_list[-period:]) / period

def compute_features(kdata, cur_date_str):
    """
    从K线数据计算所有技术特征
    kdata: [{date, open, close, high, low, volume}, ...] 按时间升序
    cur_date_str: 当前日期
    """
    # 找到当前日期索引
    idx = -1
    for i, d in enumerate(kdata):
        if d['date'] == cur_date_str:
            idx = i
            break
    if idx < 0:
        return None
    
    # 需要至少60个交易日的数据
    if idx < 60:
        return None
    
    # 提取最近数据
    recent = kdata[:idx+1]
    closes = [d['close'] for d in recent]
    highs = [d['high'] for d in recent]
    lows = [d['low'] for d in recent]
    volumes = [d['volume'] for d in recent]
    dates_list = [d['date'] for d in recent]
    
    # ============ 1. 日线多头排列 ============
    ma5 = ma(closes, 5)
    ma10 = ma(closes, 10)
    ma20 = ma(closes, 20)
    ma60 = ma(closes, 60)
    
    bull_alignment = 0
    if all(v is not None for v in [ma5, ma10, ma20, ma60]):
        if closes[-1] > ma5 > ma10 > ma20 > ma60:
            bull_alignment = 3  # 强势多头（收盘在MA5之上）
        elif ma5 > ma10 > ma20 > ma60:
            bull_alignment = 2  # 标准多头排列
        elif ma5 > ma10 and ma10 > ma20:
            bull_alignment = 1  # 短期多头
    
    # ============ 2. 连续小涨 ============
    consecutive_gains = 0
    total_small_gain_pct = 0
    for i in range(idx, max(idx-12, -1), -1):
        if i == idx:
            p = (closes[i] / closes[i-1] - 1) * 100 if i > 0 else 0
            if 0 < p < 4:
                consecutive_gains += 1
                total_small_gain_pct += p
        else:
            p_daily = (closes[i] / closes[i-1] - 1) * 100 if i > 0 else 0
            if 0 < p_daily < 4:
                consecutive_gains += 1
                total_small_gain_pct += p_daily
            else:
                break
    
    # ============ 3. 周线趋势 ============
    # 按ISO周聚合
    weeks_data = []
    cur_week_key = None
    week_close_vals = []
    
    for i in range(len(dates_list)):
        dt = datetime.strptime(dates_list[i], '%Y-%m-%d')
        iso = dt.isocalendar()
        week_key = f"{iso[0]}-W{iso[1]:02d}"
        if week_key != cur_week_key:
            if cur_week_key is not None and week_close_vals:
                weeks_data.append(week_close_vals[-1])
            cur_week_key = week_key
            week_close_vals = [closes[i]]
        else:
            week_close_vals.append(closes[i])
    if week_close_vals:
        weeks_data.append(week_close_vals[-1])
    
    weekly_up = 0
    if len(weeks_data) >= 12:
        w_ma5 = ma(weeks_data, 5)
        w_ma10 = ma(weeks_data, 10)
        if w_ma5 and w_ma10:
            if weeks_data[-1] > w_ma5 > w_ma10 and weeks_data[-1] > weeks_data[-2] if len(weeks_data) >= 2 else True:
                weekly_up = 2  # 周线强势上涨
            elif weeks_data[-1] > w_ma5:
                weekly_up = 1  # 周线温和上涨
    
    # ============ 4. 月线趋势 ============
    months_data = []
    cur_month = None
    month_vals = []
    
    for i in range(len(dates_list)):
        month_key = dates_list[i][:7]
        if month_key != cur_month:
            if cur_month is not None and month_vals:
                months_data.append(month_vals[-1])
            cur_month = month_key
            month_vals = [closes[i]]
        else:
            month_vals.append(closes[i])
    if month_vals:
        months_data.append(month_vals[-1])
    
    monthly_up = 0
    if len(months_data) >= 4:
        m_ma3 = ma(months_data, 3)
        if m_ma3 and months_data[-1] > m_ma3:
            if len(months_data) >= 3 and months_data[-1] > months_data[-2] > months_data[-3]:
                monthly_up = 2  # 月线连续上涨
            else:
                monthly_up = 1  # 月线上涨
    
    # ============ 5. 量能趋势（基金涌入信号） ============
    vol_5 = ma(volumes, 5)
    vol_20 = ma(volumes, 20)
    vol_60 = ma(volumes, 60)
    
    volume_trend = 0
    if vol_5 and vol_20:
        if vol_5 > vol_20 * 1.5:
            volume_trend = 3  # 巨量放大（主力涌入）
        elif vol_5 > vol_20 * 1.3:
            volume_trend = 2  # 明显放量
        elif vol_5 > vol_20 * 1.1:
            volume_trend = 1  # 温和放量
    
    # 量能持续增长（5日均量 > 20日均量 > 60日均量）
    vol_sustained = 0
    if vol_5 and vol_20 and vol_60:
        if vol_5 > vol_20 > vol_60:
            vol_sustained = 2
        elif vol_5 > vol_20:
            vol_sustained = 1
    
    return {
        'bull_alignment': bull_alignment,
        'consecutive_gains': consecutive_gains,
        'total_small_gain_pct': total_small_gain_pct,
        'weekly_up': weekly_up,
        'monthly_up': monthly_up,
        'volume_trend': volume_trend,
        'vol_sustained': vol_sustained,
        'ma5': ma5, 'ma10': ma10, 'ma20': ma20, 'ma60': ma60,
    }

# ============ M1过滤函数 ============
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

# ============ 评分函数（带权重参数） ============
def full_score(s, features, prev_gain, weights):
    """
    weights = {
        'p': 1.0,         # 涨跌幅权重
        'atr': 1.5,       # ATR权重
        'dif': 0.5,       # DIF权重
        'cl': 0.02,       # 收盘位权重
        'bull': 3,        # 多头排列加分
        'small_gain': 0.5, # 连续小涨(每天加分)
        'weekly': 4,       # 周线上涨加分
        'monthly': 5,      # 月线上涨加分
        'volume': 2,       # 量能趋势加分
        'vol_sustain': 3,  # 量能持续增长加分
    }
    """
    p = s.get('p', 0)
    a = s.get('a', 0)
    dif = s.get('dif_val', 0)
    cl = s.get('cl', 50)
    
    # 基础分
    score = (p * weights.get('p', 1.0) + 
             a * weights.get('atr', 1.5) + 
             dif * weights.get('dif', 0.5) + 
             cl * weights.get('cl', 0.02))
    
    # 上影扣分
    if cl < 60:
        score -= weights.get('shadow_penalty', 3)
    
    # 前一天涨幅扣分（保留）
    if prev_gain is not None:
        if prev_gain >= 8:
            score -= 15
        elif prev_gain > 7:
            score -= 8
        elif prev_gain > 6:
            score -= 5
    
    # 新加的特征加分
    if features:
        # 多头排列
        score += features['bull_alignment'] * weights.get('bull', 3)
        
        # 连续小涨（最多算8天）
        score += min(features['consecutive_gains'], 8) * weights.get('small_gain', 0.5)
        
        # 周线上涨
        score += features['weekly_up'] * weights.get('weekly', 4)
        
        # 月线上涨
        score += features['monthly_up'] * weights.get('monthly', 5)
        
        # 量能放大
        score += features['volume_trend'] * weights.get('volume', 2)
        
        # 量能持续增长
        score += features['vol_sustained'] * weights.get('vol_sustain', 3)
    
    return score

# ============ 获取前一天涨幅 ============
def get_prev_gain(code, cur_date):
    idx = date_index.get(cur_date)
    if idx is None or idx == 0:
        return None
    prev_date = dates[idx - 1]
    prev_stocks = data.get(prev_date, [])
    for s in prev_stocks:
        if s['code'] == code:
            return s['p']
    
    # 从K线取
    kdata = load_kline_full(code)
    if kdata is None:
        return None
    
    # 找前一天的索引
    prev_k_idx = -1
    for i, d in enumerate(kdata):
        if d['date'] == prev_date:
            prev_k_idx = i
            break
    if prev_k_idx < 1:
        return None
    
    prev_close = kdata[prev_k_idx]['close']
    prev_prev_close = kdata[prev_k_idx - 1]['close']
    return (prev_close / prev_prev_close - 1) * 100

def get_prev_gain_simple(code, cur_date):
    """只从缓存取前一天涨幅（快）"""
    idx = date_index.get(cur_date)
    if idx is None or idx == 0:
        return None
    prev_date = dates[idx - 1]
    prev_stocks = data.get(prev_date, [])
    for s in prev_stocks:
        if s['code'] == code:
            return s['p']
    return None

# ============ 回测 ============
def backtest(weights, name="默认"):
    print(f'\n===== {name} =====')
    t0 = time.time()
    
    total = 0
    wins = 0
    
    # 统计用
    feature_stats = {
        'bull_alignment': 0, 'has_bull': 0,
        'consecutive_gains_total': 0, 'has_gains': 0,
        'weekly_up_total': 0, 'has_weekly': 0,
        'monthly_up_total': 0, 'has_monthly': 0,
        'volume_trend_total': 0, 'has_volume': 0,
    }
    kline_loaded = 0
    missing_features = 0
    
    for date in dates:
        stocks = data[date]
        filtered = []
        
        for s in stocks:
            code = s['code']
            ri = real.get(code)
            if not m1_filter(s, ri):
                continue
            
            prev_gain = get_prev_gain_simple(code, date)
            kdata = load_kline_full(code)
            
            features = None
            if kdata:
                features = compute_features(kdata, date)
                if features is None:
                    missing_features += 1
            
            if features:
                kline_loaded += 1
                feature_stats['bull_alignment'] += features['bull_alignment']
                if features['bull_alignment'] > 0: feature_stats['has_bull'] += 1
                feature_stats['consecutive_gains_total'] += features['consecutive_gains']
                if features['consecutive_gains'] > 0: feature_stats['has_gains'] += 1
                feature_stats['weekly_up_total'] += features['weekly_up']
                if features['weekly_up'] > 0: feature_stats['has_weekly'] += 1
                feature_stats['monthly_up_total'] += features['monthly_up']
                if features['monthly_up'] > 0: feature_stats['has_monthly'] += 1
                feature_stats['volume_trend_total'] += features['volume_trend']
                if features['volume_trend'] > 0: feature_stats['has_volume'] += 1
            
            score = full_score(s, features, prev_gain, weights)
            n = s.get('n', 0) or 0
            filtered.append((score, code, s, n))
        
        if not filtered:
            continue
        
        filtered.sort(key=lambda x: -x[0])
        champ_n = filtered[0][3]
        total += 1
        if champ_n >= 2.5:
            wins += 1
    
    rate = wins / total * 100 if total > 0 else 0
    elapsed = time.time() - t0
    
    print(f'回测天数: {total} | 胜率: {wins}/{total} = {rate:.1f}% ({elapsed:.1f}s)')
    print(f'  K线加载: {kline_loaded}次 | 缺失特征: {missing_features}次')
    dm = max(kline_loaded, 1)
    _hb = feature_stats.get('has_bull', 0)
    _ba = feature_stats.get('bull_alignment', 0)
    _hg = feature_stats.get('has_gains', 0)
    _cg = feature_stats.get('consecutive_gains_total', 0)
    _hw = feature_stats.get('has_weekly', 0)
    _wt = feature_stats.get('weekly_up_total', 0)
    _hm = feature_stats.get('has_monthly', 0)
    _mt = feature_stats.get('monthly_up_total', 0)
    _hv = feature_stats.get('has_volume', 0)
    _vt = feature_stats.get('volume_trend_total', 0)
    print(f"  多头排列: {_hb}次(均{_ba/dm:.2f})")
    print(f"  连续小涨: {_hg}次(均{_cg/dm:.1f}天)")
    print(f"  周线上涨: {_hw}次(均{_wt/dm:.2f})")
    print(f"  月线上涨: {_hm}次(均{_mt/dm:.2f})")
    print(f"  量能放大: {_hv}次(均{_vt/dm:.2f})")
    
    return rate, total, wins

if __name__ == '__main__':
    # ===== 基准版本（原版评分，无新增特征） =====
    base_weights = {
        'p': 1.0, 'atr': 1.5, 'dif': 0.5, 'cl': 0.02,
        'shadow_penalty': 3,
        'bull': 0, 'small_gain': 0, 'weekly': 0, 'monthly': 0,
        'volume': 0, 'vol_sustain': 0,
    }
    backtest(base_weights, "基准版（无新增特征）")
    
    # ===== 各种组合 =====
    # 第一轮：单项新增特征测试（在基准上+1项）
    print('\n--- 单项新增特征测试 ---')
    
    for feat_name, feat_key, feat_val in [
        ("+多头排列(3)", 'bull', 3),
        ("+连小涨(0.5/天)", 'small_gain', 0.5),
        ("+周线(4)", 'weekly', 4),
        ("+月线(5)", 'monthly', 5),
        ("+量能趋势(2)", 'volume', 2),
        ("+量能持续(3)", 'vol_sustain', 3),
    ]:
        w = base_weights.copy()
        w[feat_key] = feat_val
        backtest(w, f"基准+{feat_name}")
    
    print('\n--- 组合测试 ---')
    # 全部加上
    w = base_weights.copy()
    w.update({'bull': 3, 'small_gain': 0.5, 'weekly': 4, 'monthly': 5, 'volume': 2, 'vol_sustain': 3})
    backtest(w, "全部特征")
    
    # 精简版（周月线+多头）
    w = base_weights.copy()
    w.update({'bull': 3, 'weekly': 4, 'monthly': 5})
    backtest(w, "精简版(多+周+月)")
    
    # 主动量版（连续小涨+量能）
    w = base_weights.copy()
    w.update({'small_gain': 1.0, 'volume': 3, 'vol_sustain': 3})
    backtest(w, "主动量版(小涨+量)")
    
    # 分年统计
    print('\n--- 最佳版本分年 ---')
