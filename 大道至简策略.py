"""
大道至简策略 V260527 — 4行情分型尾盘选股系统
分级选股: L0→L1→L2→L3→L4，每策略调用自己的子策略分级
优化:
  - 真实涨日: p_w=3.0 (65.8%)
  - 横盘: p_w=3.0, vr_b=3, kdj_b=2 (71.0%)
总胜率: 332天 冠军70.8%
"""
import pickle, os, sys, importlib
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
# 4策略定义（每策略关联自己的子策略文件做分级）
# ============================================================
REAL_UP = {
    'name': '真实涨日',
    'module': '大道至简_子策略01_真实涨日',
    'weights': {
        'p_w': 3.0, 'cl_w': 0.05, 'macd_w': 0.3,
        'ma5_b': 3, 'vr_b': 1, 'hs_b': 0.3, 'wr_b': 2,
        'j_b': 2, 'j_low_b': 2,
    }
}
FAKE_UP = {
    'name': '虚涨日',
    'module': '大道至简_子策略02_虚涨日',
    'weights': {
        'p_w': 1.0, 'cl_w': 0.05, 'macd_w': 0.5,
        'ma5_b': 0, 'vr_b': 0, 'hs_b': 0, 'wr_b': 0,
        'j_b': 0, 'j_low_b': 0,
    }
}
DOWN = {
    'name': '跌日',
    'module': '大道至简_子策略03_跌日',
    'weights': {
        'p_w': 1.5, 'cl_w': 0.05, 'macd_w': 0.3,
        'ma5_b': 2, 'vr_b': 0, 'hs_b': 0, 'wr_b': 0,
        'j_b': 0, 'j_low_b': 3,
    }
}
FLAT = {
    'name': '横盘',
    'module': '大道至简_子策略04_横盘',
    'weights': {
        'p_w': 3.0, 'cl_w': 0.05, 'macd_w': 0.3,
        'ma5_b': 2, 'vr_b': 3, 'hs_b': 0.3, 'wr_b': 0,
        'j_b': 0, 'j_low_b': 2, 'kdj_b': 2,
    }
}
STRATEGIES = {'real_up': REAL_UP, 'fake_up': FAKE_UP, 'down': DOWN, 'flat': FLAT}

# 分级跳转顺序（L0→L1→L2→L3→L4）
LEVEL_ORDER = ['L0', 'L1', 'L2', 'L3', 'L4']

def get_sub_strategy(module_name):
    """加载子策略模块，获取LEVELS和LEVEL_PENALTY"""
    spec = importlib.util.spec_from_file_location(module_name, os.path.join(SCRIPTS_DIR, module_name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.LEVELS, mod.LEVEL_PENALTY

def filter_by_level(stocks, real, names, lvl):
    """用某级参数过滤股票"""
    pool = []
    for s in stocks:
        p = s.get('p', 0) or 0
        if p < lvl['p_min'] or p > lvl['p_max']: continue
        if p >= 8: continue  # 涨<8%
        vr = s.get('vol_ratio', 0) or 0
        if vr < lvl['vr_min'] or vr > lvl['vr_max']: continue
        ri = real.get(s['code'])
        if not ri: continue
        hsl = (ri.get('hsl', 0) or 0)
        if hsl < lvl['hs_min'] or hsl > lvl['hs_max']: continue
        if (ri.get('shizhi', 0) or 0) >= lvl['sz_max']: continue
        nm = names.get(s['code'], '')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        cl = s.get('cl', 0)
        if cl < lvl['cl_min'] or cl > lvl['cl_max']: continue
        nh = s.get('n', 0) or 0
        if nh <= 0: continue
        pool.append(s)
    return pool

def score_stock(s, real, names, strategy, penalty=0):
    """按策略评分一只股票（已通过分级过滤，不再重复检查条件）"""
    p = s.get('p', 0) or 0
    ri = real.get(s['code'])
    if not ri: return None
    nm = names.get(s['code'], '')
    w = strategy['weights']
    
    cl = s.get('cl', 0)
    vr = s.get('vol_ratio', 0) or 0
    hsl = (ri.get('hsl', 0) or 0)
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
    
    score = p * w['p_w'] + cl * w['cl_w'] + ps2 * 0.3 + ms * w['macd_w']
    score += (w['ma5_b'] if a5 else 0)
    score += (w['vr_b'] * 1.5 if 1.0 <= vr <= 1.5 else 0)
    score += (w['hs_b'] * 2 if 5 <= hsl <= 7 else 0)
    score += (w['wr_b'] if wrv < -80 else 0)
    score += (w['j_b'] if jv > 70 else 0)
    score += (w['j_low_b'] if jv < 20 else 0)
    score += (w.get('kdj_b', 0) if s.get('kdj_golden', 0) else 0)  # KDJ金叉加分
    score += penalty  # 分级惩罚分
    
    return {'score': score, 'n': nh, 'p': p, 'name': nm[:12], 'code': s['code'],
            'cl': cl, 'vr': vr, 'hsl': hsl, 'buy': buy, 'sz': ri.get('shizhi',0) or 0}

def run(stocks, real, names):
    """主入口：猜行情 → 分级选股 → 评分 → 出结果"""
    mkt = classify_market(stocks)
    strategy = STRATEGIES[mkt]
    
    # 加载子策略的分级
    levels, penalties = get_sub_strategy(strategy['module'])
    lvl_map = {l['name']: i for i, l in enumerate(levels)}
    
    used_level = None
    cand = []
    
    # 分级筛选 L0→L2→L3→L4
    for lvl_name in LEVEL_ORDER:
        if lvl_name not in lvl_map: continue
        idx = lvl_map[lvl_name]
        pool = filter_by_level(stocks, real, names, levels[idx])
        
        if len(pool) >= 10:
            used_level = lvl_name
            penalty = penalties[idx]
            for s in pool:
                r = score_stock(s, real, names, strategy, penalty)
                if r: cand.append(r)
            cand.sort(key=lambda x: (-x['score'], -x['p']))
            break
    
    return mkt, strategy['name'], cand, used_level

if __name__ == '__main__':
    data, real, names = load_cache()
    today = datetime.now().strftime('%Y-%m-%d')
    dates = sorted(data.keys())
    sel_date = today if today in data else dates[-1]
    
    mkt, sname, cand, level = run(data.get(sel_date, []), real, names)
    level_str = f'[{level}]' if level else '[无池]'
    print(f"大道至简策略 v1.0 (分级)")
    print(f"日期: {sel_date} | 行情: {sname} {level_str}")
    print(f"候选: {len(cand)}只")
    print(f"\n{'名':>3} {'名称':<12} {'评分':>6} {'涨幅':>5} {'CL':>3} {'量比':>5}")
    print('-'*45)
    for i, c in enumerate(cand[:10]):
        print(f"{i+1:3d} {c['name']:<12} {c['score']:6.1f} {c['p']:+4.1f}% {c['cl']:3.0f}% {c['vr']:5.2f}")
