"""
回测神龙v2 — 用已训练好的权重重新训练+回测
"""
import pickle, os, numpy as np, sys, joblib, random

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
sys.path.insert(0, SCRIPTS_DIR)

with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, names = d['data'], d['names']
dates = sorted(data.keys())
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

sc = {}
for dt in dates:
    for s in data[dt]:
        sc[(s['code'], dt)] = {'p':s.get('p',0) or 0, 'cl':s.get('cl',50) or 50}

def f7(code, di):
    if di < 7 or di >= len(dates): return None
    pre = [sc.get((code, dates[di-off])) for off in range(7,0,-1)]
    if any(x is None for x in pre): return None
    pp = [x['p'] for x in pre]; pc = [x['cl'] for x in pre]
    return [sum(pp), sum(1 for p in pp if p>0), sum(1 for p in pp if p<0),
            max(pp) if pp else 0, min(pp) if pp else 0,
            pp[-1], pp[-2], pp[-3],
            sum(pc)/len(pc) if pc else 50, pc[-1] if pc else 50,
            pc[-1]-pc[-3] if len(pc)>=3 else 0]

# 训练
print('正例: T-1涨3-8% → T涨停')
Xp = []
for di in range(8, len(dates)):
    for s in data[dates[di]]:
        code = s['code']
        if not IS_MAIN(code): continue
        p = (s.get('p',0) or 0)
        if p < 9.5: continue
        yest = sc.get((code, dates[di-1]))
        if not yest or yest['p'] < 3 or yest['p'] >= 9.5: continue
        f = f7(code, di-1)
        if f: Xp.append(f + [yest['p'], yest['cl']])

print(f'正例: {len(Xp)}')
random.seed(42)
Xn = []
codes_list = sorted(set(k[0] for k in sc if IS_MAIN(k[0])))
random.shuffle(codes_list)
for code in codes_list:
    if len(Xn) >= len(Xp)*2: break
    for di in range(7, len(dates)-1):
        v = sc.get((code, dates[di]))
        if not v: continue
        p = v['p']
        if 3 <= p < 9.5:
            tmw = sc.get((code, dates[di+1]))
            if tmw and (tmw['p'] or 0) < 9.5:
                f = f7(code, di)
                if f: Xn.append(f + [p, v['cl']]); break

print(f'负例: {len(Xn)}')

X = np.array(Xp + Xn); y = np.array([1]*len(Xp) + [0]*len(Xn))
print(f'总: {len(X)}')

import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

m = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.1,
    scale_pos_weight=(len(y)-sum(y))/sum(y), random_state=42, eval_metric='logloss')
m.fit(X_tr, y_tr)
y_prob = m.predict_proba(X_te)[:,1]
print(f'AUC: {roc_auc_score(y_te, y_prob):.3f}')
print(classification_report(y_te, m.predict(X_te), target_names=['否','明天涨停']))

feat_names = ['pre7_sum','up_days','down_days','max_p','min_p','t1_p','t2_p','t3_p',
              'avg_cl','t1_cl','cl_trend','d0_p','d0_cl']
print('\n特征:')
for i in np.argsort(m.feature_importances_)[::-1]:
    print(f'  {feat_names[i]}: {m.feature_importances_[i]:.3f}')

# 2026回测
print(f'\n=== 2026回测 ===')
year_dates = [d for d in dates if d >= '2026-01-01']
results = []

for di, dt in enumerate(year_dates):
    di_real = dates.index(dt)
    if di_real >= len(dates)-1: continue  # 需要明天数据
    day = []
    for s in data[dt]:
        code = s['code']
        if not IS_MAIN(code): continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        v = sc.get((code, dt))
        if not v or v['p'] < 3 or v['p'] >= 9.5: continue
        f = f7(code, di_real)
        if f is None: continue
        prob = m.predict_proba(np.array([f+[v['p'],v['cl']]]))[0][1]
        if prob < 0.4: continue
        tmw = sc.get((code, dates[di_real+1]))
        nb = tmw and (tmw['p'] or 0) >= 9.5
        day.append((prob, code, nm, v['p'], dt, nb))
    
    if day:
        day.sort(key=lambda x: -x[0])
        results.append(day[0])

nw = sum(1 for r in results if r[5])
print(f'信号: {len(results)}/{len(year_dates)}天')
print(f'明天涨停: {nw}/{len(results)} = {nw/max(len(results),1)*100:.0f}%')
print(f'\n{"日期":>10} {"概率":>5} {"代码":>7} {"名称":>8} {"今日%":>5} {"明涨停":>6}')
for r in results:
    print(f'{r[4]:>10} {r[0]*100:>4.0f}% {r[1]:>7} {r[2][:6]:>8} {r[3]:>+4.1f}% {"✅" if r[5] else "❌":>6}')

joblib.dump(m, os.path.join(SCRIPTS_DIR, '神龙_xgb_v2.pkl'))
print(f'\n✅ 已保存')
