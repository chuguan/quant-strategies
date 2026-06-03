"""
分析V46尾盘形态预判与次日走势的相关性
"""
import os, pickle, importlib
from collections import defaultdict
import statistics

SCRIPTS_DIR = r'C:\Users\12546\AppData\Local\hermes\scripts'
RELEASE_DIR = os.path.join(SCRIPTS_DIR, 'release')

def load_strats(vdir):
    strats = {}
    for f in sorted(os.listdir(os.path.join(vdir, '评分策略'))):
        if f.endswith('.py') and '评分策略' in f:
            modname = f.replace('.py','')
            spec = importlib.util.spec_from_file_location(modname, os.path.join(vdir, '评分策略', f))
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            strats[getattr(m, 'MARKET', 'unk')] = m
    return strats

v46s = load_strats(os.path.join(RELEASE_DIR, 'V46'))

with open(os.path.join(RELEASE_DIR, 'V46', 'big_cache_full.pkl'), 'rb') as f:
    cache = pickle.load(f)
with open(os.path.join(RELEASE_DIR, 'V46', 'features_30d.pkl'), 'rb') as f:
    feats = pickle.load(f)

names = cache.get('names', {})
data = cache['data']
dates = sorted(data.keys())

d1_map = {}
for (code, dt), fv in feats.items():
    d1_map[(str(code), dt)] = fv.get('d1', 0)

def cls(p, vr):
    if p < -0.5: return 'down'
    if p > 1.5: return 'real_up'
    if p > 0.5 and vr < 0.85: return 'fake_up'
    return 'flat'

def get_tail_patterns(s):
    """返回触发了哪些尾盘形态"""
    p = s.get('p', 0) or 0
    cl = s.get('cl', 50) or 50
    vr = s.get('vr', 0) or 0
    wr = s.get('wrv', 50) or 50
    patterns = []
    if -1 < p < 1 and cl < 40:
        patterns.append('weak_bounce')
    if p > 2 and cl > 70:
        patterns.append('strong_close')
        if vr > 2 and p > 3:
            patterns.append('panic_buy')
    if p > 2 and cl > 60 and wr < 40:
        patterns.append('capital_inflow')
    return patterns

# 收集所有候选票（通过V46评分>0的）的尾盘形态和D+1
records = []  # (pattern_category, d1, d1_win, p, cl, vr, wr, market)

# 只分析有d1数据的日期（最近30天）
from datetime import datetime, timedelta
today = datetime.strptime('2026-06-01', '%Y-%m-%d')
cutoff = (today - timedelta(days=90)).strftime('%Y-%m-%d')

for d in dates:
    if d < cutoff: continue
    pool = data.get(d, [])
    if not isinstance(pool, list): continue
    
    d1_available = False
    for s in pool[:10]:
        code = str(s.get('code',''))
        d1 = d1_map.get((code, d), 0)
        if d1 != 0:
            d1_available = True
            break
    if not d1_available: continue
    
    for s in pool:
        if not isinstance(s, dict): continue
        code = str(s.get('code',''))
        p = s.get('p', 0) or 0
        vr = s.get('vol_ratio', 0) or 1.0
        s['p'] = p; s['vr'] = vr
        mk = cls(p, vr)
        st = v46s.get(mk)
        if not st: continue
        if code in names: s['nm'] = names[code]
        sc = st.score(s)
        if sc <= 0: continue
        
        d1 = d1_map.get((code, d), 0)
        if d1 == 0: continue  # 只统计有d1数据的
        
        pats = get_tail_patterns(s)
        pat_cat = '+'.join(sorted(pats)) if pats else 'none'
        records.append({
            'date': d, 'code': code, 'name': names.get(code,''),
            'p': p, 'cl': s.get('cl',50), 'vr': vr, 'wr': s.get('wrv',50),
            'd1': d1, 'win': d1 >= 2.5,
            'patterns': pats, 'pat_cat': pat_cat,
            'score': sc, 'market': mk
        })

print(f"有效样本: {len(records)}条")
print()

# ============================
# 1. 各尾盘形态的D+1达标率
# ============================
print("=" * 75)
print("  一、各尾盘形态的 D+1 达标率（≥2.5%）对比")
print("=" * 75)

# 定义要分析的类别组合
cats = {
    '无形态': lambda r: len(r['patterns']) == 0,
    '强收 alone': lambda r: r['patterns'] == ['strong_close'],
    '强收+资金进场': lambda r: sorted(r['patterns']) == ['capital_inflow', 'strong_close'],
    '强收+抢筹': lambda r: sorted(r['patterns']) == ['panic_buy', 'strong_close'],
    '强收+抢筹+资金': lambda r: sorted(r['patterns']) == ['capital_inflow', 'panic_buy', 'strong_close'],
    '弱反弹': lambda r: 'weak_bounce' in r['patterns'],
}

print(f"\n  {'形态类别':<20} {'样本数':>6} {'达标':>4} {'达标率':>8} {'均值D+1':>8} {'中位D+1':>8}")
print(f"  {'-'*54}")

baseline_win = sum(1 for r in records if r['win'])
baseline_total = len(records)

for name, fn in cats.items():
    subset = [r for r in records if fn(r)]
    n = len(subset)
    if n < 3: continue
    w = sum(1 for r in subset if r['win'])
    wr = w * 100 / n
    avg_d1 = sum(r['d1'] for r in subset) / n
    med_d1 = sorted([r['d1'] for r in subset])[n//2]
    print(f"  {name:<20} {n:>6} {w:>4} {wr:>7.1f}% {avg_d1:>+7.2f}% {med_d1:>+7.2f}%")

# 基准：全部
print(f"  {'-'*54}")
print(f"  {'全部（基准）':<20} {baseline_total:>6} {baseline_win:>4} {baseline_win*100/baseline_total:>7.1f}% "
      f"{sum(r['d1'] for r in records)/baseline_total:>+7.2f}% "
      f"{sorted([r['d1'] for r in records])[baseline_total//2]:>+7.2f}%")

# 有形态 vs 无形态
has_pat = [r for r in records if len(r['patterns']) > 0]
no_pat = [r for r in records if len(r['patterns']) == 0]
if has_pat and no_pat:
    hw = sum(1 for r in has_pat if r['win']) * 100 / len(has_pat)
    nw = sum(1 for r in no_pat if r['win']) * 100 / len(no_pat)
    h_avg = sum(r['d1'] for r in has_pat) / len(has_pat)
    n_avg = sum(r['d1'] for r in no_pat) / len(no_pat)
    print(f"\n  有形态: {len(has_pat)}条 达标率{hw:.1f}% 均值D+1={h_avg:+.2f}%")
    print(f"  无形态: {len(no_pat)}条 达标率{nw:.1f}% 均值D+1={n_avg:+.2f}%")

# ============================
# 2. 各形态加分/减分的实际D+1表现
# ============================
print("\n\n" + "=" * 75)
print("  二、加分形态的 D+1 分布明细")
print("=" * 75)

for pat_name, pat_key in [('强收📈 (+8分)', 'strong_close'), 
                            ('抢筹🔥 (+5分)', 'panic_buy'),
                            ('资金进场💹 (+5分)', 'capital_inflow'),
                            ('弱反弹⚠️ (-20分)', 'weak_bounce')]:
    subset = [r for r in records if pat_key in r['patterns']]
    n = len(subset)
    if n < 3: continue
    w = sum(1 for r in subset if r['win'])
    # D+1分布
    d1_vals = sorted([r['d1'] for r in subset])
    p10 = d1_vals[int(n*0.1)]
    p25 = d1_vals[int(n*0.25)]
    p50 = d1_vals[n//2]
    p75 = d1_vals[int(n*0.75)]
    p90 = d1_vals[int(n*0.9)]
    avg_d1 = sum(d1_vals) / n
    neg_rt = sum(1 for v in d1_vals if v < 0) * 100 / n
    print(f"\n  {pat_name}")
    print(f"    样本量: {n} | 达标率: {w/n*100:.1f}% ({w}/{n})")
    print(f"    D+1分布: P10={p10:+.1f}% P25={p25:+.1f}% P50={p50:+.1f}% P75={p75:+.1f}% P90={p90:+.1f}%")
    print(f"    均值={avg_d1:+.2f}% | 负值率={neg_rt:.1f}%")

# ============================
# 3. 尾盘形态 vs 没形态的#1票对比
# ============================
print("\n\n" + "=" * 75)
print("  三、每天#1冠军的尾盘形态 vs D+1")
print("=" * 75)

champ_records = []
processed_dates = set()

for d in dates:
    if d < cutoff: continue
    pool = data.get(d, [])
    if not isinstance(pool, list): continue
    if d in processed_dates: continue
    processed_dates.add(d)
    
    cands = []
    for s in pool:
        if not isinstance(s, dict): continue
        code = str(s.get('code',''))
        p = s.get('p', 0) or 0
        vr = s.get('vol_ratio', 0) or 1.0
        s['p'] = p; s['vr'] = vr
        mk = cls(p, vr)
        st = v46s.get(mk)
        if not st: continue
        if code in names: s['nm'] = names[code]
        sc = st.score(s)
        if sc <= 0: continue
        d1 = d1_map.get((code, d), 0)
        if d1 == 0: continue
        cands.append((code, sc, s, d1, mk))
    
    if len(cands) < 3: continue
    cands.sort(key=lambda x: x[1], reverse=True)
    code, sc, s, d1, mk = cands[0]
    pats = get_tail_patterns(s)
    pat_cat = '+'.join(sorted(pats)) if pats else '无'
    champ_records.append((d, names.get(code,''), code, s.get('p',0), d1, d1>=2.5, pat_cat, mk))

print(f"\n  {'日期':<12} {'冠军':<14} {'当日%':>7} {'D+1':>7} {'结果':>4} {'尾盘形态':<25} {'行情':<8}")
print(f"  {'-'*77}")
for r in champ_records[-50:]:
    d, nm, cd, p, d1, win, pat, mk = r
    flag = '✅' if win else '❌'
    print(f"  {d:<12} {nm:<14} {p:>+6.1f}% {d1:>+6.1f}% {flag:>4} {pat:<25} {mk:<8}")

# ============================
# 4. 加分总分 vs D+1相关性
# ============================
print("\n\n" + "=" * 75)
print("  四、V46尾盘加分总分 vs D+1 相关性")
print("=" * 75)

# 计算每条记录的尾盘总加分
# 规则: weak_bounce=-20, strong_close=+8, panic_buy=+5, capital_inflow=+5
score_map = {'weak_bounce': -20, 'strong_close': 8, 'panic_buy': 5, 'capital_inflow': 5}

for r in records:
    r['tail_total'] = sum(score_map.get(p, 0) for p in r['patterns'])

# 按尾盘总分分组
buckets = defaultdict(list)
for r in records:
    tt = r['tail_total']
    if tt <= -20:
        bucket = '≤-20(弱反弹)'
    elif tt == 8:
        bucket = '+8(强收面)'
    elif tt == 13:
        bucket = '+13(强收+资金进场)'
    elif tt == 13:
        bucket = '+13(强收+抢筹)'
    elif tt == 18:
        bucket = '+18(强收+抢筹+资金)'
    elif tt == 0:
        bucket = '0(无形态)'
    else:
        bucket = f'{tt:+d}'
    buckets[bucket].append(r)

print(f"\n  {'尾盘总分':<20} {'样本':>6} {'达标率':>8} {'均值D+1':>8}")
print(f"  {'-'*42}")
for bucket in sorted(buckets.keys(), key=lambda x: (
    0 if x.startswith('≤') else 
    1 if x == '0' else 
    2 if x.startswith('+') else 3,
    x)):
    subset = buckets[bucket]
    n = len(subset)
    w = sum(1 for r in subset if r['win'])
    avg_d1 = sum(r['d1'] for r in subset) / n
    print(f"  {bucket:<20} {n:>6} {w*100/n:>7.1f}% {avg_d1:>+7.2f}%")

# ============================
# 5. 多元分析：相同p/cl下，有尾盘形态vs无形态
# ============================
print("\n\n" + "=" * 75)
print("  五、控制涨幅(2<p<5)后，尾盘形态的边际效果")
print("=" * 75)

mid_range = [r for r in records if 2 <= r['p'] <= 5]
mid_has = [r for r in mid_range if len(r['patterns']) > 0]
mid_none = [r for r in mid_range if len(r['patterns']) == 0]

if mid_has and mid_none:
    hw = sum(1 for r in mid_has if r['win']) * 100 / len(mid_has)
    nw = sum(1 for r in mid_none if r['win']) * 100 / len(mid_none)
    h_avg = sum(r['d1'] for r in mid_has) / len(mid_has)
    n_avg = sum(r['d1'] for r in mid_none) / len(mid_none)
    print(f"\n  涨幅2~5%的票中:")
    print(f"  有形态: {len(mid_has)}条 达标率{hw:.1f}% 均值D+1={h_avg:+.2f}%")
    print(f"  无形态: {len(mid_none)}条 达标率{nw:.1f}% 均值D+1={n_avg:+.2f}%")
    print(f"  信息增益: 达标率差={hw-nw:+.1f}% | D+1差={h_avg-n_avg:+.2f}%")

# ============================
# 总结
# ============================
print("\n\n" + "=" * 75)
print("  📋 总结")
print("=" * 75)
print(f"""
  分析维度:
  ├─ 各形态达标率（vs 基线）
  ├─ D+1分布明细（P10~P90）
  ├─ 每日冠军形态 vs D+1
  ├─ 加分总分 vs D+1 相关性
  └─ 控制p后形态的信息增益

  核心问题：尾盘形态预判的加分/扣分，和次日走势
  是否真的有对应关系？
""")
