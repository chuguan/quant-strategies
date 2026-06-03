#!/usr/bin/env python3
"""全版本PK — 用统一数据跑所有master/production版本，找最高胜率"""
import pickle, os, sys, json, importlib, time
from collections import defaultdict

SCRIPTS = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS)

T0 = time.time()

# 加载数据
print("加载缓存...", flush=True)
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, real, names = d['data'], d['real'], d['names']
dates_all = [x for x in sorted(data.keys()) if '2025-01-01' <= x < '2026-06-01']

# 统一行情分类
def classify_market(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p',0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

# 预分类所有日期
mkt_dates = {'real_up':[], 'fake_up':[], 'down':[], 'flat':[]}
for dt in dates_all:
    stocks = data.get(dt, [])
    if not stocks: continue
    mkt = classify_market(stocks)
    mkt_dates[mkt].append(dt)

mkt_names = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
mkt_keys = ['real_up', 'fake_up', 'down', 'flat']

def build_stock_dict(s):
    code = s.get('code','')
    ri = real.get(code, {})
    return {
        'p': s.get('p',0) or 0, 'cl': s.get('cl',0),
        'vr': s.get('vol_ratio',0) or 0, 'hsl': (ri.get('hsl',0) or 0),
        'dif': s.get('dif_val',0) or 0, 'mg': s.get('macd_golden',0) or 0,
        'a5': s.get('above_ma5',0) or 0, 'wrv': s.get('wr_val',0) or 20,
        'jv': s.get('j_val',0) or 0, 'kv': s.get('k_val',0) or 0,
        'dv': s.get('d_val',0) or 0, 'kdj_g': s.get('kdj_golden',0) or 0,
        'buy_c': s.get('close', 0) or 0,
        'buy_c': s.get('close',0) or 0, 'next_high': s.get('n', None),
    }

def filter_level(candidates, level):
    r = []
    for s in candidates:
        if s.get('p',0) < level.get('p_min',-100) or s.get('p',0) > level.get('p_max',100): continue
        if s.get('p',0) >= 8: continue
        if s.get('vr',0) < level.get('vr_min',0) or s.get('vr',0) > level.get('vr_max',100): continue
        if s.get('hsl',0) < level.get('hs_min',0) or s.get('hsl',0) > level.get('hs_max',100): continue
        if s.get('sz',0) >= level.get('sz_max',99999): continue
        if s.get('cl',0) < level.get('cl_min',0) or s.get('cl',0) > level.get('cl_max',100): continue
        r.append(s)
    return r

def run_version(label, load_dir, mod_names):
    """加载指定目录的策略模块并跑回测"""
    sys.path.insert(0, load_dir)
    try:
        modules = {}
        for mk, info in mod_names.items():
            mod = importlib.import_module(info['mod'])
            fn = info.get('fn', 'score')
            score_fn = getattr(mod, fn)
            levels = mod.LEVELS
            # 扩展L5
            if levels:
                last = levels[-1]
                levels_ext = levels + [{"name":"L5","p_min":last.get("p_min",-10)-3,"p_max":last.get("p_max",7),
                    "vr_min":max(0.1,last.get("vr_min",0)-0.2),"vr_max":last.get("vr_max",10)+2,
                    "hs_min":max(0.1,last.get("hs_min",0)-1),"hs_max":last.get("hs_max",100)+15,
                    "sz_max":last.get("sz_max",10000)+200,"cl_min":max(0,last.get("cl_min",0)-15),"cl_max":100}]
            else:
                levels_ext = levels
            modules[mk] = {'score':score_fn, 'levels':levels_ext}
        
        # 回测函数
        def run_bt(mkt_key, date_window):
            win=0; total=0
            for dt in date_window:
                stks = data.get(dt, [])
                if len(stks) < 5: continue
                mkt = classify_market(stks)
                if mkt != mkt_key: continue
                
                # 构建候选
                cands = [build_stock_dict(r) for r in stks]
                cands = [c for c in cands if c is not None]
                cands2 = []
                for s in cands:
                    nm = names.get(s.get('code',''), '')
                    if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                    s['nm'] = nm; s['sz'] = real.get(s.get('code',''),{}).get('shizhi',100)
                    cands2.append(s)
                cands = cands2
                
                if mkt not in modules: continue
                mod = modules[mkt]
                scored = []
                for lv in mod['levels']:
                    pool = filter_level(cands, lv)
                    if len(pool) > 8:
                        for s in pool:
                            s['score'] = round(mod['score'](s), 1)
                            scored.append(s)
                        break
                if not scored: continue
                scored.sort(key=lambda x: (-x['score'], -x['p']))
                champ = scored[0]
                nh = champ.get('next_high')
                if nh is not None and nh >= 2.5: win += 1
                total += 1
            return win, total
        
        def run_window(dates, label_window):
            total_w=0; total_n=0
            by_mkt = {}
            for mk in mkt_keys:
                if mk not in modules: continue
                w, t = run_bt(mk, dates)
                if t > 0:
                    by_mkt[mk] = (w, t, round(w/t*100,1))
                    total_w += w; total_n += t
            return total_w, total_n, round(total_w/total_n*100,1) if total_n else 0, by_mkt
        
        # 30天 - 取最近
        end = '2026-05-29'
        d30 = [d for d in dates_all if d >= '2026-04-07' and d < end][-35:]
        w30, n30, r30, bm30 = run_window(d30, '30天')
        
        # 50天
        d50 = [d for d in dates_all if d >= '2026-03-20' and d < end][-55:]
        w50, n50, r50, bm50 = run_window(d50, '50天')
        
        # 100天
        d100 = [d for d in dates_all if d >= '2026-01-01' and d < end][-110:]
        w100, n100, r100, bm100 = run_window(d100, '100天')
        
        return {
            'label': label,
            '30d': (w30, n30, r30, bm30),
            '50d': (w50, n50, r50, bm50),
            '100d': (w100, n100, r100, bm100),
        }
    except Exception as e:
        print(f"  ❌ {label} 加载失败: {e}", flush=True)
        return None
    finally:
        sys.path.pop(0)

# ============ 定义所有版本 ============
VERSIONS = []

# V11 (当前)
VERSIONS.append(('V11 (当前)', os.path.join(SCRIPTS, 'V11'), {
    'real_up': {'mod': '分而治之_V11_真实涨日_评分策略'},
    'fake_up': {'mod': '分而治之_V11_虚涨日_评分策略'},
    'down': {'mod': '分而治之_V11_跌日_评分策略'},
    'flat': {'mod': '分而治之_V11_横盘_评分策略'},
}))

# master01
VERSIONS.append(('master01', os.path.join(SCRIPTS, 'dev/snapshots/master01'), {
    'real_up': {'mod': '大道至简_真实涨日_评分策略'},
    'fake_up': {'mod': '大道至简_虚涨日_评分策略'},
    'down': {'mod': '大道至简_跌日_评分策略'},
    'flat': {'mod': '大道至简_横盘_评分策略'},
}))

# master02
VERSIONS.append(('master02', os.path.join(SCRIPTS, 'dev/snapshots/master02'), {
    'real_up': {'mod': '大道至简_真实涨日_评分策略'},
    'fake_up': {'mod': '大道至简_虚涨日_评分策略'},
    'down': {'mod': '大道至简_跌日_评分策略'},
    'flat': {'mod': '大道至简_横盘_评分策略'},
}))

# V260529
VERSIONS.append(('V260529', os.path.join(SCRIPTS, 'release/V260529'), {
    'real_up': {'mod': '大道至简_真实涨日_评分策略'},
    'fake_up': {'mod': '大道至简_虚涨日_评分策略'},
    'down': {'mod': '大道至简_跌日_评分策略'},
    'flat': {'mod': '大道至简_横盘_评分策略'},
}))

# V2701
VERSIONS.append(('V2701', os.path.join(SCRIPTS, 'release/V2701'), {
    'real_up': {'mod': '大道至简_真实涨日_评分策略'},
    'fake_up': {'mod': '大道至简_虚涨日_评分策略'},
    'down': {'mod': '大道至简_跌日_评分策略'},
    'flat': {'mod': '大道至简_横盘_评分策略'},
}))

# 分而治之
VERSIONS.append(('分而治之', os.path.join(SCRIPTS, 'release/分而治之'), {
    'real_up': {'mod': '分而治之真实涨日_评分策略'},
    'fake_up': {'mod': '分而治之虚涨日_评分策略'},
    'down': {'mod': '分而治之跌日_评分策略'},
    'flat': {'mod': '分而治之横盘_评分策略'},
}))

# XR
VERSIONS.append(('XR', os.path.join(SCRIPTS, 'release/XR'), {
    'real_up': {'mod': 'XR真实涨日_评分策略'},
    'fake_up': {'mod': 'XR虚涨日_评分策略'},
    'down': {'mod': 'XR跌日_评分策略'},
    'flat': {'mod': 'XR横盘_评分策略'},
}))

# ============ 跑所有版本 ============
results = []
for label, dirpath, mods in VERSIONS:
    print(f"\n跑 {label}...", flush=True)
    r = run_version(label, dirpath, mods)
    if r:
        results.append(r)
        w30, n30, r30, _ = r['30d']
        w50, n50, r50, _ = r['50d']
        w100, n100, r100, _ = r['100d']
        print(f"  30天: {r30}%({w30}/{n30})  50天: {r50}%({w50}/{n50})  100天: {r100}%({w100}/{n100})", flush=True)

# ============ 排名 ============
print(f"\n{'='*70}")
print(f"📊 全版本PK排名（按50天胜率排序）")
print(f"{'='*70}")
print(f"{'排名':<4} {'版本':<12} {'30天':<10} {'50天':<10} {'100天':<10}")
print(f"{'-'*50}")

# 按50天排序
results.sort(key=lambda x: -x['50d'][2])
for idx, r in enumerate(results):
    _, _, r30, _ = r['30d']
    _, _, r50, _ = r['50d']
    _, _, r100, _ = r['100d']
    medal = ['🥇','🥈','🥉'][idx] if idx < 3 else '  '
    print(f"{medal} {r['label']:<12} {r30:>6.1f}%  {r50:>6.1f}%  {r100:>6.1f}%")

print(f"\n⏱ 总耗时: {time.time()-T0:.0f}秒")
