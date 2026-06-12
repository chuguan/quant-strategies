"""
动力衰竭特征计算模块 — 从个股JSON K线文件计算多日特征
用于精准淘汰（return 0）动力衰竭股票

特征清单：
  - slope5: 5日斜率（近5天涨幅%）
  - t4_shadow: T-4上影长度（% of range）
  - t1_shadow: T-1上影长度（% of range）
  - pos_in_day: 当日收盘位置（% of day's range）
  - cons_up: 连续上涨天数
  - peak_decay: 高位衰减（T-6~T-1最高收盘 - (T-2+T-1)/2）
  - t4_pct: T-4涨跌幅
  - d1: 昨日涨跌幅

淘汰规则：
  Rule1: slope5 > 8 AND t4_shadow > 25 → 假动能/动力衰竭
  Rule2: cons_up >= 5 AND slope5 > 20 → 连涨过度（透支）
"""
import os, json

# K线缓存（全局复用）
_kline_cache = {}

def _get_kline(code, cache_dir):
    """读取个股JSON K线"""
    if code in _kline_cache:
        return _kline_cache[code]
    
    pure = code[2:] if code.startswith(('sh', 'sz')) else code
    pref = 'sh' if code.startswith('sh') else 'sz'
    
    # 支持多个缓存路径
    for base_dir in [cache_dir, 
                     os.path.join(os.path.dirname(cache_dir), 'cache'),
                     os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')]:
        fp = os.path.join(base_dir, f'{pref}{pure}.json')
        if os.path.exists(fp):
            with open(fp, 'rb') as f:
                klines = json.loads(f.read().decode('utf-8'))
            _kline_cache[code] = klines
            return klines
    
    _kline_cache[code] = None
    return None


def calc_features(code, date_str, cache_dir=None):
    """
    计算一只股票在指定日期的所有多日特征
    
    Args:
        code: 股票代码（如 'sh600000' 或 '600000'）
        date_str: 日期字符串 'YYYY-MM-DD'
        cache_dir: K线缓存目录
        
    Returns:
        dict: 特征字典，若无K线数据返回空字典
    """
    if not cache_dir:
        cache_dir = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
    
    kline = _get_kline(code, cache_dir)
    if not kline:
        return {}
    
    dates = [r['date'] for r in kline]
    if date_str not in dates:
        return {}
    
    di = dates.index(date_str)
    if di < 7:  # 需要至少7根K线
        return {}
    
    c = [r['close'] for r in kline]
    h = [r['high'] for r in kline]
    l = [r['low'] for r in kline]
    o = [r['open'] for r in kline]
    
    # ═══ 特征计算 ═══
    
    # 1. slope5: 5日斜率
    slope5 = (c[di] - c[di-5]) / c[di-5] * 100 if c[di-5] > 0 else 0
    
    # 2. T-4上影长度
    t4 = di - 4
    t4_range = h[t4] - l[t4]
    t4_shadow = (h[t4] - max(o[t4], c[t4])) / t4_range * 100 if t4_range > 0 else 0
    
    # 3. T-1上影长度
    t1 = di - 1
    t1_range = h[t1] - l[t1]
    t1_shadow = (h[t1] - max(o[t1], c[t1])) / t1_range * 100 if t1_range > 0 else 0
    
    # 4. 当日收盘位置
    day_range = h[di] - l[di]
    pos_in_day = (c[di] - l[di]) / day_range * 100 if day_range > 0 else 50
    
    # 5. T-1收盘位置
    t1_range = h[t1] - l[t1]
    t1_pos = (c[t1] - l[t1]) / t1_range * 100 if t1_range > 0 else 50
    
    # 6. 连续上涨天数
    cons_up = 0
    for i in range(1, min(10, di + 1)):
        if c[di - i + 1] > c[di - i]:
            cons_up += 1
        else:
            break
    
    # 7. peak_decay: 高位衰减
    peak = max(c[di-6:di])
    avg_last2 = (c[di-2] + c[di-1]) / 2
    peak_decay = peak - avg_last2 if avg_last2 > 0 else 0
    
    # 8. T-4涨跌幅
    if di >= 5:
        t4_pct = (c[di-4] - c[di-5]) / c[di-5] * 100 if c[di-5] > 0 else 0
    else:
        t4_pct = 0
    
    # 9. 昨日涨跌幅（T-1）
    d1 = (c[di] - c[di-1]) / c[di-1] * 100 if c[di-1] > 0 else 0
    
    # 10. 前日涨跌幅（T-2）
    d2 = (c[di-1] - c[di-2]) / c[di-2] * 100 if c[di-2] > 0 else 0
    
    # 11. T-3涨跌幅
    d3 = (c[di-2] - c[di-3]) / c[di-3] * 100 if c[di-3] > 0 else 0
    
    return {
        'slope5': round(slope5, 2),
        't4_shadow': round(t4_shadow, 1),
        't1_shadow': round(t1_shadow, 1),
        'pos_in_day': round(pos_in_day, 1),
        't1_pos': round(t1_pos, 1),
        'cons_up': cons_up,
        'peak_decay': round(peak_decay, 2),
        't4_pct': round(t4_pct, 2),
        'd1': round(d1, 2),
        'd2': round(d2, 2),
        'd3': round(d3, 2),
    }


def is_momentum_exhaustion(feats, p):
    """
    动力衰竭检测 — 精准淘汰
    
    Args:
        feats: calc_features()返回的特征字典
        p: 当日涨幅%
        
    Returns:
        (bool, str): (是否动力衰竭, 原因描述)
    """
    if not feats:
        return False, ''
    
    slope5 = feats.get('slope5', 0)
    t4_shadow = feats.get('t4_shadow', 0)
    cons_up = feats.get('cons_up', 0)
    t1_shadow = feats.get('t1_shadow', 0)
    pos_in_day = feats.get('pos_in_day', 50)
    peak_decay = feats.get('peak_decay', 0)
    
    # Rule1: 假动能/动力衰竭 — 高斜率+T-4已冲高回落
    # 特征：过去5天涨了很多(slope5>8%)，但T-4已经出现长上影(>25%)
    # 说明这波上涨在4天前就开始出现分歧了
    if slope5 > 8 and t4_shadow > 25:
        return True, f'假动能衰竭: slope5={slope5}% t4_shadow={t4_shadow}%'
    
    # Rule2: 连涨过度 — 连续5天以上上涨且斜率极高
    # 特征：连涨5天+且5日涨幅>20%，动力已经释放完毕
    if cons_up >= 5 and slope5 > 20:
        return True, f'连涨过度: 连涨{cons_up}天 slope5={slope5}%'
    
    # Rule3: 高位衰减 — 峰值后大幅回落
    # 特征：6天内最高收盘比最近2天均值高很多(peak_decay>5)
    # 说明从高位回落明显
    if peak_decay > 5 and slope5 > 5 and p < 5:
        return True, f'高位衰减: peak_decay={peak_decay:.2f} slope5={slope5}%'
    
    return False, ''


def clear_cache():
    """清空K线缓存（内存节省）"""
    _kline_cache.clear()
