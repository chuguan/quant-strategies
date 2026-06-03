"""
V50新因子测试 - 逐个测试横盘
"""
import sys, os, importlib

WORK = os.path.expanduser('~/AppData/Local/hermes/scripts')
V50_DIR = os.path.join(WORK, 'release/V50')
sys.path.insert(0, V50_DIR)
sys.path.insert(0, os.path.join(V50_DIR, '评分策略'))

exec(open(os.path.join(WORK, '_v50_framework.py')).read())

mod_flat = importlib.import_module('分而治之_V10_横盘_评分策略')
mod_down = importlib.import_module('分而治之_V10_跌日_评分策略')
mod_real = importlib.import_module('分而治之_V10_真实涨日_评分策略')

def run_segment(mk, score_fn, levels, cutoff_date=None):
    mk_dates = mkt_dates[mk]
    if cutoff_date: mk_dates = [x for x in mk_dates if x >= cutoff_date]
    total_days = 0; has_cand = 0; wins = 0; nh_list = []
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
            has_cand += 1; sc, nh, code, nm = selected; nh_list.append(nh)
            if nh >= 2.5: wins += 1
    return {'total': total_days, 'has_cand': has_cand, 'wins': wins, 'nh_list': nh_list}

date_list = sorted(dates_all)
periods = [
    ('30天', date_list[-30] if len(date_list) >= 30 else date_list[0]),
    ('50天', date_list[-50] if len(date_list) >= 50 else date_list[0]),
    ('100天', date_list[-100] if len(date_list) >= 100 else date_list[0]),
]

def make_score(extra_fn):
    orig = mod_flat.score
    def wrapped(s):
        v = orig(s); v += extra_fn(s); return round(v, 1)
    return wrapped

# 测试方案列表
test_cases = [
    ('基线', lambda s: 0),
    ('above_ma10+5', lambda s: 5 if (s.get('above_ma10',0)) == 1 else 0),
    ('above_ma20+5', lambda s: 5 if (s.get('above_ma20',0)) == 1 else 0),
    ('is_yang+3', lambda s: 3 if (s.get('is_yang',0)) == 1 else 0),
    ('ma5_slope>5 +3', lambda s: 3 if (s.get('ma5_slope',0) or 0) > 5 else 0),
    ('body_pct>3 +3', lambda s: 3 if (s.get('body_pct',0) or 0) > 3 else 0),
    ('ma5_slope<-5 -5', lambda s: -5 if (s.get('ma5_slope',0) or 0) < -5 else 0),
    ('ma10+ma5>5 +5', lambda s: 5 if (s.get('above_ma10',0)) == 1 and (s.get('ma5_slope',0) or 0) > 5 else 0),
]

print("=" * 55)
print("横盘新因子测试")
print("=" * 55)

for label, cutoff in periods:
    print(f"\n▶ {label}")
    print(f"{'方案':18s} | {'出票':6s} | {'胜率':7s} | {'样本':5s}")
    print("-" * 42)
    for name, extra_fn in test_cases:
        sf = make_score(extra_fn)
        r = run_segment('flat', sf, mod_flat.LEVELS, cutoff)
        cp = r['has_cand']/r['total']*100 if r['total'] else 0
        wr = r['wins']/len(r['nh_list'])*100 if r['nh_list'] else 0
        print(f"{name:18s} | {cp:4.1f}% | {wr:5.1f}% | {len(r['nh_list'])})")

# 跌日测试
def make_down_score(extra_fn):
    orig = mod_down.score
    def wrapped(s):
        v = orig(s); v += extra_fn(s); return round(v, 1)
    return wrapped

down_cases = [
    ('基线', lambda s: 0),
    ('is_yang+5', lambda s: 5 if (s.get('is_yang',0)) == 1 else 0),  # 跌日中的阳线=强
    ('above_ma10+3', lambda s: 3 if (s.get('above_ma10',0)) == 1 else 0),
    ('body>5+5', lambda s: 5 if (s.get('body_pct',0) or 0) > 5 else 0),
    ('ma5_slope>-3 +3', lambda s: 3 if (s.get('ma5_slope',0) or 0) > -3 else 0), # 斜率不太差
    ('amplitude>5 -3', lambda s: -3 if (s.get('amplitude',0) or 0) > 5 else 0), # 振幅大=恐慌
]

print(f"\n{'='*55}")
print("跌日新因子测试")
print(f"{'='*55}")
for label, cutoff in periods[:2]:  # 50天+100天
    print(f"\n▶ {label}")
    print(f"{'方案':18s} | {'出票':6s} | {'胜率':7s} | {'样本':5s}")
    print("-" * 42)
    for name, extra_fn in down_cases:
        sf = make_down_score(extra_fn)
        r = run_segment('down', sf, mod_down.LEVELS, cutoff)
        cp = r['has_cand']/r['total']*100 if r['total'] else 0
        wr = r['wins']/len(r['nh_list'])*100 if r['nh_list'] else 0
        print(f"{name:18s} | {cp:4.1f}% | {wr:5.1f}% | {len(r['nh_list'])})")

# 真实涨日测试
def make_real_score(extra_fn):
    orig = mod_real.score
    def wrapped(s):
        v = orig(s); v += extra_fn(s); return round(v, 1)
    return wrapped

real_cases = [
    ('基线', lambda s: 0),
    ('above_ma10+5', lambda s: 5 if (s.get('above_ma10',0)) == 1 else 0),
    ('above_ma20+5', lambda s: 5 if (s.get('above_ma20',0)) == 1 else 0),
    ('body>5+3', lambda s: 3 if (s.get('body_pct',0) or 0) > 5 else 0),
    ('yang+above_ma10+5', lambda s: 5 if (s.get('is_yang',0)) == 1 and (s.get('above_ma10',0)) == 1 else 0),
]

print(f"\n{'='*55}")
print("真实涨日新因子测试")
print(f"{'='*55}")
for label, cutoff in periods[:2]:
    print(f"\n▶ {label}")
    print(f"{'方案':20s} | {'出票':6s} | {'胜率':7s} | {'样本':5s}")
    print("-" * 44)
    for name, extra_fn in real_cases:
        sf = make_real_score(extra_fn)
        r = run_segment('real_up', sf, mod_real.LEVELS, cutoff)
        cp = r['has_cand']/r['total']*100 if r['total'] else 0
        wr = r['wins']/len(r['nh_list'])*100 if r['nh_list'] else 0
        print(f"{name:20s} | {cp:4.1f}% | {wr:5.1f}% | {len(r['nh_list'])})")
