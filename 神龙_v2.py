"""
神龙启动 v2 — 预测：今天涨3-8% → 明天涨停
训练集: 正例 = T-1天涨3-8%, T天涨停
        负例 = T天涨3-8%, T+1天没涨停
"""
import pickle, os, numpy as np, sys, joblib, random
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
sys.path.insert(0, SCRIPTS_DIR)

with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, names = d['data'], d['names']
dates = sorted(data.keys())
print(f'数据: {dates[0]}~{dates[-1]}')

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

# 缓存
sc = {}
for dt in dates:
    for s in data[dt]:
        sc[(s['code'], dt)] = {'p':s.get('p',0) or 0, 'cl':s.get('cl',50) or 50}

def f7(code, di):
    """前7天特征"""
    if di < 7: return None
    pre = [sc.get((code, dates[di-off])) for off in range(7,0,-1)]
    if any(x is None for x in pre): return None
    pp = [x['p'] for x in pre]
    pc = [x['cl'] for x in pre]
    return [sum(pp), sum(1 for p in pp if p>0), sum(1 for p in pp if p<0),
            max(pp) if pp else 0, min(pp) if pp else 0,
            pp[-1], pp[-2], pp[-3],
            sum(pc)/len(pc) if pc else 50, pc[-1] if pc else 50,
            pc[-1]-pc[-3] if len(pc)>=3 else 0]

# 正例: T-1天涨3-8% → T天涨停(>=9.5%)
print('构建正例...')
Xp, Yp = [], []
for di in range(8, len(dates)):
    dt = dates[di]
    for s in data[dt]:
        code = s['code']
        if not IS_MAIN(code): continue
        p_today = (s.get('p',0) or 0)
        if p_today < 9.5: continue  # 今天涨停
        
        # 前天涨3-8%
        yesterday = sc.get((code, dates[di-1]))
        if not yesterday: continue
        p_yest = yesterday['p']
        if p_yest < 3 or p_yest >= 9.5: continue
        
        f = f7(code, di-1)  # 在T-1天做特征
        if f is None: continue
        Xp.append(f + [p_yest, yesterday['cl']])  # T-1天的p和cl
        Yp.append(1)

print(f'正例: {len(Xp)}')

# 负例: T天涨3-8% → T+1天无涨停
print('构建负例...')
Xn, Yn = [], []
random.seed(42)
codes_list = sorted(set(k[0] for k in sc if IS_MAIN(k[0])))
random.shuffle(codes_list)

for code in codes_list:
    if len(Xn) >= len(Xp)*3: break
    for di in range(7, len(dates)-1):
        k = (code, dates[di])
        v = sc.get(k)
        if not v: continue
        p = v['p']
        if 3 <= p < 9.5:  # 今天涨3-8%
            tmw = sc.get((code, dates[di+1]))
            if tmw and (tmw['p'] or 0) < 9.5:  # 明天没涨停
                f = f7(code, di)
                if f:
                    Xn.append(f + [p, v['cl']])
                    Yn.append(0)
                    break  # 每只只采1个负例

print(f'负例: {len(Xn)}')

import numpy as np
X = np.array(Xp + Xn)
y = np.array(Yp + Yn)
print(f'总: {len(X)}, 正:{sum(y)}, 负:{len(y)-sum(y)}')

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
import xgboost as xgb

X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

m = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.1,
    scale_pos_weight=(len(y)-sum(y))/sum(y), random_state=42, eval_metric='logloss')
m.fit(X_tr, y_tr)
y_prob = m.predict_proba(X_te)[:,1]
print(f'\nAUC: {roc_auc_score(y_te, y_prob):.3f}')
print(classification_report(y_te, m.predict(X_te), target_names=['不涨停','明天涨停']))

# 仅前7天(不含T-1天p/cl)
X7 = X[:, :11]
X7_tr, X7_te = X_tr[:, :11], X_te[:, :11]
m7 = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.1,
    scale_pos_weight=(len(y)-sum(y))/sum(y), random_state=42, eval_metric='logloss')
m7.fit(X7_tr, y_tr)
y7_prob = m7.predict_proba(X7_te)[:,1]
print(f'\n仅前7天 AUC: {roc_auc_score(y_te, y7_prob):.3f}')

feat_names = ['pre7_sum','up_days','down_days','max_p','min_p','t1_p','t2_p','t3_p',
              'avg_cl','t1_cl','cl_trend','d0_p','d0_cl']
print('\n特征重要性:')
inds = np.argsort(m.feature_importances_)[::-1]
for i in range(13):
    print(f'  {feat_names[inds[i]]}: {m.feature_importances_[inds[i]]:.3f}')

# 2026回测
print(f'\n=== 2026回测 ===')
year_dates = [d for d in dates if d >= '2026-01-01']
results = []
for di, dt in enumerate(year_dates):
    di_real = dates.index(dt)
    day_hits = []
    for s in data[dt]:
        code = s['code']
        if not IS_MAIN(code): continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        v = sc.get((code, dt))
        if not v: continue
        p = v['p']
        if p < 3 or p >= 9.5: continue  # 今天涨3-8%
        
        f = f7(code, di_real)
        if f is None: continue
        feats = np.array([f + [p, v['cl']]])
        prob = m.predict_proba(feats)[0][1]
        if prob < 0.4: continue
        
        # 明天是否涨停
        tmw = sc.get((code, dates[di_real+1]))
        nb = tmw and (tmw['p'] or 0) >= 9.5
        
        day_hits.append((prob, code, nm, p, dt, nb))
    
    if day_hits:
        day_hits.sort(key=lambda x: -x[0])
        results.append(day_hits[0])

next_wins = sum(1 for r in results if r[5])
print(f'信号天数: {len(results)}/{len(year_dates)}')
print(f'明天涨停: {next_wins}/{len(results)} = {next_wins/max(len(results),1)*100:.0f}%')
print(f'\n逐日:')
print(f'{"日期":>10} {"概率":>5} {"代码":>7} {"名称":>8} {"今日%":>5} {"明涨停":>6}')
for r in results:
    print(f'{r[4]:>10} {r[0]*100:>4.0f}% {r[1]:>7} {r[2][:6]:>8} {r[3]:>+4.1f}% {"✅" if r[5] else "❌":>6}')

joblib.dump(m, os.path.join(SCRIPTS_DIR, '神龙_xgb_v2.pkl'))
print(f'\n✅ 已保存: 神龙_xgb_v2.pkl')
