"""
自动化调优脚本 — 目标：冠军达2.5%≥70%
策略：先优化基础过滤保证出票率 → 再加评分提冠军胜率
每轮输出最佳结果，没到70%自动迭代下一轮
"""
import pickle, os, json, sys, statistics, itertools, math, time
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
KLINE_CACHE = {}

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
all_days = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]

print(f'2026年 {len(all_days)}天 | 全量{len(real)}只', flush=True)

def get_kline(code):
    if code not in KLINE_CACHE:
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    KLINE_CACHE[code] = json.load(f)
            except:
                KLINE_CACHE[code] = None
        else:
            KLINE_CACHE[code] = None
    return KLINE_CACHE[code]

def score_stock(s, use_kline=False):
    """给单只股票打分（不含基础过滤）"""
    p = s['p']; vr = s.get('vol_ratio',0) or 0; cl = s.get('cl',0)
    
    # 伯乐v4基础分
    sc = 10
    if 5 <= p <= 6.5: sc += 15
    elif 6.5 < p <= 7: sc += 8
    elif 4.5 <= p < 5: sc += 5
    elif p > 7: sc -= 15
    if 60 <= cl <= 85: sc += 10
    elif cl > 90: sc -= 15
    if 0.8 <= vr <= 1.5: sc += 10
    elif 1.5 < vr <= 2.0: sc += 5
    elif vr > 2: sc -= 8
    
    if use_kline:
        code = s['code']
        buy_c = s.get('close', 0)
        kd = get_kline(code)
        if kd:
            today_idx = next((i for i,d in enumerate(kd) if d['date'] == s.get('date','')), None)
            if today_idx and today_idx >= 20:
                td = kd[today_idx]
                close_price = td['close']
                ma10 = statistics.mean([kd[i]['close'] for i in range(today_idx-9, today_idx+1)])
                ma20 = statistics.mean([kd[i]['close'] for i in range(today_idx-19, today_idx+1)])
                sc += 5 if ma10 >= ma20 else 0
                sc += 2 if close_price >= ma10 else 0
                sc += 3 if close_price >= ma20 else 0
                
                prev_pct = (kd[today_idx-1]['close']/kd[today_idx-2]['close']-1)*100 if today_idx>=2 else 0
                today_pct = (close_price/kd[today_idx-1]['close']-1)*100
                accel = today_pct - prev_pct
                sc += 3 if accel < 7 else 0
                
                vol_ma5 = statistics.mean([kd[i]['volume'] for i in range(today_idx-4, today_idx+1)])
                vol_ratio_v = td['volume']/vol_ma5 if vol_ma5 > 0 else 0
                sc += 2 if vol_ratio_v < 2 else (-3 if vol_ratio_v > 3 else 0)
                
                h20 = max([kd[i]['high'] for i in range(today_idx-19, today_idx+1)])
                l20 = min([kd[i]['low'] for i in range(today_idx-19, today_idx+1)])
                near20 = (close_price-l20)/(h20-l20)*100 if h20>l20 else 50
                sc += 3 if 40 <= near20 <= 80 else (-3 if near20 > 90 else 0)
    return sc

def backtest(params, scoring='none'):
    """
    params = {p_min,p_max, vr_min,vr_max, hsl_min,hsl_max, sz_max, j_max, cl_min,cl_max}
    scoring: 'none'=按涨幅排序, 'basic'=伯乐评分, 'kline'=K线评分
    """
    champ_nvs = []
    days_with_candidates = 0
    
    for dt in all_days:
        stocks = data.get(dt, [])
        filtered = []
        for s in stocks:
            code, p = s['code'], s['p']
            if p < params['p_min'] or p > params['p_max']: continue
            vr = s.get('vol_ratio',0) or 0
            if vr < params['vr_min'] or vr > params['vr_max']: continue
            ri = real.get(code)
            if not ri: continue
            hsl = (ri.get('hsl',0) or 0)
            if hsl < params['hsl_min'] or hsl > params['hsl_max']: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz > params['sz_max']: continue
            nm = names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv = s.get('j_val',0) or 0
            if jv > params['j_max']: continue
            cl = s.get('cl',0)
            if cl < params['cl_min'] or cl > params['cl_max']: continue
            
            nv = s.get('n',0) or 0
            
            if scoring == 'none':
                score_val = p  # 默认按涨幅
            elif scoring == 'basic':
                score_val = score_stock(s, use_kline=False)
            else:
                s['date'] = dt
                score_val = score_stock(s, use_kline=True)
            
            filtered.append((score_val, p, nv))
        
        if not filtered: continue
        days_with_candidates += 1
        # 评分降序，同分按涨幅降序
        filtered.sort(key=lambda x: (-x[0], -x[1]))
        champ_nvs.append(filtered[0][2])
    
    if not champ_nvs: return 0, 0, 0, 0
    
    n = len(champ_nvs)
    w25 = sum(1 for v in champ_nvs if v >= 2.5)
    w5 = sum(1 for v in champ_nvs if v >= 5)
    avg = statistics.mean(champ_nvs)
    chupiao = days_with_candidates * 100 / len(all_days)
    
    return w25*100/n, w5*100/n, avg, chupiao, n

def dict_to_str(d):
    return f'涨{d["p_min"]}~{d["p_max"]}% 量{d["vr_min"]}~{d["vr_max"]} 换手{d["hsl_min"]}~{d["hsl_max"]}% 市值<{d["sz_max"]} J<{d["j_max"]} CL{d["cl_min"]}~{d["cl_max"]}'

# ===== 第1轮：找最佳基础过滤 =====
print(f'\n{"="*80}')
print(f'第1轮：基础过滤参数网格搜索')
print(f'{"="*80}', flush=True)

param_grid = {
    'p_min': [5.0],
    'p_max': [7.0, 7.5, 8.0],
    'vr_min': [0.8, 1.0],
    'vr_max': [1.5, 2.0, 3.0],
    'hsl_min': [5],
    'hsl_max': [12, 15],
    'sz_max': [100, 150, 200],
    'j_max': [80, 100],
    'cl_min': [0, 60, 65],
    'cl_max': [85, 90, 100],
}

results = []
total_params = 1
for k, v in param_grid.items():
    total_params *= len(v)
print(f'总组合: {total_params}', flush=True)

keys = list(param_grid.keys())
values = list(param_grid.values())
idx = 0
best_w25_none = 0
best_params_none = None

for combo in itertools.product(*values):
    params = dict(zip(keys, combo))
    idx += 1
    w25, w5, avg, cp, n = backtest(params, 'none')
    
    # 优先：达2.5% > 出票率
    score = w25 + cp * 0.2
    results.append((score, w25, cp, n, params))
    
    if w25 > best_w25_none:
        best_w25_none = w25
        best_params_none = params
        print(f'[{idx}/{total_params}] 新基准🏆 达2.5%:{w25:.1f}% 出票率:{cp:.1f}% {dict_to_str(params)}', flush=True)

# 最佳基础过滤
results.sort(key=lambda x: -x[0])
best_none = results[0]
b_params = best_none[4]
print(f'\n最佳基础过滤(无评分): 达2.5%:{best_none[1]:.1f}% 出票率:{best_none[2]:.1f}% {dict_to_str(b_params)}', flush=True)

# ===== 第2轮：最佳基础+评分 =====
print(f'\n{"="*80}')
print(f'第2轮：最佳基础+伯乐评分')
print(f'{"="*80}', flush=True)

# 用最佳基础参数 + 伯乐评分
w25_basic, w5_basic, avg_basic, cp_basic, n_basic = backtest(b_params, 'basic')
print(f'基础+伯乐评分: 达2.5%:{w25_basic:.1f}% 出票率:{cp_basic:.1f}% 均{avg_basic:.2f}% {n_basic}天', flush=True)

# ===== 第3轮：最佳基础+K线评分 =====
print(f'\n{"="*80}')
print(f'第3轮：最佳基础+K线评分')
print(f'{"="*80}', flush=True)

w25_k, w5_k, avg_k, cp_k, n_k = backtest(b_params, 'kline')
print(f'基础+K线评分: 达2.5%:{w25_k:.1f}% 出票率:{cp_k:.1f}% 均{avg_k:.2f}% {n_k}天', flush=True)

# ===== 如果没到70%，调参重试 =====
target = 70.0
current_best = max(w25_basic, w25_k) if w25_k > 0 else w25_basic

if current_best < target:
    print(f'\n{"="*80}')
    print(f'第4轮：未达{target}%，尝试放宽基础过滤+强化评分')
    print(f'{"="*80}', flush=True)
    
    # 尝试放宽基础过滤：去掉CL限制、放宽J
    relaxed_params = dict(b_params)
    relaxed_params['cl_min'] = 0
    relaxed_params['cl_max'] = 100
    relaxed_params['j_max'] = 100
    
    w25_r, w5_r, avg_r, cp_r, n_r = backtest(relaxed_params, 'basic')
    print(f'放宽过滤+伯乐评分: 达2.5%:{w25_r:.1f}% 出票率:{cp_r:.1f}% {dict_to_str(relaxed_params)}', flush=True)
    
    # 再试K线评分
    w25_rk, w5_rk, avg_rk, cp_rk, n_rk = backtest(relaxed_params, 'kline')
    print(f'放宽过滤+K线评分: 达2.5%:{w25_rk:.1f}% 出票率:{cp_rk:.1f}%', flush=True)
    
    # 试试最宽松（原版过滤）
    loose_params = {'p_min':5,'p_max':8,'vr_min':0.8,'vr_max':3.0,'hsl_min':5,'hsl_max':15,'sz_max':200,'j_max':100,'cl_min':0,'cl_max':100}
    w25_l, w5_l, avg_l, cp_l, n_l = backtest(loose_params, 'kline')
    print(f'最宽松+K线评分: 达2.5%:{w25_l:.1f}% 出票率:{cp_l:.1f}%', flush=True)

# ===== 汇总报告 =====
print(f'\n{"="*80}')
print(f'📊 自动化调优汇总报告')
print(f'{"="*80}', flush=True)
print(f'目标：冠军达2.5% ≥ 70%')
print(f'')
print(f'结果：')
print(f'  [无评分] 最佳基础过滤 → 达2.5%:{best_none[1]:.1f}% 出票率:{best_none[2]:.1f}%')
print(f'  [伯乐评分] 最佳基础+评分 → 达2.5%:{w25_basic:.1f}% 出票率:{cp_basic:.1f}%')
print(f'  [K线评分] 最佳基础+K线 → 达2.5%:{w25_k:.1f}% 出票率:{cp_k:.1f}%', flush=True)

if current_best >= target:
    print(f'\n🎉 达成目标{target}%!')
    print(f'最佳参数: {dict_to_str(b_params)}')
    print(f'评分方式: {"K线" if w25_k > w25_basic else "伯乐"}')
else:
    print(f'\n❌ 当前最优 {current_best:.1f}% 未达{target}%')
    print(f'差距: {target - current_best:.1f}%')
    print(f'\n下一步方向：')
    print(f'  1. 完全放宽所有条件，用K线评分拼')
    print(f'  2. 换评分权重（加速度/均线/量比权重调整）')
    print(f'  3. 加入板块/资金流向维度（需外部数据）')

print(f'\n最佳基础参数: {json.dumps(b_params)}', flush=True)
print(f'耗时: {time.time()-cache.get("_load_time", time.time()):.1f}秒', flush=True)

# 保存结果
import json as j
with open('auto_opt_result.json','w') as f:
    j.dump({
        'best_params': b_params,
        'no_score': {'w25':best_none[1], 'cp':best_none[2]},
        'basic_score': {'w25':w25_basic, 'cp':cp_basic},
        'kline_score': {'w25':w25_k, 'cp':cp_k},
        'target': target,
        'best_achieved': current_best,
    }, f, ensure_ascii=False, indent=2)
print('结果已保存到 auto_opt_result.json', flush=True)
