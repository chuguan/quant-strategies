"""
神龙启动 v1.1 — 用big_cache重新验证+训练
"""
import pickle, os, numpy as np, sys, joblib
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
sys.path.insert(0, SCRIPTS_DIR)

# 加载
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, names = d['data'], d['names']
dates = sorted(data.keys())
print(f'数据: {dates[0]}~{dates[-1]}')

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

# ===== Step 1: big_cache中有多少五连板 =====
print('\n=== big_cache五连板统计 ===')
fb_cache = []
for di, dt in enumerate(dates):
    if di > len(dates)-6: break
    for s in data[dt]:
        code = s.get('code','')
        if not IS_MAIN(code): continue
        if (s.get('p',0) or 0) < 9.5: continue
        streak = 1
        for off in range(1,5):
            ns = [x for x in data[dates[di+off]] if x['code']==code]
            if ns and (ns[0].get('p',0) or 0) >= 9.5: streak+=1
            else: break
        if streak >= 5:
            fb_cache.append((code, names.get(code,'?'), dt))

print(f'总计: {len(fb_cache)}个')
for y in ['2025','2026']:
    cnt = len([x for x in fb_cache if x[2].startswith(y)])
    print(f'{y}: {cnt}个')

# ===== Step 2: 用big_cache重新训练 =====
print('\n=== 训练（只用big_cache数据）===')

# 构建特征缓存
stock_cache = {}
for dt in dates:
    for s in data[dt]:
        stock_cache[(s['code'], dt)] = {'p':s.get('p',0) or 0, 'cl':s.get('cl',50) or 50, 'close':s.get('close',0) or 0}

def extract(di, code):
    """提取7+1天特征"""
    if di < 7 or di >= len(dates)-1: return None, None
    pre7 = []
    for off in range(-7, 0):
        v = stock_cache.get((code, dates[di+off]))
        if not v: return None, None
        pre7.append(v)
    d0 = stock_cache.get((code, dates[di]))
    if not d0: return None, None
    
    pp = [x['p'] for x in pre7]
    pc = [x['cl'] for x in pre7]
    f = [sum(pp), sum(1 for p in pp if p>0), sum(1 for p in pp if p<0),
         max(pp) if pp else 0, min(pp) if pp else 0,
         pp[-1], pp[-2] if len(pp)>=2 else 0, pp[-3] if len(pp)>=3 else 0,
         sum(pc)/len(pc) if pc else 50, pc[-1] if pc else 50,
         pc[-1]-pc[-3] if len(pc)>=3 else 0, d0['p'], d0['cl']]
    return f, d0

# 正例: 五连板启动日
X_pos, Y_pos = [], []
for code, nm, dt in fb_cache:
    di = dates.index(dt)
    f, _ = extract(di, code)
    if f: X_pos.append(f); Y_pos.append(1)

# 负例: 今天涨3-8%但后续5天无涨停
print(f'正例: {len(X_pos)}')
import random; random.seed(42)
X_neg, Y_neg, NEG_TARGET = [], [], len(X_pos)*3
codes_list = list(set(k[0] for k in stock_cache if IS_MAIN(k[0])))

for code in codes_list:
    if len(X_neg) >= NEG_TARGET: break
    for di in range(7, len(dates)-6):
        if len(X_neg) >= NEG_TARGET: break
        k = (code, dates[di])
        v = stock_cache.get(k)
        if not v: continue
        p = v['p']
        if 3 <= p < 9.5:
            # 后续5天无涨停
            has_board = any(
                (stock_cache.get((code, dates[di+off]),{}) or {}).get('p',0) >= 9.5
                for off in range(1,6) if di+off < len(dates)
            )
            if not has_board:
                f, _ = extract(di, code)
                if f: X_neg.append(f); Y_neg.append(0)

print(f'负例: {len(X_neg)}')

X = np.array(X_pos + X_neg)
y = np.array(Y_pos + Y_neg)
print(f'总: {len(X)}')

# 训练
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
import xgboost as xgb

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

m = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.1,
    scale_pos_weight=(len(y)-sum(y))/sum(y), random_state=42, eval_metric='logloss')
m.fit(X_train, y_train)
y_prob = m.predict_proba(X_test)[:,1]
print(f'\nAUC: {roc_auc_score(y_test, y_prob):.3f}')
print(classification_report(y_test, m.predict(X_test), target_names=['否','是']))

# 仅前7天
from sklearn.metrics import roc_auc_score
Xp = X[:, :11]
Xp_train, Xp_test = X_train[:, :11], X_test[:, :11]
mp = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.1,
    scale_pos_weight=(len(y)-sum(y))/sum(y), random_state=42, eval_metric='logloss')
mp.fit(Xp_train, y_train)
yp_prob = mp.predict_proba(Xp_test)[:,1]
print(f'\n仅前7天 AUC: {roc_auc_score(y_test, yp_prob):.3f}')
print(classification_report(y_test, mp.predict(Xp_test), target_names=['否','是']))

# 特征重要性
print('\n特征重要性:')
inds = np.argsort(m.feature_importances_)[::-1]
feat_names = ['pre7_sum','up_days','down_days','max_p','min_p','t1_p','t2_p','t3_p',
              'avg_cl','t1_cl','cl_trend','d0_p','d0_cl']
for i in range(13):
    print(f'  {feat_names[inds[i]]}: {m.feature_importances_[inds[i]]:.3f}')

joblib.dump(m, os.path.join(SCRIPTS_DIR, '神龙_xgb_v11.pkl'))

# ===== Step 3: 2026年回测 =====
print('\n=== 2026年回测 ===')
year_dates = [d for d in dates if d >= '2026-01-01']
results = []

for di, dt in enumerate(year_dates):
    di_real = dates.index(dt)
    day_best = []
    for s in data[dt]:
        code = s['code']
        if not IS_MAIN(code): continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        
        f, d0 = extract(di_real, code)
        if f is None: continue
        p = f[11]  # d0_p
        if p < 3 or p >= 9.5: continue
        if f[10] > 0.5: continue  # 排除CL趋势太强的
        
        prob = m.predict_proba(np.array([f]))[0][1]
        if prob < 0.3: continue
        
        # 后续5天涨停情况
        n5 = [stock_cache.get((code, dates[di_real+off]),{}).get('p',0) for off in range(1,6) if di_real+off < len(dates)]
        next_board = any(x >= 9.5 for x in n5)
        
        day_best.append((prob, code, nm, d0['close'], p, next_board))
    
    if day_best:
        day_best.sort(key=lambda x: -x[0])
        best = day_best[0]
        results.append(best)

# 输出
print(f'\n信号天数: {len(results)}/{len(year_dates)}')
next_ok = sum(1 for r in results if r[5])
print(f'次日涨停: {next_ok}/{len(results)} = {next_ok/max(len(results),1)*100:.0f}%')
print(f'\n逐日:')
print(f'{"日期":>10} {"概率":>5} {"代码":>7} {"名称":>8} {"价格":>8} {"今日%":>6} {"后续板":>6}')
for di, dt in enumerate(year_dates):
    if di >= len(results): break
    prob, code, nm, price, p, nb = results[di]
    print(f'{dt:>10} {prob*100:>4.0f}% {code:>7} {nm[:6]:>8} {price:>8.2f} {p:>+5.1f}% {"✅" if nb else "❌":>6}')

joblib.dump(m, os.path.join(SCRIPTS_DIR, '神龙_xgb_v11.pkl'))
print(f'\n✅ 已保存新模型')
