"""
4行情 L1~L5 最终分级定稿 + 100%出票验证
"""
import pickle, sys, os
sys.stdout.reconfigure(line_buffering=True)

with open(os.path.join(os.path.dirname(__file__), 'big_cache_full.pkl'), 'rb') as f:
    cache = pickle.load(f)
data = cache['data']
real_data = cache.get('real', {})
names = cache.get('names', {})

dates = sorted(x for x in data.keys() if '2025-06-01' <= x < '2026-06-01')

def cm(stocks):
    ps = [s.get('p',0) or 0 for s in stocks]
    if not ps: return 'flat'
    ap = sum(ps)/len(ps)
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    av = sum(vrs)/len(vrs) if vrs else 0
    ht = sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if ht<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

def check_day(s_list, p_min, p_max, v1, v2, c1, c2, h1, h2, sz, a5, kdj_g, mg, wr, j_min, j_max):
    pool = []
    for sx in s_list:
        code = sx.get('code','')
        p = (sx.get('p',0) or 0)
        if p < p_min or p > p_max: continue
        if p >= 8: continue
        vr = (sx.get('vol_ratio',0) or 0)
        if vr < v1 or vr > v2: continue
        cl = (sx.get('cl',0) or 0)
        if cl < c1 or cl > c2: continue
        ri = real_data.get(code)
        if ri:
            hsl = (ri.get('hsl',0) or 0)
            if hsl < h1 or hsl > h2: continue
            szv = ri.get('shizhi',0) or 0
            if isinstance(szv,(int,float)) and szv > 1: szv *= 1e-8
            if szv >= sz: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        nh = (sx.get('n',0) or 0)
        if nh <= 0: continue
        if a5 and (sx.get('above_ma5',0) or 0) < 1: continue
        if kdj_g and (sx.get('kdj_golden',0) or 0) < 1: continue
        if mg != 0:
            mgv = (sx.get('macd_golden',0) or 0)
            if mg > 0 and mgv < 1: continue        # mg>0: 要求金叉
            if mg < 0 and mgv >= 1: continue        # mg<0: 排除金叉
        jv = sx.get('j_val',0) or 0
        if j_min > -998 and jv < j_min: continue
        if j_max < 998 and jv > j_max: continue
        pool.append(nh)
    return pool

all_s = {}
for dt in dates:
    s = data.get(dt, [])
    m = cm(s)
    if m not in all_s:
        all_s[m] = []
    all_s[m].append(s)

for nm, mk, total in [('跌日','down',57),('真实涨日','real_up',87),('横盘','flat',90),('虚涨日','fake_up',5)]:
    print(f'\n{"="*60}')
    print(f'{nm} ({total}天)')
    print(f'{"="*60}')
    sl = all_s.get(mk, [])

    # 5级定义
    levels = {
        '跌日': [
            ('L1', 2,7, 0.6,1.5, 40,90, 5,20,150, 1,1,0,-1,-999,999),
            ('L2', 2,7, 0.6,1.5, 40,90, 5,20,150, 1,0,0,-1,-999,999),
            ('L3', 2,7, 0.6,2.0, 30,95, 3,25,200, 0,0,0,-1,-999,999),
            ('L4', 0,7, 0.5,2.5, 20,98, 2,30,300, 0,0,0,-1,-999,999),
            ('L5', -10,7, 0.1,10, 0,100, 0.1,100,10000, 0,0,0,-1,-999,999),
        ],
        '真实涨日': [
            ('L1', 3.5,6, 0.8,2.0, 65,85, 5,10,100, 0,0,0,-1,-999,999),
            ('L2', 3,7, 0.6,2.5, 60,90, 5,15,150, 0,0,0,-1,-999,999),
            ('L3', 2,7, 0.6,2.5, 50,95, 3,20,200, 0,0,0,-1,-999,999),
            ('L4', 1,7, 0.5,3.0, 40,98, 2,25,300, 0,0,0,-1,-999,999),
            ('L5', -5,7, 0.1,10, 10,100, 0.5,50,5000, 0,0,0,-1,-999,999),
        ],
        '横盘': [
            ('L1', 4,7, 0.6,2.0, 40,90, 3,20,200, 0,0,-1,0,-999,999),   # p>=4 + hsl>=3 + 排除MACD金叉
            ('L2', 3,7, 0.5,2.5, 30,90, 3,20,200, 0,0,0,-1,-999,999),    # p>=3
            ('L3', 2,7, 0.4,3.0, 20,95, 2,30,300, 0,0,0,-1,-999,999),    # p>=2
            ('L4', 0,7, 0.3,5.0, 10,98, 1,40,500, 0,0,0,-1,-999,999),    # p>=0 保底
            ('L5', -10,7, 0.1,10, 0,100, 0.1,100,10000, 0,0,0,-1,-999,999),
        ],
        '虚涨日': [
            ('L1', 4,7, 0.6,2.0, 30,90, 5,20,200, 0,0,0,-1,-999,999),
            ('L2', 3,7, 0.6,2.5, 30,95, 5,20,200, 0,0,0,-1,-999,999),
            ('L3', 2,7, 0.5,2.5, 20,95, 3,25,300, 0,0,0,-1,-999,999),
            ('L4', 1,7, 0.4,3.0, 10,98, 2,30,400, 0,0,0,-1,-999,999),
            ('L5', -10,7, 0.1,10, 0,100, 0.1,100,10000, 0,0,0,-1,-999,999),
        ],
    }
    
    lv_list = levels[nm]
    
    # 级别测试
    for lv_def in lv_list:
        name = lv_def[0]
        params = lv_def[1:]
        p_min, p_max, v1, v2, c1, c2, h1, h2, sz, a5, kdj_g, mg, wr, j_min, j_max = params
        
        ok_days = 0
        stats = []
        for s_list in sl:
            pool = check_day(s_list, *params)
            if len(pool) > 8:
                ok_days += 1
                qual = sum(1 for nh in pool if nh >= 2.5)
                stats.append({'n': len(pool), 'qual': qual})
        
        if stats:
            tn = sum(d['n'] for d in stats)
            tq = sum(d['qual'] for d in stats)
            rate = tq/tn*100
            avg = tn/len(stats)
            pct = ok_days/total*100
            tags = []
            if a5: tags.append('站MA5')
            if kdj_g: tags.append('KDJ金叉')
            if mg: tags.append('MACD金叉')
            tag_str = f' +{"+".join(tags)}' if tags else ''
            print(f'  {name}: 质量{rate:5.1f}%  {avg:4.0f}只/天  {ok_days}/{total}天({pct:.0f}%)  p[{p_min},{p_max}] vr[{v1},{v2}] cl[{c1},{c2}]{tag_str}')
        else:
            print(f'  {name}: 0天出票 ❌')
    
    # 分级模拟
    print(f'  分级选股结果:', flush=True)
    day_results = []
    for s_list in sl:
        selected = None
        used_lvl = None
        for lv_def in lv_list:
            pool = check_day(s_list, *lv_def[1:])
            if len(pool) > 8:
                selected = pool
                used_lvl = lv_def[0]
                break
        if selected:
            qual = sum(1 for nh in selected if nh >= 2.5)
            day_results.append({'n': len(selected), 'qual': qual, 'lvl': used_lvl})
        else:
            day_results.append({'n': 0, 'qual': 0, 'lvl': '弃权❌'})
    
    tn = sum(d['n'] for d in day_results)
    tq = sum(d['qual'] for d in day_results)
    rate = tq/tn*100 if tn else 0
    issued = sum(1 for d in day_results if d['n'] > 0)
    lvl_usage = {}
    for d in day_results:
        lvl_usage[d['lvl']] = lvl_usage.get(d['lvl'], 0) + 1
    
    print(f'    最终池质量: {rate:.1f}% ({tq}/{tn})')
    print(f'    出票率: {issued}/{total}天 ({issued/total*100:.0f}%)')
    for l in ['L1','L2','L3','L4','L5','弃权❌']:
        if l in lvl_usage:
            print(f'      {l}: {lvl_usage[l]}天')
