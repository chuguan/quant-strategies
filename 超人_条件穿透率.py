"""
分析：基本硬过滤条件下，哪些条件区间达2.5%概率最高（去掉评分）
还要算出票率（多少天能选出票）
"""
import pickle, os, json, statistics
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
all_days = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]

print(f'2026年 {len(all_days)}天 全量分析', flush=True)

# ===== 基础过滤条件 =====
def basic_filter(s):
    """基础硬过滤（不加评分）"""
    code, p = s['code'], s['p']
    if p < 5 or p > 8: return False
    if (s.get('vol_ratio',0) or 0) < 0.8: return False
    ri = real.get(code)
    if not ri: return False
    hsl = (ri.get('hsl',0) or 0)
    if hsl < 5 or hsl > 15: return False
    sz = (ri.get('shizhi',0) or 0)
    if sz >= 150: return False
    nm = names.get(code,'')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return False
    jv = s.get('j_val',0) or 0
    if jv > 80: return False
    return True

def candidate_stats(s):
    code = s['code']
    nv = s.get('n',0) or 0
    return {
        'p': s['p'], 'vr': s.get('vol_ratio',0) or 0, 'cl': s.get('cl',0),
        'hsl': (real.get(code,{}) or {}).get('hsl',0) or 0,
        'sz': (real.get(code,{}) or {}).get('shizhi',0) or 0,
        'j': s.get('j_val',0) or 0, 'nv': nv,
        'code': code, 'name': names.get(code,'')
    }

# ===== 1. 基础过滤出票率 =====
print(f'\n{"="*70}')
print(f'1️⃣ 基础硬过滤出票率（不加评分）')
print(f'{"="*70}', flush=True)

total_days = 0
days_with_candidates = 0
total_candidates = 0
all_candidates = []

for dt in all_days:
    stocks = data.get(dt, [])
    cand = [basic_filter(s) for s in stocks]
    filtered = [s for s in stocks if basic_filter(s)]
    if filtered:
        days_with_candidates += 1
        total_candidates += len(filtered)
        for s in filtered:
            all_candidates.append((dt, candidate_stats(s)))
    total_days += 1

print(f'基础过滤: {days_with_candidates}/{total_days}天有候选 ({days_with_candidates*100/total_days:.1f}%)', flush=True)
print(f'总候选数量: {total_candidates}只, 日均{total_candidates/max(days_with_candidates,1):.1f}只', flush=True)

# 全局达2.5%率
w25 = sum(1 for _, c in all_candidates if c['nv'] >= 2.5)
w5 = sum(1 for _, c in all_candidates if c['nv'] >= 5)
print(f'全局候选达2.5%: {w25}/{len(all_candidates)} = {w25*100/len(all_candidates):.1f}%', flush=True)
print(f'全局候选达5%: {w5}/{len(all_candidates)} = {w5*100/len(all_candidates):.1f}%', flush=True)

# ===== 2. 单条件区间穿透率 =====
print(f'\n{"="*70}')
print(f'2️⃣ 各条件区间穿透率（达2.5%概率 + 出票率）')
print(f'{"="*70}', flush=True)

features = [
    ('当日涨幅%', 'p', [(5,5.5),(5.5,6.0),(6.0,6.5),(6.5,7.0),(7.0,8.0)]),
    ('收盘位CL%', 'cl', [(0,60),(60,65),(65,70),(70,75),(75,80),(80,85),(85,90),(90,100)]),
    ('量比', 'vr', [(0.8,1.0),(1.0,1.2),(1.2,1.5),(1.5,2.0),(2.0,3.0),(3.0,10)]),
    ('换手率%', 'hsl', [(5,6),(6,8),(8,10),(10,12),(12,15)]),
    ('市值(亿)', 'sz', [(0,20),(20,30),(30,50),(50,80),(80,120),(120,150)]),
    ('J值', 'j', [(0,20),(20,30),(30,40),(40,50),(50,60),(60,70),(70,80)]),
]

for feat_name, key, bins in features:
    print(f'\n{feat_name}:', flush=True)
    print(f'  {"区间":<14} {"候选数":<8} {"天/年":<8} {"达2.5%":<8} {"达标率":<8} {"均次日%":<8} {"出票率":<8}', flush=True)
    print(f'  {"-":<60}', flush=True)
    
    for lo, hi in bins:
        days_seen = set()
        wins, total = 0, 0
        
        for dt, c in all_candidates:
            val = c.get(key, c[key])
            if lo <= val < hi:
                total += 1
                days_seen.add(dt)
                if c['nv'] >= 2.5: wins += 1
        
        if total == 0: continue
        rate = wins*100/total
        avg = statistics.mean([c['nv'] for _, c in all_candidates if lo <= c.get(key, c[key]) < hi])
        chupiao = len(days_seen)*100/total_days
        bar = '█' * int(rate/5)
        print(f'  {lo:<6.1f}~{hi:<6.1f}  {total:<8} {len(days_seen):<8} {wins:<8} {rate:<8.1f}% {avg:<8.2f}% {chupiao:<8.1f}% {bar}', flush=True)

# ===== 3. 冠军（每天选第1只）概率 =====
print(f'\n{"="*70}')
print(f'3️⃣ 冠军（每天选第1只）各区间达标率')
print(f'{"="*70}', flush=True)
print(f'说明：每天基础过滤后按涨幅降序取第1只，看各区间特征下的达标率', flush=True)

# 每天只取涨幅最高的第1只
champs = []
for dt in all_days:
    stocks = data.get(dt, [])
    filtered = [s for s in stocks if basic_filter(s)]
    if not filtered: continue
    # 按涨幅降序
    filtered.sort(key=lambda s: -s['p'])
    s = filtered[0]
    champs.append((dt, candidate_stats(s)))

print(f'冠军总天数: {len(champs)}', flush=True)
champ_w25 = sum(1 for _, c in champs if c['nv'] >= 2.5)
print(f'冠军达2.5%: {champ_w25}/{len(champs)} = {champ_w25*100/len(champs):.1f}%', flush=True)

# 冠军各区间
for feat_name, key, bins in features:
    print(f'\n{feat_name} (冠军):', flush=True)
    print(f'  {"区间":<14} {"天数":<6} {"达2.5%":<8} {"达标率":<8} {"均次日%":<8}', flush=True)
    for lo, hi in bins:
        in_bin = [(dt, c) for dt, c in champs if lo <= c[key] < hi]
        if not in_bin: continue
        wins = sum(1 for _, c in in_bin if c['nv'] >= 2.5)
        avg = statistics.mean([c['nv'] for _, c in in_bin])
        rate = wins*100/len(in_bin)
        bar = '█' * int(rate/4)
        print(f'  {lo:<6.1f}~{hi:<6.1f}  {len(in_bin):<6} {wins:<8} {rate:<8.1f}% {avg:<8.2f}% {bar}', flush=True)

# ===== 4. 关键：如何提升冠军胜率 =====
print(f'\n{"="*70}')
print(f'4️⃣ 冠军不达标原因深度分析')
print(f'{"="*70}', flush=True)

champ_pass = [(dt, c) for dt, c in champs if c['nv'] >= 2.5]
champ_fail = [(dt, c) for dt, c in champs if c['nv'] < 2.5]

print(f'达标冠军: {len(champ_pass)} | 不达标冠军: {len(champ_fail)}', flush=True)

# 不达标冠军中，有多少是"盘中到过2.5%但收盘回落" vs "全程没到2.5%"
hard_fail = []
close_fail = []
for dt, c in champ_fail:
    # 读K线看收盘
    nxt_st = next((x for x in dates if x > dt), None)
    nxt_close = 0
    if nxt_st:
        fp = os.path.join(CACHE_DIR, f'{c["code"]}.json')
        if os.path.exists(fp):
            with open(fp) as f:
                kd = json.load(f)
            for d in kd:
                if d['date'] == nxt_st:
                    nxt_close = (d['close']/c['nv'] if False else 0)  # wrong formula, skip
                    break
    
    if c['nv'] < 2.5:
        hard_fail.append((dt, c))

# Actually let me simplify
print(f'\n不达标冠军({len(champ_fail)}天)特征：', flush=True)
for feat_name, key in [('涨幅%', 'p'), ('CL%', 'cl'), ('量比', 'vr'), ('换手%', 'hsl'), ('市值', 'sz'), ('J值', 'j')]:
    p_vals = [c[key] for _, c in champ_pass]
    f_vals = [c[key] for _, c in champ_fail]
    if not p_vals or not f_vals: continue
    import math
    p_avg, f_avg = statistics.mean(p_vals), statistics.mean(f_vals)
    p_std, f_std = statistics.stdev(p_vals), statistics.stdev(f_vals)
    sep = abs(p_avg-f_avg)/max(math.sqrt(p_std**2+f_std**2), 0.001)
    sig = '🔥' if sep >= 0.3 else ('📊' if sep >= 0.15 else '')
    print(f'  {sig} {feat_name}: 达标avg={p_avg:.2f} 不达标avg={f_avg:.2f} 分离度={sep:.2f}σ', flush=True)

# ===== 5. 最优条件组合（用连胜率换出票率） =====
print(f'\n{"="*70}')
print(f'5️⃣ 最优条件：胜率 × 出票率 综合评分')
print(f'{"="*70}', flush=True)
print(f'综合分 = 达标率% × 出票率% / 100 → 越高越好', flush=True)
print(f'{"条件":<40} {"天数":<6} {"达标率":<8} {"出票率":<8} {"综合分":<8}', flush=True)
print(f'{"-":<75}', flush=True)

conditions = [
    ('无额外条件(仅基础过滤)', lambda c: True),
    ('涨幅5~6.5%', lambda c: 5 <= c['p'] < 6.5),
    ('涨幅5~6%', lambda c: 5 <= c['p'] < 6),
    ('涨幅6~6.5%', lambda c: 6 <= c['p'] < 6.5),
    ('CL 60~85', lambda c: 60 <= c['cl'] <= 85),
    ('CL 70~85', lambda c: 70 <= c['cl'] <= 85),
    ('CL 60~80', lambda c: 60 <= c['cl'] <= 80),
    ('量比0.8~1.5', lambda c: 0.8 <= c['vr'] <= 1.5),
    ('量比1.0~1.2', lambda c: 1.0 <= c['vr'] <= 1.2),
    ('换手5~8%', lambda c: 5 <= c['hsl'] < 8),
    ('换手5~10%', lambda c: 5 <= c['hsl'] < 10),
    ('J值40~50', lambda c: 40 <= c['j'] < 50),
    ('J值30~60', lambda c: 30 <= c['j'] < 60),
    ('市值30~120亿', lambda c: 30 <= c['sz'] <= 120),
    ('市值50~150亿', lambda c: 50 <= c['sz'] <= 150),
    ('涨幅5~6% + CL60~85', lambda c: 5 <= c['p'] < 6 and 60 <= c['cl'] <= 85),
    ('涨幅5~6% + 量比0.8~1.5', lambda c: 5 <= c['p'] < 6 and 0.8 <= c['vr'] <= 1.5),
    ('涨幅5~6% + 换手5~8%', lambda c: 5 <= c['p'] < 6 and 5 <= c['hsl'] < 8),
    ('涨幅6~6.5% + CL60~85', lambda c: 6 <= c['p'] < 6.5 and 60 <= c['cl'] <= 85),
    ('涨幅6~6.5% + J值30~60', lambda c: 6 <= c['p'] < 6.5 and 30 <= c['j'] < 60),
    ('涨幅5~6.5% + CL60~85 + 量比0.8~1.5', lambda c: 5 <= c['p'] < 6.5 and 60 <= c['cl'] <= 85 and 0.8 <= c['vr'] <= 1.5),
    ('涨幅5~6% + CL60~85 + 换手5~10%', lambda c: 5 <= c['p'] < 6 and 60 <= c['cl'] <= 85 and 5 <= c['hsl'] < 10),
]

# 对冠军（每天涨幅最高第1只）做条件测试
for name, cond in conditions:
    in_cond = [(dt, c) for dt, c in champs if cond(c)]
    if not in_cond: continue
    wins = sum(1 for _, c in in_cond if c['nv'] >= 2.5)
    days_unique = len(set(dt for dt, _ in in_cond))
    rate = wins*100/len(in_cond)
    chupiao = days_unique*100/total_days
    composite = rate * chupiao / 100
    print(f'{name:<40} {len(in_cond):<6} {rate:<8.1f}% {chupiao:<8.1f}% {composite:<8.1f}', flush=True)

# ===== 最终结论 =====
print(f'\n{"="*70}')
print(f'  🚀 最终结论')
print(f'{"="*70}', flush=True)
print(f'1. 基础过滤下全局候选达2.5%: {w25*100/len(all_candidates):.1f}%', flush=True)
print(f'2. 冠军（涨幅最高第1只）达2.5%: {champ_w25*100/len(champs):.1f}%', flush=True)
print(f'3. 最佳单区间: 涨幅6~6.5% + CL60~85', flush=True)
print(f'4. 出票率与达标率不可兼得', flush=True)
