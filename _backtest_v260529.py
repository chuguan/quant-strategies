"""
回测当前V260529各行情胜率+出票率
目标：冠军胜率≥70%，出票率≥80%
"""
import pickle, sys, os, importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dev/current'))

with open(os.path.join(os.path.dirname(__file__), 'big_cache_full.pkl'), 'rb') as f:
    cache = pickle.load(f)
data = cache['data']
real_data = cache.get('real', {})
names = cache.get('names', {})

dates = sorted(x for x in data.keys() if '2025-06-01' <= x < '2026-06-01')

def classify_mkt(stocks):
    ps = [s.get('p',0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps)
    avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

# 加载子策略
mod_real = importlib.import_module('大道至简_真实涨日_评分策略')
mod_fake = importlib.import_module('大道至简_虚涨日_评分策略')
mod_down = importlib.import_module('大道至简_跌日_评分策略')
mod_flat = importlib.import_module('大道至简_横盘_评分策略')

score_map = {
    'real_up': (mod_real.真实涨日_评分, mod_real.LEVELS, '真实涨日'),
    'fake_up': (mod_fake.虚涨日_评分, mod_fake.LEVELS, '虚涨日'),
    'down': (mod_down.跌日_评分, mod_down.LEVELS, '跌日'),
    'flat': (mod_flat.横盘_评分, mod_flat.LEVELS, '横盘'),
}

def process(mk):
    sc_fn, levels, name = score_map[mk]
    
    total_days = 0
    has_cand = 0
    wins = 0
    nh_list = []
    level_use = {}
    cand_list = []
    fail_list = []  # 记录失败日
    
    for dt in dates:
        s = data.get(dt, [])
        m = classify_mkt(s)
        if m != mk: continue
        total_days += 1
        
        selected = None
        used_lvl = None
        for lv in levels:
            pool = []
            for sx in s:
                code = sx.get('code','')
                p = (sx.get('p',0) or 0)
                if p < lv['p_min'] or p > lv['p_max']: continue
                if p >= 8: continue
                vr = (sx.get('vol_ratio',0) or 0)
                if vr < lv['vr_min'] or vr > lv['vr_max']: continue
                cl = (sx.get('cl',0) or 0)
                if cl < lv['cl_min'] or cl > lv['cl_max']: continue
                ri = real_data.get(code)
                if ri:
                    hsl = (ri.get('hsl',0) or 0)
                    if hsl < lv['hs_min'] or hsl > lv['hs_max']: continue
                    sz = ri.get('shizhi',0) or 0
                    if isinstance(sz,(int,float)) and sz > 1: sz *= 1e-8
                    if sz >= lv['sz_max']: continue
                nm = names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                if (sx.get('n',0) or 0) <= 0: continue
                
                stock = {
                    'p': p, 'cl': cl, 'vr': vr,
                    'hsl': (ri.get('hsl',0) or 0) if ri else 0,
                    'dif': (sx.get('dif_val',0) or 0),
                    'mg': (sx.get('macd_golden',0) or 0),
                    'a5': (sx.get('above_ma5',0) or 0),
                    'wrv': (sx.get('wr',0) or 0),
                    'jv': (sx.get('j_val',0) or 0),
                    'kv': (sx.get('k_val',0) or 0),
                    'dv': (sx.get('d_val',0) or 0),
                    'kdj_g': (sx.get('kdj_golden',0) or 0),
                    'buy_c': (sx.get('close',0) or 0),
                }
                sc = sc_fn(stock)
                nh = (sx.get('n',0) or 0)
                pool.append((sc, nh, code, names.get(code,'')[:6]))
            
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
        'name': name, 'total': total_days, 'has_cand': has_cand,
        'wins': wins, 'nh_list': nh_list, 'level_use': level_use,
        'cand_list': cand_list, 'fail_list': fail_list
    }

all_results = {}
for mk in ['real_up', 'fake_up', 'down', 'flat']:
    r = process(mk)
    all_results[mk] = r
    
    print(f"\n{'='*60}")
    print(f"{r['name']} | 总天数: {r['total']}")
    print(f"{'='*60}")
    
    出票率 = r['has_cand']/r['total']*100 if r['total'] else 0
    达标 = '✅' if 出票率 >= 80 else '❌'
    print(f"出票率: {出票率:.1f}% ({r['has_cand']}/{r['total']}) {达标}")
    
    if r['nh_list']:
        胜率 = r['wins']/len(r['nh_list'])*100
        avg_nh = sum(r['nh_list'])/len(r['nh_list'])
        达标2 = '✅' if 胜率 >= 70 else '❌'
        print(f"冠军胜率: {胜率:.1f}% ({r['wins']}/{len(r['nh_list'])}) {达标2}")
        print(f"次日最高均值: {avg_nh:.1f}%")
        avg_cand = sum(r['cand_list'])/len(r['cand_list'])
        print(f"平均候选: {avg_cand:.0f}只")
        print(f"分级使用: {r['level_use']}")
        for lvl in ['L','L1','L2','L3','L4','L5']:
            if lvl in r['level_use']:
                print(f"  {lvl}: {r['level_use'][lvl]}天 ({r['level_use'][lvl]/r['has_cand']*100:.0f}%)")
        
        if r['fail_list']:
            print(f"\n--- 失败日 ({len(r['fail_list'])}天) ---")
            for f in r['fail_list']:
                print(f"  {f['dt']} [{f['lvl']}] {f['nm']}({f['code']}) nh={f['nh']:.1f}% 候选{f['n_cand']}只")
    
    print()

print(f"\n{'='*60}")
print("汇总")
print(f"{'='*60}")
for mk, r in all_results.items():
    出票率 = r['has_cand']/r['total']*100 if r['total'] else 0
    胜率 = r['wins']/len(r['nh_list'])*100 if r['nh_list'] else 0
    avg_cand = sum(r['cand_list'])/len(r['cand_list']) if r['cand_list'] else 0
    print(f"{r['name']:8s} | 出票 {出票率:5.1f}% | 胜率 {胜率:5.1f}% | 候选 {avg_cand:4.0f}只 | {r['total']}天")
