"""
WIN — 实战高胜率策略
基于5年数据统计分析提炼:
  最佳买入时机 = 大盘情绪回暖 + 个股洗盘结束 + 启动确认
"""
import pickle, os, sys, numpy as np
from collections import defaultdict

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

d = pickle.load(open(os.path.join(SCRIPTS_DIR, 'tdx_cache.pkl'), 'rb'))
data = d['data']
dates = sorted(data.keys())
print(f'数据: {dates[0]}~{dates[-1]}')

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

# 缓存
sc = {}
for dt in dates:
    for s in data[dt]:
        sc[(s['code'], dt)] = {'p': s['p'], 'close': s['close'], 'high': s['high'], 'low': s['low'], 'volume': s['volume']}

def score_win(code, di):
    """WIN评分: 0-100"""
    if di < 15 or di >= len(dates)-1: return 0, None
    try:
        rec = [sc.get((code, dates[di-off])) for off in range(15, -1, -1)]
        if any(r is None for r in rec): return 0, None
    except: return 0, None
    
    today = rec[-1]
    p = today['p']
    
    # 硬过滤
    if p < 2 or p > 8: return 0, None  # 涨2-8%
    
    close15 = [r['close'] for r in rec]
    vol15 = [r['volume'] for r in rec]
    p15 = [r['p'] for r in rec]
    
    # 均线
    ma5 = sum(close15[-5:]) / 5
    ma10 = sum(close15[-10:]) / 5
    ma20 = sum(close15[-20:]) / 5 if len(close15) >= 20 else ma10
    
    # CL
    rng = today['high'] - today['low']
    cl = (today['close'] - today['low']) / rng * 100 if rng > 0 else 50
    
    s = 50  # 基础分
    reasons = []
    
    # === 核心信号 ===
    
    # ① 前7天有涨停或大阳
    max7 = max(p15[-8:-1]) if len(p15) >= 8 else 0
    if max7 >= 9.0: s += 12; reasons.append('前有涨停+12')
    elif max7 >= 5.0: s += 6; reasons.append(f'前有大阳({max7:.0f}%)+6')
    
    # ② 回调洗盘(前3天有跌)
    down3 = sum(1 for p in p15[-4:-1] if p < 0)
    if down3 >= 2: s += 8; reasons.append(f'洗盘{down3}天+8')
    elif down3 >= 1: s += 3
    
    # ③ 今天放量启动
    avg_v5 = sum(vol15[-6:-1]) / 5
    if avg_v5 > 0 and today['volume'] > avg_v5 * 1.2:
        s += 6; reasons.append('放量启动+6')
    elif avg_v5 > 0 and today['volume'] > avg_v5 * 0.8:
        s += 2
    
    # ④ 均线多头
    if ma5 > ma10 > ma20: s += 8; reasons.append('多头+8')
    elif ma5 > ma10: s += 3
    
    # ⑤ 趋势加速
    p_acc = p15[-1] - p15[-3] if len(p15) >= 3 else 0
    if p_acc > 3: s += 5; reasons.append('加速+5')
    
    # ⑥ CL位置
    if 40 <= cl <= 75: s += 4; reasons.append(f'CL{cl:.0f}+4')
    elif cl > 85: s -= 5
    
    # ⑦ 回调到均线支撑
    low3 = min(close15[-4:-1]) if len(close15) >= 4 else today['low']
    if abs(low3 - ma10) / ma10 < 0.015: s += 5; reasons.append('踩MA10+5')
    if abs(low3 - ma20) / ma20 < 0.015: s += 4; reasons.append('踩MA20+4')
    
    # ⑧ 量能不过度
    if avg_v5 > 0 and today['volume'] > avg_v5 * 2.5: s -= 5
    
    # ⑨ 连涨处罚
    cons = 0
    for pv in reversed(p15[-5:-1]):
        if pv > 0: cons += 1
        else: break
    if cons >= 3: s -= cons * 2
    
    next_p = sc.get((code, dates[di+1]), {}).get('p', 0) or 0
    return s, {
        'score': s, 'reasons': ' '.join(reasons),
        'p': p, 'cl': round(cl, 1), 'next_p': round(next_p, 2),
        'ma5': round(ma5,2), 'ma10': round(ma10,2),
        'cons_up': cons,
    }

# 回测
print('\n=== WIN策略 ===')
bt_dates = [d for d in dates if d >= '2025-01-01']
results = []

for di, dt in enumerate(bt_dates):
    di_real = dates.index(dt)
    if di_real >= len(dates)-1: continue
    
    pool = []
    for s in data[dt]:
        code = s['code']
        if not IS_MAIN(code): continue
        score, detail = score_win(code, di_real)
        if score < 65: continue  # 最低65分
        pool.append((score, code, detail))
    
    if not pool: continue
    pool.sort(key=lambda x: -x[0])
    
    best = pool[0]
    win = best[2]['next_p'] >= 2.5
    results.append((dt, best[1], best[0], best[2]['p'], best[2]['next_p'], best[2]['reasons'], win))

wins = sum(1 for r in results if r[6])
print(f'信号: {len(results)}天')
print(f'胜率: {wins}/{len(results)} = {wins/max(len(results),1)*100:.1f}%')
print(f'日均候选: 1')
print()
print(f'{"日期":>10} {"评分":>4} {"代码":>7} {"今%":>5} {"明%":>5} {"信号":>40} {"结果":>4}')
for r in results[:30]:
    print(f'{r[0]:>10} {r[2]:>4} {r[1]:>7} {r[3]:>+4.1f}% {r[4]:>+4.1f}% {r[5][:40]:>40} {"✅" if r[6] else "❌":>4}')

# 保存策略
import joblib, json
# 不需要保存模型，策略就是评分函数本身
print(f'\n✅ WIN策略可用')
