"""
横盘 - ma5_slope阈值和力度精细化测试
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

orig = mod_flat.score

# ma5_slope 阈值+力度网格搜索
test_cases = []
for thresh in [2, 3, 4, 5, 6, 8, 10]:
    for bonus in [5, 8, 10, 12, 15]:
        test_cases.append((f'ms5>{thresh}+{bonus}', thresh, bonus))

# 再试试扣分版
for thresh in [-2, -3, -5, -8]:
    for bonus in [-5, -8, -10, -15]:
        test_cases.append((f'ms5<{thresh}{bonus}', thresh, bonus))

# 反转测试：ma5_slope低反而好（暗示跌到位了）
test_cases.append(('ms5Neg+8', lambda s: 8 if (s.get('ma5_slope',0) or 0) < -5 else 0))

date_list = sorted(dates_all)
cutoff_100 = date_list[-100]
cutoff_50 = date_list[-50]
cutoff_30 = date_list[-30]

print("=" * 60)
print("横盘 ma5_slope 参数搜索 (100天)")
print("=" * 60)
best_schemes = []
for name, thresh, bonus in test_cases[:30]:  # 先测试加分
    def make_fn(t=thresh, b=bonus):
        def fn(s):
            ms = s.get('ma5_slope',0) or 0
            if t > 0 and ms > t: return b
            return 0
        return fn
    sf = lambda s, orig=orig, t=thresh, b=bonus: round(orig(s) + (b if (s.get('ma5_slope',0) or 0) > t else 0), 1)
    
    r100 = run_segment('flat', sf, mod_flat.LEVELS, cutoff_100)
    r50 = run_segment('flat', sf, mod_flat.LEVELS, cutoff_50)
    wr100 = r100['wins']/len(r100['nh_list'])*100 if r100['nh_list'] else 0
    wr50 = r50['wins']/len(r50['nh_list'])*100 if r50['nh_list'] else 0
    print(f"{name:15s} | 50天:{wr50:5.1f}%({len(r50['nh_list']):2d}) | 100天:{wr100:5.1f}%({len(r100['nh_list']):2d})")
    
# 基线
br100 = run_segment('flat', orig, mod_flat.LEVELS, cutoff_100)
br50 = run_segment('flat', orig, mod_flat.LEVELS, cutoff_50)
bwr100 = br100['wins']/len(br100['nh_list'])*100 if br100['nh_list'] else 0
bwr50 = br50['wins']/len(br50['nh_list'])*100 if br50['nh_list'] else 0
print(f"{'基线':15s} | 50天:{bwr50:5.1f}%({len(br50['nh_list']):2d}) | 100天:{bwr100:5.1f}%({len(br100['nh_list']):2d})")

print(f"\n扣分版测试:")
for name, thresh, bonus in test_cases:
    if thresh > 0: continue  # skip positive thresholds
    if not isinstance(thresh, int) and not isinstance(thresh, float): continue
    if not isinstance(bonus, int) and not isinstance(bonus, float): continue
    t, b = thresh, bonus
    sf = lambda s, orig=orig, tt=t, bb=b: round(orig(s) + (bb if (s.get('ma5_slope',0) or 0) < tt else 0), 1)
    r100 = run_segment('flat', sf, mod_flat.LEVELS, cutoff_100)
    r50 = run_segment('flat', sf, mod_flat.LEVELS, cutoff_50)
    wr100 = r100['wins']/len(r100['nh_list'])*100 if r100['nh_list'] else 0
    wr50 = r50['wins']/len(r50['nh_list'])*100 if r50['nh_list'] else 0
    print(f"{name:15s} | 50天:{wr50:5.1f}%({len(r50['nh_list']):2d}) | 100天:{wr100:5.1f}%({len(r100['nh_list']):2d})")
