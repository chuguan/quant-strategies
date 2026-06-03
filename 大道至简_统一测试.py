"""
统一真实胜率核算 — 4行情用各自的子策略模块+正确字段映射
"""
import pickle, os, sys, json, importlib
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))

d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, real, names = d['data'], d['real'], d['names']
dates_all = [x for x in sorted(data.keys()) if '2025-01-01' <= x < '2026-06-01']

# 从缓存item构建评分用的stock dict
def build_stock_dict(s):
    code = s.get('code','')
    ri = real.get(code, {})
    return {
        'p': s.get('p',0) or 0,
        'cl': s.get('cl',0),
        'vr': s.get('vol_ratio',0) or 0,
        'hsl': (ri.get('hsl',0) or 0),
        'dif': s.get('dif_val',0) or 0,
        'mg': s.get('macd_golden',0) or 0,
        'a5': s.get('above_ma5',0) or 0,
        'wrv': s.get('wr_val',0) or 20,
        'jv': s.get('j_val',0) or 0,
        'kv': s.get('k_val',0) or 0,
        'dv': s.get('d_val',0) or 0,
        'kdj_g': s.get('kdj_golden',0) or 0,
        'buy_c': s.get('close',0) or 0,
    }

def classify_market(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p',0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

def get_filtered_dates():
    """预分类所有日期"""
    mkt_dates = {'real_up':[], 'fake_up':[], 'down':[], 'flat':[]}
    for dt in dates_all:
        stocks = data.get(dt, [])
        if not stocks: continue
        mkt = classify_market(stocks)
        mkt_dates[mkt].append(dt)
    return mkt_dates

mkt_dates = get_filtered_dates()

def run_regime(mkt_key, mod, fn_name):
    """用模块的评分函数和LEVELS跑回测"""
    score_fn = getattr(mod, fn_name)
    levels = mod.LEVELS
    dates = mkt_dates[mkt_key]
    
    wins_all = 0; total_all = 0
    wins_30 = 0; total_30 = 0
    wins_80 = 0; total_80 = 0
    
    for i, dt in enumerate(dates):
        stocks = data.get(dt, [])
        if not stocks: continue
        
        # 分级筛选
        cand = None
        for lv in levels:
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
                if (s.get('n',0) or 0) <= 0: continue
                pool.append(s)
            if len(pool) > 8:
                cand = pool
                break
        if not cand or len(cand) <= 8: continue
        
        # 用模块的评分函数
        scored = [(score_fn(build_stock_dict(s)), s.get('n',0) or 0) for s in cand]
        scored.sort(key=lambda x: (-x[0]))
        champ_nh = scored[0][1]
        
        # 计算在30/80天窗口内
        days_from_end = len(dates) - i
        
        total_all += 1
        if champ_nh >= 2.5: wins_all += 1
        
        if days_from_end <= 30:
            total_30 += 1
            if champ_nh >= 2.5: wins_30 += 1
        
        if days_from_end <= 80:
            total_80 += 1
            if champ_nh >= 2.5: wins_80 += 1
    
    r_all = f"{wins_all*100/total_all:.1f}%" if total_all else "—"
    r_30 = f"{wins_30*100/total_30:.1f}%" if total_30 else "—"
    r_80 = f"{wins_80*100/total_80:.1f}%" if total_80 else "—"
    return r_all, r_30, r_80, total_all, total_30, total_80, wins_all, wins_30, wins_80

# 测试所有行情
REGIMES = [
    ('real_up', '真实涨日', '大道至简_真实涨日_评分策略', '真实涨日_评分'),
    ('fake_up', '虚涨日', '大道至简_虚涨日_评分策略', '虚涨日_评分'),
    ('down', '跌日', '大道至简_跌日_评分策略', '跌日_评分'),
    ('flat', '横盘', '大道至简_横盘_评分策略', '横盘_评分'),
]

print(f"{'='*75}")
print(f"{'行情':10s} | {'版本':25s} | {'全量':>10s} | {'30天':>10s} | {'80天':>10s} | {'天':>4s}")
print(f"{'='*75}")

for mkt_key, mkt_name, mod_name, fn_name in REGIMES:
    mod = importlib.import_module(mod_name)
    # 获取描述中的版本号
    doc = mod.__doc__ or ''
    lines = [l.strip() for l in doc.split('\n') if l.strip() and not l.startswith('"""')]
    version = lines[1] if len(lines) >= 2 else mod_name
    
    r_all, r_30, r_80, t_all, t_30, t_80, w_all, w_30, w_80 = run_regime(mkt_key, mod, fn_name)
    print(f"{mkt_name:10s} | {version:25s} | {r_all:>10s} | {r_30:>10s} | {r_80:>10s} | {t_all:>4d}")

print(f"{'='*75}")
print(f"总计天数: 真实涨日{len(mkt_dates['real_up'])}天 虚涨日{len(mkt_dates['fake_up'])}天 跌日{len(mkt_dates['down'])}天 横盘{len(mkt_dates['flat'])}天")
