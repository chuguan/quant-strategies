"""
V46新增特色分析 — 凸显 尾盘形态加分 的实际效果
"""
import os, pickle, importlib.util
from collections import defaultdict

SCRIPTS_DIR = r'C:\Users\12546\AppData\Local\hermes\scripts'
RELEASE_DIR = os.path.join(SCRIPTS_DIR, 'release')

def load_strats(version_dir, tag):
    strats = {}
    for f in sorted(os.listdir(os.path.join(version_dir, '评分策略'))):
        if f.endswith('.py') and '评分策略' in f:
            mname = f'{tag}_{f.replace(".py","")}'
            spec = importlib.util.spec_from_file_location(mname, os.path.join(version_dir, '评分策略', f))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            strats[getattr(mod, 'MARKET', 'unknown')] = mod
    return strats

def classify_market(p, vr):
    if p < -0.5: return 'down'
    if p > 1.5: return 'real_up'
    if p > 0.5 and vr < 0.85: return 'fake_up'
    return 'flat'

# Load data
v42_strats = load_strats(os.path.join(RELEASE_DIR, 'V42'), 'V42')
v46_strats = load_strats(os.path.join(RELEASE_DIR, 'V46'), 'V46')

with open(os.path.join(RELEASE_DIR, 'V42', 'big_cache_full.pkl'), 'rb') as f:
    cache = pickle.load(f)
with open(os.path.join(RELEASE_DIR, 'V42', 'features_30d.pkl'), 'rb') as f:
    features = pickle.load(f)

names_map = cache.get('names', {})
data = cache['data']
dates = sorted(data.keys())

# Build d1 lookup: (code, date) -> d1%
d1_lookup = {}
for (code, date), fdata in features.items():
    d1_lookup[(str(code), date)] = fdata.get('d1', 0)

def get_d1(code, date):
    return d1_lookup.get((code, date), 0)

print("=" * 80)
print("  V42 vs V46 分析 — 聚焦V46新增的「尾盘形态加分」")
print("=" * 80)
print(f"\n▶ 数据: {len(dates)}个交易日, 每日约{len(data[dates[0]])}只股票")
print(f"▶ d1数据: {len(d1_lookup)}条")

# ============================================
# 单日回测
# ============================================
def score_day(strats, d):
    """给某日所有票打分，返回排序后的(代码, 分数, stock_dict)"""
    cands = []
    for s in data.get(d, []):
        if not isinstance(s, dict): continue
        code = str(s.get('code', ''))
        p = s.get('p', 0) or 0
        vr = s.get('vol_ratio', 0) or 1.0
        s['p'] = p
        s['vr'] = vr
        
        market = classify_market(p, vr)
        strat = strats.get(market)
        if not strat: continue
        
        if code in names_map:
            s['nm'] = names_map[code]
        
        score = strat.score(s)
        if score <= 0: continue
        cands.append((code, score, s, market))
    
    cands.sort(key=lambda x: x[1], reverse=True)
    return cands

# 逐日跑
v42_results = {}
v46_results = {}
for d in dates:
    v42r = score_day(v42_strats, d)
    v46r = score_day(v46_strats, d)
    if v42r and v46r:
        v42_results[d] = v42r
        v46_results[d] = v46r

# ============================================
# 核心分析
# ============================================
days_analyzed = list(set(v42_results.keys()) & set(v46_results.keys()))
days_analyzed.sort()

# 多周期统计
def calc_wins(strats, results, days, name):
    w, t = 0, 0
    for d in days:
        r = results.get(d, [])
        if not r: continue
        code = r[0][0]
        d1 = get_d1(code, d)
        if d1 >= 2.5: w += 1
        t += 1
    return w, t

print(f"\n▶ 有效分析天数: {len(days_analyzed)}")

# 全量
v42w_all, v42t_all = calc_wins(v42_strats, v42_results, days_analyzed, 'V42')
v46w_all, v46t_all = calc_wins(v46_strats, v46_results, days_analyzed, 'V46')

# 多周期
from datetime import datetime, timedelta
today = datetime.strptime('2026-06-01', '%Y-%m-%d')
for label, nd in [('近30天', 30), ('近60天', 60), ('全部', 999)]:
    cutoff = today - timedelta(days=nd*2) if nd != 999 else datetime.min
    d_filtered = [d for d in days_analyzed if datetime.strptime(d, '%Y-%m-%d') >= cutoff]
    if len(d_filtered) < 5: continue
    v42w, v42t = calc_wins(v42_strats, v42_results, d_filtered, 'V42')
    v46w, v46t = calc_wins(v46_strats, v46_results, d_filtered, 'V46')
    diff = v46w*100/v46t - v42w*100/v42t if v42t else 0
    print(f"  {label:>8}: V42={v42w}/{v42t}={v42w*100/v42t:.1f}%  V46={v46w}/{v46t}={v46w*100/v46t:.1f}%  差异={diff:+.1f}%")

# ============================================
# 1. 尾盘形态加分触发统计
# ============================================
print("\n" + "=" * 70)
print("  🆕 1. V46新增「尾盘形态加分(_tail_end_score)」触发频率")
print("=" * 70)

tail_stats = {'pos_hit': 0, 'pos_total': 0, 'neg_hit': 0, 'neg_total': 0, 
              'zero_total': 0, 'total': 0}
tail_mk = defaultdict(lambda: {'pos': 0, 'pos_hit': 0, 'neg': 0, 'neg_hit': 0})
weak_examples = []
strong_examples = []

for d in days_analyzed:
    r = v46_results.get(d, [])
    for j, (code, sc, s, mk) in enumerate(r[:3]):
        rank = j + 1
        st = v46_strats.get(mk)
        tail_val = st._tail_end_score(s) if hasattr(st, '_tail_end_score') else 0
        
        d1 = get_d1(code, d)
        hit = d1 >= 2.5
        
        tail_stats['total'] += 1
        if tail_val > 0:
            tail_stats['pos_total'] += 1
            if hit: tail_stats['pos_hit'] += 1
            tail_mk[mk]['pos'] += 1
            if hit: tail_mk[mk]['pos_hit'] += 1
        elif tail_val < 0:
            tail_stats['neg_total'] += 1
            if hit: tail_stats['neg_hit'] += 1
            tail_mk[mk]['neg'] += 1
            if hit: tail_mk[mk]['neg_hit'] += 1
        else:
            tail_stats['zero_total'] += 1
        
        # Collect examples
        n = names_map.get(code, '')
        if tail_val < 0 and len(weak_examples) < 10:
            weak_examples.append((d, code, n, s.get('p', 0), s.get('cl', 50), d1, hit, mk))
        if tail_val > 5 and rank == 1 and len(strong_examples) < 10:
            strong_examples.append((d, code, n, s.get('p', 0), s.get('cl', 50), d1, hit, mk, tail_val))

t = tail_stats['total']
print(f"\n  TOP3票中尾盘评分分布 (总计{t}次):")
print(f"    📈 加分(+) : {tail_stats['pos_total']:>4}次 ({tail_stats['pos_total']*100/t:.1f}%)")
print(f"    📉 罚分(-) : {tail_stats['neg_total']:>4}次 ({tail_stats['neg_total']*100/t:.1f}%)")
print(f"    ➖ 无影响(0): {tail_stats['zero_total']:>4}次 ({tail_stats['zero_total']*100/t:.1f}%)")

print(f"\n  ▶ 加分券达标率: {tail_stats['pos_hit']}/{tail_stats['pos_total']} = {tail_stats['pos_hit']*100/tail_stats['pos_total']:.1f}%" if tail_stats['pos_total'] > 0 else "")
print(f"  ▶ 罚分券达标率: {tail_stats['neg_hit']}/{tail_stats['neg_total']} = {tail_stats['neg_hit']*100/tail_stats['neg_total']:.1f}%" if tail_stats['neg_total'] > 0 else "")

# 按行情
mk_cn = {'down':'跌日','flat':'横盘','real_up':'真实涨日','fake_up':'虚涨日'}
print(f"\n  按行情:")
for mk in ['down', 'flat', 'real_up', 'fake_up']:
    tm = tail_mk.get(mk)
    if tm and (tm['pos'] > 0 or tm['neg'] > 0):
        pr = f"达标率{tm['pos_hit']*100/tm['pos']:.0f}%" if tm['pos'] > 0 else "—"
        nr = f"达标率{tm['neg_hit']*100/tm['neg']:.0f}%" if tm['neg'] > 0 else "—"
        print(f"    {mk_cn.get(mk,mk):>8}: 加分{tm['pos']:>3}次({pr}) | 罚分{tm['neg']:>3}次({nr})")

# ============================================
# 2. 排名变更
# ============================================
print("\n\n" + "=" * 70)
print("  🆕 2. 尾盘评分导致的#1选择变化")
print("=" * 70)

changes = []
for d in days_analyzed:
    v42r = v42_results.get(d, [])
    v46r = v46_results.get(d, [])
    if not v42r or not v46r: continue
    
    c42, sc42, s42, mk42 = v42r[0]
    c46, sc46, s46, mk46 = v46r[0]
    
    if c42 != c46:
        st46 = v46_strats.get(mk46)
        st42 = v46_strats.get(mk42)
        tail46 = st46._tail_end_score(s46) if hasattr(st46, '_tail_end_score') else 0
        tail42 = st42._tail_end_score(s42) if hasattr(st42, '_tail_end_score') else 0
        
        d1_42 = get_d1(c42, d)
        d1_46 = get_d1(c46, d)
        
        changes.append((d, c42, names_map.get(c42,''), s42.get('p',0), s42.get('cl',50), d1_42,
                        c46, names_map.get(c46,''), s46.get('p',0), s46.get('cl',50), d1_46,
                        tail42, tail46, mk46))

print(f"\n  总天数: {len(days_analyzed)}")
print(f"  #1选择不同的天数: {len(changes)} ({len(changes)*100/len(days_analyzed):.1f}%)")

# 其中尾盘评分起关键作用
key_positive = [c for c in changes if c[12] >= 3]
print(f"  尾盘评分关键影响(加分≥3分): {len(key_positive)}天")

# 尾盘评分做的选择是否更好
v46_better = sum(1 for c in changes if c[11] >= 2.5 and c[5] < 2.5)  # V46达标但V42不达标
v46_worse = sum(1 for c in changes if c[11] < 2.5 and c[5] >= 2.5)   # V42达标但V46不达标
v46_same_good = sum(1 for c in changes if c[11] >= 2.5 and c[5] >= 2.5)  # 都好
v46_same_bad = sum(1 for c in changes if c[11] < 2.5 and c[5] < 2.5)  # 都不好

print(f"  V46替换效果:")
print(f"    ✅ V46救了好票(变达标): {v46_better}次")
print(f"    ❌ V46换到坏票(变不达标): {v46_worse}次")
print(f"    ➖ 两者都好: {v46_same_good}次 / 两者都不好: {v46_same_bad}次")

# 展示关键案例
key_cases = [c for c in changes if c[12] >= 3 and (c[11] >= 2.5 or c[5] >= 2.5)]
key_cases.sort(key=lambda x: -abs(x[12]))

print(f"\n  关键案例(尾盘评分≥3分且有达标差异):")
if key_cases:
    print(f"  {'日期':<12} {'V42#1':<22} {'→ V46#1':<22} {'尾分':>4} {'V42D+1':>7} {'V46D+1':>7}")
    print(f"  {'-'*12} {'-'*22} {'-'*22} {'-'*4} {'-'*7} {'-'*7}")
    for c in key_cases[:15]:
        d, c42, n42, p42, cl42, d1_42, c46, n46, p46, cl46, d1_46, t42, t46, mk = c
        mark = "✅" if d1_46 >= 2.5 else "❌"
        v46n = f"{n46}({c46})"
        v42n = f"{n42}({c42})"
        print(f"  {d:<12} {v42n:<22} {v46n:<22} {t46:>+4.0f} {d1_42:>+6.1f}% {d1_46:>+6.1f}% {mark}")

# ============================================
# 3. 弱反弹罚分案例
# ============================================
print("\n\n" + "=" * 70)
print("  🆕 3. 弱反弹罚分(-20) — 剔除模式②坏票")
print("=" * 70)

print(f"\n  触发了-20罚分的TOP3票: {tail_stats['neg_total']}次")
if weak_examples:
    print(f"  {'日期':<12} {'名称':<12} {'p':>6} {'CL':>5} {'D+1':>6} {'结果':>6}")
    print(f"  {'-'*12} {'-'*12} {'-'*6} {'-'*5} {'-'*6} {'-'*6}")
    for ex in weak_examples[:10]:
        d, code, n, p, cl, d1, hit, mk = ex
        r = "✅剔" if not hit else "❌误伤"
        print(f"  {d:<12} {n:<12} {p:>+5.1f}% {cl:>4.0f} {d1:>+5.1f}% {r}")

# ============================================
# 4. V46 vs V42 差异总结
# ============================================
print("\n\n" + "=" * 70)
print("  📋 V46新增特色总结")
print("=" * 70)

net_effect = v46_better - v46_worse
print(f"""
  🔸 V46 = V42 + 尾盘形态加分(_tail_end_score)

  ┌────────────────────────────────────────────────────────────┬───────┐
  │ 尾盘形态加分规则                                          │ 分值  │
  ├────────────────────────────────────────────────────────────┼───────┤
  │ ① 弱反弹罚分: -1<p<1 且 CL<40 → 剔除弱反弹               │ -20   │
  │ ② 强收加分:   p>2 且 CL>70 → 强势收盘                    │  +8   │
  │ ③ 抢筹加分:   满足② + vr>2 + p>3 → 抢筹信号              │  +5   │
  │ ④ 资金进场加分: p>2 + CL>60 + WR<40 → 资金进场          │  +5   │
  └────────────────────────────────────────────────────────────┴───────┘

  🔸 触发频率: {tail_stats['pos_total']}次加分 + {tail_stats['neg_total']}次罚分
  🔸 排名变更: {len(changes)}/{len(days_analyzed)}天={len(changes)*100/len(days_analyzed):.1f}%的#1选择改变

  🔸 替换效果:
     ✅ V46换出更好的票: {v46_better}次
     ❌ V46换出更差的票: {v46_worse}次
     ➖ 净效果: {net_effect:+d}次
""")
