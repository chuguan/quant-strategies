"""
计算候选池整体质量：所有通过L级筛选的票中，次日最高≥2.5%的比例
对比冠军胜率 vs 池平均
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
    avg_p = sum(ps)/len(ps) if ps else 0
    avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

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
    date_results = []
    
    for dt in dates:
        s = data.get(dt, [])
        m = classify_mkt(s)
        if m != mk: continue
        total_days += 1
        
        # 收集本日所有通过L级的候选
        pool_all = []
        for lv in levels:
            day_pool = []
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
                day_pool.append({'code':code,'nm':names.get(code,'')[:6],'nh':(sx.get('n',0) or 0)})
            
            if day_pool:
                pool_all.extend(day_pool)
                # 只取第一个达标级别(L)的池
                # 如果L已有>8只，只取L级
                if len(day_pool) > 8:
                    break
        
        if pool_all:
            n_wins = sum(1 for x in pool_all if x['nh'] >= 2.5)
            date_results.append({
                'dt': dt,
                'total': len(pool_all),
                'wins': n_wins,
                'rate': n_wins/len(pool_all)*100,
                'used_lvl': lv['name'] if day_pool else '?'
            })
    
    return {'name': name, 'total_days': total_days, 'results': date_results}

for mk in ['real_up', 'fake_up', 'down', 'flat']:
    r = process(mk)
    
    print(f"\n{'='*60}")
    print(f"{r['name']} | 总天数: {r['total_days']}")
    print(f"{'='*60}")
    
    if not r['results']:
        print("  无样本")
        continue
    
    # 池总量统计
    all_pool = sum(x['total'] for x in r['results'])
    all_wins = sum(x['wins'] for x in r['results'])
    
    # 按票算：所有候选票中，次日≥2.5%的比例
    pool_rate = all_wins/all_pool*100 if all_pool else 0
    print(f"\n【按票统计】所有候选 = {all_pool}票")
    print(f"  次日≥2.5% = {all_wins}票 ({pool_rate:.2f}%)")
    print(f"  随机基准 ≈ 10%")
    print(f"  相对基准 = {pool_rate/10:.1f}x")
    
    # 按天算：每天池的胜率均值
    avg_day_rate = sum(x['rate'] for x in r['results'])/len(r['results'])
    print(f"\n【按天统计】{len(r['results'])}天")
    print(f"  每天池均胜率 = {avg_day_rate:.1f}%")
    
    # 冠军胜率
    champ_wins = sum(1 for x in r['results'] if True)  # 先标记
    # 补充冠军统计
    champion_rates = []
    # 重新跑冠军
    sc_fn, levels, _ = score_map[mk]
    dates2 = sorted(x for x in data.keys() if '2025-06-01' <= x < '2026-06-01')
    champ_nh = []
    for dt in dates2:
        s = data.get(dt, [])
        m = classify_mkt(s)
        if m != mk: continue
        pool = []
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
                pool.append((sc, nh))
            if len(pool) > 8:
                pool.sort(key=lambda x: -x[0])
                champ_nh.append(pool[0][1])
                break
    
    if champ_nh:
        champ_w = sum(1 for n in champ_nh if n >= 2.5)
        champ_rate = champ_w/len(champ_nh)*100
        print(f"\n【冠军统计】")
        print(f"  冠军胜率: {champ_rate:.1f}% ({champ_w}/{len(champ_nh)})")
        print(f"  池平均 vs 冠军: {pool_rate:.1f}% vs {champ_rate:.1f}% (差距 {champ_rate-pool_rate:.1f}%)")
        print(f"  冠军高出池平均: {champ_rate/pool_rate:.1f}x" if pool_rate > 0 else "")
    print()
