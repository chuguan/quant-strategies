"""V42 vs V47 对比回测 — 近30天"""
import pickle, os, sys, importlib

SCRIPTS_DIR = r'C:\Users\12546\AppData\Local\hermes\scripts'
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')

# 加载V42和V47评分策略
VERSIONS = {}
for ver in ['V42', 'V47']:
    VDIR = os.path.join(SCRIPTS_DIR, 'release', ver, '评分策略')
    STRATS = {}
    for n in ['真实涨日','虚涨日','跌日','横盘']:
        fp = os.path.join(VDIR, f'分而治之_V10_{n}_评分策略.py')
        spec = importlib.util.spec_from_file_location(f'{ver}_{n}', fp)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        STRATS[n] = (m, m.score)
    VERSIONS[ver] = STRATS

with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d['real'], d['names']

with open(os.path.join(V13_DIR, 'features_30d.pkl'), 'rb') as f:
    precomputed = pickle.load(f)

dates = sorted(k for k in data.keys() if '2025-01-01'<=k<='2026-05-28')

def mkt_class(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

MK_MAP = {'real_up': '真实涨日', 'fake_up': '虚涨日', 'down': '跌日', 'flat': '横盘'}
LO = ['L0','L1','L2','L3','L4']

for ver_name, strats in VERSIONS.items():
    print(f"\n===== {ver_name} =====")
    all_top3 = []
    
    for dt in dates:
        ss = data[dt]
        ss = [s for s in ss if (s.get('p', 0) or 0) < 15]
        if not ss: continue
        
        mk = mkt_class(ss)
        mk_cn = MK_MAP.get(mk, '横盘')
        if mk_cn not in strats: continue
        
        mod, score_fn = strats[mk_cn]
        LEVELS = mod.LEVELS
        
        lm = {l['name']:i for i,l in enumerate(LEVELS)}
        pool = None
        for ln in LO:
            if ln not in lm: continue
            i = lm[ln]; lv = LEVELS[i]
            cand = []
            for s in ss:
                p = s.get('p',0) or 0
                if p < lv.get('p_min', -999) or p > lv.get('p_max', 999): continue
                vr = s.get('vol_ratio', 0) or s.get('vr', 0) or 0
                if vr < lv.get('vr_min', 0) or vr > lv.get('vr_max', 999): continue
                ri_hsl = real.get(s.get('code',''), {})
                hs = ri_hsl.get('hsl', 0) or 0
                if hs < lv.get('hs_min', 0) or hs > lv.get('hs_max', 999): continue
                cl = s.get('cl',50) or 50
                if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
                if lv.get('a5_req', 0) and not s.get('above_ma5',0): continue
                if lv.get('kdj_g_req', 0) and not (s.get('kdj_golden',0) or s.get('kdj_g',0)): continue
                cand.append(s)
            if len(cand) >= 10:
                pool = cand
                break
        
        if pool is None or len(pool) < 10: continue
        
        scored = []
        for s in pool:
            code = s.get('code', '')
            stock = {}
            stock['p'] = s.get('p', 0) or 0
            stock['cl'] = s.get('cl', 50)
            stock['vr'] = s.get('vol_ratio', 1) or s.get('vr', 1)
            stock['dif'] = s.get('dif_val', 0) or s.get('dif', 0)
            stock['mg'] = s.get('macd_golden', 0) or s.get('mg', 0)
            stock['wrv'] = s.get('wr_val', 0) or s.get('wrv', 50)
            stock['dv'] = s.get('d_val', 0) or s.get('dv', 50)
            stock['a5'] = s.get('above_ma5', 0)
            stock['kdj_g'] = s.get('kdj_golden', 0) or s.get('kdj_g', 0)
            stock['pos_in_day'] = s.get('pos_in_day', 50)
            stock['nm'] = s.get('nm', '') or s.get('name', '') or names.get(code, '')
            ri = real.get(code, {})
            stock['hsl'] = ri.get('hsl', 0) or 0
            feats = precomputed.get((code, dt), {})
            stock['t4_shadow'] = feats.get('t4_shadow', 0)
            stock['slope5'] = feats.get('slope5', 0)
            stock['cons_up'] = feats.get('cons_up', 0)
            
            sc = score_fn(stock)
            if sc > 0:
                scored.append((sc, code, s))
        
        scored.sort(key=lambda x: -x[0])
        
        for rank, (sc, code, s) in enumerate(scored[:3], 1):
            nh = s.get('next_high', 0) or 0
            all_top3.append({
                'dt': dt, 'mk': mk_cn, 'rank': rank, 'score': sc,
                'code': code, 'name': names.get(code, code[:8]),
                'p': s.get('p',0) or 0,
                'nh': nh,
                'ok': 1 if nh >= 2.5 else 0,
            })
    
    oks = [r for r in all_top3 if r['ok']]
    fails = [r for r in all_top3 if not r['ok']]
    
    # 按日期统计（每天只要TOP3任一达标就算当天赢）
    date_results = {}
    for r in all_top3:
        dt = r['dt']
        if dt not in date_results:
            date_results[dt] = {'ok': False, 'total': 0}
        date_results[dt]['total'] += 1
        if r['ok']:
            date_results[dt]['ok'] = True
    
    total_days = len(date_results)
    win_days = sum(1 for dr in date_results.values() if dr['ok'])
    
    # 近30天
    recent_dates = sorted(date_results.keys())[-30:]
    recent_win = sum(1 for dt in recent_dates if date_results[dt]['ok'])
    
    print(f"天数: {total_days}")
    print(f"全量: {win_days}/{total_days} = {win_days/total_days*100:.1f}%")
    print(f"近30天: {recent_win}/{len(recent_dates)} = {recent_win/len(recent_dates)*100:.1f}%")
    print(f"TOP3达标: {len(oks)}/{len(all_top3)} = {len(oks)/len(all_top3)*100:.1f}%")
    print(f"TOP3失败: {len(fails)}只")
    
    # 被p>6否决的票有多少
    if ver_name == 'V47':
        veto_count = 0
        for dt in dates:
            ss = data[dt]
            for s in ss:
                if (s.get('p', 0) or 0) > 6:
                    veto_count += 1
        print(f"p>6的票在数据中: {veto_count}条")
        # 这些被否决的票如果没被否决会不会达标
        veto_ok = 0
        veto_total = 0
        for dt in dates[-60:]:  # 只看近60天
            ss = data[dt]
            for s in ss:
                if (s.get('p', 0) or 0) > 6:
                    nh = s.get('next_high', 0) or 0
                    veto_total += 1
                    if nh >= 2.5:
                        veto_ok += 1
        print(f"近60天p>6的票: {veto_total}只, 其中达标: {veto_ok}({veto_ok/max(veto_total,1)*100:.1f}%)")
    
    print()
