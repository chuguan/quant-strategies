"""
逐行情逐天输出：选票质量报告
每天 → 候选数 | 达标数(次日最高≥2.5%) | 达标率 | 使用级别
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

levels_map = {
    'real_up': (mod_real.LEVELS, '真实涨日'),
    'fake_up': (mod_fake.LEVELS, '虚涨日'),
    'down': (mod_down.LEVELS, '跌日'),
    'flat': (mod_flat.LEVELS, '横盘'),
}

def filter_pool(stocks, levels):
    """L→L5分级筛选，返回[候选票]和使用的级别名"""
    for lv in levels:
        pool = []
        for sx in stocks:
            code = sx.get('code','')
            p = (sx.get('p',0) or 0)
            if p < lv['p_min'] or p > lv['p_max']: continue
            if p >= 8: continue  # 第三条：当日涨幅<8%
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
            if (sx.get('n',0) or 0) <= 0: continue  # 无次日数据
            pool.append({
                'code': code, 'nm': names.get(code,'')[:6],
                'nh': (sx.get('n',0) or 0), 'p': p
            })
        if len(pool) > 8:
            return pool, lv['name']
    return [], None

# 处理每个行情
for mk, (levels, name) in levels_map.items():
    print(f"\n{'='*70}")
    print(f"【{name}】")
    print(f"{'='*70}")
    
    all_cand = 0       # 全部候选票数
    all_qual = 0       # 全部达标票数
    day_records = []   # 逐日记录
    
    for dt in dates:
        s = data.get(dt, [])
        m = classify_mkt(s)
        if m != mk: continue
        
        pool, used_lvl = filter_pool(s, levels)
        if not pool:
            day_records.append({'dt': dt, 'n': 0, 'qual': 0, 'rate': 0, 'lvl': '弃权'})
            continue
        
        n_total = len(pool)
        n_qual = sum(1 for x in pool if x['nh'] >= 2.5)
        qual_rate = n_qual / n_total * 100
        
        all_cand += n_total
        all_qual += n_qual
        day_records.append({
            'dt': dt, 'n': n_total, 'qual': n_qual,
            'rate': qual_rate, 'lvl': used_lvl
        })
    
    # 输出逐日明细
    header = f"{'日期':<14} {'候选':>6} {'达标':>6} {'达标率':>8} {'级别':<6}"
    print(header)
    print('-' * len(header))
    
    for r in day_records:
        if r['n'] == 0:
            print(f"{r['dt']:<14} {'弃权':>6} {'—':>6} {'—':>8} {'—':<6}")
        else:
            rate_str = f"{r['rate']:.1f}%"
            print(f"{r['dt']:<14} {r['n']:>6} {r['qual']:>6} {rate_str:>8} {r['lvl']:<6}")
    
    # 汇总统计
    print()
    print(f"--- {name} 汇总 ---")
    print(f"总天数: {len(day_records)}天")
    print(f"出票天数: {sum(1 for r in day_records if r['n']>0)}天 ({sum(1 for r in day_records if r['n']>0)/len(day_records)*100:.1f}%)")
    print(f"弃权天数: {sum(1 for r in day_records if r['n']==0)}天")
    if all_cand > 0:
        print(f"候选总数: {all_cand}票")
        print(f"达标总数(次日最高≥2.5%): {all_qual}票")
        print(f"池总达标率: {all_qual/all_cand*100:.2f}%")
    
    # 分级别统计
    lvl_stats = {}
    for r in day_records:
        if r['lvl'] and r['lvl'] != '弃权':
            if r['lvl'] not in lvl_stats:
                lvl_stats[r['lvl']] = {'days':0, 'cand':0, 'qual':0}
            lvl_stats[r['lvl']]['days'] += 1
            lvl_stats[r['lvl']]['cand'] += r['n']
            lvl_stats[r['lvl']]['qual'] += r['qual']
    
    if lvl_stats:
        print(f"\n分级使用统计:")
        for lvl in ['L','L1','L2','L3','L4','L5']:
            if lvl in lvl_stats:
                st = lvl_stats[lvl]
                r = st['qual']/st['cand']*100 if st['cand'] else 0
                print(f"  {lvl}: {st['days']}天 | {st['cand']}票 | 达标率{r:.1f}%")
    
    # 达标率分布
    rates = [r['rate'] for r in day_records if r['n'] > 0]
    if rates:
        rate_buckets = {'0-20%':0, '20-30%':0, '30-40%':0, '40-50%':0, '50-60%':0, '60-70%':0, '70-80%':0, '80%+':0}
        for r in rates:
            if r < 20: rate_buckets['0-20%'] += 1
            elif r < 30: rate_buckets['20-30%'] += 1
            elif r < 40: rate_buckets['30-40%'] += 1
            elif r < 50: rate_buckets['40-50%'] += 1
            elif r < 60: rate_buckets['50-60%'] += 1
            elif r < 70: rate_buckets['60-70%'] += 1
            elif r < 80: rate_buckets['70-80%'] += 1
            else: rate_buckets['80%+'] += 1
        print(f"\n达标率分布:")
        for k, v in rate_buckets.items():
            if v > 0:
                bar = '█' * (v * 30 // max(rate_buckets.values()) if max(rate_buckets.values()) > 0 else v)
                print(f"  {k:>10}: {v:3d}天 {bar}")
    
    print()
