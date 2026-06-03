"""V9 30天回测 - 不发邮件"""
import sys, os, importlib, pickle, time
from datetime import datetime

SCRIPTS_DIR = 'C:/Users/12546/AppData/Local/hermes/scripts'
sys.path.insert(0, os.path.join(SCRIPTS_DIR, 'archive/V9'))

# 强制清除模块缓存
for mod in list(sys.modules.keys()):
    if '分而治之' in mod or 'V9' in mod:
        del sys.modules[mod]

# 直接导入各评分模块
from archive.V9 import 分而治之_V9_真实涨日_评分策略 as zzr_mod
from archive.V9 import 分而治之_V9_跌日_评分策略 as dr_mod
from archive.V9 import 分而治之_V9_横盘_评分策略 as hp_mod
from archive.V9 import 分而治之_V9_虚涨日_评分策略 as xzr_mod

# 加载整则中的calc_historical_win_rate和classify_mkt_hist
# 直接复制回测逻辑，避免import整则脚本触发主流程
def classify_mkt_hist(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p',0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

def backtest(mkt_key, module, levels, max_days=30):
    mkt_names = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
    try:
        d = pickle.load(open(os.path.join(SCRIPTS_DIR, 'big_cache_full.pkl'), 'rb'))
        data, real, names = d['data'], d['real'], d['names']
    except Exception as e:
        return f'❌ 加载缓存失败: {e}'
    
    dates = sorted(x for x in data.keys() if '2025-01-01' <= x < '2026-06-01')[-max_days:]
    
    score_fn = getattr(module, 'score', None)
    if not score_fn:
        return f'❌ {module} 无score函数'
    
    wins = 0; total = 0
    detail_days = []
    for dt in dates:
        stocks = data.get(dt, [])
        if not stocks: continue
        m = classify_mkt_hist(stocks)
        if m != mkt_key: continue
        
        pool = None
        for lv in levels:
            pool = []
            for s in stocks:
                code = s.get('code',''); p = s.get('p',0) or 0
                if p < lv['p_min'] or p > lv['p_max']: continue
                if p >= 8: continue
                vr = s.get('vol_ratio',0) or 0
                if vr < lv['vr_min'] or vr > lv['vr_max']: continue
                ri = real.get(code)
                if not ri: continue
                hsl = (ri.get('hsl',0) or 0)
                if hsl < lv['hs_min'] or hsl > lv['hs_max']: continue
                if (ri.get('shizhi',0) or 0) >= lv['sz_max']: continue
                nm = names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl = s.get('cl',0)
                if cl < lv['cl_min'] or cl > lv['cl_max']: continue
                if (s.get('n',0) or 0) <= 0: continue
                pool.append(s)
            if len(pool) > 8: break
            pool = None
        if not pool or len(pool) <= 8: continue
        
        scored = []
        for s in pool:
            stock = {
                'p': s.get('p',0) or 0, 'cl': s.get('cl',0),
                'vr': s.get('vol_ratio',0) or 0,
                'hsl': (real.get(s['code'],{}).get('hsl',0) or 0),
                'dif': s.get('dif_val',0) or 0, 'mg': s.get('macd_golden',0),
                'a5': s.get('above_ma5',0) or 0, 'wrv': s.get('wr_val',0) or 50,
                'jv': s.get('j_val',0) or 0, 'kv': s.get('k_val',0) or 0,
                'dv': s.get('d_val',0) or 0,
                'kdj_g': s.get('kdj_golden',0) or 0,
                'buy_c': s.get('close',0) or 0,
                'pos_in_day': s.get('pos_in_day', 50) or 50,
            }
            sc = score_fn(stock)
            nh = s.get('n',0) or 0
            scored.append({'sc':sc, 'nh':nh, 'code': s.get('code',''), 'nm': names.get(s.get('code',''),''), 'p': s.get('p',0)})
        
        if not scored: continue
        scored.sort(key=lambda x: (-x['sc']))
        total += 1
        champ = scored[0]
        win = champ['nh'] >= 2.5
        if win: wins += 1
        detail_days.append(f"{dt} | {'✅' if win else '❌'} | {champ['nm']}({champ['code']}) p={champ['p']:.1f}% nh={champ['nh']:.1f}% sc={champ['sc']:.1f}")
    
    if total == 0:
        return f'{mkt_names[mkt_key]}: ⚠️ 无交易日数据'
    rate = round(wins*100/total, 1)
    return {
        'name': mkt_names[mkt_key],
        'key': mkt_key,
        'rate': rate,
        'wins': wins,
        'total': total,
        'details': detail_days
    }

# 各行情LEVELS
levels_map = {
    'real_up': zzr_mod.LEVELS,
    'fake_up': xzr_mod.LEVELS,
    'down': dr_mod.LEVELS,
    'flat': hp_mod.LEVELS,
}
module_map = {
    'real_up': zzr_mod,
    'fake_up': xzr_mod,
    'down': dr_mod,
    'flat': hp_mod,
}

print('='*60)
print(f'  V9 30天回测 ({datetime.now().strftime("%Y-%m-%d %H:%M")})')
print('='*60)

results = []
for key, mod in module_map.items():
    result = backtest(key, mod, levels_map[key], max_days=30)
    results.append(result)
    if isinstance(result, dict):
        print(f'\n📊 {result["name"]}: {result["rate"]}% ({result["wins"]}/{result["total"]})')
        print(f'  最近交易日:')
        for d in result['details'][-5:]:
            print(f'  {d}')
    else:
        print(f'\n{result}')

print('\n' + '='*60)
print('  V9 汇总')
print('='*60)
total_w = sum(r['wins'] for r in results if isinstance(r, dict))
total_t = sum(r['total'] for r in results if isinstance(r, dict))
if total_t > 0:
    print(f'  总冠军胜率: {round(total_w*100/total_t,1)}% ({total_w}/{total_t})')
for r in results:
    if isinstance(r, dict):
        bars = '█' * int(r['rate']/5) + '░' * (20 - int(r['rate']/5))
        print(f'  {r["name"]:8s} {bars} {r["rate"]:5.1f}% ({r["wins"]:2d}/{r["total"]:2d})')
print()
