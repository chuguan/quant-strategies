"""
权重评分搜索：找出最佳特征权重组合，把达2.5%概率最高的票推到第1名
评分 = w1*f1(p) + w2*f2(vr) + w3*f3(cl) + w4*f4(j) + w5*f5(hsl) + w6*f6(sz)
"""
import pickle, os, json, statistics, itertools, math
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
KC = {}

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
ad = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]

print(f'2026年 {len(ad)}天', flush=True)

def gk(code):
    if code not in KC:
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        KC[code] = json.load(open(fp)) if os.path.exists(fp) else None
    return KC[code]

# 基础过滤（出票率≥90%的宽松条件）
BASE_PARAMS = {'p_min':5,'p_max':8,'vr_min':0.8,'vr_max':3.0,
               'hsl_min':5,'hsl_max':15,'sz_max':200,'j_max':100,'cl_min':0,'cl_max':100}

def get_pool(dt):
    """获取当天候选池"""
    pool = []
    for s in data.get(dt, []):
        code, px = s['code'], s['p']
        if px < BASE_PARAMS['p_min'] or px > BASE_PARAMS['p_max']: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < BASE_PARAMS['vr_min'] or vr > BASE_PARAMS['vr_max']: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < BASE_PARAMS['hsl_min'] or hsl > BASE_PARAMS['hsl_max']: continue
        if (ri.get('shizhi',0) or 0) > BASE_PARAMS['sz_max']: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm: continue
        if (s.get('j_val',0) or 0) > BASE_PARAMS['j_max']: continue
        cl = s.get('cl',0)
        if cl < BASE_PARAMS['cl_min'] or cl > BASE_PARAMS['cl_max']: continue
        nv = s.get('n',0) or 0
        pool.append({'p':px, 'vr':vr, 'cl':cl, 'j':s.get('j_val',0) or 0, 
                     'hsl':hsl, 'sz':ri.get('shizhi',0) or 0, 'nv':nv, 'code':code})
    return pool

# ===== 定义特征评分函数 =====
def score_features(s, weights):
    """
    weights格式: {'p_w':{区间:分数}, 'vr_w':{区间:分数}, 'cl_w':{区间:分数},
                  'j_w':{区间:分数}, 'hsl_w':{区间:分数}, 'sz_w':{区间:分数}}
    区间: (lo, hi) -> 分数
    """
    sc = 10  # 基础分
    
    # 涨幅
    for (lo, hi), pts in weights.get('p_w', {}).items():
        if lo <= s['p'] < hi: sc += pts; break
    
    # 量比
    for (lo, hi), pts in weights.get('vr_w', {}).items():
        if lo <= s['vr'] < hi: sc += pts; break
    
    # CL
    for (lo, hi), pts in weights.get('cl_w', {}).items():
        if lo <= s['cl'] < hi: sc += pts; break
    
    # J值
    for (lo, hi), pts in weights.get('j_w', {}).items():
        if lo <= s['j'] < hi: sc += pts; break
    
    # 换手
    for (lo, hi), pts in weights.get('hsl_w', {}).items():
        if lo <= s['hsl'] < hi: sc += pts; break
    
    # 市值
    for (lo, hi), pts in weights.get('sz_w', {}).items():
        if lo <= s['sz'] < hi: sc += pts; break
    
    return sc

# ===== 评分回测 =====
def backtest_scoring(weights):
    """用评分排序取冠军，返回冠军达2.5%"""
    nvs = []
    for dt in ad:
        pool = get_pool(dt)
        if not pool: continue
        for s in pool:
            s['score'] = score_features(s, weights)
        pool.sort(key=lambda x: -x['score'])
        nvs.append(pool[0]['nv'])
    
    if not nvs: return 0, 0, 0
    n = len(nvs)
    w25 = sum(1 for v in nvs if v>=2.5)*100/n
    w5 = sum(1 for v in nvs if v>=5)*100/n
    avg = statistics.mean(nvs)
    return n, w25, w5, avg

# ===== 基准：纯涨幅排序 =====
print(f'\n{"="*70}')
print(f'基准：纯涨幅排序')
print(f'{"="*70}', flush=True)

base_nvs = []
for dt in ad:
    pool = get_pool(dt)
    if not pool: continue
    pool.sort(key=lambda x: -x['p'])
    base_nvs.append(pool[0]['nv'])

n_base = len(base_nvs)
w25_base = sum(1 for v in base_nvs if v>=2.5)*100/n_base
print(f'涨幅排序: {n_base}天 达2.5%:{w25_base:.1f}% 出票率:{n_base*100/len(ad):.1f}%', flush=True)

# ===== 权重搜索 =====
print(f'\n{"="*70}')
print(f'权重评分搜索')
print(f'{"="*70}', flush=True)

# 定义每个特征的评分选项
# 涨幅分段 (权重必须高，但不能独占)
p_tiers = {
    (4.5, 5.0): [3, 5, 8],
    (5.0, 5.5): [8, 10, 12, 15],
    (5.5, 6.0): [5, 8, 10, 12],
    (6.0, 6.5): [10, 12, 15, 18],
    (6.5, 7.0): [5, 8, 10, 12],
    (7.0, 8.0): [3, 5, 8],
}

# 量比分段
vr_tiers = {
    (0.5, 0.8): [-5, -3, 0],
    (0.8, 1.0): [3, 5, 8],
    (1.0, 1.2): [5, 8, 10],
    (1.2, 1.5): [5, 8, 10],
    (1.5, 2.0): [3, 5, 8],
    (2.0, 10): [-5, -3, 0],
}

# CL分段
cl_tiers = {
    (0, 60): [-3, 0, 3],
    (60, 70): [3, 5, 8],
    (70, 80): [5, 8, 10],
    (80, 85): [3, 5, 8],
    (85, 90): [0, 3, 5],
    (90, 100): [-8, -5, -3],
}

# 换手分段
hsl_tiers = {
    (5, 8): [3, 5, 8],
    (8, 10): [3, 5],
    (10, 12): [0, 3],
    (12, 15): [-3, 0],
}

# 市值分段
sz_tiers = {
    (0, 30): [3, 5],
    (30, 50): [3, 5],
    (50, 80): [0, 3],
    (80, 150): [0, 3, 5],
    (150, 200): [-3, 0],
}

# J值分段
j_tiers = {
    (0, 20): [0, 3, 5],
    (20, 40): [3, 5],
    (40, 50): [3, 5],
    (50, 65): [0, 3],
    (65, 80): [0, 3],
    (80, 100): [-5, -3],
}

# 搜索策略：先对每个特征单独搜索最佳权重，再组合
print(f'\n--- 单特征最佳权重搜索 ---', flush=True)

def single_feature_search(tiers, feat_name, feat_key):
    """搜索单个特征的最佳分段权重（固定其他特征权重为0）"""
    best_w25 = w25_base
    best_weights = {}
    
    keys = list(tiers.keys())
    vals = list(tiers.values())
    
    # 生成所有组合（笛卡尔积）
    total = 1
    for v in vals: total *= len(v)
    
    if total > 500:
        # 太大，随机采样
        import random
        for _ in range(200):
            weights = {}
            for k in keys:
                weights[k] = random.choice(tiers[k])
            w = {feat_name: weights}
            n, w25, w5, avg = backtest_scoring(w)
            if n > 0 and w25 > best_w25:
                best_w25 = w25
                best_weights = weights
    else:
        for combo in itertools.product(*vals):
            weights = dict(zip(keys, combo))
            w = {feat_name: weights}
            n, w25, w5, avg = backtest_scoring(w)
            if n > 0 and w25 > best_w25:
                best_w25 = w25
                best_weights = weights
    
    diff = best_w25 - w25_base
    sig = '🔥' if diff > 3 else ('✅' if diff > 0 else '')
    print(f'{sig} {feat_name:<4} 最佳:{best_w25:.1f}% ({diff:+.1f}%) 权重:{best_weights}', flush=True)
    return feat_name, best_weights

best_single = []
for feat_name, feat_key, tiers in [
    ('p_w', 'p', p_tiers), ('vr_w', 'vr', vr_tiers), ('cl_w', 'cl', cl_tiers),
    ('hsl_w', 'hsl', hsl_tiers), ('sz_w', 'sz', sz_tiers), ('j_w', 'j', j_tiers)
]:
    fn, bw = single_feature_search(tiers, feat_name, feat_key)
    best_single.append((fn, bw))

# ===== 最佳组合搜索 =====
print(f'\n--- 最佳多特征组合搜索 ---', flush=True)

# 用单特征最佳结果作为起点，组合
comb_weights = {}
for fn, bw in best_single:
    comb_weights[fn] = bw

n, w25, w5, avg = backtest_scoring(comb_weights)
print(f'全部组合: 达2.5%:{w25:.1f}% {n}天', flush=True)

# 逐个删减特征，看哪个加分哪个扣分
print(f'\n--- 逐个特征贡献分析 ---', flush=True)
for fn, _ in best_single:
    test_w = dict(comb_weights)
    test_w[fn] = {k:0 for k in test_w[fn]}  # 该特征权重归零
    n, tw25, _, _ = backtest_scoring(test_w)
    diff = tw25 - w25
    sig = '🔥' if diff < -1 else ('✅' if diff < -0.5 else '')
    print(f'{sig} 去掉{fn:<4}: {tw25:.1f}% ({diff:+.1f}%) ← 负值说明该特征有用', flush=True)

# ===== 尝试：涨幅权重加倍 + 其他特征微调 =====
print(f'\n--- 涨幅加权组合微调 ---', flush=True)

# 让涨幅占主导（高权重），其他特征微调
for p_mult in [1.5, 2, 2.5, 3]:
    for vr_bonus in [0, 3, 5]:
        for cl_bonus in [0, 3, 5]:
            test_w = {
                'p_w': {(4.5,5):5*p_mult, (5,5.5):12*p_mult, (5.5,6):10*p_mult, 
                        (6,6.5):15*p_mult, (6.5,7):10*p_mult, (7,8):5*p_mult},
                'vr_w': {(0.5,0.8):-3, (0.8,1):vr_bonus, (1,1.2):vr_bonus+2,
                        (1.2,1.5):vr_bonus+2, (1.5,2):vr_bonus, (2,10):-5},
                'cl_w': {(0,60):-3, (60,70):cl_bonus, (70,80):cl_bonus+2, 
                        (80,85):cl_bonus, (85,90):0, (90,100):-5},
            }
            n, w25, w5, avg = backtest_scoring(test_w)
            if w25 > w25_base + 2:
                diff = w25 - w25_base
                print(f'  p×{p_mult} vr+{vr_bonus} cl+{cl_bonus} → 达2.5%:{w25:.1f}% (+{diff:.1f}%) {n}天', flush=True)

print(f'\n{"="*70}')
print(f'📊 结论')
print(f'{"="*70}', flush=True)
print(f'涨幅排序基准: {w25_base:.1f}%', flush=True)
# 最佳权重评分
best_w = {}
for fn, bw in best_single:
    best_w[fn] = bw
_, bw25, _, _ = backtest_scoring(best_w)
print(f'最佳权重评分: {bw25:.1f}%', flush=True)
