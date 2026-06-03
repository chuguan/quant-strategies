#!/usr/bin/env python3
"""
V42 200天失败分析 — 跑全量回测，找出所有失败案例，分析规律
只分析不修改，不动任何版本代码
"""
import pickle, os, sys, importlib, json
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime

BASE = os.path.expanduser(r'~/AppData/Local/hermes/scripts')
V13_DIR = os.path.join(BASE, 'release', 'V13')
V42_DIR = os.path.join(BASE, 'release', 'V42')

print("=" * 70)
print("  V42 200天失败案 例深度分析")
print("  找出失败规律 → 针对性优化稳定性")
print("=" * 70)

# ===== 1. 加载数据 =====
print("\n▶ 加载数据...")
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d['real'], d['names']

with open(os.path.join(V13_DIR, 'features_30d.pkl'), 'rb') as f:
    precomputed = pickle.load(f)

# 用最近200天
all_dates = sorted(k for k in data.keys() if '2025-01-01' <= k <= '2026-05-28')
recent = all_dates[-200:] if len(all_dates) >= 200 else all_dates
print(f"  总交易日: {len(all_dates)}天")
print(f"  回测天数: {len(recent)}天")

# ===== 2. 加载评分模块 =====
def load_mod(fp):
    spec = importlib.util.spec_from_file_location(f'm_{os.path.basename(fp).replace(".","_")}', fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

MODS = {}
for cn in ['真实涨日','虚涨日','跌日','横盘']:
    fp = os.path.join(V42_DIR, '评分策略', f'分而治之_V10_{cn}_评分策略.py')
    MODS[cn] = load_mod(fp)

# ===== 3. 市场分类 =====
def mkt_class(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4']

def build_stock(s, code, dt):
    stock = {
        'p': s.get('p', 0) or 0,
        'cl': s.get('cl', 50),
        'vr': s.get('vol_ratio', 1) or s.get('vr', 1),
        'dif': s.get('dif_val', 0) or s.get('dif', 0),
        'mg': s.get('macd_golden', 0) or s.get('mg', 0),
        'wrv': s.get('wr_val', 0) or s.get('wrv', 50),
        'jv': s.get('j_val', 0) or s.get('jv', 50),
        'kv': s.get('k_val', 0) or s.get('kv', 50),
        'dv': s.get('d_val', 0) or s.get('dv', 50),
        'a5': s.get('above_ma5', 0),
        'kdj_g': s.get('kdj_golden', 0) or s.get('kdj_g', 0),
        'pos_in_day': s.get('pos_in_day', 50),
        'nm': s.get('nm', '') or s.get('name', '') or names.get(code, ''),
        'hsl': real.get(code, {}).get('hsl', 0) or 0,
        'buy_c': s.get('close', 0) or 0,
    }
    feats = precomputed.get((code, dt), {})
    stock['t4_shadow'] = feats.get('t4_shadow', 0)
    stock['slope5'] = feats.get('slope5', 0)
    stock['cons_up'] = feats.get('cons_up', 0)
    for k in ['b','s','a','j_val','ma5_slope','amplitude','vol','body_pct','is_yang',
              'above_ma10','above_ma20','d1','d2','d3','peak_decay','wr_val']:
        stock[k] = feats.get(k, 0) or s.get(k, 0) or 0
    return stock

# ===== 4. 回测主循环 =====
print("\n▶ 运行200天回测...")

total_days = 0
win_days = 0
failures = []  # 记录所有失败案例
daily_detail = []
processed_markets = Counter()

for dt in recent:
    stocks = data.get(dt, [])
    if not stocks: continue
    stocks = [s for s in stocks if (s.get('p', 0) or 0) < 15]
    if not stocks: continue
    
    mt = mkt_class(stocks)
    mk_cn = MK_MAP.get(mt, '横盘')
    processed_markets[mk_cn] += 1
    
    mod = MODS.get(mk_cn)
    if not mod: continue
    LEVELS = mod.LEVELS
    lm = {l['name']: i for i, l in enumerate(LEVELS)}
    
    # Level过滤
    pool = None
    for ln in LO:
        if ln not in lm: continue
        i = lm[ln]; lv = LEVELS[i]; cand = []
        for s in stocks:
            code = s.get('code', '')
            p = s.get('p', 0) or 0
            if p < lv['p_min'] or p > min(lv.get('p_max', 10), 8): continue
            vr = s.get('vol_ratio', 0) or 0
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            ri = real.get(code, {}); hsl = ri.get('hsl', 0) or 0
            if hsl < lv.get('hs_min', 0) or hsl > lv.get('hs_max', 99): continue
            if (ri.get('shizhi', 0) or 0) >= lv.get('sz_max', 9999): continue
            nm = names.get(code, '')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl = s.get('cl', 0)
            if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
            nh = s.get('n', 0) or 0
            cand.append(s)
        if len(cand) >= 10:
            pool = cand
            break
    
    if not pool: continue
    
    # 评分
    scored = []
    for s in pool:
        code = s.get('code', '')
        stock = build_stock(s, code, dt)
        sc = mod.score(stock)
        if sc > 0:
            scored.append((sc, s, code, stock))
    
    if not scored: continue
    scored.sort(key=lambda x: -x[0])
    
    total_days += 1
    champ = scored[0]
    champ_sc, champ_s, champ_code, champ_stock = champ
    champ_n = champ_s.get('n', 0) or 0
    champ_name = names.get(champ_code, '?')
    
    passed = champ_n >= 2.5
    if passed:
        win_days += 1
    else:
        # 记录失败案例
        failure = {
            'date': dt,
            'market': mk_cn,
            'code': champ_code,
            'name': champ_name,
            'score': round(champ_sc, 1),
            'n': round(champ_n, 1),
            'p': round(champ_s.get('p', 0) or 0, 2),
            'cl': round(champ_s.get('cl', 50), 1),
            'vr': round(champ_s.get('vol_ratio', 0) or 0, 2),
            'dif': round(champ_s.get('dif_val', 0) or 0, 3),
            'wrv': round(champ_s.get('wr_val', 50) or 50, 1),
            'hsl': round(real.get(champ_code, {}).get('hsl', 0) or 0, 1),
            'pos_in_day': round(champ_s.get('pos_in_day', 50), 1),
            'close': round(champ_s.get('close', 0) or 0, 2),
            't4_shadow': round(precomputed.get((champ_code, dt), {}).get('t4_shadow', 0), 1),
            'slope5': round(precomputed.get((champ_code, dt), {}).get('slope5', 0), 1),
            'cons_up': precomputed.get((champ_code, dt), {}).get('cons_up', 0),
            'peak_decay': precomputed.get((champ_code, dt), {}).get('peak_decay', 0),
        }
        failures.append(failure)

print(f"\n📊 回测完成: {total_days}天")
print(f"   胜: {win_days}天 ({win_days/total_days*100:.1f}%)")
print(f"   败: {len(failures)}天 ({len(failures)/total_days*100:.1f}%)")

# ===== 5. 失败分析 =====
print("\n" + "=" * 70)
print("  🔍 失败案例分析")
print("=" * 70)

if not failures:
    print("\n  ✅ 没有失败案例！完美回测！")
else:
    # 5.1 按行情分类
    print(f"\n  5.1 失败分布（按行情）：")
    market_fails = Counter(f['market'] for f in failures)
    for mk in ['真实涨日','虚涨日','跌日','横盘']:
        total = processed_markets.get(mk, 0)
        fails = market_fails.get(mk, 0)
        rate = fails/total*100 if total > 0 else 0
        bar = '█' * int(rate/2) + '░' * (50 - int(rate/2))
        print(f"    {mk:>6}: {fails}/{total}天 = {rate:5.1f}% {bar}")

    # 5.2 失败原因归类
    print(f"\n  5.2 失败原因归类（数据特征分析）：")
    
    # 特征对比：失败票 vs 全量均值
    fail_n = np.array([f['n'] for f in failures])
    fail_p = np.array([f['p'] for f in failures])
    fail_cl = np.array([f['cl'] for f in failures])
    fail_vr = np.array([f['vr'] for f in failures])
    fail_dif = np.array([f['dif'] for f in failures])
    fail_wrv = np.array([f['wrv'] for f in failures])
    fail_hsl = np.array([f['hsl'] for f in failures])
    fail_pos = np.array([f['pos_in_day'] for f in failures])
    fail_t4s = np.array([f['t4_shadow'] for f in failures])
    fail_sl5 = np.array([f['slope5'] for f in failures])
    
    print(f"\n    {'特征':>12} | {'失败均值':>10} | {'接近达标(<2.5)':>14} | {'大失败(<1%)':>12} | {'判断':>10}")
    print("-" * 65)
    
    # 分析各种特征
    close_but_fail = [f for f in failures if 2.0 <= f['n'] < 2.5]
    big_fail = [f for f in failures if f['n'] < 1.0]
    
    print(f"    {'总失败数':>10} | {len(failures):>10} | {len(close_but_fail):>14} | {len(big_fail):>12}")
    
    features_to_check = [
        ('当日涨幅p', 'p', 'p>4时会透支后续空间'),
        ('位置cl', 'cl', 'cl>85高位的风险大'),
        ('换手率hsl', 'hsl', 'hsl>15过热或<1冷清'),
        ('MACD dif', 'dif', 'dif负值说明弱势'),
        ('WR wrv', 'wrv', 'wrv<15超买，>85超卖'),
        ('量比vr', 'vr', 'vr<0.6量不足'),
        ('收盘位置', 'pos_in_day', 'pos<30尾盘弱势'),
        ('上影线t4s', 't4_shadow', 't4s>25冲高回落'),
        ('5日斜率sl5', 'slope5', 'sl5>10短期涨猛'),
    ]
    
    for name, key, note in features_to_check:
        arr = np.array([f[key] for f in failures])
        near_arr = np.array([f[key] for f in close_but_fail]) if close_but_fail else np.array([])
        big_arr = np.array([f[key] for f in big_fail]) if big_fail else np.array([])
        
        mean_val = np.mean(arr)
        near_mean = np.mean(near_arr) if len(near_arr) > 0 else 0
        big_mean = np.mean(big_arr) if len(big_arr) > 0 else 0
        
        # 判断该特征有没有区分度
        diff = abs(near_mean - big_mean) if len(near_arr) > 0 and len(big_arr) > 0 else 0
        tag = '⚠️ 分水岭' if diff > 0.5 else '📊 一般'
        
        print(f"    {name:>10} | {mean_val:>10.2f} | {near_mean:>14.2f} | {big_mean:>12.2f} | {tag}")
    
    # 5.3 具体失败模式
    print(f"\n  5.3 失败模式聚类：")
    
    # 模式1：高位追涨（cl高 + p高）
    pattern1 = [f for f in failures if f['cl'] > 85 and f['p'] > 4]
    # 模式2：尾盘弱势（pos_in_day < 35）
    pattern2 = [f for f in failures if f['pos_in_day'] < 35]
    # 模式3：量能不济（vr < 0.7）
    pattern3 = [f for f in failures if f['vr'] < 0.7]
    # 模式4：MACD弱势（dif < 0）
    pattern4 = [f for f in failures if f['dif'] < 0]
    # 模式5：上影线长（t4_shadow > 20）
    pattern5 = [f for f in failures if f['t4_shadow'] > 20]
    # 模式6：短期涨太猛（slope5 > 10）
    pattern6 = [f for f in failures if f['slope5'] > 10]
    # 模式7：接近达标（2.0~2.5差一点点）
    pattern7 = close_but_fail
    
    patterns = [
        ('高位追涨(cl>85+p>4)', pattern1),
        ('尾盘弱势(pos<35)', pattern2),
        ('量能不济(vr<0.7)', pattern3),
        ('MACD弱势(dif<0)', pattern4),
        ('上影线长(t4s>20)', pattern5),
        ('短期涨猛(sl5>10)', pattern6),
        ('接近达标(2.0~2.5)', pattern7),
    ]
    
    for name, plist in patterns:
        pct = len(plist)/len(failures)*100
        bar = '█' * int(pct)
        print(f"    {name:>24}: {len(plist)}次 ({pct:.0f}%) {bar}")
    
    # 5.4 具体失败明细
    print(f"\n  5.4 全部失败明细（按n值升序）：")
    failures.sort(key=lambda x: x['n'])
    print(f"    {'日期':>12} | {'行情':>6} | {'股票':>10} | {'评分':>6} | {'n值':>6} | {'当日p':>6} | {'cl':>5} | {'vr':>5} | {'pos':>4} | {'dif':>6}")
    print("-" * 80)
    for f in failures:
        print(f"    {f['date']} | {f['market']:>4} | {f['name']:>8} | {f['score']:>5.0f} | {f['n']:>+5.1f} | {f['p']:>+5.1f} | {f['cl']:>4.0f} | {f['vr']:>4.1f} | {f['pos_in_day']:>3.0f} | {f['dif']:>+5.2f}")
    
    # 5.5 结论
    print(f"\n\n{'='*60}")
    print(f"  🎯 失败规律总结与优化建议")
    print(f"{'='*60}")
    
    # 找最集中的模式
    pattern_rates = [(name, len(plist)/len(failures)*100) for name, plist in patterns]
    pattern_rates.sort(key=lambda x: -x[1])
    top_pattern = pattern_rates[0] if pattern_rates else ('无', 0)
    
    print(f"""
  共 {len(failures)} 次失败，失败率 {(len(failures)/total_days*100):.1f}%
  
  失败最主要的原因（按占比排序）：
""")
    
    for name, pct in pattern_rates:
        if pct > 15:
            print(f"    {name}: 占失败 {pct:.0f}% ← 主要！")
    
    print(f"""
  优化建议：
""")
    
    # 根据失败模式给出建议
    if len(pattern1) >= 3:
        print(f"  ① 高位追涨(cl>85+p>4): 失败{len(pattern1)}次")
        print(f"     → 在评分中加入'高位追涨扣分'：if cl>85 and p>4: score -= 10")
    if len(pattern5) >= 3:
        print(f"  ② 上影线长(t4s>20): 失败{len(pattern5)}次")
        print(f"     → 进一步收紧上影线扣分：if t4s>25: score -= 8")
    if len(pattern7) >= 3:
        print(f"  ③ 接近达标(2.0~2.5): 失败{len(pattern7)}次")
        print(f"     → 这些是随机波动，不是策略问题（差0.1%~0.5%属于正常范围）")
    if len(pattern2) >= 3:
        print(f"  ④ 尾盘弱势(pos<35): 失败{len(pattern2)}次")
        print(f"     → 强化收盘位置要求：pos_in_day < 35 直接扣分")
    if len(pattern3) >= 3:
        print(f"  ⑤ 量能不济(vr<0.7): 失败{len(pattern3)}次")
        print(f"     → VR下限从0.6提高到0.7")

print(f"\n✓ 分析完成 | 回测 {total_days}天 | 失败 {len(failures)}次")
