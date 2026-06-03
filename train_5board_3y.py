"""
五连板BO+XGBoost完整训练 — 3年数据
1. 加载扫描结果
2. 去重
3. 提取7+1+5天特征
4. BO+XGBoost训练
5. 输出规则
"""
import os, pickle, time, json, sys, numpy as np
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

# ===== 1. 加载扫描结果 =====
print('加载扫描结果...')
with open(os.path.join(SCRIPTS_DIR, 'five_board_3year.pkl'), 'rb') as f:
    d = pickle.load(f)
raw_boards = d['boards']  # [(code, name, start, end, pcts)]
names = d['names']
print(f'原始: {len(raw_boards)}个')

# ===== 2. 去重 =====
seen = set()
boards = []
for c, n, s, e, ps in raw_boards:
    key = f"{c}_{s}"
    if key not in seen:
        seen.add(key)
        boards.append({'code': c, 'name': n, 'start': s, 'end': e, 'pcts': ps})

boards.sort(key=lambda x: x['start'])
print(f'去重后: {len(boards)}个')
years = {}
for b in boards:
    years[b['start'][:4]] = years.get(b['start'][:4], 0) + 1
print(f'按年份: {years}')

# ===== 3. 提取特征 =====
print('\n提取特征（逐只下载日K线）...')
import akshare as ak
PREFIX = lambda c: 'sh' if c.startswith('6') else 'sz'
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

def get_daily_data(code):
    sym = f"{PREFIX(code)}{code}"
    try:
        df = ak.stock_zh_a_daily(symbol=sym, adjust='qfq')
        records = []
        prev_c = None
        for _, row in df.iterrows():
            dt = str(row['date'])[:10]
            c = float(row['close'])
            o = float(row['open'])
            h = float(row['high'])
            l = float(row['low'])
            v = float(row['volume'])
            p = round((c - prev_c) / prev_c * 100, 2) if prev_c and prev_c > 0 else 0
            records.append({'date': dt, 'close': c, 'open': o, 'high': h, 'low': l, 
                           'volume': v, 'p': p})
            prev_c = c
        return records
    except:
        return None

# 下载所有五连板股票的日K线
stock_data = {}  # code -> [records]

for i, b in enumerate(boards):
    code = b['code']
    if code not in stock_data:
        records = get_daily_data(code)
        if records:
            stock_data[code] = records
            time.sleep(0.05)
    if (i+1) % 50 == 0:
        print(f'  [{i+1}/{len(boards)}] 已缓存{len(stock_data)}只')

print(f'缓存: {len(stock_data)}只股票')

# ===== 4. 构建特征 =====
FEATURE_NAMES = [
    'pre7_sum_p', 'pre7_up_days', 'pre7_down_days', 'pre7_max_p', 'pre7_min_p',
    't_1_p', 't_2_p', 't_3_p',
    'pre7_avg_cl', 't_1_cl', 'cl_trend_3d',
    'pre7_avg_vr', 't_1_vr',
    'pre7_avg_close', 't_1_close',
    'pre7_std_p',
    'd0_p', 'd0_cl', 'd0_vr',
    'd0_vr_ratio',  # d0_vr / pre7_avg_vr
]

def extract(sample_records, start_idx):
    """从records提取7+1特征"""
    pre7 = sample_records[start_idx-7:start_idx]
    d0 = sample_records[start_idx]
    
    pre_ps = [x['p'] for x in pre7]
    pre_cls = [(x['close'] - x['low']) / (x['high'] - x['low']) * 100 
               if (x['high'] - x['low']) > 0 else 50 for x in pre7]
    pre_vrs = []
    for j, x in enumerate(pre7):
        idx = start_idx - 7 + j
        if idx >= 5:
            avg5 = sum(sample_records[idx-k]['volume'] for k in range(1,6)) / 5
            pre_vrs.append(x['volume'] / avg5 if avg5 > 0 else 1)
        else:
            pre_vrs.append(1)
    pre_close = [x['close'] for x in pre7]
    
    # pre7 avg_vr (用5日均量比)
    avg_vr = sum(pre_vrs) / len(pre_vrs) if pre_vrs else 1
    
    # d0 features
    d0_cl = (d0['close'] - d0['low']) / (d0['high'] - d0['low']) * 100 if (d0['high'] - d0['low']) > 0 else 50
    d0_vr = d0['volume'] / (sum(pre_close[-5:])/5) if sum(pre_close[-5:]) > 0 else 1  # 近似量比
    
    # 前7天量比（用成交量比例估算）
    avg5_vol = sum(sample_records[start_idx-k-1]['volume'] for k in range(5)) / 5
    d0_vr_actual = d0['volume'] / avg5_vol if avg5_vol > 0 else 1
    
    return [
        sum(pre_ps),
        sum(1 for p in pre_ps if p > 0),
        sum(1 for p in pre_ps if p < 0),
        max(pre_ps) if pre_ps else 0,
        min(pre_ps) if pre_ps else 0,
        pre_ps[-1] if len(pre_ps) >= 1 else 0,
        pre_ps[-2] if len(pre_ps) >= 2 else 0,
        pre_ps[-3] if len(pre_ps) >= 3 else 0,
        sum(pre_cls)/len(pre_cls) if pre_cls else 50,
        pre_cls[-1] if len(pre_cls) >= 1 else 50,
        pre_cls[-1] - pre_cls[-3] if len(pre_cls) >= 3 else 0,
        avg_vr,
        pre_vrs[-1] if pre_vrs else 1,
        sum(pre_close)/len(pre_close) if pre_close else 0,
        pre_close[-1] if pre_close else 0,
        np.std(pre_ps) if len(pre_ps) > 1 else 0,
        d0['p'],
        d0_cl,
        d0_vr_actual,
        d0_vr_actual / avg_vr if avg_vr > 0 else 1,
    ]

# 正例
X_pos, y_pos = [], []
for b in boards:
    code = b['code']
    records = stock_data.get(code)
    if not records: continue
    
    # 找到这个日期在records中的索引
    start = b['start']
    idx = next((i for i, r in enumerate(records) if r['date'] == start), -1)
    if idx < 7 or idx >= len(records) - 1: continue
    
    try:
        feats = extract(records, idx)
        X_pos.append(feats)
        y_pos.append(1)
    except:
        pass

print(f'正例: {len(X_pos)}个')

# 负例: 随机取涨幅5-9%但没连板的
print('构建负例...')
X_neg, y_neg = [], []
random_codes = sorted(stock_data.keys())
import random
random.shuffle(random_codes)

neg_target = min(2000, len(X_pos) * 3)
for code in random_codes:
    if len(X_neg) >= neg_target: break
    records = stock_data.get(code)
    if not records or len(records) < 60: continue
    
    # 随机选一些日期（涨幅5-9%但后续没有涨停）
    for _ in range(min(5, len(records))):
        idx = random.randint(7, len(records) - 6)
        p = records[idx]['p']
        if 5 <= p <= 9.5:  # 大涨但不是涨停
            # 检查后续5天没有涨停
            has_board = any(records[idx+k]['p'] >= 9.5 for k in range(1, 6))
            if not has_board:
                try:
                    feats = extract(records, idx)
                    X_neg.append(feats)
                    y_neg.append(0)
                    break
                except:
                    pass

print(f'负例: {len(X_neg)}个')

# ===== 5. 合并+训练 =====
X_all = np.array(X_pos + X_neg)
y_all = np.array(y_pos + y_neg)

print(f'\n总样本: {len(X_all)}个')
print(f'正例: {sum(y_all)}, 负例: {len(y_all)-sum(y_all)}')

from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(
    X_all, y_all, test_size=0.2, random_state=42, stratify=y_all
)

# ===== BO + XGBoost =====
print('\n训练XGBoost...')
import xgboost as xgb

# 先默认参数基线
model = xgb.XGBClassifier(
    n_estimators=500, max_depth=6, learning_rate=0.1,
    scale_pos_weight=(len(y_all)-sum(y_all))/sum(y_all),
    random_state=42, eval_metric='logloss'
)
model.fit(X_train, y_train)

from sklearn.metrics import classification_report, roc_auc_score
y_prob = model.predict_proba(X_test)[:, 1]
y_pred = model.predict(X_test)
print(f'默认参数 AUC: {roc_auc_score(y_test, y_prob):.3f}')

# BO调参
try:
    from skopt import BayesSearchCV
    from skopt.space import Real, Integer
    from sklearn.model_selection import StratifiedKFold
    
    param_space = {
        'n_estimators': Integer(100, 500),
        'max_depth': Integer(3, 10),
        'learning_rate': Real(0.01, 0.3, 'log-uniform'),
        'min_child_weight': Integer(1, 10),
        'subsample': Real(0.5, 1.0),
        'colsample_bytree': Real(0.3, 1.0),
        'gamma': Real(0, 5),
    }
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    bs = BayesSearchCV(
        xgb.XGBClassifier(scale_pos_weight=(len(y_all)-sum(y_all))/sum(y_all), 
                          random_state=42, eval_metric='logloss'),
        param_space, n_iter=30, cv=cv, scoring='roc_auc', n_jobs=1, random_state=42, verbose=0
    )
    print('BO 30轮...')
    bs.fit(X_train, y_train)
    model = bs.best_estimator_
    print(f'\n最优参数:')
    for k, v in bs.best_params_.items():
        print(f'  {k}: {v}')
    print(f'最优CV AUC: {bs.best_score_:.3f}')
except ImportError:
    print('skopt未安装, 用GridSearch')
    from sklearn.model_selection import GridSearchCV
    grid = GridSearchCV(model, {
        'max_depth': [4, 6, 8], 'learning_rate': [0.05, 0.1, 0.2], 'subsample': [0.7, 0.9]
    }, cv=5, scoring='roc_auc')
    grid.fit(X_train, y_train)
    model = grid.best_estimator_

# 测试
y_prob = model.predict_proba(X_test)[:, 1]
y_pred = model.predict(X_test)
print(f'\n====== 3年数据BO+XGBoost结果 ======')
print(f'AUC: {roc_auc_score(y_test, y_prob):.3f}')
print(classification_report(y_test, y_pred, target_names=['非五连板','五连板']))

# 特征重要性
print('\n====== 特征重要性 ======')
importances = model.feature_importances_
indices = np.argsort(importances)[::-1]
for i in range(min(15, len(FEATURE_NAMES))):
    idx = indices[i]
    print(f'  {i+1}. {FEATURE_NAMES[idx]}: {importances[idx]:.3f}')

# 保存模型
import joblib
model_path = os.path.join(SCRIPTS_DIR, 'five_board_3y_xgb.pkl')
joblib.dump(model, model_path)
print(f'\n✅ 模型已保存: {model_path}')
