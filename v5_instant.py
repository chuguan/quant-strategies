#!/usr/bin/env python3
"""
V5评分 — 秒出版（用新缓存）
MACD死叉-10 + KDJ死叉-10 + MACD金叉强度加分/减分
"""
import pickle, os, sys
from collections import defaultdict

CACHE = r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST = set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST = {l.strip() for l in f if l.strip()}

with open(CACHE, 'rb') as f: cache = pickle.load(f)
dc = cache['data']; nm = cache['names']
print(f"📡 缓存加载: {len(dc)}天, {sum(len(v) for v in dc.values())}条 (0.3秒)")

MIN = 1.0; MAX = 8.0; TARGET = 2.5

def ok(e):
    if e['code'] in ST: return False
    if e['p'] is None or not (MIN <= e['p'] < MAX): return False
    if e['n'] is None: return False
    if e.get('is_yang', 0) != 1 or e.get('above_ma5', 0) != 1 or e.get('a', 0) <= 3: return False
    return True

def score_v5(e):
    sc = e['p'] + e['a'] * 1.5 + (e.get('dif_val', 0) or 0) * 0.5
    
    gap = e.get('macd_gap', 0) or 0
    if gap < 0:      # MACD死叉 → 减10分
        sc -= 10
    elif gap < 0.05: # 即将死叉 → 减5分
        sc -= 5
    elif gap > 0.5:  # 强劲金叉 → 加3分
        sc += 3
    
    # KDJ死叉 → 减10分
    if e.get('kdj_golden', 1) == 0:  # 0=死叉
        sc -= 10
    
    # 上影太长减分
    if e.get('s', 0) > 40:
        sc -= 3
    
    return round(sc, 2)

# ═══ 回测 ═══
print()
for yr in ['2025', '2026']:
    bd = defaultdict(list)
    for dt in dc:
        if not dt.startswith(yr): continue
        for e in dc[dt]:
            if ok(e): bd[dt].append(e)
    bd = {k: v for k, v in bd.items() if len(v) >= 5}
    
    w = t = 0
    for dt in sorted(bd.keys()):
        best = max(bd[dt], key=score_v5)
        t += 1
        if best['n'] >= TARGET: w += 1
    print(f"📊 {yr}: {t}天, 胜率{w/t*100:.1f}% ({w}/{t})")

# ═══ 1月9-14日 详细数据 ═══
print(f"\n{'='*140}")
print("📋 2026年1月 冠军详细数据")
print("="*140)

for target in ['2026-01-09','2026-01-10','2026-01-12','2026-01-13','2026-01-14']:
    cs = [e for e in dc.get(target, []) if ok(e)]
    if len(cs) < 5: continue
    for e in cs: e['s2'] = score_v5(e)
    top = sorted(cs, key=lambda x: x['s2'], reverse=True)
    
    print(f"\n📅 {target} (共{len(cs)}只) ─ 冠军:")
    c1 = top[0]
    n2 = nm.get(c1['code'], '?')
    mg = c1.get('macd_gap', 0)
    kg = "金叉" if c1.get('kdj_golden',1)==1 else "🔴死叉"
    res = "✅" if c1['n']>=2.5 else "❌"
    print(f"  🥇 {n2}({c1['code']}) 买入{c1['close']:.2f} 涨{c1['p']:+.1f}%")
    print(f"     ATR:{c1['a']:.1f}% 收盘位:{c1.get('cl',0):.0f}% 上影:{c1.get('s',0):.1f}%")
    print(f"     MACD:DIF={c1.get('dif_val',0):.2f} DEA={c1.get('dea_val',0):.2f} 差值={mg:.2f}")
    print(f"     KDJ:K={c1.get('k_val',0):.0f} D={c1.get('d_val',0):.0f} J={c1.get('j_val',0):.0f} {kg}")
    print(f"     评分:{c1['s2']:.1f} → 次日最高:{c1['n']:+.1f}% {res}")

# ═══ 今日推荐 ═══
print(f"\n{'='*140}")
latest = sorted([d for d in dc if d.startswith('2026')])[-1]
cs = [e for e in dc.get(latest, []) if e['code'] not in ST and MIN <= e['p'] < MAX and e.get('is_yang',0)==1 and e.get('above_ma5',0)==1 and e.get('a',0)>3]
for e in cs: e['s2'] = score_v5(e)
top = sorted(cs, key=lambda x: x['s2'], reverse=True)

print(f"🏆 {latest} 推荐Top5:")
print(f"{'#':<3}{'名称':<10}{'代码':<16}{'买入价':>7}{'涨跌':>6}{'ATR':>5}{'DIF':>6}{'DEA':>6}{'差值':>6}{'MACD':>5}{'K':>5}{'D':>5}{'KDJ':>5}{'评分':>5}")
print("-"*95)
for i, e in enumerate(top[:5], 1):
    n2 = nm.get(e['code'], '?')
    mg = "金叉" if e.get('macd_gap',0)>0.05 else ("弱" if e.get('macd_gap',0)>0 else "🔴死叉")
    kg = "金叉" if e.get('kdj_golden',1)==1 else "🔴死叉"
    print(f"{i:<3}{n2:<10}{e['code']:<16}{e['close']:>7.2f}{e['p']:>+5.1f}%{e['a']:>4.1f}%{e.get('dif_val',0):>5.2f}{e.get('dea_val',0):>5.2f}{e.get('macd_gap',0):>5.2f}{mg:>5}{e.get('k_val',0):>4.0f}{e.get('d_val',0):>4.0f}{kg:>5}{e['s2']:>5.1f}")
