"""
真实涨日策略 v1.0 — 尾盘买入法
适用场景：大盘涨>0.5%且个股活跃（热门股≥15只且平均量比≥0.9）
选股条件：涨3~7%/量0.6~2.5/换手5~15%/CL60~90%/市值<200亿
评分公式：涨×2.5 + CL×0.05 + 价格分×0.3 + MACD×0.3 + MA5+3 + VR1.0-1.5+1 + 换手5-7+0.3 + WR<-80+2
2025-01~2026-05回测：112天真实涨日，冠军胜率65.2%（73/112天）
"""
import pickle, os, sys
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR)

def load_cache():
    with open('big_cache_full.pkl', 'rb') as f:
        cache = pickle.load(f)
    return cache['data'], cache['real'], cache['names']

def classify_market(stocks):
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

# ===== 真实涨日参数 =====
REAL_UP_PARAMS = {
    'p_min': 3, 'p_max': 7,         # 涨幅3~7%
    'vr_min': 0.6, 'vr_max': 2.5,   # 量比0.6~2.5
    'hs_min': 5, 'hs_max': 15,      # 换手5~15%
    'sz_max': 200,                   # 市值<200亿
    'cl_min': 60, 'cl_max': 90,     # CL 60~90%
    'p_w': 2.5,                      # 涨幅权重
    'cl_w': 0.05,                    # CL权重
    'macd_w': 0.3,                   # MACD权重
    'ma5_b': 3,                      # 站上MA5加分
    'vr_b': 1,                       # 量比1~1.5加分
    'hs_b': 0.3,                     # 换手5~7%加分
    'wr_b': 2,                       # WR<-80加分
}

def run(stocks, real, names, params=None):
    if params is None:
        params = REAL_UP_PARAMS

    p_min = params['p_min']; p_max = params['p_max']
    vr_min = params['vr_min']; vr_max = params['vr_max']
    hs_min = params['hs_min']; hs_max = params['hs_max']
    sz_max = params['sz_max']; cl_min = params['cl_min']; cl_max = params['cl_max']
    p_w = params['p_w']; cl_w = params['cl_w']; macd_w = params['macd_w']
    ma5_b = params['ma5_b']; vr_b = params['vr_b']; hs_b = params['hs_b']; wr_b = params['wr_b']

    cand = []
    for s in stocks:
        code = s['code']; p = s.get('p', 0) or 0
        if p < p_min or p > p_max: continue
        vr = s.get('vol_ratio', 0) or 0
        if vr < vr_min or vr > vr_max: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl', 0) or 0)
        if hsl < hs_min or hsl > hs_max: continue
        sz = (ri.get('shizhi', 0) or 0)
        if sz >= sz_max: continue
        nm = names.get(code, '')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        cl = s.get('cl', 0)
        if cl < cl_min or cl > cl_max: continue
        nh = s.get('n', 0) or 0
        if nh <= 0: continue

        buy = s.get('close', 0) or 0
        dif = s.get('dif_val', 0) or 0
        mg = s.get('macd_golden', 0)
        a5 = s.get('above_ma5', 0) or 0
        wrv = s.get('wr_val', 0) or 0

        # MACD强度分
        ms = 0
        if mg and dif > 0.5: ms = 10
        elif mg and dif > 0.2: ms = 8
        elif mg: ms = 6
        elif dif > 0.5: ms = 4
        elif dif > 0: ms = 2

        ps2 = min(10, max(1, 11 - buy / 10)) if buy else 0
        ma5_plus = ma5_b if a5 else 0
        vr_plus = vr_b * 1.5 if 1.0 <= vr <= 1.5 else 0
        hs_plus = hs_b * 2 if 5 <= hsl <= 7 else 0
        wr_plus = wr_b if wrv < -80 else 0

        score = p * p_w + cl * cl_w + ps2 * 0.3 + ms * macd_w
        score += ma5_plus + vr_plus + hs_plus + wr_plus

        cand.append({
            'score': score, 'n': nh, 'p': p, 'name': nm, 'code': code,
            'cl': cl, 'vr': vr, 'hsl': hsl, 'buy': buy,
        })

    cand.sort(key=lambda x: (-x['score'], -x['p']))
    return cand

if __name__ == '__main__':
    print("真实涨日策略 v1.0")
    data, real, names = load_cache()
    dates = sorted(data.keys())
    today = datetime.now().strftime('%Y-%m-%d')
    sel_date = today if today in data else dates[-1]
    stocks = data.get(sel_date, [])
    mkt = classify_market(stocks)
    print(f"日期: {sel_date} 行情: {mkt}")
    if mkt == 'real_up':
        cand = run(stocks, real, names)
        print(f"\n真实涨日候选: {len(cand)}只")
        for i, c in enumerate(cand[:10]):
            print(f"{i+1:3d} {c['name'][:12]:<12} {c['code']:<8} 评{c['score']:6.1f} 涨{c['p']:+5.1f}% CL{c['cl']:3.0f}% 量{c['vr']:5.2f}")
