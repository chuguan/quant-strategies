"""
神龙启动v2 — 5年数据BO+XGBoost (1453个五连板)
"""
import pickle, os, sys, numpy as np, random, joblib
from collections import defaultdict
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

# 加载数据
print('加载5年缓存...')
d = pickle.load(open(os.path.join(SCRIPTS_DIR, 'tdx_cache.pkl'), 'rb'))
data = d['data']
dates = sorted(data.keys())
print(f'数据: {dates[0]}~{dates[-1]} ({len(dates)}天)')

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

# 股票缓存
sc = {}
for dt in dates:
    for s in data[dt]:
        sc[(s['code'], dt)] = {'p': s['p'], 'close': s['close'], 'high': s['high'], 'low': s['low'], 'open': s['open'], 'volume': s['volume']}

def f7(code, di):
    """前7天特征"""
    if di < 7: return None
    pre = [sc.get((code, dates[di-off])) for off in range(7,0,-1)]
    if any(x is None for x in pre): return None
    pp = [x['p'] for x in pre]
    # 计算CL (收盘位置)
    pc = []
    for x in pre:
        r = x['high'] - x['low']
        cl = (x['close'] - x['low']) / r * 100 if r > 0 else 50
        pc.append(cl)
    return [
        sum(pp), sum(1 for p in pp if p>0), sum(1 for p in pp if p<0),
        max(pp) if pp else 0, min(pp) if pp else 0,
        pp[-1], pp[-2], pp[-3],
        sum(pc)/len(pc) if pc else 50, pc[-1] if pc else 50,
        pc[-1]-pc[-3] if len(pc)>=3 else 0,
    ]

# ===== 正例: T-1天涨3-8% → T天涨停(>=9.5%) =====
print('构建正例 (T-1涨3-8% → T涨停)...')
Xp = []
for di in range(8, len(dates)):
    for s in data[dates[di]]:
        code = s['code']
        if not IS_MAIN(code): continue
        p_today = s['p']
        if p_today < 9.5: continue  # 今天涨停
        
        yest = sc.get((code, dates[di-1]))
        if not yest: continue
        p_yest = yest['p']
        if p_yest < 3 or p_yest >= 9.5: continue  # 前天涨3-8%
        
        f = f7(code, di-1)
        if f is None: continue
        Xp.append(f + [p_yest, yest['close']])

print(f'正例: {len(Xp)}')

# ===== 负例: T天涨3-8% → T+1天无涨停 =====
print('构建负例...')
random.seed(42)
codes_list = sorted(set(k[0] for k in sc if IS_MAIN(k[0])))
random.shuffle(codes_list)
Xn = []
target_neg = len(Xp) * 2

for code in codes_list:
    if len(Xn) >= target_neg: break
    for di in range(8, len(dates)-1):
        v = sc.get((code, dates[di]))
        if not v: continue
        p = v['p']
        if 3 <= p < 9.5:
            tmw = sc.get((code, dates[di+1]))
            if tmw and tmw['p'] < 9.5:
                f = f7(code, di)
                if f:
                    Xn.append(f + [p, v['close']])
                    break  # 每只1个负例

print(f'负例: {len(Xn)}')

X = np.array(Xp + Xn)
y = np.array([1]*len(Xp) + [0]*len(Xn))
print(f'总: {len(X)}, 正:{sum(y)} 负:{len(y)-sum(y)}')

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
import xgboost as xgb

X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

m = xgb.XGBClassifier(n_estimators=500, max_depth=6, learning_rate=0.1,
    scale_pos_weight=(len(y)-sum(y))/sum(y), random_state=42, eval_metric='logloss')
m.fit(X_tr, y_tr)
y_prob = m.predict_proba(X_te)[:,1]
print(f'\nAUC: {roc_auc_score(y_te, y_prob):.3f}')
print(classification_report(y_te, m.predict(X_te), target_names=['否','明天涨停']))

# 仅前7天
X7 = X[:, :11]; X7_tr, X7_te = X_tr[:, :11], X_te[:, :11]
m7 = xgb.XGBClassifier(n_estimators=500, max_depth=5, learning_rate=0.1,
    scale_pos_weight=(len(y)-sum(y))/sum(y), random_state=42, eval_metric='logloss')
m7.fit(X7_tr, y_tr)
y7_prob = m7.predict_proba(X7_te)[:,1]
print(f'\n仅前7天 AUC: {roc_auc_score(y_te, y7_prob):.3f}')
print(classification_report(y_te, m7.predict(X7_te), target_names=['否','明天涨停']))

# 特征
feat_names = ['pre7_sum','up_days','down_days','max_p','min_p','t1_p','t2_p','t3_p',
              'avg_cl','t1_cl','cl_trend','d0_p','d0_close']
print('\n特征重要性:')
for i in np.argsort(m.feature_importances_)[::-1]:
    print(f'  {feat_names[i]}: {m.feature_importances_[i]:.3f}')

# 2026回测
print(f'\n=== 2026回测 ===')
year_dates = [d for d in dates if d >= '2026-01-01']
results = []

for di, dt in enumerate(year_dates):
    di_real = dates.index(dt)
    if di_real >= len(dates)-1: continue
    day = []
    for s in data[dt]:
        code = s['code']
        if not IS_MAIN(code): continue
        p = s['p']
        if p < 3 or p >= 9.5: continue
        f = f7(code, di_real)
        if f is None: continue
        prob = m.predict_proba(np.array([f+[p, s['close']]]))[0][1]
        if prob < 0.4: continue
        tmw = sc.get((code, dates[di_real+1]))
        nb = tmw and tmw['p'] >= 9.5
        day.append((prob, code, p, dt, nb))
    
    if day:
        day.sort(key=lambda x: -x[0])
        results.append(day[0])

nw = sum(1 for r in results if r[4])
print(f'信号: {len(results)}/94天')
print(f'明天涨停: {nw}/{len(results)} = {nw/max(len(results),1)*100:.0f}%')
print(f'\n{"日期":>10} {"概率":>5} {"代码":>7} {"今日%":>5} {"明涨停":>6}')
for r in results[:30]:
    print(f'{r[3]:>10} {r[0]*100:>4.0f}% {r[1]:>7} {r[2]:>+4.1f}% {"✅" if r[4] else "❌":>6}')

joblib.dump(m, os.path.join(SCRIPTS_DIR, '神龙_xgb_v2.pkl'))
print(f'\n✅ 已保存: 神龙_xgb_v2.pkl')
