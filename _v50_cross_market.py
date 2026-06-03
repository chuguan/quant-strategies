"""
验证ma5_slope>5因子对跌日/真实涨日的影响
如有效则一并纳入V50
"""
import sys, os, importlib

WORK = os.path.expanduser('~/AppData/Local/hermes/scripts')
V50_DIR = os.path.join(WORK, 'release/V50')
sys.path.insert(0, V50_DIR)
sys.path.insert(0, os.path.join(V50_DIR, '评分策略'))
exec(open(os.path.join(WORK, '_v50_framework.py')).read())

mod_down = importlib.import_module('分而治之_V10_跌日_评分策略')
mod_real = importlib.import_module('分而治之_V10_真实涨日_评分策略')
mod_flat = importlib.import_module('分而治之_V10_横盘_评分策略')

def run_all(score_fns):
    """运行4行情+3时间段，返回结果dict"""
    results = {}
    for label, cutoff in periods:
        for mk, mod, sf in score_fns:
            key = f'{label}_{mk}'
            mk_dates = mkt_dates[mk]
            if cutoff: dts = [x for x in mk_dates if x >= cutoff]
            else: dts = mk_dates
            total=0; has_cand=0; wins=0; nh=[]
            for dt in dts:
                s = data.get(dt, []); total += 1; selected = None
                for lv in mod.LEVELS:
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
                        sc = sf(stock)
                        nh_ = sx.get('n',0) or 0
                        pool.append((sc, nh_, code, nm[:6]))
                    if len(pool) > 8:
                        pool.sort(key=lambda x: -x[0]); selected = pool[0]; break
                if selected:
                    has_cand += 1; sc, nh_, code, nm = selected; nh.append(nh_)
                    if nh_ >= 2.5: wins += 1
            results[key] = {'total': total, 'has_cand': has_cand, 'wins': wins, 'nh_list': nh}
    return results

def make_score(mod, extra_fn):
    orig = mod.score
    def wrapped(s):
        return round(orig(s) + extra_fn(s), 1)
    return wrapped

def ms5_bonus(bonus):
    return lambda s: bonus if (s.get('ma5_slope',0) or 0) > 5 else 0

date_list = sorted(dates_all)
periods = [
    ('30d', date_list[-30]),
    ('50d', date_list[-50]),
    ('100d', date_list[-100]),
]

print("=" * 55)
print("ma5_slope>5 +10 各行情影响")
print("=" * 55)

tests = [
    ('基线(原版)', [
        ('down', mod_down, mod_down.score),
        ('flat', mod_flat, mod_flat.score),
        ('real_up', mod_real, mod_real.score),
    ]),
    ('ma5>5+10', [
        ('down', mod_down, make_score(mod_down, ms5_bonus(10))),
        ('flat', mod_flat, make_score(mod_flat, ms5_bonus(10))),
        ('real_up', mod_real, make_score(mod_real, ms5_bonus(10))),
    ]),
]

for name, sc in tests:
    print(f"\n▶ {name}")
    r = run_all(sc)
    for label, _ in periods:
        for mk_name, mk in [('跌日','down'), ('横盘','flat'), ('真实','real_up')]:
            key = f'{label}_{mk}'
            if key in r:
                wr = r[key]['wins']/len(r[key]['nh_list'])*100 if r[key]['nh_list'] else 0
                cp = r[key]['has_cand']/r[key]['total']*100 if r[key]['total'] else 0
                print(f"  {mk_name:4s} {label}: 胜率{wr:5.1f}% 出票{cp:4.1f}% | {len(r[key]['nh_list'])}天")

# 也测试扣分版(ma5_slope<0)
def ms5_neg_deduct(ded):
    def fn(s):
        ms = s.get('ma5_slope',0) or 0
        if ms < 0: return ded
        return 0
    return fn

# 只测跌日 - 斜率向下扣分
print(f"\n▶ ma5_slope<0 -5 (跌日)")
sf = make_score(mod_down, ms5_neg_deduct(-5))
for label, cutoff in periods:
    dts = [x for x in mkt_dates['down'] if x >= cutoff]
    total=0; wins=0; nh=[]
    for dt in dts:
        s = data.get(dt,[]); total+=1; selected=None
        for lv in mod_down.LEVELS:
            pool=[]
            for sx in s:
                code=sx.get('code',''); p=(sx.get('p',0) or 0)
                if p<lv['p_min'] or p>lv['p_max'] or p>=8: continue
                vr=sx.get('vol_ratio',0) or 0
                if vr<lv['vr_min'] or vr>lv['vr_max']: continue
                cl=sx.get('cl',0) or 0
                if cl<lv['cl_min'] or cl>lv['cl_max']: continue
                ri=real.get(code)
                if ri:
                    hsl=ri.get('hsl',0) or 0
                    if hsl<lv['hs_min'] or hsl>lv['hs_max']: continue
                    sz=ri.get('shizhi',0) or 0
                    if isinstance(sz,(int,float)) and sz>1: sz*=1e-8
                    if sz>=lv['sz_max']: continue
                nm=names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                if (sx.get('n',0) or 0)<=0: continue
                stock=build(sx,ri)
                sc=sf(stock)
                nh_=sx.get('n',0) or 0
                pool.append((sc, nh_, code, nm[:6]))
            if len(pool)>8:
                pool.sort(key=lambda x:-x[0]); selected=pool[0]; break
        if selected:
            sc,nh_,code,nm=selected; nh.append(nh_)
            if nh_>=2.5: wins+=1
    wr=wins/len(nh)*100 if nh else 0
    print(f"  跌日 {label}: 胜率{wr:5.1f}% | {len(nh)}天")
