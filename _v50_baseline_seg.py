"""V50基线 - 多时间分段"""
import sys, os, importlib, pickle

WORK = os.path.expanduser('~/AppData/Local/hermes/scripts')
V50_DIR = os.path.join(WORK, 'release/V50')
sys.path.insert(0, V50_DIR)
sys.path.insert(0, os.path.join(V50_DIR, '评分策略'))

# 加载评分模块
mod_down = importlib.import_module('分而治之_V10_跌日_评分策略')
mod_flat = importlib.import_module('分而治之_V10_横盘_评分策略')
mod_real = importlib.import_module('分而治之_V10_真实涨日_评分策略')
mod_fake = importlib.import_module('分而治之_V10_虚涨日_评分策略')

exec(open(os.path.join(WORK, '_v50_framework.py')).read())

def run_backtest_segment(mk, mod, cutoff_date=None, extra_fields_cb=None):
    """在某时间段内回测。可选cutoff_date进行时间分段"""
    sc_fn = mod.score
    levels = mod.LEVELS
    
    # 筛选日期
    mk_all = mkt_dates[mk]
    if cutoff_date:
        mk_dates = [x for x in mk_all if x >= cutoff_date]
    else:
        mk_dates = mk_all
    
    total_days = 0
    has_cand = 0
    wins = 0
    nh_list = []
    
    for dt in mk_dates:
        s = data.get(dt, [])
        total_days += 1
        selected = None
        for lv in levels:
            pool = []
            for sx in s:
                code = sx.get('code','')
                p = sx.get('p',0) or 0
                if p < lv['p_min'] or p > lv['p_max']: continue
                if p >= 8: continue
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
                
                extra = extra_fields_cb(dt, sx, ri) if extra_fields_cb else {}
                stock = build(sx, ri, extra)
                sc = sc_fn(stock)
                nh = sx.get('n',0) or 0
                pool.append((sc, nh, code, nm[:6]))
            
            if len(pool) > 8:
                pool.sort(key=lambda x: -x[0])
                selected = pool[0]
                break
        
        if selected:
            has_cand += 1
            sc, nh, code, nm = selected
            nh_list.append(nh)
            if nh >= 2.5:
                wins += 1
    
    return {
        'name': mod.NAME if hasattr(mod, 'NAME') else mk,
        'total': total_days, 'has_cand': has_cand,
        'wins': wins, 'nh_list': nh_list
    }

# 全量
print("="*60)
print("V50 基线 - 全量")
print("="*60)
full_results = {}
for mk, mod in [('down', mod_down), ('flat', mod_flat), ('real_up', mod_real), ('fake_up', mod_fake)]:
    r = run_backtest_segment(mk, mod)
    full_results[mk] = r
    print_result(r)

# 时间分段
date_list = sorted(dates_all)
for days, label in [(150,'150天'), (100,'100天'), (50,'50天'), (30,'30天')]:
    cutoff = date_list[-days] if len(date_list) >= days else date_list[0]
    print(f"\n{'='*60}")
    print(f"V50 {label} (≥{cutoff})")
    print(f"{'='*60}")
    seg_results = {}
    for mk, mod in [('down', mod_down), ('flat', mod_flat), ('real_up', mod_real), ('fake_up', mod_fake)]:
        r = run_backtest_segment(mk, mod, cutoff_date=cutoff)
        seg_results[mk] = r
        print_result(r)
    
    total_w = sum(r['wins'] for r in seg_results.values())
    total_h = sum(len(r['nh_list']) for r in seg_results.values())
    wr = total_w/total_h*100 if total_h else 0
    print(f"  {'合计':12s} | 胜率{wr:5.1f}% ({total_w}/{total_h})")
