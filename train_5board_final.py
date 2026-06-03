"""
五连板BO+XGBoost完整训练 — 使用预缓存数据
"""
import os, pickle, sys, numpy as np, random
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

# 加载
print('加载数据...')
with open(os.path.join(SCRIPTS_DIR, 'five_board_3year.pkl'), 'rb') as f:
    raw = pickle.load(f)['boards']
with open(os.path.join(SCRIPTS_DIR, 'five_board_stock_cache.pkl'), 'rb') as f:
    stock_data = pickle.load(f)

# 去重
seen = set()
boards = []
for c, n, s, e, ps in raw:
    if (c, s) not in seen:
        seen.add((c, s))
        boards.append({'code': c, 'name': n, 'start': s, 'end': e, 'pcts': ps})
print(f'事件: {len(boards)}个, 缓存: {len(stock_data)}只')

# 特征定义
FEATS = [
    'pre7_sum_p', 'pre7_up_days', 'pre7_down_days', 'pre7_max_p', 'pre7_min_p',
    't_1_p', 't_2_p', 't_3_p',
    'pre7_avg_cl', 't_1_cl', 'cl_trend_3d',
    'd0_p','d0_cl',
]

def extract(rec, idx):
    p7 = rec[idx-7:idx]
    pp = [x['p'] for x in p7]
    pc = [(x['close']-x['low'])/(x['high']-x['low'])*100 if (x['high']-x['low'])>0 else 50 for x in p7]
    d0 = rec[idx]
    d0c = (d0['close']-d0['low'])/(d0['high']-d0['low'])*100 if (d0['high']-d0['low'])>0 else 50
    return [
        sum(pp), sum(1 for p in pp if p>0), sum(1 for p in pp if p<0),
        max(pp) if pp else 0, min(pp) if pp else 0,
        pp[-1] if len(pp)>=1 else 0,
        pp[-2] if len(pp)>=2 else 0,
        pp[-3] if len(pp)>=3 else 0,
        sum(pc)/len(pc) if pc else 50,
        pc[-1] if len(pc)>=1 else 50,
        pc[-1]-pc[-3] if len(pc)>=3 else 0,
        d0['p'], d0c,
    ]

# 正例
Xp = []; codes = list(stock_data.keys())
for b in boards:
    rec = stock_data.get(b['code'])
    if not rec: continue
    idx = next((i for i,r in enumerate(rec) if r['date']==b['start']), -1)
    if idx < 7: continue
    Xp.append(extract(rec, idx))

print(f'正例: {len(Xp)}')

# 负例：每个五连板股票找5个涨幅5-9%但没连板的日期
random.seed(42)
Xn = []
for code in codes:
    rec = stock_data.get(code)
    if not rec or len(rec) < 60: continue
    found = 0
    for idx in range(7, len(rec)-6):
        if found >= 5: break
        p = rec[idx]['p']
        if 5 <= p <= 9.5 and not any(rec[idx+k]['p']>=9.5 for k in range(1,6)):
            Xn.append(extract(rec, idx))
            found += 1
    if codes.index(code) % 100 == 0:
        print(f'  负例: {len(Xn)}', end='\r')

print(f'负例: {len(Xn)}')

# 平衡采样
if len(Xn) > len(Xp) * 2:
    Xn = random.sample(Xn, len(Xp) * 2)

X = np.array(Xp + Xn)
y = np.array([1]*len(Xp) + [0]*len(Xn))
print(f'总样本: {len(X)}, 正:{sum(y)} 负:{len(y)-sum(y)}')

from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

import xgboost as xgb
from sklearn.metrics import classification_report, roc_auc_score

# 先用默认参数看基线
m = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.1,
    scale_pos_weight=(len(y)-sum(y))/sum(y), random_state=42, eval_metric='logloss')
m.fit(X_train, y_train)
print(f'\n默认AUC: {roc_auc_score(y_test, m.predict_proba(X_test)[:,1]):.3f}')

# BO优化
from skopt import BayesSearchCV
from skopt.space import Real, Integer
from sklearn.model_selection import StratifiedKFold

bs = BayesSearchCV(
    xgb.XGBClassifier(scale_pos_weight=(len(y)-sum(y))/sum(y), random_state=42, eval_metric='logloss'),
    {'n_estimators': Integer(100,500), 'max_depth': Integer(3,10),
     'learning_rate': Real(0.01,0.3,'log-uniform'), 'subsample': Real(0.5,1.0),
     'colsample_bytree': Real(0.3,1.0)},
    n_iter=30, cv=StratifiedKFold(5,shuffle=True,random_state=42),
    scoring='roc_auc', n_jobs=1, random_state=42
)
print('\nBO 30轮...')
bs.fit(X_train, y_train)
m = bs.best_estimator_

y_pred = m.predict(X_test)
y_prob = m.predict_proba(X_test)[:,1]
print(f'\n====== 3年五连板BO+XGBoost ======')
print(f'AUC: {roc_auc_score(y_test, y_prob):.3f}')
print(classification_report(y_test, y_pred, target_names=['非五连板','五连板']))

# 只使用前7天特征（不含d0）
print('\n====== 仅前7天特征（不含启动当天） ======')
X7_train = X_train[:, :11]
X7_test = X_test[:, :11]
m7 = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.1,
    scale_pos_weight=(len(y)-sum(y))/sum(y), random_state=42, eval_metric='logloss')
m7.fit(X7_train, y_train)
print(f'AUC: {roc_auc_score(y_test, m7.predict_proba(X7_test)[:,1]):.3f}')
print(classification_report(y_test, m7.predict(X7_test), target_names=['非五连板','五连板']))

# 特征重要性（完整模型）
print('\n====== 特征重要性 ======')
inds = np.argsort(m.feature_importances_)[::-1]
for i in range(len(FEATS)):
    print(f'  {i+1}. {FEATS[inds[i]]}: {m.feature_importances_[inds[i]]:.3f}')

import joblib
joblib.dump(m, os.path.join(SCRIPTS_DIR, 'five_board_3y_xgb.pkl'))
print(f'\n✅ 已保存: five_board_3y_xgb.pkl')
