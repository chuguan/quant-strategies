"""V50回测框架 - 支持新TDX因子测试"""
import pickle, os, sys, importlib.util, importlib

WORK = os.path.expanduser('~/AppData/Local/hermes/scripts')
V50_DIR = os.path.join(WORK, 'release/V50')

# 加载V50缓存
with open(os.path.join(V50_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d['real'], d['names']
dates_all = sorted(x for x in data.keys() if '2025-06-01' <= x < '2026-06-01')

# 行情分类
def cls(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p',0) or 0 for s in stocks]; avg_p=sum(ps)/len(ps)
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    hot=sum(1 for p in ps if 5<=p<=8)
    avg_vr=sum(vrs)/max(len(vrs),1) if vrs else 0
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    if avg_p<-0.5: return 'down'
    return 'flat'

mkt_dates = {k:[] for k in ['real_up','fake_up','down','flat']}
for dt in dates_all:
    s=data.get(dt,[]); m=cls(s)
    mkt_dates[m].append(dt)

# 构建stock dict（含全部可用字段 + 传入new_fields）
def build(s, ri=None, extra_fields=None):
    if ri is None: ri=real.get(s.get('code',''),{})
    stock = {
        'p': s.get('p',0) or 0,
        'cl': s.get('cl',0) or 0,
        'vr': s.get('vol_ratio',0) or 0,
        'hsl': ri.get('hsl',0) or 0,
        'dif': s.get('dif_val',0) or 0,
        'mg': s.get('macd_golden',0) or 0,
        'a5': s.get('above_ma5',0) or 0,
        'wrv': s.get('wr_val',0) or 20,
        'jv': s.get('j_val',0) or 0,
        'kv': s.get('k_val',0) or 0,
        'dv': s.get('d_val',0) or 0,
        'kdj_g': s.get('kdj_golden',0) or 0,
        'buy_c': s.get('close',0) or 0,
        'n': s.get('n',0) or 0,
        'pos_in_day': s.get('pos_in_day',50) or 50,
        't4_shadow': s.get('t4_shadow',0) or 0,
        'slope5': s.get('slope5',0) or 0,
        'cons_up': s.get('cons_up',0) or 0,
        'nm': names.get(s.get('code',''), ''),
        'code': s.get('code',''),
        # V50场
        'above_ma10': s.get('above_ma10',0) or 0,
        'above_ma20': s.get('above_ma20',0) or 0,
        'is_yang': s.get('is_yang',0) or 0,
        'ma5_slope': s.get('ma5_slope',0) or 0,
        'amplitude': s.get('amplitude',0) or 0,
        'body_pct': s.get('body_pct',0) or 0,
        'vol': s.get('vol',0) or 0,
    }
    if extra_fields:
        stock.update(extra_fields)
    return stock

def run_backtest(mk, mod, extra_fields_cb=None):
    sc_fn = mod.score
    levels = mod.LEVELS
    total_days = 0
    has_cand = 0
    wins = 0
    nh_list = []
    level_use = {}
    cand_list = []
    fail_list = []
    for dt in mkt_dates[mk]:
        s = data.get(dt, [])
        total_days += 1
        selected = None
        used_lvl = None
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
                used_lvl = lv['name']
                cand_list.append(len(pool))
                break
        if selected:
            has_cand += 1
            level_use[used_lvl] = level_use.get(used_lvl,0) + 1
            sc, nh, code, nm = selected
            nh_list.append(nh)
            if nh >= 2.5:
                wins += 1
            else:
                fail_list.append({'dt': dt, 'lvl': used_lvl, 'code': code, 'nm': nm, 'nh': nh, 'n_cand': cand_list[-1] if cand_list else 0})
    return {
        'name': mod.NAME if hasattr(mod, 'NAME') else mk,
        'total': total_days, 'has_cand': has_cand,
        'wins': wins, 'nh_list': nh_list, 'level_use': level_use,
        'cand_list': cand_list, 'fail_list': fail_list
    }

def print_result(r, label=''):
    cp = r['has_cand']/r['total']*100 if r['total'] else 0
    wr = r['wins']/len(r['nh_list'])*100 if r['nh_list'] else 0
    avg_nh = sum(r['nh_list'])/len(r['nh_list']) if r['nh_list'] else 0
    cand = r.get('cand_list', [])
    avg_cand = sum(cand)/len(cand) if cand else 0
    tag = f' [{label}]' if label else ''
    print(f"  {r['name']:12s}{tag} | 出票{cp:5.1f}% | 胜率{wr:5.1f}% ({r['wins']}/{len(r['nh_list'])}) | 均涨幅{avg_nh:.1f}% | 候选{avg_cand:.0f}只 | {r['total']}天")

def print_summary(results):
    print(f"\n{'='*60}")
    print("V50 汇总")
    print(f"{'='*60}")
    total_w = sum(r['wins'] for r in results.values())
    total_h = sum(len(r['nh_list']) for r in results.values())
    total_t = sum(r['total'] for r in results.values())
    total_c = sum(r['has_cand'] for r in results.values())
    pct = total_c/total_t*100 if total_t else 0
    wr = total_w/total_h*100 if total_h else 0
    print(f"总胜率: {wr:.1f}% ({total_w}/{total_h})")
    print(f"总出票: {pct:.1f}% ({total_c}/{total_t})")
    for mk in ['down','flat','real_up','fake_up']:
        r = results[mk]
        cp = r['has_cand']/r['total']*100 if r['total'] else 0
        wr = r['wins']/len(r['nh_list'])*100 if r['nh_list'] else 0
        print(f"  {r['name']:8s} | 出票{cp:5.1f}% | 胜率{wr:5.1f}% ({r['wins']}/{len(r['nh_list'])}) | {r['total']}天")
