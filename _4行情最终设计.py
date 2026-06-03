"""
最终L1~L5分级：4行情×多维选股
各行情独立配参 + 分级模拟
"""
import pickle, sys, os, time
sys.stdout.reconfigure(line_buffering=True)

t0 = time.time()
with open(os.path.join(os.path.dirname(__file__), 'big_cache_full.pkl'), 'rb') as f:
    cache = pickle.load(f)
data = cache['data']
real_data = cache.get('real', {})
names = cache.get('names', {})

dates = sorted(x for x in data.keys() if '2025-06-01' <= x < '2026-06-01')

def classify_mkt(stocks):
    ps = [s.get('p',0) or 0 for s in stocks]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps)
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

def check_stock(sx, ldef, real_data, names):
    code = sx.get('code','')
    p = (sx.get('p',0) or 0)
    if p < ldef.get('p_min',-10) or p > ldef.get('p_max',10): return False
    if p >= 8: return False
    vr = (sx.get('vol_ratio',0) or 0)
    if vr < ldef.get('vr_min',0) or vr > ldef.get('vr_max',99): return False
    cl = (sx.get('cl',0) or 0)
    if cl < ldef.get('cl_min',0) or cl > ldef.get('cl_max',100): return False
    ri = real_data.get(code)
    if ri:
        hsl = (ri.get('hsl',0) or 0)
        if hsl < ldef.get('hs_min',0) or hsl > ldef.get('hs_max',99): return False
        szv = ri.get('shizhi',0) or 0
        if isinstance(szv,(int,float)) and szv > 1: szv *= 1e-8
        if szv >= ldef.get('sz_max',99999): return False
    nm = names.get(code,'')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return False
    nh = (sx.get('n',0) or 0)
    if nh <= 0: return False
    
    # 多维度过滤
    if ldef.get('mg_req',0) > 0 and (sx.get('macd_golden',0) or 0) < 1: return False
    if ldef.get('a5_req',0) > 0 and (sx.get('above_ma5',0) or 0) < 1: return False
    if ldef.get('kdj_g_req',0) > 0 and (sx.get('kdj_golden',0) or 0) < 1: return False
    if ldef.get('dif_min',-999) > -998 and (sx.get('dif_val',0) or 0) < ldef['dif_min']: return False
    jv = sx.get('j_val',0) or 0
    if ldef.get('j_min',-999) > -998 and jv < ldef['j_min']: return False
    if ldef.get('j_max',999) < 998 and jv > ldef['j_max']: return False
    wr = sx.get('wr',0) or 0
    if ldef.get('wr_min',-1) > -1 and wr < ldef['wr_min']: return False
    if ldef.get('wr_max',101) < 101 and wr > ldef['wr_max']: return False
    
    return True

# ===== 4行情分级定义 =====
MKTS = {
    # 跌日: 抗跌票+站MA5+KDJ金叉 质量最高
    'down': {
        'name': '跌日',
        'levels': [
            {'name':'L1','p_min':2,'p_max':7,'vr_min':0.6,'vr_max':1.5,'cl_min':40,'cl_max':90,
             'hs_min':5,'hs_max':20,'sz_max':150,'a5_req':1,'kdj_g_req':1,
             'j_min':-999,'j_max':999,'dif_min':-999},
            {'name':'L2','p_min':2,'p_max':7,'vr_min':0.6,'vr_max':1.5,'cl_min':40,'cl_max':90,
             'hs_min':5,'hs_max':20,'sz_max':150,'a5_req':1,'kdj_g_req':0,  # L1条件-去掉KDJ
             'j_min':-999,'j_max':999,'dif_min':-999},
            {'name':'L3','p_min':2,'p_max':7,'vr_min':0.6,'vr_max':2.0,'cl_min':30,'cl_max':95,
             'hs_min':3,'hs_max':25,'sz_max':200,'a5_req':0,'kdj_g_req':0,  # 全部去掉多维
             'j_min':-999,'j_max':999,'dif_min':-999},
            {'name':'L4','p_min':0,'p_max':7,'vr_min':0.5,'vr_max':2.5,'cl_min':20,'cl_max':98,
             'hs_min':2,'hs_max':30,'sz_max':300,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
        ]
    },
    # 横盘: 方向不明，收紧基本参数
    'flat': {
        'name': '横盘',
        'levels': [
            {'name':'L1','p_min':2,'p_max':6,'vr_min':0.8,'vr_max':1.5,'cl_min':60,'cl_max':85,
             'hs_min':5,'hs_max':15,'sz_max':100,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
            {'name':'L2','p_min':1,'p_max':7,'vr_min':0.6,'vr_max':2.0,'cl_min':50,'cl_max':90,
             'hs_min':3,'hs_max':20,'sz_max':150,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
            {'name':'L3','p_min':0,'p_max':7,'vr_min':0.5,'vr_max':2.5,'cl_min':40,'cl_max':95,
             'hs_min':2,'hs_max':25,'sz_max':200,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
            {'name':'L4','p_min':-1,'p_max':7,'vr_min':0.4,'vr_max':3.0,'cl_min':30,'cl_max':98,
             'hs_min':1,'hs_max':30,'sz_max':300,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
        ]
    },
    # 真实涨日: 趋势向上
    'real_up': {
        'name': '真实涨日',
        'levels': [
            {'name':'L1','p_min':3.5,'p_max':6,'vr_min':0.8,'vr_max':2.0,'cl_min':65,'cl_max':85,
             'hs_min':5,'hs_max':10,'sz_max':100,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
            {'name':'L2','p_min':3,'p_max':7,'vr_min':0.6,'vr_max':2.5,'cl_min':60,'cl_max':90,
             'hs_min':5,'hs_max':15,'sz_max':150,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
            {'name':'L3','p_min':2,'p_max':7,'vr_min':0.6,'vr_max':2.5,'cl_min':50,'cl_max':95,
             'hs_min':3,'hs_max':20,'sz_max':200,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
            {'name':'L4','p_min':1,'p_max':7,'vr_min':0.5,'vr_max':3.0,'cl_min':40,'cl_max':98,
             'hs_min':2,'hs_max':25,'sz_max':300,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
        ]
    },
    # 虚涨日: 样本少，简单
    'fake_up': {
        'name': '虚涨日',
        'levels': [
            {'name':'L1','p_min':2,'p_max':6,'vr_min':0.8,'vr_max':1.5,'cl_min':50,'cl_max':85,
             'hs_min':8,'hs_max':15,'sz_max':100,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
            {'name':'L2','p_min':1,'p_max':6,'vr_min':0.6,'vr_max':2.0,'cl_min':40,'cl_max':90,
             'hs_min':5,'hs_max':20,'sz_max':200,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
            {'name':'L3','p_min':0,'p_max':7,'vr_min':0.5,'vr_max':2.5,'cl_min':30,'cl_max':95,
             'hs_min':3,'hs_max':25,'sz_max':300,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
            {'name':'L4','p_min':-1,'p_max':7,'vr_min':0.4,'vr_max':3.0,'cl_min':20,'cl_max':98,
             'hs_min':2,'hs_max':30,'sz_max':400,'a5_req':0,'kdj_g_req':0,
             'j_min':-999,'j_max':999,'dif_min':-999},
        ]
    }
}

# ===== 测试并模拟分级 =====
print("="*80, flush=True)
print("4行情 L1~L4 分级选股 → 多维度提升", flush=True)
print("="*80, flush=True)

all_stocks = {}
for dt in dates:
    s = data.get(dt, [])
    m = classify_mkt(s)
    if m not in all_stocks: all_stocks[m] = []
    all_stocks[m].append(s)

for mk, info in MKTS.items():
    name = info['name']
    levels = info['levels']
    stocks = all_stocks.get(mk, [])
    
    print(f"\n{'='*60}", flush=True)
    print(f"{name} ({len(stocks)}天)", flush=True)
    print(f"{'='*60}", flush=True)
    
    for lv in levels:
        day_n = 0
        pool_stats = []
        for s_list in stocks:
            pool = []
            for sx in s_list:
                if check_stock(sx, lv, real_data, names):
                    nh = (sx.get('n',0) or 0)
                    pool.append(nh)
            if len(pool) > 8:
                day_n += 1
                qual = sum(1 for nh in pool if nh >= 2.5)
                pool_stats.append({'n': len(pool), 'qual': qual})
        
        if pool_stats:
            total_n = sum(d['n'] for d in pool_stats)
            total_qual = sum(d['qual'] for d in pool_stats)
            rate = total_qual/total_n*100
            avg_n = total_n/len(pool_stats)
            cov = day_n/len(stocks)*100
            print(f"  {lv['name']}: 质量{rate:5.1f}% 日均{avg_n:4.0f}只 出票{day_n}/{len(stocks)}天({cov:.0f}%)", flush=True)
            # 打印多维条件
            conds = []
            conds.append(f"p[{lv.get('p_min',0)},{lv.get('p_max',10)}]")
            conds.append(f"vr[{lv.get('vr_min',0)},{lv.get('vr_max',5)}]")
            conds.append(f"cl[{lv.get('cl_min',0)},{lv.get('cl_max',100)}]")
            conds.append(f"hsl[{lv.get('hs_min',0)},{lv.get('hs_max',30)}]")
            conds.append(f"sz<{lv.get('sz_max',999)}")
            if lv.get('a5_req',0): conds.append('站MA5')
            if lv.get('kdj_g_req',0): conds.append('KDJ金叉')
            print(f"        {' '.join(conds)}", flush=True)
        else:
            print(f"  {lv['name']}: 0天出票 ❌", flush=True)
    
    # 分级模拟
    print(f"\n  分级选股模拟:", flush=True)
    day_results = []
    for s_list in stocks:
        selected = None
        used_lvl = None
        for lv in levels:
            pool = []
            for sx in s_list:
                if check_stock(sx, lv, real_data, names):
                    nh = (sx.get('n',0) or 0)
                    pool.append(nh)
            if len(pool) > 8:
                selected = pool
                used_lvl = lv['name']
                break
        
        if selected:
            qual = sum(1 for nh in selected if nh >= 2.5)
            day_results.append({'n': len(selected), 'qual': qual, 'lvl': used_lvl})
        else:
            day_results.append({'n': 0, 'qual': 0, 'lvl': '弃权'})
    
    total = sum(r['n'] for r in day_results)
    qual = sum(r['qual'] for r in day_results)
    rate = qual/total*100 if total else 0
    issued = sum(1 for r in day_results if r['n'] > 0)
    lvl_usage = {}
    for r in day_results:
        lvl_usage[r['lvl']] = lvl_usage.get(r['lvl'], 0) + 1
    
    print(f"    最终池质量: {rate:.1f}% ({qual}/{total})", flush=True)
    print(f"    出票率: {issued}/{len(stocks)}天 ({issued/len(stocks)*100:.0f}%)", flush=True)
    for l in ['L1','L2','L3','L4','弃权']:
        if l in lvl_usage:
            print(f"      {l}: {lvl_usage[l]}天", flush=True)

print(f"\n\n耗时: {time.time()-t0:.0f}s", flush=True)
