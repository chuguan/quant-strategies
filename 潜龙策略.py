"""
潜龙策略 v1 — 高胜率尾盘选股
核心逻辑:
  1. 趋势股回调不破位 → 尾盘买入 → 次日反弹
  2. N字型: 涨停→回调1-3天(缩量不破涨停价)→再涨
  3. 弱转强: 前一天冲高回落→当天企稳→次日反包
"""
import pickle, os, sys, numpy as np, json
from datetime import datetime
from collections import defaultdict

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

# 加载数据
d = pickle.load(open(os.path.join(SCRIPTS_DIR, 'tdx_cache.pkl'), 'rb'))
data, names = d['data'], d['names']
dates = sorted(data.keys())
print(f'数据: {dates[0]}~{dates[-1]} ({len(dates)}天)')

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

# 缓存
sc = {}
for dt in dates:
    for s in data[dt]:
        sc[(s['code'], dt)] = {'p': s['p'], 'close': s['close'], 'high': s['high'], 'low': s['low'], 'volume': s['volume']}

# ===== 潜龙策略评分 =====
def score_dragon(code, di):
    """
    潜龙评分:
    加分:
    - N字形态: 前5天内有涨停+回调不破涨停价 +5
    - 缩量回调: 今天量 < 5日均量×0.8 +3
    - 关键支撑: 价格在MA10以上 +3
    - 趋势: MA5 > MA10 > MA20 +5
    - MACD水上: DIF > 0 +2
    - CL适中: CL在40-75之间 +2
    扣分:
    - 放了: 量 > 5日均量×1.5 -3
    - 高位: CL > 85 -3
    - 连涨5天+ -5
    """
    if di < 20: return None, None
    
    # 取20天数据
    rec20 = []
    for off in range(20, -1, -1):
        r = sc.get((code, dates[di-off]))
        if r is None: return None, None
        rec20.append(r)
    
    today = rec20[-1]
    p_today = today['p']
    
    # 排除涨停/跌停
    if p_today >= 9.5 or p_today <= -9.5: return None, None
    
    # 今天涨跌范围
    if p_today < 2: return None, None  # 太弱
    if p_today > 8: return None, None  # 太高
    
    score = 0
    reasons = []
    
    # 算技术指标
    close20 = [r['close'] for r in rec20]
    vol20 = [r['volume'] for r in rec20]
    p20 = [r['p'] for r in rec20]
    
    # 均线
    ma5 = sum(close20[-5:]) / 5
    ma10 = sum(close20[-10:]) / 10
    ma20 = sum(close20[-20:]) / 20
    ma5_prev = sum(close20[-10:-5]) / 5
    
    # 5日均量
    avg_vol5 = sum(vol20[-5:]) / 5
    avg_vol10 = sum(vol20[-10:]) / 10
    
    # CL
    rng = today['high'] - today['low']
    cl = (today['close'] - today['low']) / rng * 100 if rng > 0 else 50
    
    # ===== N字形态检测 =====
    # 前5天内是否有涨停
    has_zt = False
    zt_idx = -1
    for off in range(2, 8):  # 2-7天前
        if p20[-off] >= 9.5:
            has_zt = True
            zt_idx = off
            break
    
    if has_zt:
        zt_close = close20[-zt_idx]
        lowest_after_zt = min(close20[-zt_idx+1:]) if zt_idx > 1 else 99999
        # 回调不破涨停价的95%
        if lowest_after_zt >= zt_close * 0.95:
            score += 8
            reasons.append('N字✅')
        elif lowest_after_zt >= zt_close * 0.90:
            score += 4
            reasons.append('N字△')
    
    # ===== 缩量回调 =====
    if today['volume'] < avg_vol5 * 0.8 and p_today < 0:
        score += 4
        reasons.append('缩量回调✅')
    
    # ===== 趋势 =====
    if ma5 > ma10 > ma20 and ma5 > ma5_prev:
        score += 6
        reasons.append('多头排列✅')
    elif ma5 > ma10 > ma20:
        score += 3
        reasons.append('多头排列△')
    elif ma5 > ma20:
        score += 1
        reasons.append('站MA20')
    
    # ===== 回调到均线 =====
    lowest_recent = min(close20[-5:])
    if abs(lowest_recent - ma10) / ma10 < 0.02:  # 回踩MA10
        score += 4
        reasons.append('踩MA10✅')
    if abs(lowest_recent - ma20) / ma20 < 0.02:
        score += 3
        reasons.append('踩MA20✅')
    
    # ===== CL位置 =====
    if 40 <= cl <= 75:
        score += 2
        reasons.append(f'CL适中({cl:.0f})')
    elif cl > 85:
        score -= 3
        reasons.append(f'CL过高({cl:.0f})')
    
    # ===== 量能 =====
    if today['volume'] > avg_vol5 * 1.5:
        score -= 3
        reasons.append('放量❌')
    
    # ===== 连涨惩罚 =====
    cons_up = 0
    for p in reversed(p20[-5:]):
        if p > 0: cons_up += 1
        else: break
    if cons_up >= 4:
        score -= 5
        reasons.append(f'连涨{cons_up}天❌')
    
    # ===== 次日预期 =====
    if di < len(dates) - 1:
        tmw = sc.get((code, dates[di+1]))
        next_p = tmw['p'] if tmw else 0
    else:
        next_p = 0
    
    return score, {
        'score': score, 'reasons': ' '.join(reasons),
        'p': p_today, 'cl': round(cl, 1),
        'ma5': round(ma5, 2), 'ma10': round(ma10, 2),
        'ma20': round(ma20, 2),
        'vol_ratio': round(today['volume'] / avg_vol5, 2) if avg_vol5 > 0 else 0,
        'next_p': round(next_p, 2),
        'close': today['close'],
    }

# ===== 回测 =====
print('\n=== 潜龙策略回测 (2025-2026) ===')
bt_dates = [d for d in dates if d >= '2025-01-01']
results = []
import random; random.seed(42)

# 每天选Top3
for di, dt in enumerate(bt_dates):
    di_real = dates.index(dt)
    if di_real >= len(dates)-1: continue
    
    candidates = []
    for s in data[dt]:
        code = s['code']
        if not IS_MAIN(code): continue
        r = score_dragon(code, di_real)
        if r is None or r[0] is None: continue
        score, detail = r
        if score < 6: continue  # 最低6分
        candidates.append((score, code, detail))
    
    if not candidates: continue
    candidates.sort(key=lambda x: -x[0])
    
    # #1冠军
    best = candidates[0]
    win = best[2]['next_p'] >= 2.5
    results.append({
        'date': dt, 'code': best[1], 'score': best[0],
        'p': best[2]['p'], 'next_p': best[2]['next_p'],
        'reasons': best[2]['reasons'],
        'win': win,
    })

# 统计
wins = sum(1 for r in results if r['win'])
total = len(results)
print(f'信号天数: {total}/{len(bt_dates)}')
print(f'胜率(次日≥2.5%): {wins}/{total} = {wins/max(total,1)*100:.1f}%')

# 按年份
years = defaultdict(lambda: [0,0])
for r in results:
    y = r['date'][:4]
    years[y][1] += 1
    if r['win']: years[y][0] += 1
for y, (w, t) in sorted(years.items()):
    print(f'  {y}: {w}/{t} = {w/max(t,1)*100:.1f}%')

print(f'\n前20条:')
print(f'{"日期":>10} {"评分":>4} {"代码":>7} {"今%":>5} {"明%":>5} {"原因":>30} {"结果":>4}')
for r in results[:20]:
    mk = '✅' if r['win'] else '❌'
    print(f'{r["date"]:>10} {r["score"]:>4} {r["code"]:>7} {r["p"]:>+4.1f}% {r["next_p"]:>+4.1f}% {r["reasons"]:>30} {mk:>4}')
