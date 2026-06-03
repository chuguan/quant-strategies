"""
V260529-01 跌日评分优化
测试多种评分变体，对比30天/80天冠军胜率
"""
import pickle, os, sys, importlib

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)

d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, real, names = d['data'], d['real'], d['names']
dates = sorted(x for x in data.keys() if '2025-01-01' <= x < '2026-06-01')

# ===== 跌日L级参数（从子策略文件加载） =====
mod = importlib.import_module('大道至简_跌日_评分策略')
lv = mod.LEVELS[0]  # L0=最严
# 重命名为L
lv = {**lv, 'name': 'L'}

def classify_mkt(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p',0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

# ===== 各种评分变体 =====
def score_baseline(s):
    """当前跌日评分（原始版）"""
    p = s['p']; cl = s['cl']; dif = s['dif']; mg = s['mg']
    a5 = s['a5']; jv = s['jv']; kv = s['kv']; dv = s['dv']
    ms = 0
    if mg and dif > 0.5: ms = 10
    elif mg and dif > 0.2: ms = 8
    elif mg: ms = 6
    elif dif > 0.5: ms = 4
    elif dif > 0: ms = 2
    ps2 = min(10, max(1, 11 - s['buy_c']/10)) if s['buy_c'] else 0
    sc = p * 1.5 + cl * 0.05 + ps2 * 0.3 + ms * 0.3
    sc += (2 if a5 else 0)
    sc += (3 if 20 <= jv <= 40 else 0)
    return sc

def score_vA(s):
    """A: j_low放宽到15~45"""
    sc = score_baseline(s)
    jv = s['jv']
    # 替换j_low条件（覆盖原+3）
    sc -= (3 if 20 <= jv <= 40 else 0)
    sc += (3 if 15 <= jv <= 45 else 0)
    return sc

def score_vB(s):
    """B: 加WR超卖信号(wrv > 75 → +3)"""
    sc = score_baseline(s)
    sc += (3 if s['wrv'] > 75 else 0)
    return sc

def score_vC(s):
    """C: 加CL超跌(cl < 15 → +3)"""
    sc = score_baseline(s)
    sc += (3 if s['cl'] < 15 else 0)
    return sc

def score_vD(s):
    """D: 加大跌幅惩罚(p < -3 → +2，跌越深反弹越强)"""
    sc = score_baseline(s)
    sc += (2 if s['p'] < -3 else 0)
    return sc

def score_vE(s):
    """E: 降低p_w从1.5到1.0"""
    sc = score_baseline(s)
    # 重算：p_w=1.0替换原始p*1.5
    sc2 = s['p'] * 1.0 + s['cl'] * 0.05 + 0  # +价格分+MACD已包含
    sc2 += (2 if s['a5'] else 0)
    sc2 += (3 if 20 <= s['jv'] <= 40 else 0)
    ms = 0
    if s['mg'] and s['dif'] > 0.5: ms = 10
    elif s['mg'] and s['dif'] > 0.2: ms = 8
    elif s['mg']: ms = 6
    elif s['dif'] > 0.5: ms = 4
    elif s['dif'] > 0: ms = 2
    ps2 = min(10, max(1, 11 - s['buy_c']/10)) if s['buy_c'] else 0
    sc2 += ps2 * 0.3 + ms * 0.3
    return sc2

def score_vF(s):
    """F: 加MACD势头加分(dif>0.3→+2)"""
    sc = score_baseline(s)
    sc += (2 if s['dif'] > 0.3 else 0)
    return sc

def score_vG(s):
    """G: 组合B+C+D — WR超卖+CL超跌+深度跌幅"""
    sc = score_baseline(s)
    sc += (3 if s['wrv'] > 75 else 0)
    sc += (3 if s['cl'] < 15 else 0)
    sc += (2 if s['p'] < -3 else 0)
    return sc

def score_vH(s):
    """H: 去掉j_low，改加WR+CL超跌"""
    sc = score_baseline(s)
    sc -= (3 if 20 <= s['jv'] <= 40 else 0)  # 去掉j_low
    sc += (3 if s['wrv'] > 75 else 0)
    sc += (3 if s['cl'] < 15 else 0)
    sc += (2 if s['p'] < -3 else 0)
    return sc

def score_vI(s):
    """I: 调整权重 — p_w=2.0 + j_low范围20~50"""
    sc = score_baseline(s)
    sc -= (3 if 20 <= s['jv'] <= 40 else 0)
    sc += (3 if 20 <= s['jv'] <= 50 else 0)
    # 提高涨幅权重的影响（间接通过重算）
    p_part = s['p'] * 2.0  # 原来是1.5
    old_part = s['p'] * 1.5
    sc += (p_part - old_part)
    return sc

# 所有变体
VARIANTS = [
    ('基线', score_baseline),
    ('A_j_low15~45', score_vA),
    ('B_WR超卖+3', score_vB),
    ('C_CL超跌+3', score_vC),
    ('D_深跌+2', score_vD),
    ('E_p_w=1.0', score_vE),
    ('F_MACD>0.3+2', score_vF),
    ('G_B+C+D组合', score_vG),
    ('H_去j改WR+CL', score_vH),
    ('I_p_w=2.0+j_20~50', score_vI),
]

def run_variant(score_fn, max_days=None):
    """跑单变体回测"""
    test_dates = dates[-max_days:] if max_days else dates
    wins30 = 0; total30 = 0
    wins80 = 0; total80 = 0
    wins_all = 0; total_all = 0
    
    for dt in test_dates:
        stocks = data.get(dt, [])
        if not stocks: continue
        if classify_mkt(stocks) != 'down': continue
        
        pool = []
        for s in stocks:
            code = s.get('code',''); p = s.get('p',0) or 0
            if p < lv['p_min'] or p > lv['p_max']: continue
            if p >= 8: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            ri = real.get(code)
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < lv['hs_min'] or hsl > lv['hs_max']: continue
            if (ri.get('shizhi',0) or 0) >= lv['sz_max']: continue
            nm = names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl = s.get('cl',0)
            if cl < lv['cl_min'] or cl > lv['cl_max']: continue
            nh = s.get('n',0) or 0
            if nh <= 0: continue
            pool.append(s)
        
        if len(pool) <= 8: continue
        
        scored = []
        for s in pool:
            stock_data = {
                'p': s.get('p',0) or 0, 'cl': s.get('cl',0),
                'vr': s.get('vol_ratio',0) or 0,
                'hsl': (real.get(s['code'],{}).get('hsl',0) or 0),
                'dif': s.get('dif_val',0) or 0, 'mg': s.get('macd_golden',0),
                'a5': s.get('above_ma5',0) or 0, 'wrv': 0,
                'jv': s.get('j_val',0) or 0, 'kv': s.get('k_val',0) or 0,
                'dv': s.get('d_val',0) or 0,
                'kdj_g': s.get('kdj_golden',0) or 0,
                'buy_c': s.get('close',0) or 0,
            }
            sc = score_fn(stock_data)
            nh = s.get('n',0) or 0
            scored.append({'sc':sc, 'nh':nh})
        
        if not scored: continue
        scored.sort(key=lambda x: (-x['sc']))
        
        total_all += 1
        if scored[0]['nh'] >= 2.5: wins_all += 1
        
        # 区分30天和80天
        idx = test_dates.index(dt)
        days_from_end = len(test_dates) - 1 - idx
        
        if days_from_end < 30:
            total30 += 1
            if scored[0]['nh'] >= 2.5: wins30 += 1
        if days_from_end < 80:
            total80 += 1
            if scored[0]['nh'] >= 2.5: wins80 += 1
    
    return {
        '30天': f"{wins30*100/total30:.1f}%({wins30}/{total30})" if total30 else '—',
        '80天': f"{wins80*100/total80:.1f}%({wins80}/{total80})" if total80 else '—',
        '全量': f"{wins_all*100/total_all:.1f}%({wins_all}/{total_all})" if total_all else '—',
    }

print("\n" + "="*70)
print("V260529-01 跌日评分优化测试")
print("="*70)
print(f"{'变体':<20} {'30天':<16} {'80天':<16} {'全量':<16}")
print("-"*70)

for name, fn in VARIANTS:
    r = run_variant(fn)
    print(f"{name:<20} {r['30天']:<16} {r['80天']:<16} {r['全量']:<16}")
