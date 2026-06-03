"""分而治之 V5 生产调优 — 找到最优参数并保存到JSON"""
import pickle, os, sys, copy, random, json, importlib
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
IDX_FILE = os.path.join(SCRIPTS_DIR, '分而治之_日期索引.pkl')

sys.path.insert(0, SCRIPTS_DIR)
with open(IDX_FILE, 'rb') as f: di = pickle.load(f)

daily = di['daily']; dates = di['dates']; kline = di['kline']
TARGET = 85.0

market_names = {'real_up': '真实涨日', 'fake_up': '虚涨日', 'down': '跌日', 'flat': '横盘'}
strat_names = {'real_up': '分而治之_真实涨日_评分策略', 'fake_up': '分而治之_虚涨日_评分策略',
               'down': '分而治之_跌日_评分策略', 'flat': '分而治之_横盘_评分策略'}
score_fn_names = {'real_up': '真实涨日_评分', 'fake_up': '虚涨日_评分',
                  'down': '跌日_评分', 'flat': '横盘_评分'}

def get_nd_high(code, dt, kline):
    kd = kline.get(code)
    if not kd: return None
    d8 = dt.replace('-', '')
    ads = sorted([d for d in kd.keys() if len(d) == 8 and d.isdigit()])
    try: idx = ads.index(d8)
    except: return None
    if idx + 1 >= len(ads): return None
    bc = kd.get(d8, {}).get('c', 0)
    if bc <= 0: return None
    return round((kd[ads[idx+1]]['h'] / bc - 1) * 100, 2)

def classify(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) for s in stocks]; vrs = [s.get('vr', 0) for s in stocks if s.get('vr', 0)]
    if not ps: return 'flat'
    ap = sum(ps) / len(ps); av = sum(vrs) / len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

# 预分类
mkt_dates = {reg: [] for reg in market_names}
for dt in dates:
    ss = [s for s in daily.get(dt, []) if abs(s.get('p', 0)) < 9.98]
    if ss: mkt_dates[classify(ss)].append(dt)

for reg, ds in mkt_dates.items():
    print(f"  {market_names[reg]}: {len(ds)}天")

def prepare_stock_dict(s):
    """把daily里的原始stock转成评分函数需要的格式"""
    return {
        'p': s.get('p', 0) or 0,
        'cl': s.get('cl', 0) or 0,
        'vr': s.get('vr', 0) or 0,
        'hsl': s.get('hs', 0) or 0,
        'dif': s.get('dif_val', 0) or 0,
        'mg': s.get('macd_golden', 0) or 0,
        'a5': s.get('above_ma5', 0) or 0,
        'wrv': s.get('wr', 50) or 50,
        'jv': s.get('j_val', 50) or 50,
        'kv': s.get('k_val', 50) or 50,
        'dv': s.get('d_val', 50) or 50,
        'kdj_g': s.get('kdj_golden', 0) or 0,
        'buy_c': s.get('close', 0) or 0,
    }

def mutate_score(orig_score):
    """随机变异SCORE权重值"""
    s = copy.deepcopy(orig_score)
    for key in s:
        if isinstance(s[key], (int, float)):
            # 随机扰动: ±30%或±2取大者
            factor = random.uniform(0.3, 2.0)
            s[key] = round(s[key] * factor, 2)
    return s

def mutate_level(lv):
    """随机微调LEVEL筛选条件"""
    l = copy.deepcopy(lv)
    if 'p_min' in l: l['p_min'] = l['p_min'] + random.choice([-2, -1, 0, 0, 0, 1, 2])
    if 'p_max' in l: l['p_max'] = l['p_max'] + random.choice([-1, 0, 0, 1])
    if 'vr_min' in l: l['vr_min'] = max(0.1, round(l['vr_min'] + random.choice([-0.2, -0.1, 0, 0, 0.1, 0.2]), 1))
    if 'vr_max' in l: l['vr_max'] = max(0.3, round(l['vr_max'] + random.choice([-0.3, -0.2, 0, 0, 0.2, 0.3, 0.5]), 1))
    if 'hs_min' in l: l['hs_min'] = max(0.1, l['hs_min'] + random.choice([-1, 0, 0, 0, 1, 2]))
    if 'hs_max' in l: l['hs_max'] = l['hs_max'] + random.choice([-3, -2, 0, 0, 2, 3, 5])
    if 'sz_max' in l: l['sz_max'] = l['sz_max'] + random.choice([-50, -20, 0, 0, 0, 20, 50])
    if 'cl_min' in l: l['cl_min'] = max(0, l['cl_min'] + random.choice([-10, -5, 0, 0, 0, 5, 10]))
    if 'cl_max' in l: l['cl_max'] = min(100, l['cl_max'] + random.choice([-5, 0, 0, 0, 5]))
    return l

def run_tuning(regime, iterations=10000):
    name = market_names[regime]
    print(f"\n📊 {name}: 调优 {iterations}次")
    
    mod = importlib.import_module(strat_names[regime])
    importlib.reload(mod)
    score_fn = getattr(mod, score_fn_names[regime])
    orig_score = getattr(mod, 'SCORE')
    orig_levels = getattr(mod, 'LEVELS')
    
    targets = mkt_dates[regime][-30:] if len(mkt_dates[regime]) >= 30 else mkt_dates[regime]
    print(f"  回测天数: {len(targets)}")
    
    best_score = orig_score
    best_levels = orig_levels
    best_rate = 0.0
    best_wins = 0
    best_total = 0
    
    for i in range(iterations):
        # 70%调SCORE + 30%调LEVELS+SCORE
        if random.random() < 0.7:
            cur_score = mutate_score(orig_score)
            cur_levels = orig_levels
        else:
            cur_score = mutate_score(orig_score)
            cur_levels = [mutate_level(l) for l in orig_levels[:3]] + orig_levels[3:]
        
        wins = total = 0
        for dt in targets:
            ss = [s for s in daily.get(dt, []) if abs(s.get('p', 0)) < 9.98]
            if not ss: continue
            
            pool = None
            for lv in cur_levels:
                pool = []
                for s in ss:
                    p = s.get('p', 0) or 0
                    if p < lv.get('p_min', -10) or p > lv.get('p_max', 8): continue
                    if p >= 8: continue
                    vr = s.get('vr', 0) or 0
                    if vr < lv.get('vr_min', 0.1) or vr > lv.get('vr_max', 10): continue
                    cl = s.get('cl', 0) or 0
                    if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
                    pool.append(s)
                if len(pool) > 8: break
                pool = None
            
            if not pool or len(pool) <= 8: continue
            
            # 临时把score权重挂到模块上
            old_score = getattr(mod, 'SCORE')
            setattr(mod, 'SCORE', cur_score)
            
            scored = []
            for s in pool:
                sd = prepare_stock_dict(s)
                sc = score_fn(sd)
                nh = get_nd_high(s['code'], dt, kline)
                scored.append({'sc': sc, 'nh': nh})
            
            setattr(mod, 'SCORE', old_score)
            
            if not scored: continue
            scored.sort(key=lambda x: -x['sc'])
            total += 1
            if scored[0]['nh'] is not None and scored[0]['nh'] >= 2.5:
                wins += 1
        
        rate = round(wins * 100 / total, 1) if total else 0
        
        if rate > best_rate:
            best_rate = rate
            best_score = cur_score
            best_levels = cur_levels
            best_wins = wins
            best_total = total
            print(f"  ⬆️ [{i}] {rate}% ({wins}/{total}) ✅")
            if rate >= TARGET:
                break
        
        if i % 500 == 0 and i > 0:
            print(f"  ... {i}/{iterations} 当前最佳: {best_rate}%", flush=True)
    
    print(f"  → 最佳: {best_rate}% {'✅' if best_rate >= TARGET else '❌'}")
    return best_score, best_levels, best_rate, best_wins, best_total

# ===== 主 =====
print(f"🚀 分而治之 V5 生产调优 {datetime.now()}")
print(f"目标胜率: {TARGET}%")

results = {}
all_params = {}

for regime in ['real_up', 'fake_up', 'down', 'flat']:
    if len(mkt_dates[regime]) < 20:
        print(f"❌ {market_names[regime]}: 数据不足 {len(mkt_dates[regime])}天")
        continue
    
    best_score, best_levels, best_rate, wins, total = run_tuning(regime)
    results[regime] = (best_rate, wins, total)
    all_params[regime] = {
        'SCORE': best_score,
        'LEVELS': best_levels,
        'win_rate': best_rate,
        'wins': wins,
        'total': total,
    }
    print(f"  ✅ {market_names[regime]}: {wins}/{total} = {best_rate}%")

# 保存所有参数
params_path = os.path.join(SCRIPTS_DIR, '分而治之_V5_PARAMS.json')
with open(params_path, 'w', encoding='utf-8') as f:
    json.dump(all_params, f, ensure_ascii=False, indent=2)
print(f"\n💾 参数已保存: {params_path}")

# 汇总
print(f"\n{'='*50}")
print(f"  V5 生产调优结果:")
for reg, (rate, w, t) in results.items():
    emoji = '✅' if rate >= TARGET else '❌'
    print(f"  {emoji} {market_names[reg]}: {w}/{t} = {rate}%")
print(f"  达标: {sum(1 for r in results.values() if r[0] >= TARGET)}/4")

# 写入策略文件
print(f"\n🔄 写入策略文件...")
for regime in results:
    p = all_params[regime]
    fn = os.path.join(SCRIPTS_DIR, f"{strat_names[regime]}.py")
    
    with open(fn, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换SCORE块
    import re
    score_str = json.dumps(p['SCORE'], indent=4)
    score_str = score_str.replace('"', "'")  # to Python dict format
    score_block = f"SCORE = {score_str}"
    
    # Find and replace SCORE = { ... }
    content = re.sub(
        r'SCORE\s*=\s*\{[^}]+\}',
        score_block,
        content,
        count=1
    )
    
    # 替换LEVELS块
    levels_str = json.dumps(p['LEVELS'], indent=4)
    levels_str = levels_str.replace('"', "'")
    levels_str = levels_str.replace("'name': '", "\n    {'name':'").replace("', '", "','")
    levels_str = levels_str.replace("': ", "':")
    
    # Simple LEVELS replacement
    content = re.sub(
        r'LEVELS\s*=\s*\[.*?\]',
        f"LEVELS = {levels_str}",
        content,
        count=1,
        flags=re.DOTALL
    )
    
    # Update BACKTEST
    rate = p['win_rate']
    content = re.sub(
        r'BACKTEST\s*=\s*"[^"]*"',
        f'BACKTEST = "v5_prod_{rate}%"',
        content,
        count=1
    )
    
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  ✅ 已更新: {strat_names[regime]}.py ({p['win_rate']}%)")

print(f"\n🎉 V5生产调优完成!")
