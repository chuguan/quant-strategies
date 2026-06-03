"""
大道至简策略 v1.0 — 4行情分型尾盘选股系统
大盘分为4类行情，分别调用独立策略选股，互不干扰。
任何子策略有突破可独立替换，不影响其他。
"""
import pickle, os, sys
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR)
CACHE_PATH = 'big_cache_full.pkl'

def load_cache():
    with open(CACHE_PATH, 'rb') as f:
        cache = pickle.load(f)
    return cache['data'], cache['real'], cache['names']

def classify_market(stocks):
    """4类行情判断"""
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    avg_p = sum(ps) / len(ps)
    avg_vr = sum(vrs) / len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5:
        return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

def calc_macd(dif, mg):
    if mg and dif > 0.5: return 10
    if mg and dif > 0.2: return 8
    if mg: return 6
    if dif > 0.5: return 4
    if dif > 0: return 2
    return 0

# ============================================================
# 策略1️⃣ 真实涨日策略 (2026-06-05定版)
# ============================================================
REAL_UP = {
    'name': '真实涨日',
    'params': {
        'p_min': 3, 'p_max': 7, 'vr_min': 0.6, 'vr_max': 2.5,
        'hs_min': 5, 'hs_max': 15, 'sz_max': 200, 'cl_min': 60, 'cl_max': 90,
    },
    'weights': {
        'p_w': 2.5, 'cl_w': 0.05, 'macd_w': 0.3,
        'ma5_b': 3, 'vr_b': 1, 'hs_b': 0.3, 'wr_b': 2,
        'j_b': 2, 'j_low_b': 2,
    }
}

# ============================================================
# 策略2️⃣ 虚涨日策略 (2026-06-05定版)
# ============================================================
FAKE_UP = {
    'name': '虚涨日',
    'params': {
        'p_min': 0, 'p_max': 6, 'vr_min': 0.6, 'vr_max': 2.5,
        'hs_min': 5, 'hs_max': 20, 'sz_max': 200, 'cl_min': 30, 'cl_max': 95,
    },
    'weights': {
        'p_w': 1.0, 'cl_w': 0.05, 'macd_w': 0.5,
        'ma5_b': 0, 'vr_b': 0, 'hs_b': 0, 'wr_b': 0,
        'j_b': 0, 'j_low_b': 0,
    }
}

# ============================================================
# 策略3️⃣ 跌日策略 (2026-06-05定版)
# ============================================================
DOWN = {
    'name': '跌日',
    'params': {
        'p_min': 5, 'p_max': 8, 'vr_min': 0.8, 'vr_max': 2.0,
        'hs_min': 5, 'hs_max': 15, 'sz_max': 300, 'cl_min': 60, 'cl_max': 90,
    },
    'weights': {
        'p_w': 2.0, 'cl_w': 0.05, 'macd_w': 0.3,
        'ma5_b': 0, 'vr_b': 0, 'hs_b': 0, 'wr_b': 0,
        'j_b': 0, 'j_low_b': 0,
    }
}

# ============================================================
# 策略4️⃣ 横盘策略 (2026-06-05定版，同跌日)
# ============================================================
FLAT = {
    'name': '横盘',
    'params': {
        'p_min': 5, 'p_max': 8, 'vr_min': 0.8, 'vr_max': 2.0,
        'hs_min': 5, 'hs_max': 15, 'sz_max': 300, 'cl_min': 60, 'cl_max': 90,
    },
    'weights': {
        'p_w': 2.0, 'cl_w': 0.05, 'macd_w': 0.3,
        'ma5_b': 0, 'vr_b': 0, 'hs_b': 0, 'wr_b': 0,
        'j_b': 0, 'j_low_b': 0,
    }
}

STRATEGIES = {'real_up': REAL_UP, 'fake_up': FAKE_UP, 'down': DOWN, 'flat': FLAT}

def score_stock(s, real, names, strategy):
    """按策略评分一只股票"""
    p = s.get('p', 0) or 0
    params = strategy['params']
    weights = strategy['weights']
    
    if p < params['p_min'] or p > params['p_max']: return None
    vr = s.get('vol_ratio', 0) or 0
    if vr < params['vr_min'] or vr > params['vr_max']: return None
    ri = real.get(s['code'])
    if not ri: return None
    hsl = (ri.get('hsl', 0) or 0)
    if hsl < params['hs_min'] or hsl > params['hs_max']: return None
    if (ri.get('shizhi', 0) or 0) >= params['sz_max']: return None
    nm = names.get(s['code'], '')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return None
    cl = s.get('cl', 0)
    if cl < params['cl_min'] or cl > params['cl_max']: return None
    nh = s.get('n', 0) or 0
    if nh <= 0: return None
    
    buy = s.get('close', 0) or 0
    dif = s.get('dif_val', 0) or 0
    mg = s.get('macd_golden', 0)
    a5 = s.get('above_ma5', 0) or 0
    wrv = s.get('wr_val', 0) or 0
    jv = s.get('j_val', 0) or 0
    
    ms = calc_macd(dif, mg)
    ps2 = min(10, max(1, 11 - buy / 10)) if buy else 0
    w = weights
    
    score = p * w['p_w'] + cl * w['cl_w'] + ps2 * 0.3 + ms * w['macd_w']
    score += (w['ma5_b'] if a5 else 0)
    score += (w['vr_b'] * 1.5 if 1.0 <= vr <= 1.5 else 0)
    score += (w['hs_b'] * 2 if 5 <= hsl <= 7 else 0)
    score += (w['wr_b'] if wrv < -80 else 0)
    score += (w['j_b'] if jv > 70 else 0)
    score += (w['j_low_b'] if jv < 20 else 0)
    
    return {'score': score, 'n': nh, 'p': p, 'name': nm[:12], 'code': s['code'],
            'cl': cl, 'vr': vr, 'hsl': hsl, 'buy': buy, 'sz': ri.get('shizhi',0) or 0}

def run(stocks, real, names):
    """主入口：猜行情 → 选策略 → 出结果"""
    mkt = classify_market(stocks)
    strategy = STRATEGIES[mkt]
    cand = []
    for s in stocks:
        r = score_stock(s, real, names, strategy)
        if r: cand.append(r)
    cand.sort(key=lambda x: (-x['score'], -x['p']))
    return mkt, strategy['name'], cand

if __name__ == '__main__':
    data, real, names = load_cache()
    today = datetime.now().strftime('%Y-%m-%d')
    dates = sorted(data.keys())
    sel_date = today if today in data else dates[-1]
    
    mkt, sname, cand = run(data.get(sel_date, []), real, names)
    print(f"大道至简策略 v1.0")
    print(f"日期: {sel_date} | 行情: {sname}")
    print(f"候选: {len(cand)}只")
    print(f"\n{'名':>3} {'名称':<12} {'评分':>6} {'涨幅':>5} {'CL':>3} {'量比':>5}")
    print('-'*45)
    for i, c in enumerate(cand[:10]):
        print(f"{i+1:3d} {c['name']:<12} {c['score']:6.1f} {c['p']:+4.1f}% {c['cl']:3.0f}% {c['vr']:5.2f}")
