"""
多维度提升池质量 - 4行情×L1~L4分级
新增维度：MACD金叉/KDJ金叉/站上MA5/WR超卖/透支惩罚
每个行情独立配参数
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

def get_stock_dict(sx, code):
    """提取今天所有可用指标"""
    return {
        'p': (sx.get('p',0) or 0),
        'vr': (sx.get('vol_ratio',0) or 0),
        'cl': (sx.get('cl',0) or 0),
        'dif': (sx.get('dif_val',0) or 0),
        'mg': (sx.get('macd_golden',0) or 0),
        'a5': (sx.get('above_ma5',0) or 0),
        'wr': (sx.get('wr',0) or 0),
        'jv': (sx.get('j_val',0) or 0),
        'kv': (sx.get('k_val',0) or 0),
        'dv': (sx.get('d_val',0) or 0),
        'kdj_g': (sx.get('kdj_golden',0) or 0),
        'nh': (sx.get('n',0) or 0),
    }

def passes_level(s, level_def):
    """多维度检查是否通过某级别"""
    # 基本选股条件
    p = s['p']
    if p < level_def.get('p_min', -10) or p > level_def.get('p_max', 10): return False
    if p >= 8: return False
    if p < level_def.get('p_abs_min', -10): return False
    
    vr = s['vr']
    if vr < level_def.get('vr_min', 0) or vr > level_def.get('vr_max', 10): return False
    
    cl = s['cl']
    if cl < level_def.get('cl_min', 0) or cl > level_def.get('cl_max', 100): return False
    
    # 多维度加分/过滤条件 (可选)
    if level_def.get('mg_min', 0) > 0 and s['mg'] < level_def['mg_min']: return False
    if level_def.get('a5_req', 0) > 0 and s['a5'] < level_def['a5_req']: return False
    if level_def.get('kdj_g_req', 0) > 0 and s['kdj_g'] < level_def['kdj_g_req']: return False
    if level_def.get('dif_min', -999) > -998 and s['dif'] < level_def['dif_min']: return False
    
    # J值范围
    j_min = level_def.get('j_min', -999)
    j_max = level_def.get('j_max', 999)
    if s['jv'] < j_min or s['jv'] > j_max: return False
    
    # WR范围
    wr_min = level_def.get('wr_min', -1)
    wr_max = level_def.get('wr_max', 101)
    if s['wr'] < wr_min or s['wr'] > wr_max: return False
    
    return True

def test_level(stocks_list, level_def, real_data, names):
    day_stats = []
    for s_list in stocks_list:
        pool_nh = []
        for sx in s_list:
            code = sx.get('code','')
            sd = get_stock_dict(sx, code)
            if sd['nh'] <= 0: continue
            
            # 外部过滤（ST/市值/换手）
            ri = real_data.get(code)
            if ri:
                hsl = (ri.get('hsl',0) or 0)
                if hsl < level_def.get('hs_min', 0) or hsl > level_def.get('hs_max', 100): continue
                szv = ri.get('shizhi',0) or 0
                if isinstance(szv,(int,float)) and szv > 1: szv *= 1e-8
                if szv >= level_def.get('sz_max', 99999): continue
            nm = names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            
            if passes_level(sd, level_def):
                pool_nh.append(sd['nh'])
        
        if len(pool_nh) > 8:
            qual = sum(1 for nh in pool_nh if nh >= 2.5)
            day_stats.append({'n': len(pool_nh), 'qual': qual})
    
    if not day_stats:
        return 0, 0, 0, len(stocks_list)
    total_n = sum(d['n'] for d in day_stats)
    total_qual = sum(d['qual'] for d in day_stats)
    return total_qual/total_n*100, total_n/len(day_stats), len(day_stats), len(stocks_list)

# 预分组
mkt_data = {}
for dt in dates:
    s = data.get(dt, [])
    m = classify_mkt(s)
    if m not in mkt_data: mkt_data[m] = []
    mkt_data[m].append(s)

# ====== 搜索最佳多维参数 ======
print("="*80, flush=True)
print("多维度池质量优化 - 搜索最佳L1参数", flush=True)
print("="*80, flush=True)

# 跌日 - 抗跌+反弹逻辑
print("\n=== 跌日 ===", flush=True)
stocks = mkt_data.get('down', [])
print(f"样本: {len(stocks)}天", flush=True)

# 测试不同维度组合
tests = []
# 基本组合：p[2,7] vr[0.6,1.5] cl[40,90] hsl[5,20] sz<150 (当前L2:62%)
base = {'p_min':2,'p_max':7,'vr_min':0.6,'vr_max':1.5,'cl_min':40,'cl_max':90,
        'hs_min':5,'hs_max':20,'sz_max':150}
rate,avg,ok,total = test_level(stocks, base, real_data, names)
print(f"  基础版 (p[2,7] vr[0.6,1.5] cl[40,90]): {rate:.1f}%  日均{avg:.0f}只  {ok}/{total}天", flush=True)

# 加MACD金叉
for mg_min in [0, 1]:
    for a5_req in [0, 1]:
        for kdj_g_req in [0, 1]:
            for j_min, j_max in [(-999,999), (0,80), (20,100)]:
                for dif_min in [-999, 0]:
                    params = {**base}
                    params['mg_min'] = mg_min
                    params['a5_req'] = a5_req
                    params['kdj_g_req'] = kdj_g_req
                    params['j_min'] = j_min
                    params['j_max'] = j_max
                    params['dif_min'] = dif_min
                    
                    rate,avg,ok,total = test_level(stocks, params, real_data, names)
                    if ok >= total*0.3 and rate > 60:  # 至少30%天出票
                        tags = []
                        if mg_min: tags.append('MACD金叉')
                        if a5_req: tags.append('站MA5')
                        if kdj_g_req: tags.append('KDJ金叉')
                        if j_min > -998: tags.append(f'J>{j_min}')
                        if j_max < 998: tags.append(f'J<{j_max}')
                        if dif_min > -998: tags.append('DIF>0')
                        tests.append((rate, ok, total, avg, '+'.join(tags) if tags else '基础'))

tests.sort(key=lambda x: -x[0])
for i, (rate, ok, total, avg, tags) in enumerate(tests[:15]):
    print(f"  #{i+1}: {rate:5.1f}%  {ok}/{total}天  {avg:3.0f}只/天  {tags}", flush=True)

# 横盘
print("\n=== 横盘 ===", flush=True)
stocks = mkt_data.get('flat', [])
print(f"样本: {len(stocks)}天", flush=True)
tests2 = []
base2 = {'p_min':1,'p_max':7,'vr_min':0.6,'vr_max':2.0,'cl_min':50,'cl_max':90,
         'hs_min':3,'hs_max':20,'sz_max':150}

for mg_min in [0, 1]:
    for a5_req in [0, 1]:
        for kdj_g_req in [0, 1]:
            for vr_min in [0.6, 0.8]:
                params = {**base2, 'mg_min':mg_min, 'a5_req':a5_req, 'kdj_g_req':kdj_g_req,
                          'j_min':-999, 'j_max':999, 'dif_min':-999, 'vr_min':vr_min}
                rate,avg,ok,total = test_level(stocks, params, real_data, names)
                if ok >= total*0.5 and rate > 40:
                    tags = []
                    if mg_min: tags.append('MACD金叉')
                    if a5_req: tags.append('站MA5')
                    if kdj_g_req: tags.append('KDJ金叉')
                    if vr_min > 0.6: tags.append(f'VR>{vr_min}')
                    tests2.append((rate, ok, total, avg, '+'.join(tags) if tags else '基础'))

tests2.sort(key=lambda x: -x[0])
for i, (rate, ok, total, avg, tags) in enumerate(tests2[:15]):
    print(f"  #{i+1}: {rate:5.1f}%  {ok}/{total}天  {avg:3.0f}只/天  {tags}", flush=True)

# 真实涨日
print("\n=== 真实涨日 ===", flush=True)
stocks = mkt_data.get('real_up', [])
print(f"样本: {len(stocks)}天", flush=True)
tests3 = []
base3 = {'p_min':3,'p_max':7,'vr_min':0.6,'vr_max':2.5,'cl_min':60,'cl_max':90,
         'hs_min':5,'hs_max':15,'sz_max':150}

for mg_min in [0, 1]:
    for a5_req in [0, 1]:
        for kdj_g_req in [0, 1]:
            for cl_min in [60, 65]:
                params = {**base3, 'mg_min':mg_min, 'a5_req':a5_req, 'kdj_g_req':kdj_g_req,
                          'j_min':-999, 'j_max':999, 'dif_min':-999, 'cl_min':cl_min}
                rate,avg,ok,total = test_level(stocks, params, real_data, names)
                if ok >= total*0.5 and rate > 40:
                    tags = []
                    if mg_min: tags.append('MACD金叉')
                    if a5_req: tags.append('站MA5')
                    if kdj_g_req: tags.append('KDJ金叉')
                    if cl_min > 60: tags.append(f'CL>{cl_min}')
                    tests3.append((rate, ok, total, avg, '+'.join(tags) if tags else '基础'))

tests3.sort(key=lambda x: -x[0])
for i, (rate, ok, total, avg, tags) in enumerate(tests3[:15]):
    print(f"  #{i+1}: {rate:5.1f}%  {ok}/{total}天  {avg:3.0f}只/天  {tags}", flush=True)

print(f"\n总耗时: {time.time()-t0:.0f}s", flush=True)
