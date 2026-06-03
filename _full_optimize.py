"""
大道至简 全行情L0参数+评分参数优化
规则：
1. L0第一级参数必须出8~200只候选
2. 超200就收紧L0，不降级
3. 不足8才降级
4. 每个行情独立找最优参数+最优评分权重
"""
import pickle, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dev/current'))

with open(os.path.join(os.path.dirname(__file__), 'big_cache_full.pkl'), 'rb') as f:
    cache = pickle.load(f)
data = cache['data']
real_data = cache.get('real', {})
names = cache.get('names', {})

dates = sorted(x for x in data.keys() if '2025-06-01' <= x < '2026-06-01')
print(f"总日期: {len(dates)}天")

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

# 按行情分组
stocks_by_mkt = {'real_up':[], 'fake_up':[], 'down':[], 'flat':[]}
mkt_dates = {'real_up':[], 'fake_up':[], 'down':[], 'flat':[]}
for dt in dates:
    s = data.get(dt, [])
    m = classify_mkt(s)
    if m in stocks_by_mkt:
        stocks_by_mkt[m].append(s)
        mkt_dates[m].append(dt)

for mk, mn in [('real_up','真实涨日'),('fake_up','虚涨日'),('down','跌日'),('flat','横盘')]:
    print(f"\n{'='*60}")
    print(f"{mn}: {len(stocks_by_mkt[mk])}天")
    print(f"{'='*60}")
    
    # === 步骤1: 搜索最优L0参数 ===
    print(f"\n--- 步骤1: L0参数搜索 (目标8~200只) ---")
    
    def count_l0(stocks, p_min, p_max, vr_min, vr_max, cl_min, cl_max, hs_min=1, hs_max=50, sz_max=1000):
        """带完整过滤的L0计数"""
        cnt = 0
        for s in stocks:
            code = s.get('code', '')
            p = s.get('p',0) or 0
            if p < p_min or p > p_max: continue
            if p >= 8: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < vr_min or vr > vr_max: continue
            cl = s.get('cl',0) or 0
            if cl < cl_min or cl > cl_max: continue
            ri = real_data.get(code)
            if ri:
                hsl = (ri.get('hsl',0) or 0)
                if hsl < hs_min or hsl > hs_max: continue
                sz = (ri.get('shizhi',0) or 0) * 1e-8 if isinstance(ri.get('shizhi'), (int,float)) and ri.get('shizhi',0) > 1 else (ri.get('shizhi',0) or 0)
                if sz >= sz_max: continue
            nm = names.get(code, '')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cnt += 1
        return cnt
    
    # 为每个行情生成L0参数候选
    l0_candidates = []
    
    if mk == 'real_up':
        # 当前已OK: p∈[3.5,6] vr∈[0.8,2.0] cl∈[65,85] → 平均30只
        # 微调保持8~200
        for p_min in [3.0, 3.5, 4.0]:
            for p_max in [5, 6]:
                for cl_min in [60, 65]:
                    for cl_max in [85, 88]:
                        counts = []
                        for s_list in stocks_by_mkt[mk]:
                            c = count_l0(s_list, p_min, p_max, 0.8, 2.0, cl_min, cl_max, 5, 10, 100)
                            counts.append(c)
                        avg = sum(counts)/len(counts) if counts else 0
                        ok = sum(1 for c in counts if 8 < c <= 200)
                        rate = ok/len(counts)*100 if counts else 0
                        l0_candidates.append((avg, rate, p_min, p_max, 0.8, 2.0, cl_min, cl_max, 5, 10, 100))
    
    elif mk == 'fake_up':
        # 当前L0 806只 → 大幅收紧
        for p_min in [2, 3]:
            for p_max in [5, 6]:
                for vr_min in [0.8, 1.0]:
                    for vr_max in [1.5, 1.8]:
                        for cl_min in [50, 60]:
                            for cl_max in [80, 85]:
                                for hs_min in [5, 8]:
                                    for hs_max in [15]:
                                        counts = []
                                        for s_list in stocks_by_mkt[mk]:
                                            c = count_l0(s_list, p_min, p_max, vr_min, vr_max, cl_min, cl_max, hs_min, hs_max, 200)
                                            counts.append(c)
                                        avg = sum(counts)/len(counts) if counts else 0
                                        ok = sum(1 for c in counts if 8 < c <= 200)
                                        rate = ok/len(counts)*100 if counts else 0
                                        if avg >= 5 and rate >= 40:
                                            l0_candidates.append((avg, rate, p_min, p_max, vr_min, vr_max, cl_min, cl_max, hs_min, hs_max, 200))
    
    elif mk == 'down':
        # 当前L0 1833只 → 大幅收紧
        for p_min in [0, 1, 2]:
            for p_max in [5, 6, 7]:
                for vr_min in [0.6, 0.8]:
                    for vr_max in [1.5, 2.0]:
                        for cl_min in [20, 30]:
                            for cl_max in [80, 85]:
                                for hs_min in [1, 3]:
                                    for hs_max in [20, 30]:
                                        for sz_max in [200, 300]:
                                            counts = []
                                            for s_list in stocks_by_mkt[mk]:
                                                c = count_l0(s_list, p_min, p_max, vr_min, vr_max, cl_min, cl_max, hs_min, hs_max, sz_max)
                                                counts.append(c)
                                            avg = sum(counts)/len(counts) if counts else 0
                                            ok = sum(1 for c in counts if 8 < c <= 200)
                                            rate = ok/len(counts)*100 if counts else 0
                                            if avg >= 5 and rate >= 40:
                                                l0_candidates.append((avg, rate, p_min, p_max, vr_min, vr_max, cl_min, cl_max, hs_min, hs_max, sz_max))
    
    elif mk == 'flat':
        # 当前L0 781只 → 收紧
        for p_min in [1, 2]:
            for p_max in [5, 6, 7]:
                for vr_min in [0.6, 0.8]:
                    for vr_max in [1.5, 1.8, 2.0]:
                        for cl_min in [50, 60]:
                            for cl_max in [85, 90]:
                                for hs_min in [3, 5]:
                                    for hs_max in [15, 20]:
                                        counts = []
                                        for s_list in stocks_by_mkt[mk]:
                                            c = count_l0(s_list, p_min, p_max, vr_min, vr_max, cl_min, cl_max, hs_min, hs_max, 200)
                                            counts.append(c)
                                        avg = sum(counts)/len(counts) if counts else 0
                                        ok = sum(1 for c in counts if 8 < c <= 200)
                                        rate = ok/len(counts)*100 if counts else 0
                                        if avg >= 5 and rate >= 50:
                                            l0_candidates.append((avg, rate, p_min, p_max, vr_min, vr_max, cl_min, cl_max, hs_min, hs_max, 200))
    
    # 排序：优先OK率，其次靠近50只
    if l0_candidates:
        l0_candidates.sort(key=lambda x: (-x[1], abs(x[0]-50)))
        print(f"  找到 {len(l0_candidates)} 组候选参数")
        for i, (avg, rate, *params) in enumerate(l0_candidates[:5]):
            p1, p2, v1, v2, c1, c2, h1, h2, sz = params
            print(f"  候选#{i+1}: avg={avg:.0f}只 OK率={rate:.0f}% p∈[{p1},{p2}] vr∈[{v1},{v2}] cl∈[{c1},{c2}] hsl∈[{h1},{h2}] sz<{sz}")
        
        # 选最优L0参数
        best_l0 = l0_candidates[0]
        avg, rate, *best_params = best_l0
        p1, p2, v1, v2, c1, c2, h1, h2, sz = best_params
        
        print(f"\n  → 选定L0: p∈[{p1},{p2}] vr∈[{v1},{v2}] cl∈[{c1},{c2}] hsl∈[{h1},{h2}] sz<{sz}")
        
        # === 步骤2: 测试评分参数 ===
        print(f"\n--- 步骤2: 评分参数搜索 ---")
        
        # 定义评分函数模板
        def make_score_fn(name, p_w, cl_w, macd_w, ma5_b, vr_b, hs_b, wr_b, j_b, j_low_b, 
                          cl_bonus=0, cl_penalty=0, vr_bonus=0, zone_b=0, 
                          cl_low_b=0, p_deep_b=0, cl_high_pen=0, p_high_pen=0,
                          kdj_g=0, hs_bonus=0, vr_bonus2=0):
            def fn(stock):
                p = stock.get('p',0) or 0
                cl = stock.get('cl',0) or 0
                vr = stock.get('vr',0) or 0
                hsl = stock.get('hsl',0) or 0
                dif = stock.get('dif',0) or 0
                mg = stock.get('mg',0) or 0
                a5 = stock.get('a5',0) or 0
                wrv = stock.get('wrv',0) or 0
                jv = stock.get('jv',0) or 0
                kv = stock.get('kv',0) or 0
                dv = stock.get('dv',0) or 0
                kdj_golden = stock.get('kdj_g',0) or 0
                buy_c = stock.get('buy_c',0) or 0
                
                ms = 0
                if mg and dif > 0.5: ms = 10
                elif mg and dif > 0.2: ms = 8
                elif mg: ms = 6
                elif dif > 0.5: ms = 4
                elif dif > 0: ms = 2
                
                ps2 = min(10, max(1, 11 - buy_c / 10)) if buy_c else 0
                score = p * p_w + cl * cl_w + ps2 * 0.3 + ms * macd_w
                score += (ma5_b if a5 else 0)
                score += (vr_b * 1.5 if 1.0 <= vr <= 1.5 else 0)
                score += (hs_b * 2 if 5 <= hsl <= 7 else 0)
                score += (wr_b if wrv < 25 else 0)
                score += (j_b if jv > kv > dv else 0)
                score += (j_low_b if 20 <= jv <= 40 else 0)
                
                # V260528通用
                if p > 5 and cl > 80: score -= 8
                if dif > 0.5: score += 3
                if mg: score += 3
                
                # 扩展加分
                score += (cl_bonus if 65 <= cl <= 83 else 0)
                score += (cl_penalty if 70 <= cl < 80 else 0)
                score += (vr_bonus if 1.0 <= vr <= 1.3 else 0)
                score += (zone_b if 50 <= cl <= 75 else 0)
                score += (cl_low_b if cl < 15 else 0)
                score += (p_deep_b if p < -3 else 0)
                score += (cl_high_pen if cl > 85 else 0)
                score += (p_high_pen if p >= 6.5 else 0)
                score += (kdj_g * 2 if kdj_golden else 0)
                score += (hs_bonus if hsl >= 5 else 0)
                score += (vr_bonus2 if 0.6 <= vr <= 1.0 else 0)
                
                return score
            fn.__name__ = f"{name}_score"
            return fn
        
        # 根据行情生成评分参数网格
        score_grids = []
        
        if mk == 'real_up':
            # 已较优：p_w=1.2 cl_bonus+cl_penalty+vr_bonus
            for p_w in [1.0, 1.2, 1.5]:
                for macd_w in [0.3, 0.5]:
                    for cl_bonus in [1, 2, 3]:
                        for vr_bonus in [1, 2]:
                            score_grids.append({
                                'name': f'p{p_w}_m{macd_w}_clb{cl_bonus}_vrb{vr_bonus}',
                                'p_w': p_w, 'cl_w': 0.05, 'macd_w': macd_w,
                                'ma5_b': 3, 'vr_b': 1, 'hs_b': 0.3,
                                'wr_b': 2, 'j_b': 2, 'j_low_b': 2,
                                'cl_bonus': cl_bonus, 'cl_penalty': -1, 'vr_bonus': vr_bonus,
                            })
        
        elif mk == 'fake_up':
            # 样本少，极简为主
            for p_w in [1.0, 1.5, 2.0]:
                for macd_w in [0.3, 0.5, 0.8]:
                    for ma5_b in [0, 2]:
                        for vr_b in [0, 2]:
                            score_grids.append({
                                'name': f'p{p_w}_m{macd_w}_m5{ma5_b}_vr{vr_b}',
                                'p_w': p_w, 'cl_w': 0.05, 'macd_w': macd_w,
                                'ma5_b': ma5_b, 'vr_b': vr_b, 'hs_b': 0,
                                'wr_b': 0, 'j_b': 0, 'j_low_b': 0,
                            })
        
        elif mk == 'down':
            # 跌日：抓反弹
            for p_w in [1.0, 1.5, 2.0]:
                for macd_w in [0.3, 0.5]:
                    for zone_b in [2, 3]:
                        for cl_low_b in [2, 3]:
                            for p_deep_b in [0, 2]:
                                for vr_bonus2 in [2, 3]:
                                    score_grids.append({
                                        'name': f'p{p_w}_m{macd_w}_z{zone_b}_lo{cl_low_b}_d{p_deep_b}_vr{vr_bonus2}',
                                        'p_w': p_w, 'cl_w': 0.05, 'macd_w': macd_w,
                                        'ma5_b': 2, 'vr_b': 0, 'hs_b': 0,
                                        'wr_b': 0, 'j_b': 0, 'j_low_b': 0,
                                        'zone_b': zone_b, 'cl_low_b': cl_low_b,
                                        'p_deep_b': p_deep_b, 'cl_high_pen': -3,
                                        'p_high_pen': -1, 'hs_bonus': 2,
                                        'vr_bonus2': vr_bonus2,
                                    })
        
        elif mk == 'flat':
            # 横盘：量价确认型
            for p_w in [1.5, 2.0, 2.5]:
                for macd_w in [0.2, 0.3, 0.5]:
                    for vr_b in [2, 4, 6]:
                        for ma5_b in [2, 3]:
                            for kdj_g in [0, 1]:
                                score_grids.append({
                                    'name': f'p{p_w}_m{macd_w}_vr{vr_b}_m5{ma5_b}_kdj{kdj_g}',
                                    'p_w': p_w, 'cl_w': 0.05, 'macd_w': macd_w,
                                    'ma5_b': ma5_b, 'vr_b': vr_b, 'hs_b': 0.3,
                                    'wr_b': 0, 'j_b': 0, 'j_low_b': 2,
                                    'kdj_g': kdj_g,
                                })
        
        # 回测评分
        best_rate = 0
        best_config = None
        best_champion_pct = 0  # 次日最高均值
        results_list = []
        
        total_grids = len(score_grids)
        for gi, grid in enumerate(score_grids):
            fn = make_score_fn(grid['name'], **{k: grid[k] for k in grid if k != 'name'})
            wins = 0
            total = 0
            day_results = []
            
            s_list = stocks_by_mkt[mk]
            d_list = mkt_dates[mk]
            
            for idx, (s_list_day, dt) in enumerate(zip(s_list, d_list)):
                # L0过滤
                pool = []
                for s in s_list_day:
                    code = s.get('code', '')
                    p = s.get('p',0) or 0
                    if p < p1 or p > p2: continue
                    if p >= 8: continue
                    vr = s.get('vol_ratio',0) or 0
                    if vr < v1 or vr > v2: continue
                    cl = s.get('cl',0) or 0
                    if cl < c1 or cl > c2: continue
                    ri = real_data.get(code)
                    if ri:
                        hsl = (ri.get('hsl',0) or 0)
                        if hsl < h1 or hsl > h2: continue
                        sz_val = (ri.get('shizhi',0) or 0)
                        if isinstance(sz_val, (int,float)) and sz_val > 1:
                            sz_val = sz_val * 1e-8
                        if sz_val >= sz: continue
                    nm = names.get(code, '')
                    if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                    
                    stock_dict = {
                        'p': p, 'cl': cl, 'vr': vr, 'hsl': (ri.get('hsl',0) or 0) if ri else 0,
                        'dif': s.get('dif_val',0) or 0, 'mg': s.get('macd_golden',0),
                        'a5': s.get('above_ma5',0) or 0, 'wrv': s.get('wr',0) or 0,
                        'jv': s.get('j_val',0) or 0, 'kv': s.get('k_val',0) or 0,
                        'dv': s.get('d_val',0) or 0, 'kdj_g': s.get('kdj_golden',0) or 0,
                        'buy_c': s.get('close',0) or 0,
                    }
                    sc = fn(stock_dict)
                    nh = s.get('n',0) or 0
                    pool.append({'sc': sc, 'nh': nh, 'code': code, 'nm': names.get(code,'')[:6]})
                
                if not pool: continue
                pool.sort(key=lambda x: -x['sc'])
                
                champion = pool[0]
                total += 1
                if champion['nh'] >= 2.5:
                    wins += 1
                day_results.append(champion['nh'])
            
            if total >= 3:  # 至少3天样本
                rate_val = wins/total*100
                avg_nh = sum(day_results)/len(day_results) if day_results else 0
                results_list.append((rate_val, wins, total, avg_nh, grid['name'], grid))
                
                if rate_val > best_rate:
                    best_rate = rate_val
                    best_champion_pct = avg_nh
                    best_config = grid
        
        # 输出前10结果
        results_list.sort(key=lambda x: (-x[0], -x[3]))
        print(f"  共测试 {len(results_list)} 组评分参数")
        for i, (rate, w, t, avg_nh, name, _) in enumerate(results_list[:10]):
            print(f"  #{i+1}: {name} → {rate:.1f}% ({w}/{t}) 次日最高均值={avg_nh:.1f}%")
        
        # 输出最优
        if best_config:
            print(f"\n  ✅ 最优评分: {best_config['name']}")
            print(f"     胜率: {best_rate:.1f}% 次日最高均值: {best_champion_pct:.1f}%")
            
            # 输出最终建议
            print(f"\n  📋 最终建议:")
            print(f"     L0: p∈[{p1},{p2}] vr∈[{v1},{v2}] cl∈[{c1},{c2}] hsl∈[{h1},{h2}] sz<{sz}")
            for k, v in best_config.items():
                if k != 'name':
                    spaces = ' ' * (15 - len(k))
                    print(f"     {k}:{spaces}{v}")
    else:
        print(f"  ❌ 未找到合适的L0参数")

print("\n\n✅ 全部完成")
