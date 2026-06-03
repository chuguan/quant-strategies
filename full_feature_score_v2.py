"""
全维度多因子评分策略回测
特征：多头排列 + 连续小涨 + 周线上涨 + 月线上涨 + 量能持续
权重可调，自动寻优
"""
import os, pickle, json, time, sys
from datetime import datetime

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
BIG_CACHE = 'big_cache.pkl'

print('加载大缓存...', flush=True)
t0 = time.time()
with open(BIG_CACHE, 'rb') as f:
    cache = pickle.load(f)
names = cache['names']
real = cache['real']
data = cache['data']
dates = sorted(data.keys())
date_index = {d: i for i, d in enumerate(dates)}
print(f'已加载 {len(dates)} 天数据 ({time.time()-t0:.1f}s)', flush=True)

# K线缓存
kline_cache = {}

def load_kline_recent(code, cur_date, lookback=80):
    """只加载最近N条K线"""
    key = f'{code}_{cur_date[:7]}'
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
    
    result = kdata[max(0, idx-lookback):idx+1]
    kline_cache[key] = result
    return result

def compute_features(code, cur_date):
    """从K线数据计算所有技术特征（优化版）"""
    recent = load_kline_recent(code, cur_date)
    if not recent or len(recent) < 60:
        return None
    
    closes = [d['close'] for d in recent]
    volumes = [d['volume'] for d in recent]
    dates_list = [d['date'] for d in recent]
    
    # 1. 日线多头排列
    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60
    bull_ali = 3 if closes[-1] > ma5 > ma10 > ma20 > ma60 else (
              2 if ma5 > ma10 > ma20 > ma60 else (
              1 if ma5 > ma10 > ma20 else 0))
    
    # 2. 连续小涨
    gains = 0
    total_gain_pct = 0
    idx = len(recent) - 1
    for j in range(idx, max(1, idx-12), -1):
        pg = (recent[j]['close'] / recent[j-1]['close'] - 1) * 100
        if 0 < pg < 4:
            gains += 1
            total_gain_pct += pg
        else:
            break
    
    # 3. 周线（用最近16周数据）
    weeks = {}
    for d in recent:
        dt = datetime.strptime(d['date'], '%Y-%m-%d')
        iso = dt.isocalendar()
        weeks[f'{iso[0]}-W{iso[1]:02d}'] = d['close']
    wk_closes = list(weeks.values())
    weekly_up = 0
    if len(wk_closes) >= 10:
        wk5 = sum(wk_closes[-5:]) / 5
        wk10 = sum(wk_closes[-10:]) / 10
        if wk_closes[-1] > wk5 > wk10:
            weekly_up = 2
        elif wk_closes[-1] > wk5:
            weekly_up = 1
    
    # 4. 月线
    months = {}
    for d in recent:
        months[d['date'][:7]] = d['close']
    mon_closes = list(months.values())
    monthly_up = 0
    if len(mon_closes) >= 4:
        mo3 = sum(mon_closes[-3:]) / 3
        if mon_closes[-1] > mo3:
            if len(mon_closes) >= 3 and mon_closes[-1] > mon_closes[-2] > mon_closes[-3]:
                monthly_up = 2
            else:
                monthly_up = 1
    
    # 5. 量能趋势
    vol_5 = sum(volumes[-5:]) / 5
    vol_20 = sum(volumes[-20:]) / 20
    vol_60 = sum(volumes[-60:]) / 60
    volume_trend = 0
    if vol_5 > vol_20 * 1.5:
        volume_trend = 3
    elif vol_5 > vol_20 * 1.3:
        volume_trend = 2
    elif vol_5 > vol_20 * 1.1:
        volume_trend = 1
    vol_sustained = 2 if vol_5 > vol_20 > vol_60 else (1 if vol_5 > vol_20 else 0)
    
    return {
        'bull': bull_ali, 'gains': gains, 'gain_pct': total_gain_pct,
        'weekly': weekly_up, 'monthly': monthly_up,
        'volume': volume_trend, 'vol_sus': vol_sustained,
    }

def m1_filter(s, ri):
    if not ri: return False
    p = s.get('p', -999)
    if p < 1 or p > 8: return False
    if s.get('is_yang', 0) != 1: return False
    if s.get('above_ma5', 0) != 1: return False
    if (s.get('vol_ratio', 0) or 0) <= 1: return False
    hsl = ri.get('hsl', 0) or 0
    if hsl < 3 or hsl > 15: return False
    pe = ri.get('pe', 0) or 0
    if pe <= 0: return False
    sz = ri.get('shizhi', 0) or 0
    if sz >= 200: return False
    return True

def get_prev_gain(code, cur_date):
    idx = date_index.get(cur_date)
    if idx is None or idx == 0: return None
    prev_date = dates[idx - 1]
    prev_stocks = data.get(prev_date, [])
    for s in prev_stocks:
        if s['code'] == code:
            return s['p']
    # 从K线取
    recent = load_kline_recent(code, cur_date)
    if not recent: return None
    for i, d in enumerate(recent):
        if d['date'] == prev_date and i > 0:
            return (d['close'] / recent[i-1]['close'] - 1) * 100
    return None

def calc_score(s, feat, prev_gain, w):
    """综合评分：基础分 + 特征加分 + 扣分"""
    p, a, dif, cl = s['p'], s['a'], s['dif_val'], s['cl']
    score = p * w['p'] + a * w['atr'] + dif * w['dif'] + cl * w['cl']
    if cl < 60:
        score -= w.get('shadow', 3)
    
    # 前一天涨幅扣分
    if prev_gain is not None:
        if prev_gain >= 8: score -= 15
        elif prev_gain > 7: score -= 8
        elif prev_gain > 6: score -= 5
    
    # 新增特征加分
    if feat:
        score += feat['bull'] * w['bull']
        score += min(feat['gains'], 8) * w['small_gain']
        score += feat['weekly'] * w['weekly']
        score += feat['monthly'] * w['monthly']
        score += feat['volume'] * w['volume']
        score += feat['vol_sus'] * w['vol_sus']
    
    return score

def run_backtest(weights, name=''):
    """跑一次回测"""
    total = wins = changed = better = worse = 0
    missing_feat = 0
    t0 = time.time()
    
    for date in dates:
        stocks = data[date]
        filtered = []
        for s in stocks:
            code = s['code']
            ri = real.get(code)
            if not m1_filter(s, ri): continue
            
            prev_gain = get_prev_gain(code, date)
            feat = compute_features(code, date)
            if feat is None:
                missing_feat += 1
            
            score = calc_score(s, feat, prev_gain, weights)
            n = s.get('n', 0) or 0
            f_name = names.get(code, code)
            filtered.append((score, code, f_name, n))
        
        if not filtered: continue
        filtered.sort(key=lambda x: -x[0])
        total += 1
        if filtered[0][3] >= 2.5:
            wins += 1
    
    rate = wins * 100 / total if total > 0 else 0
    elapsed = time.time() - t0
    s_name = f' [{name}]' if name else ''
    print(f'{name:<12} 胜率: {wins:>3}/{total}={rate:>5.1f}%  ({elapsed:.1f}s) 缺失特征:{missing_feat}', flush=True)
    return rate

if __name__ == '__main__':
    print('\n===== 小猪策略 多因子评分回测 =====\n', flush=True)
    
    # 基准权重
    base = {'p': 1.0, 'atr': 1.5, 'dif': 0.5, 'cl': 0.02, 'shadow': 3,
            'bull': 0, 'small_gain': 0, 'weekly': 0, 'monthly': 0,
            'volume': 0, 'vol_sus': 0}
    
    print('--- 基准版 ---', flush=True)
    run_backtest(base, '原版(无额外特征)')
    
    print('\n--- 单项新增特征测试（与基准对比）---', flush=True)
    for name, key, val in [
        ('+多头排列', 'bull', 3),
        ('+连续小涨', 'small_gain', 0.5),
        ('+周线上涨', 'weekly', 4),
        ('+月线上涨', 'monthly', 5),
        ('+量能趋势', 'volume', 2),
        ('+量能持续', 'vol_sus', 3),
    ]:
        w = base.copy()
        w[key] = val
        run_backtest(w, name)
    
    print('\n--- 组合测试 ---', flush=True)
    
    # 全部特征
    w_all = base.copy()
    w_all.update({'bull': 3, 'small_gain': 0.5, 'weekly': 4, 'monthly': 5, 'volume': 2, 'vol_sus': 3})
    run_backtest(w_all, '全部特征')
    
    # 趋势版（多头+周+月）
    w_trend = base.copy()
    w_trend.update({'bull': 4, 'weekly': 5, 'monthly': 6})
    run_backtest(w_trend, '趋势版(多周月)')
    
    # 动量版（小涨+量能）
    w_momentum = base.copy()
    w_momentum.update({'small_gain': 1.5, 'volume': 3, 'vol_sus': 4})
    run_backtest(w_momentum, '动量版(涨量能)')
    
    # 轻度趋势版
    w_light = base.copy()
    w_light.update({'bull': 2, 'weekly': 3, 'monthly': 4, 'small_gain': 0.5, 'volume': 1, 'vol_sus': 1})
    run_backtest(w_light, '轻量综合')
    
    # 重型趋势
    w_heavy = base.copy()
    w_heavy.update({'bull': 5, 'weekly': 6, 'monthly': 7, 'small_gain': 1.0})
    run_backtest(w_heavy, '重趋势')
    
    print('\n--- 最优版本分年统计 ---', flush=True)
    # 用最好的型号分年
    best_w = base.copy()
    best_w.update({'bull': 4, 'weekly': 5, 'monthly': 6})
    
    for year in ['2025', '2026']:
        y_dates = [d for d in dates if d.startswith(year)]
        y_total = y_wins = 0
        for date in y_dates:
            stocks = data[date]
            filtered = []
            for s in stocks:
                code = s['code']
                ri = real.get(code)
                if not m1_filter(s, ri): continue
                prev_gain = get_prev_gain(code, date)
                feat = compute_features(code, date)
                score = calc_score(s, feat, prev_gain, best_w)
                n = s.get('n', 0) or 0
                filtered.append((score, code, n))
            if not filtered: continue
            filtered.sort(key=lambda x: -x[0])
            y_total += 1
            if filtered[0][2] >= 2.5:
                y_wins += 1
        print(f'  {year}年: {y_wins}/{y_total} = {y_wins*100/y_total:.1f}%' if y_total > 0 else f'  {year}年: 无数据')
    
    print('\n===== 回测完成 =====', flush=True)
