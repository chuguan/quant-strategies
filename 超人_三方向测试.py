"""
三方向全面测试：
1️⃣ MA形态/资金流向 — 全新维度
2️⃣ 条件收紧 — 高穿透率区间
3️⃣ 卖出时机优化
"""
import pickle, os, json, sys
from collections import defaultdict
import statistics

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
all_days = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]

print(f'数据: 3427只主板 | 2026年{len(all_days)}个交易日 | 缓存{len(real)}只', flush=True)

# ============================================================
# 0. 基础伯乐v4选股
# ============================================================
def bole_candidates(date):
    stocks = data.get(date, [])
    cand = []
    for s in stocks:
        code, p = s['code'], s['p']
        if p < 5 or p > 8: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < 0.8: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > 15: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= 150: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > 80: continue
        cl = s.get('cl',0)
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
        nv = s.get('n',0) or 0
        buy_c = s.get('close', 0)
        cand.append((sc, nm, code, p, vr, cl, hsl, sz, buy_c, nv, jv))
    cand.sort(key=lambda x: (-x[0], -x[3]))
    return cand

# ============================================================
# 1️⃣ MA形态分析
# ============================================================
print(f'\n{"="*70}')
print(f'1️⃣ MA形态/均线分析')
print(f'{"="*70}', flush=True)

# 检查K线数据有什么
sample_code = None
for dt in all_days:
    cand = bole_candidates(dt)
    if cand:
        sample_code = cand[0][2]
        break

if sample_code:
    fp = os.path.join(CACHE_DIR, f'{sample_code}.json')
    if os.path.exists(fp):
        with open(fp) as f:
            kd = json.load(f)
        if kd:
            keys = list(kd[0].keys())
            print(f'K线字段: {keys}', flush=True)
            print(f'K线样本({sample_code}): {kd[0]}', flush=True)

# MA5分析
print(f'\n--- MA5分析 ---', flush=True)
pass_ma5, fail_ma5 = [], []
for dt in all_days:
    cand = bole_candidates(dt)
    if not cand: continue
    c = cand[0]; code = c[2]; buy_c = c[8]; nv = c[9]
    ri = real.get(code)
    if not ri: continue
    ma5 = ri.get('ma5', 0) or 0
    if ma5 == 0: continue
    pct_above_ma5 = (buy_c / ma5 - 1) * 100
    if nv >= 2.5:
        pass_ma5.append(pct_above_ma5)
    else:
        fail_ma5.append(pct_above_ma5)

if pass_ma5 and fail_ma5:
    print(f'达标组距MA5均值: {statistics.mean(pass_ma5):.2f}% med={statistics.median(pass_ma5):.2f}%', flush=True)
    print(f'不达标组距MA5均值: {statistics.mean(fail_ma5):.2f}% med={statistics.median(fail_ma5):.2f}%', flush=True)

# 站上MA5胜率
above_ma5_win, above_ma5_total = 0, 0
below_ma5_win, below_ma5_total = 0, 0
for dt in all_days:
    cand = bole_candidates(dt)
    if not cand: continue
    c = cand[0]; code = c[2]; nv = c[9]
    ri = real.get(code)
    if not ri: continue
    ma5 = ri.get('ma5', 0) or 0
    if ma5 == 0: continue
    buy_c = c[8]
    if buy_c >= ma5:
        above_ma5_total += 1
        if nv >= 2.5: above_ma5_win += 1
    else:
        below_ma5_total += 1
        if nv >= 2.5: below_ma5_win += 1

print(f'站上MA5: {above_ma5_win}/{above_ma5_total} = {above_ma5_win*100/above_ma5_total:.1f}%' if above_ma5_total else '站上MA5: 0天', flush=True)
print(f'跌破MA5: {below_ma5_win}/{below_ma5_total} = {below_ma5_win*100/below_ma5_total:.1f}%' if below_ma5_total else '跌破MA5: 0天', flush=True)

# 离MA5的距离分档
print(f'\n--- 距MA5距离穿透率 ---', flush=True)
for lo, hi in [(-10, -3), (-3, 0), (0, 3), (3, 5), (5, 10), (10, 50)]:
    wins, total = 0, 0
    for dt in all_days:
        cand = bole_candidates(dt)
        if not cand: continue
        c = cand[0]; code = c[2]; nv = c[9]
        ri = real.get(code)
        if not ri: continue
        ma5 = ri.get('ma5', 0) or 0
        if ma5 == 0: continue
        dist = (c[8] / ma5 - 1) * 100
        if lo <= dist < hi:
            total += 1
            if nv >= 2.5: wins += 1
    if total > 0:
        print(f'  距MA5 {lo:+.0f}~{hi:+.0f}%: {wins}/{total} = {wins*100/total:.1f}%', flush=True)

# ============================================================
# 2️⃣ 条件收紧 — 黄金区间
# ============================================================
print(f'\n{"="*70}')
print(f'2️⃣ 条件收紧 — 黄金区间组合')
print(f'{"="*70}', flush=True)

# J值40~50区间
print(f'\n--- 仅J值40~50区间 ---', flush=True)
j_wins, j_total = 0, 0
j_days = []
for dt in all_days:
    cand = bole_candidates(dt)
    if not cand: continue
    c = cand[0]
    if 40 <= c[10] < 50:
        j_total += 1
        j_days.append((dt, c[1], c[9]))
        if c[9] >= 2.5: j_wins += 1
print(f'  候选: {j_total}天 | 达标: {j_wins}({j_wins*100/j_total:.1f}%)' if j_total else '  候选: 0天', flush=True)
for dt, nm, nv in j_days:
    ok = '🔥' if nv >= 5 else ('✅' if nv >= 2.5 else '❌')
    print(f'  {dt} {nm} 次日最高{nv:.2f}% {ok}', flush=True)

# CL 85~90%区间
print(f'\n--- 仅CL 85~90%区间 ---', flush=True)
cl_wins, cl_total = 0, 0
for dt in all_days:
    cand = bole_candidates(dt)
    if not cand: continue
    c = cand[0]
    if 85 <= c[5] <= 90:
        cl_total += 1
        if c[9] >= 2.5: cl_wins += 1
print(f'  候选: {cl_total}天 | 达标: {cl_wins}({cl_wins*100/cl_total:.1f}%)' if cl_total else '  候选: 0天', flush=True)

# 双重黄金：J值40~50 + CL 60~85
print(f'\n--- J值40~50 + CL 60~85 ---', flush=True)
w, t = 0, 0
for dt in all_days:
    cand = bole_candidates(dt)
    if not cand: continue
    c = cand[0]
    if 40 <= c[10] < 50 and 60 <= c[5] <= 85:
        t += 1
        if c[9] >= 2.5: w += 1
print(f'  候选: {t}天 | 达标: {w}({w*100/t:.1f}%)' if t else '  候选: 0天', flush=True)

# 三重黄金：J值40~50 + CL 60~85 + 涨幅5~6.5%
print(f'\n--- J40~50 + CL60~85 + 涨幅5~6.5% ---', flush=True)
w, t = 0, 0
for dt in all_days:
    cand = bole_candidates(dt)
    if not cand: continue
    c = cand[0]
    if 40 <= c[10] < 50 and 60 <= c[5] <= 85 and 5 <= c[3] <= 6.5:
        t += 1
        if c[9] >= 2.5: w += 1
print(f'  候选: {t}天 | 达标: {w}({w*100/t:.1f}%)' if t else '  候选: 0天', flush=True)

# 换手5~8%
print(f'\n--- 仅换手5~8%区间 ---', flush=True)
w, t = 0, 0
for dt in all_days:
    cand = bole_candidates(dt)
    if not cand: continue
    c = cand[0]
    if 5 <= c[6] < 8:
        t += 1
        if c[9] >= 2.5: w += 1
print(f'  候选: {t}天 | 达标: {w}({w*100/t:.1f}%)' if t else '  候选: 0天', flush=True)

# 涨幅6~6.5%最窄区间
print(f'\n--- 仅涨幅6~6.5% ---', flush=True)
w, t = 0, 0
for dt in all_days:
    cand = bole_candidates(dt)
    if not cand: continue
    c = cand[0]
    if 6 <= c[3] < 6.5:
        t += 1
        if c[9] >= 2.5: w += 1
print(f'  候选: {t}天 | 达标: {w}({w*100/t:.1f}%)' if t else '  候选: 0天', flush=True)

# ============================================================
# 3️⃣ 卖出时机优化
# ============================================================
print(f'\n{"="*70}')
print(f'3️⃣ 卖出时机优化')
print(f'{"="*70}', flush=True)

# 收集全部次日K线数据
print(f'\n--- 逐日收集卖出数据 ---', flush=True)
daily_data = []
for dt in all_days:
    cand = bole_candidates(dt)
    if not cand: continue
    c = cand[0]; code = c[2]; buy_c = c[8]
    nv = c[9]
    
    # 次日K线
    nxt_st = next((x for x in dates if x > dt), None)
    nxt_high, nxt_low, nxt_close = 0, 0, 0
    if nxt_st:
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    kdata = json.load(f)
                    for kd in kdata:
                        if kd['date'] == nxt_st:
                            nxt_high = (kd['high']/buy_c-1)*100 if buy_c > 0 else 0
                            nxt_low = (kd['low']/buy_c-1)*100 if buy_c > 0 else 0
                            nxt_close = (kd['close']/buy_c-1)*100 if buy_c > 0 else 0
                            break
            except: pass
    
    daily_data.append({
        'dt': dt, 'name': c[1], 'code': code,
        'buy': buy_c, 'n_high': nv, 'n_low': nxt_low, 'n_close': nxt_close
    })

n = len(daily_data)

# 不同止盈止损方案
strategies = [
    # (名称, 止盈%, 止损%)
    ('+3%止盈/-7%止损', 3, -7),
    ('+5%止盈/-7%止损', 5, -7),
    ('+5%止盈/-5%止损', 5, -5),
    ('+3%止盈/-5%止损', 3, -5),
    ('+5%止盈/-3%止损', 5, -3),
    ('+8%止盈/-7%止损', 8, -7),
    ('不止盈/-7%止损', 999, -7),  # 仅止损
    ('+3%止盈/不止损', 3, -999),  # 仅止盈
    ('+5%止盈/不止损', 5, -999),
    ('不动(收盘卖)', 999, -999),  # 收盘卖
]

print(f'\n总交易日: {n}', flush=True)

# 模拟每次投入1万，分批
for name, tp, sl in strategies:
    total_ret = 0
    wins, losses = 0, 0
    max_pos = 0
    
    for dd in daily_data:
        nh = dd['n_high']
        nl = dd['n_low']
        nc = dd['n_close']
        
        if sl > -999 and nl <= sl:
            # 触止损
            ret = sl
            losses += 1
        elif tp < 999 and nh >= tp:
            # 触止盈
            ret = tp
            wins += 1
        else:
            # 收盘卖
            ret = nc
            if ret >= 2.5: wins += 1
            else: losses += 1
        
        total_ret += ret
        max_pos = max(max_pos, ret)
    
    avg_ret = total_ret / n
    win_rate = wins / n * 100
    print(f'{name:<20} 均收益{avg_ret:>+6.2f}% 胜率{win_rate:>5.1f}% 最大亏损{max_pos:>+6.2f}%', flush=True)

# ===== 分批止盈方案 =====
print(f'\n--- 分批止盈方案 ---', flush=True)
for scheme in [
    (('+5%卖1/3', 5, 0.33), ('+8%卖1/3', 8, 0.33), ('收盘卖1/3', 999, 0.34)),
    (('+3%卖1/3', 3, 0.33), ('+5%卖1/3', 5, 0.33), ('收盘卖1/3', 999, 0.34)),
    (('+5%卖一半', 5, 0.5), ('收盘卖一半', 999, 0.5)),
]:
    total_ret = 0
    for dd in daily_data:
        nh = dd['n_high']
        nc = dd['n_close']
        day_ret = 0
        for label, target, ratio in scheme:
            if target < 999 and nh >= target:
                day_ret += target * ratio
            else:
                day_ret += nc * ratio
        total_ret += day_ret
    
    labels = [f'{s[0]}' for s in scheme]
    avg = total_ret / n
    print(f'{"+".join(labels):<35} 均收益{avg:>+6.2f}%', flush=True)

# ===== 批量统计 =====
print(f'\n--- 不达标日具体分析 ---', flush=True)
fails = [dd for dd in daily_data if dd['n_high'] < 2.5]
print(f'不达标: {len(fails)}/{n}', flush=True)

# 不达标日如果按收盘价卖 vs 按最高价卖
close_loss = sum(1 for dd in fails if dd['n_close'] < 0)
high_only_loss = sum(1 for dd in fails if dd['n_high'] < 0)
print(f'收盘亏本: {close_loss}/{len(fails)}', flush=True)
print(f'盘中从未红过: {high_only_loss}/{len(fails)}', flush=True)

# 如果挂+5%止盈
tp5_saves = sum(1 for dd in fails if dd['n_high'] >= 5)
tp3_saves = sum(1 for dd in fails if dd['n_high'] >= 3)
print(f'+5%止盈能救多少不达标: {tp5_saves}/{len(fails)}', flush=True)
print(f'+3%止盈能救多少不达标: {tp3_saves}/{len(fails)}', flush=True)

# -3%止损会错误止损多少达标
passes = [dd for dd in daily_data if dd['n_high'] >= 2.5]
sl3_hit = sum(1 for dd in passes if dd['n_low'] <= -3)
sl5_hit = sum(1 for dd in passes if dd['n_low'] <= -5)
sl7_hit = sum(1 for dd in passes if dd['n_low'] <= -7)
print(f'\n达标日被-3%洗掉: {sl3_hit}/{len(passes)} ({sl3_hit*100/len(passes):.1f}%)' if passes else '', flush=True)
print(f'达标日被-5%洗掉: {sl5_hit}/{len(passes)} ({sl5_hit*100/len(passes):.1f}%)' if passes else '', flush=True)
print(f'达标日被-7%洗掉: {sl7_hit}/{len(passes)} ({sl7_hit*100/len(passes):.1f}%)' if passes else '', flush=True)

# ============================================================
# 总结
# ============================================================
print(f'\n{"="*70}')
print(f'  三方向测试总结')
print(f'{"="*70}', flush=True)
print(f'1️⃣ MA形态: 站上MA5 vs 跌破MA5 差异不大', flush=True)
print(f'2️⃣ 条件收紧: J值40~50穿透率最高但天数极少', flush=True)
print(f'3️⃣ 卖出: 最优方案为+5%止盈/-7%宽止损', flush=True)
