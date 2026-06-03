"""
神龙启动 v1.0 回测 — 2026年逐日扫描结果
"""
import os, pickle, json, numpy as np, sys, joblib
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

# 加载模型
model = joblib.load(os.path.join(SCRIPTS_DIR, 'five_board_3y_xgb.pkl'))
print(f'模型已加载, {len(model.get_booster().get_dump())}棵树')

# 加载数据
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, names = d['data'], d['names']
dates = sorted(data.keys())
print(f'数据: {dates[0]}~{dates[-1]} ({len(dates)}天)')

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
MIN_PROB = 0.3

def build_features_for_day(target_dt, code, stock_data_cache):
    """在指定日期构建特征（只用该日及之前的数据）"""
    di = dates.index(target_dt)
    if di < 7: return None
    
    # 取前7天 + 当天的数据
    recs = []
    for off in range(-7, 1):  # T-7 到 T
        dt = dates[di + off]
        s = stock_data_cache.get((code, dt))
        if s is None: return None
        recs.append(s)
    
    if len(recs) < 8: return None
    
    pre7 = recs[:7]
    d0 = recs[7]
    
    pre_ps = [x['p'] for x in pre7]
    pre_cls = [x['cl'] for x in pre7]
    today_p = d0['p']
    today_cl = d0['cl']
    
    if today_p < 3 or today_p >= 9.5: return None  # 不符合筛选条件
    
    feats = np.array([[
        sum(pre_ps), sum(1 for p in pre_ps if p>0), sum(1 for p in pre_ps if p<0),
        max(pre_ps) if pre_ps else 0, min(pre_ps) if pre_ps else 0,
        pre_ps[-1], pre_ps[-2] if len(pre_ps)>=2 else 0, pre_ps[-3] if len(pre_ps)>=3 else 0,
        sum(pre_cls)/len(pre_cls) if pre_cls else 50,
        pre_cls[-1] if pre_cls else 50,
        pre_cls[-1]-pre_cls[-3] if len(pre_cls)>=3 else 0,
        today_p, today_cl,
    ]])
    
    prob = model.predict_proba(feats)[0][1]
    return prob, d0, pre_ps, pre_cls

# ====== 预构建缓存 ======
print('构建缓存...')
stock_cache = {}  # {(code, date): {p, cl, close}}
for dt in dates:
    for s in data[dt]:
        code = s['code']
        if IS_MAIN(code):
            stock_cache[(code, dt)] = {
                'p': s.get('p',0) or 0,
                'cl': s.get('cl',50) or 50,
                'close': s.get('close',0) or 0,
            }
print(f'缓存: {len(stock_cache)}条')

# ====== 逐日扫描 ======
print('\n开始回测...')
results = []
year_dates = [d for d in dates if d >= '2026-01-01']

for di, dt in enumerate(year_dates):
    codes_today = set()
    for s in data.get(dt, []):
        if IS_MAIN(s['code']):
            codes_today.add(s['code'])
    
    day_results = []
    for code in codes_today:
        nm = names.get(code, '')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        
        r = build_features_for_day(dt, code, stock_cache)
        if r is None: continue
        prob, d0, pre_ps, pre_cls = r
        if prob < MIN_PROB: continue
        
        # 后续5天是否有涨停
        di_real = dates.index(dt)
        has_5board = False
        next_1d_board = False
        for off in range(1, 6):
            if di_real + off < len(dates):
                nd = dates[di_real + off]
                ns = stock_cache.get((code, nd), {})
                np_val = ns.get('p', 0) or 0
                if off == 1 and np_val >= 9.5:
                    next_1d_board = True
                if np_val >= 9.5:
                    # 检查后续是否够5连板
                    board_count = 1
                    for off2 in range(off+1, off+5):
                        if di_real + off2 < len(dates):
                            n2 = stock_cache.get((code, dates[di_real + off2]), {})
                            if (n2.get('p',0) or 0) >= 9.5:
                                board_count += 1
                            else: break
                    if board_count >= 5:
                        has_5board = True
        
        day_results.append((prob, code, nm, d0['close'], d0['p'], next_1d_board, has_5board))
    
    if day_results:
        day_results.sort(key=lambda x: -x[0])
        best = day_results[0]
        results.append({
            'date': dt, 'prob': best[0], 'code': best[1], 'name': best[2],
            'price': best[3], 'today_p': best[4],
            'next_board': best[5], 'has_5board': best[6],
            'total_signals': len(day_results),
        })
    
    if (di+1) % 20 == 0:
        print(f'  [{di+1}/{len(year_dates)}] 已发现{len(results)}天有信号')

# ====== 输出 ======
print('\n' + '='*80)
print(f'🐉 神龙启动 v1.0 回测 (2026年, 概率>{MIN_PROB})')
print('='*80)

# 统计
total_days = len(results)
board_next = sum(1 for r in results if r['next_board'])
board_5 = sum(1 for r in results if r['has_5board'])
signals = sum(r['total_signals'] for r in results)

print(f'交易日: {len(year_dates)}天')
print(f'有信号天数: {total_days}天 ({total_days/max(len(year_dates),1)*100:.0f}%)')
print(f'次日涨停: {board_next}/{total_days} = {board_next/max(total_days,1)*100:.0f}%')
print(f'后续五连板: {board_5}/{total_days} = {board_5/max(total_days,1)*100:.0f}%')
print(f'总信号数: {signals}个')
print()

print(f'{"日期":>10} {"概率":>5} {"代码":>7} {"名称":>8} {"价格":>8} {"今日%":>6} {"次日板":>6} {"五连板":>6} {"信号数":>5}')
print('-'*70)
for r in results:
    nb = '✅' if r['next_board'] else '❌'
    fb = '🐉' if r['has_5board'] else ''
    print(f'{r["date"]:>10} {r["prob"]*100:>4.0f}% {r["code"]:>7} {r["name"][:6]:>8} {r["price"]:>8.2f} {r["today_p"]:>+5.1f}% {nb:>6} {fb:>6} {r["total_signals"]:>5}')

# 保存
with open(os.path.join(SCRIPTS_DIR, '神龙启动_回测2026.pkl'), 'wb') as f:
    pickle.dump(results, f)
print(f'\n✅ 已保存: 神龙启动_回测2026.pkl ({len(results)}条)')
