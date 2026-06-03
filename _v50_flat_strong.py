"""
横盘 - 加大力度测试
用更强加减分改变选股结果
"""
import sys, os, importlib

WORK = os.path.expanduser('~/AppData/Local/hermes/scripts')
V50_DIR = os.path.join(WORK, 'release/V50')
sys.path.insert(0, V50_DIR)
sys.path.insert(0, os.path.join(V50_DIR, '评分策略'))
exec(open(os.path.join(WORK, '_v50_framework.py')).read())

mod_flat = importlib.import_module('分而治之_V10_横盘_评分策略')

def run_segment(mk, score_fn, levels, cutoff_date=None):
    mk_dates = mkt_dates[mk]
    if cutoff_date: mk_dates = [x for x in mk_dates if x >= cutoff_date]
    total_days = 0; has_cand = 0; wins = 0; nh_list = []; fail_list = []; codes = []
    for dt in mk_dates:
        s = data.get(dt, []); total_days += 1; selected = None
        for lv in levels:
            pool = []
            for sx in s:
                code = sx.get('code',''); p = sx.get('p',0) or 0
                if p < lv['p_min'] or p > lv['p_max'] or p >= 8: continue
                vr = sx.get('vol_ratio',0) or 0
                if vr < lv['vr_min'] or vr > lv['vr_max']: continue
                cl = sx.get('cl',0) or 0
                if cl < lv['cl_min'] or cl > lv['cl_max']: continue
                ri = real.get(code)
                if ri:
                    hsl = ri.get('hsl',0) or 0
                    if hsl < lv['hs_min'] or hsl > lv['hs_max']: continue
                    sz = ri.get('shizhi',0) or 0
                    if isinstance(sz,(int,float)) and sz > 1: sz *= 1e-8
                    if sz >= lv['sz_max']: continue
                nm = names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                if (sx.get('n',0) or 0) <= 0: continue
                stock = build(sx, ri)
                sc = score_fn(stock)
                nh = sx.get('n',0) or 0
                pool.append((sc, nh, code, nm[:6]))
            if len(pool) > 8:
                pool.sort(key=lambda x: -x[0]); selected = pool[0]; break
        if selected:
            has_cand += 1; sc, nh, code, nm = selected; nh_list.append(nh); codes.append(code)
            if nh >= 2.5: wins += 1
            else: fail_list.append(f'{dt} {nm}({code}) nh={nh:.1f}')
    return {'total': total_days, 'has_cand': has_cand, 'wins': wins, 'nh_list': nh_list, 'codes': codes, 'fail_list': fail_list}

def make_score(extra_fn):
    orig = mod_flat.score
    def wrapped(s):
        v = orig(s); v += extra_fn(s); return round(v, 1)
    return wrapped

# 更强加减分方案
test_cases = [
    ('基线', lambda s: 0),
    ('ma10+ma5>5 +20', lambda s: 20 if (s.get('above_ma10',0)) == 1 and (s.get('ma5_slope',0) or 0) > 5 else 0),
    ('ma10+ma5>5 +10', lambda s: 10 if (s.get('above_ma10',0)) == 1 and (s.get('ma5_slope',0) or 0) > 5 else 0),
    ('ma5_slope>5 +10', lambda s: 10 if (s.get('ma5_slope',0) or 0) > 5 else 0),
    ('ma5_slope<-8 -20', lambda s: -20 if (s.get('ma5_slope',0) or 0) < -8 else 0),
    ('ma5_slope<-5 -15', lambda s: -15 if (s.get('ma5_slope',0) or 0) < -5 else 0),
    ('above_ma10 +15', lambda s: 15 if (s.get('above_ma10',0)) == 1 else 0),
    ('has_ma10+ma20 +15', lambda s: 15 if (s.get('above_ma10',0)) == 1 and (s.get('above_ma20',0)) == 1 else 0),
    ('ma5_3_ma10 +5', lambda s: 5 if (s.get('ma5_slope',0) or 0) > 3 and (s.get('above_ma10',0)) == 1 else 0),
    ('ma5_negs -10', lambda s: -10 if (s.get('ma5_slope',0) or 0) < -3 else 0),
]

date_list = sorted(dates_all)
periods = [
    ('30天', date_list[-30] if len(date_list) >= 30 else date_list[0]),
    ('50天', date_list[-50] if len(date_list) >= 50 else date_list[0]),
    ('100天', date_list[-100] if len(date_list) >= 100 else date_list[0]),
]

print("=" * 55)
print("横盘 - 强力度因子测试")
print("=" * 55)
for label, cutoff in periods:
    print(f"\n▶ {label}")
    print(f"{'方案':20s} | {'出票':6s} | {'胜率':7s} | {'样本':5s} | {'差异天':6s}")
    print("-" * 48)
    
    for name, extra_fn in test_cases:
        sf = make_score(extra_fn)
        r = run_segment('flat', sf, mod_flat.LEVELS, cutoff)
        cp = r['has_cand']/r['total']*100 if r['total'] else 0
        wr = r['wins']/len(r['nh_list'])*100 if r['nh_list'] else 0
        
        # 与基线比较胜率差值
        if name == '基线':
            base_wr = wr
            base_nh = sum(r['nh_list'])/len(r['nh_list']) if r['nh_list'] else 0
            print(f"{name:20s} | {cp:4.1f}% | {wr:5.1f}% | {len(r['nh_list'])})")
        else:
            diff = wr - base_wr
            arrow = '⬆' if diff > 1 else ('⬇' if diff < -1 else '➡')
            print(f"{name:20s} | {cp:4.1f}% | {wr:5.1f}% | {len(r['nh_list'])}) | {diff:+.1f}%{arrow}")
