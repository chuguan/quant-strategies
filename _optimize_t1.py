#!/usr/bin/env python3
"""跌日 T-1参数优化（从_optimize_down_v2.py移植，仅T-1因子）"""
import pickle, os, sys, json, time, random
from collections import defaultdict

SCRIPTS = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(SCRIPTS)

TARGET = 2.5

print("加载缓存...", flush=True)
with open('big_cache_full.pkl', 'rb') as f:
    cache = pickle.load(f)
data = cache['data']
names = cache['names']
real = cache.get('real', {})

def classify_market(records):
    ps = [r.get('p',0) for r in records if abs(r.get('p',0)) < 15]
    vrs = [r.get('vol_ratio',1) for r in records if r.get('vol_ratio',0) > 0]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

print("加载K线...", flush=True)
kline_cache = {}
for fn in os.listdir(CACHE_DIR):
    if not fn.endswith('.json'): continue
    code = fn.replace('.json','')
    try:
        with open(os.path.join(CACHE_DIR, fn), 'rb') as f:
            kline_cache[code] = json.loads(f.read().decode('utf-8'))
    except: pass
print(f"{len(kline_cache)}只", flush=True)

def get_prev_features(code, date_str):
    recs = None
    code_clean = code[-6:] if len(code) > 6 else code
    for pfx in ['', 'sh', 'sz']:
        key = f'{pfx}{code_clean}'
        if key in kline_cache: recs = kline_cache[key]; break
    if not recs: return None
    idx = next((i for i,k in enumerate(recs) if k.get('date')==date_str), None)
    if idx is None or idx == 0: return None
    k = recs[idx-1]
    prev_close = recs[idx-2]['close'] if idx >= 2 else k['open']
    prev_pct = round((k['close']/prev_close-1)*100, 2)
    prev_pos = round((k['close']-k['low'])/(k['high']-k['low']+0.001)*100, 1)
    prev_shadow = round((k['high']-max(k['close'],k['open']))/(k['high']-k['low']+0.001)*100, 1)
    prev_is_yang = 1 if k['close'] > k['open'] else 0
    cons_down = 0
    for i in range(idx-1, 0, -1):
        pc = round((recs[i]['close']/recs[i-1]['close']-1)*100, 2)
        if pc < 0: cons_down += 1
        else: break
    return {'prev_pct':prev_pct,'prev_pos':prev_pos,'prev_shadow':prev_shadow,'prev_is_yang':prev_is_yang,'cons_down':cons_down}

def map_stock(r):
    hsl = real.get(r['code'], {}).get('hsl', 5.0)
    sz = real.get(r['code'], {}).get('shizhi', 100.0)
    nm = names.get(r['code'], r['code'][-6:])
    if 'ST' in nm or '*ST' in nm or '退' in nm: return None
    if not nm or nm == 'NO_NAME' or (len(nm) == 6 and nm.isdigit()): return None
    return {'code':r['code'],'nm':nm,'p':r.get('p',0),'cl':r.get('cl',50),
        'vr':r.get('vol_ratio',1.0),'hsl':hsl,'sz':sz,
        'dif':r.get('dif_val',0),'mg':r.get('mg',0),
        'a5':r.get('above_ma5',0),'wrv':r.get('wrv',50),
        'kv':r.get('k_val',50),'dv':r.get('d_val',50),
        'jv':r.get('j_val',50),'kdj_g':r.get('kdj_g',0),
        'pos_in_day':r.get('pos_in_day',50),'s':r.get('s',50),
        'buy_c':r.get('close',0),'next_high':r.get('n',None)}

def filter_level(candidates, level):
    result = []
    for s in candidates:
        if s is None: continue
        if s['p'] < level['p_min'] or s['p'] > level['p_max']: continue
        if s['p'] >= 8: continue
        if s['vr'] < level['vr_min'] or s['vr'] > level['vr_max']: continue
        if s['hsl'] < level['hs_min'] or s['hsl'] > level['hs_max']: continue
        if s['sz'] >= level['sz_max']: continue
        if s['cl'] < level['cl_min'] or s['cl'] > level['cl_max']: continue
        result.append(s)
    return result

levels = [
    {"name":"L0","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":1.5,"hs_min":5,"hs_max":20,"sz_max":150,"cl_min":40,"cl_max":90},
    {"name":"L1","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":1.5,"hs_min":5,"hs_max":20,"sz_max":150,"cl_min":40,"cl_max":90},
    {"name":"L2","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":2.0,"hs_min":3,"hs_max":25,"sz_max":200,"cl_min":30,"cl_max":95},
    {"name":"L3","p_min":0,"p_max":7,"vr_min":0.5,"vr_max":2.5,"hs_min":2,"hs_max":30,"sz_max":300,"cl_min":20,"cl_max":98},
    {"name":"L4","p_min":-10,"p_max":7,"vr_min":0.1,"vr_max":10,"hs_min":0.1,"hs_max":100,"sz_max":10000,"cl_min":0,"cl_max":100},
]
last = levels[-1]
levels_ext = levels + [{"name":"L5","p_min":last["p_min"]-3,"p_max":last["p_max"],
    "vr_min":max(0.1,last["vr_min"]-0.2),"vr_max":last["vr_max"]+2,
    "hs_min":max(0.1,last["hs_min"]-1),"hs_max":last["hs_max"]+15,
    "sz_max":last["sz_max"]+200,"cl_min":max(0,last["cl_min"]-15),"cl_max":100}]

all_dates = sorted([d for d in data.keys() if '2025' <= d[:4] <= '2026'])
test_dates = [d for d in all_dates if d < '2026-05-29']

# 收集跌日数据
down_data = {}
for dt in test_dates:
    stks = data.get(dt, [])
    if len(stks) < 5: continue
    mkt = classify_market(stks)
    if mkt != 'down': continue
    cands = [map_stock(r) for r in stks]
    cands = [c for c in cands if c is not None]
    for s in cands:
        pf = get_prev_features(s['code'], dt)
        if pf: s.update(pf)
        else: s['prev_pct']=0; s['prev_pos']=50; s['prev_shadow']=20; s['prev_is_yang']=1; s['cons_down']=0
    down_data[dt] = cands
print(f"跌日: {len(down_data)}天", flush=True)

# 评分函数（完全匹配_optimize_down_v2.py的内联评分）
def score_stock(s, params):
    p = params
    sc = 0.0
    sc += s['p'] * p.get('p_w', 0.5)
    sc += s['cl'] * p.get('cl_w', 0.4)
    dif = s['dif']; mg = s['mg']
    ms = 0
    if mg and dif > 0.5: ms = 10
    elif mg and dif > 0.2: ms = 8
    elif mg: ms = 6
    elif dif > 0.5: ms = 4
    elif dif > 0: ms = 2
    sc += ms * p.get('macd_w', 3.0)
    if dif > 0.5: sc += p.get('dif_bonus', 5)
    if s['a5']: sc += p.get('ma5_b', 20)
    wrv = s['wrv']
    if wrv < p.get('wr_lo', 20): sc += p.get('wr_b', 20)
    jv = s['jv']; kv = s['kv']; dv = s['dv']
    if jv > kv > dv: sc += p.get('j_b', 5)
    if jv < p.get('j_low_thresh', 15): sc += p.get('j_low_b', 5)
    if s['p'] > p.get('p_high_thresh', 6): sc += p.get('p_high_pen', -20)
    vr = s['vr']
    if 0.8 <= vr <= 1.5: sc += p.get('vr_b', 0)
    if 50 <= s['cl'] <= 80: sc += p.get('zone_b', 0)
    if s['cl'] < 50: sc += p.get('cl_low_b', 0)
    if s['cl'] > 90: sc += p.get('cl_high_pen', 0)
    if s['p'] < 1: sc += p.get('p_deep_b', 0)
    if s['hsl'] >= 3: sc += p.get('hs_b', 0)
    if wrv > 75: sc += p.get('wr_bonus', 0)
    # T-1因子
    pp = s.get('prev_pct', 0)
    pp_pos = s.get('prev_pos', 50)
    pp_shadow = s.get('prev_shadow', 20)
    pp_yang = s.get('prev_is_yang', 1)
    if pp < -1: sc += p.get('prev_down_pen', -5)
    if pp < -3: sc += p.get('prev_deep_pen', -10)
    if pp_pos < 35: sc += p.get('prev_low_pos_pen', -8)
    if pp_pos < 20: sc += p.get('prev_very_low_pen', -5)
    if pp_shadow > 30: sc += p.get('prev_long_shadow_pen', -5)
    if pp_shadow > 50: sc += p.get('prev_vlong_shadow_pen', -5)
    if not pp_yang: sc += p.get('prev_yin_pen', -3)
    if pp < -1 and pp_pos < 35: sc += p.get('prev_down_low_combo', -5)
    if s.get('s', 50) > 30: sc += p.get('curr_shadow_pen', -3)
    if s.get('s', 50) > 50: sc += p.get('curr_vshadow_pen', -3)
    return round(sc, 1)

def run_test(params):
    wins = 0; total = 0
    for dt, cands in down_data.items():
        scored = []
        for lv in levels_ext:
            pool = filter_level(cands, lv)
            if len(pool) > 8:
                for s in pool:
                    s['score'] = score_stock(s, params)
                    scored.append(s)
                break
        if not scored: continue
        scored.sort(key=lambda x: (-x['score'], -x['p']))
        champ = scored[0]
        nh = champ['next_high']
        if nh is not None and nh >= TARGET: wins += 1
        total += 1
    return wins, total

# 基准
baseline = {'p_w':0.5,'cl_w':0.4,'macd_w':3.0,'dif_bonus':5,'ma5_b':20,'wr_lo':20,'wr_b':20,'j_b':5,'j_low_thresh':15,'j_low_b':5,'p_high_thresh':6,'p_high_pen':-20,'vr_b':0,'vr_bonus':2,'zone_b':0,'cl_low_b':0,'cl_high_pen':0,'p_deep_b':0,'hs_b':0,'hs_bonus':0,'wr_bonus':0,'prev_down_pen':0,'prev_deep_pen':0,'prev_low_pos_pen':0,'prev_very_low_pen':0,'prev_long_shadow_pen':0,'prev_vlong_shadow_pen':0,'prev_yin_pen':0,'prev_down_low_combo':0,'curr_shadow_pen':0,'curr_vshadow_pen':0}
bw, bt = run_test(baseline)
print(f"基准: {bw}/{bt} = {bw/bt*100:.1f}%", flush=True)

# T-1网格搜索
prev_grid = {'prev_down_pen': [0,-3,-5,-8,-10,-15], 'prev_deep_pen': [0,-5,-8,-10,-15,-20], 'prev_low_pos_pen': [0,-3,-5,-8,-10,-15], 'prev_very_low_pen': [0,-3,-5,-8], 'prev_long_shadow_pen': [0,-3,-5,-8,-10], 'prev_vlong_shadow_pen': [0,-3,-5,-8], 'prev_yin_pen': [0,-2,-3,-5,-8], 'prev_down_low_combo': [0,-3,-5,-8,-10]}

best_rate = bw/bt if bt > 0 else 0
best_params = baseline.copy()
best_wins, best_total = bw, bt

random.seed(42)
SAMPLE = min(5000, 6*6*6*4*5*4*5*5)
print(f"搜索 {SAMPLE} 组...", flush=True)
for i in range(SAMPLE - 1):
    p = {}
    for k, vals in prev_grid.items():
        p[k] = random.choice(vals)
    p.update({k:v for k,v in baseline.items() if k not in prev_grid})
    wins, total = run_test(p)
    rate = wins/total if total > 0 else 0
    if rate > best_rate:
        best_rate = rate
        best_params.update(p)
        best_wins, best_total = wins, total
        print(f"  #{i+1}: {wins}/{total}={rate*100:.1f}% T1:", {k:v for k,v in sorted(p.items()) if k in prev_grid and v!=0}, flush=True)

print(f"\n🏆 跌日最优: {best_wins}/{best_total} = {best_rate*100:.1f}%", flush=True)
print(f"提升: {best_rate*100 - bw/bt*100:+.1f}%", flush=True)
print(f"\n参数:", flush=True)
for k, v in sorted(best_params.items()):
    if v != 0:
        print(f"  '{k}': {v}", flush=True)
print(f"\nCSV:", flush=True)
print(','.join(f"{k}={v}" for k,v in sorted(best_params.items()) if v!=0))
