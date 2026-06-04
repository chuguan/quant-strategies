#!/usr/bin/env python3
"""
1180/V50 100天回测因子差异分析 — 真正的问题根源分析方法
不要猜新因子，让数据告诉我：成功票和失败票，每个因子分布差异有多大
"""
import pickle, os, sys, importlib, math
from collections import defaultdict
from datetime import datetime, timedelta

DIR = os.path.dirname(os.path.abspath(__file__))
STRATEGY_DIR = os.path.join(DIR, '评分策略')
PKL = os.path.join(DIR, 'big_cache_full.pkl')

print('📊 加载 big_cache_full.pkl...', flush=True)
with open(PKL, 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d.get('real', {}), d.get('names', {})

FEAT_PKL = os.path.join(DIR, 'features_30d.pkl')
with open(FEAT_PKL, 'rb') as f:
    precomputed = pickle.load(f)
print(f'✅ {len(data)}天, 特征: {len(precomputed)}条', flush=True)

# ===== 加载评分策略 =====
def load_mod(name):
    fp = os.path.join(STRATEGY_DIR, f'分而治之_V10_{name}_评分策略.py')
    if not os.path.exists(fp):
        print(f'⚠️  找不到评分策略: {fp}')
        return None
    spec = importlib.util.spec_from_file_location('m', fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

STRATS = {}
STRAT_ORDER = ['真实涨日', '虚涨日', '跌日', '横盘']
for n in STRAT_ORDER:
    STRATS[n] = load_mod(n)
MK_MAP = {'real_up': '真实涨日', 'fake_up': '虚涨日', 'down': '跌日', 'flat': '横盘'}
LO = ['L0', 'L1', 'L2', 'L3', 'L4']


def mkt_class(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    ap = sum(ps) / len(ps)
    av = sum(vrs) / len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'


def is_momentum_exhausted(s, code, dt):
    feats = precomputed.get((code, dt), {})
    if not feats: return False
    sl5 = feats.get('slope5', 0)
    t4s = feats.get('t4_shadow', 0)
    cu = feats.get('cons_up', 0)
    pk = feats.get('peak_decay', 0)
    pv = s.get('p', 0) or 0
    if sl5 > 8 and t4s > 25: return True
    if sl5 > 10 and t4s > 18: return True
    if cu >= 5 and sl5 > 15: return True
    if pk > 5 and sl5 > 5 and pv < 6: return True
    if sl5 > 5 and t4s > 30: return True
    if cu >= 4 and sl5 > 10 and pv < 7: return True
    return False


def compute_7day_decay_penalty(code, dt, p_today):
    all_dates = sorted(data.keys())
    try:
        idx = all_dates.index(dt)
    except ValueError:
        return 0
    prev = all_dates[max(0, idx - 6):idx]
    gains = []
    for pd in prev:
        found = False
        for s in data[pd]:
            if s['code'] == code:
                gains.append(s.get('p', 0) or 0)
                found = True
                break
        if not found: gains.append(0)
    gains.append(p_today)
    n = len(gains)
    if n < 5: return 0
    d6, d5, d4, d3, d2, d1, p = gains[-7:] if n >= 7 else [0] * (7 - n) + gains
    p_is_max = p >= max(gains[:-1]) if len(gains) > 1 else True
    avg_7d = sum(gains) / n
    penalty = 0
    wrv = 50
    for s in data.get(dt, []):
        if s['code'] == code:
            wrv = s.get('wr_val', 50) or s.get('wrv', 50)
            break
    if wrv < 10 and p_is_max and avg_7d < 2.0 and p < 6: penalty -= 8
    if p_is_max and avg_7d < 0.8 and p < 8:
        if avg_7d < 0: penalty -= 15
        elif avg_7d < 0.3: penalty -= 12
        elif avg_7d < 0.7: penalty -= 8
        else: penalty -= 5
    if d1 < -1.5 and d2 < -1.0 and p > 3 and avg_7d < 1.0: penalty -= 8
    if max(d4, d3, d2) > 5 and d1 < 0 and d2 < 0: penalty -= 10
    if n >= 5 and d5 > d1 and d5 > d2 and p <= d5:
        rs = (d4 + d3 + d2 + d1) if n >= 6 else (d3 + d2 + d1)
        if rs <= 2: penalty -= 8
    if n >= 5:
        last5 = gains[-5:]
        if all(last5[i] >= last5[i + 1] for i in range(len(last5) - 1)): penalty -= 10
    return penalty


def v10_score(stock, code, dt, mk_cn):
    """V50评分标准"""
    mod = STRATS[mk_cn]
    s = {}
    s['p'] = stock.get('p', 0) or 0
    s['cl'] = stock.get('cl', 50)
    s['vr'] = stock.get('vol_ratio', 1) or stock.get('vr', 1)
    s['dif'] = stock.get('dif_val', 0) or stock.get('dif', 0)
    s['mg'] = stock.get('macd_golden', 0) or stock.get('mg', 0)
    s['wrv'] = stock.get('wr_val', 0) or stock.get('wrv', 50)
    s['jv'] = stock.get('j_val', 0) or stock.get('jv', 50)
    s['kv'] = stock.get('k_val', 0) or stock.get('kv', 50)
    s['dv'] = stock.get('d_val', 0) or stock.get('dv', 50)
    s['a5'] = stock.get('above_ma5', 0)
    s['kdj_g'] = stock.get('kdj_golden', 0) or stock.get('kdj_g', 0)
    s['pos_in_day'] = stock.get('pos_in_day', 50)
    s['nm'] = stock.get('nm', '') or names.get(stock['code'], '')
    ri = real.get(stock['code'], {})
    s['hsl'] = ri.get('hsl', 0) or 0
    feats = precomputed.get((code, dt), {})
    s['t4_shadow'] = feats.get('t4_shadow', 0)
    s['slope5'] = feats.get('slope5', 0)
    s['cons_up'] = feats.get('cons_up', 0)
    s['d1'] = feats.get('d1', 0)
    s['d2'] = feats.get('d2', 0)
    s['d3'] = feats.get('d3', 0)
    s['ma5_slope'] = feats.get('ma5_slope', 0)
    s['volume'] = stock.get('volume', 0) or 0
    s['close'] = stock.get('close', 0) or 0
    s['open'] = stock.get('open', 0) or 0
    s['high'] = stock.get('high', 0) or 0
    s['low'] = stock.get('low', 0) or 0
    sp = compute_7day_decay_penalty(code, dt, stock.get('p', 0) or 0)
    return round(mod.score(s) + sp, 1)


# ===== 100天回测，记录每只候选股的因子 =====
dates = sorted(k for k in data.keys())
recent = [d for d in dates if d >= '2026-02-01'][:100]
print(f'\n===== 1180因子差异分析 =====')
print(f'回测区间: {recent[0]}~{recent[-1]} ({len(recent)}天)')

# 收集所有候选股的因子数据
# champ_records: 冠军票 {factors...}, winner_records: 前3且成功的票
champ_records = []  # {'factors': {...}, 'success': bool, 'market': str, 'date': str, 'rank': 1}
all_records = []    # 所有候选池票

total_days = 0
win_days = 0

for dt in recent:
    ss = data.get(dt, [])
    ss = [s for s in ss if (s.get('p', 0) or 0) < 15]
    if not ss: continue

    mk = mkt_class(ss)
    mk_cn = MK_MAP.get(mk, '横盘')
    mod = STRATS.get(mk_cn)
    if not mod: continue

    LEVELS = getattr(mod, 'LEVELS', None)
    if not LEVELS: continue

    lm = {l['name']: i for i, l in enumerate(LEVELS)}
    pool = None
    for ln in LO:
        if ln not in lm: continue
        lv = LEVELS[lm[ln]]
        cand = []
        for s in ss:
            p = s.get('p', 0) or 0
            if p < lv['p_min'] or p > min(lv.get('p_max', 10), 8): continue
            vr = s.get('vol_ratio', 0) or 0
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            ri = real.get(s['code'], {})
            hsl = ri.get('hsl', 0) or 0
            if hsl < lv.get('hs_min', 0) or hsl > lv.get('hs_max', 99): continue
            nm = names.get(s['code'], '')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl = s.get('cl', 0)
            if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
            if is_momentum_exhausted(s, s['code'], dt): continue
            cand.append(s)
        if len(cand) >= 10:
            pool = cand
            break

    if not pool: continue

    # 打分
    scored = [(v10_score(s, s['code'], dt, mk_cn), s) for s in pool]
    scored.sort(key=lambda x: -x[0])

    total_days += 1
    champ = scored[0][1]
    champ_sc = scored[0][0]
    nh = champ.get('n', 0) or 0
    success = nh >= 2.5
    if success: win_days += 1

    # 提取因子特征
    def extract_factors(s, is_champ=False, rank=0):
        feats = precomputed.get((s['code'], dt), {})
        ri = real.get(s['code'], {})
        close = s.get('close', 0) or 0
        high = s.get('high', 0) or 0
        low = s.get('low', 0) or 0

        # 基础因子
        factors = {
            # === 现有评分核心因子 ===
            'p': s.get('p', 0) or 0,           # 当日涨幅
            'cl': s.get('cl', 50),              # CL位置
            'vr': s.get('vol_ratio', 1) or 1,   # 量比
            'wr': s.get('wr_val', 50) or 50,    # WR威廉
            'dif': s.get('dif_val', 0) or 0,     # DIF
            'hsl': ri.get('hsl', 0) or 0,       # 换手率
            'ma5_slope': feats.get('ma5_slope', 0),  # 5日均线斜率
            't4_shadow': feats.get('t4_shadow', 0),  # 4日影线
            'slope5': feats.get('slope5', 0),    # 5日斜率
            'cons_up': feats.get('cons_up', 0),  # 连涨天数
            'peak_decay': feats.get('peak_decay', 0),  # 峰值衰减

            # === 4个新尝试因子 ===
            'amp': s.get('amplitude', 0) or 0,         # 振幅%
            'body_to_amp': (s.get('body_pct', 0) or 0) / max((s.get('amplitude', 0) or 0), 0.01),  # 实体/振幅比
            'p_times_vr': (s.get('p', 0) or 0) * (s.get('vol_ratio', 1) or 1),  # 涨幅×量比
            'amp_to_p': (s.get('amplitude', 0) or 0) / max(abs(s.get('p', 0) or 0), 0.01),  # 振幅/涨幅比

            # === 扩展因子 ===
            'body_pct': s.get('body_pct', 0) or 0,     # 实体%
            'cl_vs_amp': (s.get('cl', 50) or 50) * max((s.get('amplitude', 0) or 0), 0),  # CL×振幅
            'is_yang': s.get('is_yang', 0) or 0,        # 阳线
            'vol': s.get('volume', 0) or 0,             # 成交量
            'close': close,
            'open': s.get('open', 0) or 0,
            'high': high,
            'low': low,

            # 前N日涨幅
            'd1': feats.get('d1', 0),
            'd2': feats.get('d2', 0),
            'd3': feats.get('d3', 0),

            # D+1结果
            'n': s.get('n', 0) or 0,
        }
        return factors

    # 记录冠军
    champ_factors = extract_factors(champ, True, 1)
    champ_records.append({
        'factors': champ_factors,
        'success': success,
        'market': mk_cn,
        'date': dt,
        'champ_score': champ_sc,
        'name': names.get(champ['code'], '?'),
        'code': champ['code'],
    })

    # 记录所有候选池票（全部！）
    for rank, (sc, s) in enumerate(scored):
        if rank >= 3:  # 只记前3
            break
        factors = extract_factors(s, rank == 0, rank + 1)
        all_records.append({
            'factors': factors,
            'success': s.get('n', 0) or 0 >= 2.5,
            'market': mk_cn,
            'date': dt,
            'score': sc,
            'rank': rank + 1,
            'name': names.get(s['code'], '?'),
            'code': s['code'],
        })

print(f'\n✅ 完成回测: {total_days}天, 冠军胜率: {win_days}/{total_days}={win_days*100/total_days:.1f}%')
print(f'   冠军样本: {len(champ_records)} ({sum(1 for r in champ_records if r["success"])}胜/{sum(1 for r in champ_records if not r["success"])}败)')
print(f'   前3样本: {len(all_records)}')

# ===== 因子差异分析 =====
# 对每个因子，计算成功组 vs 失败组的：均值、中位数、标准差、差异%
# 统计指标：均值差、中位数差、效果量(Cohen's d)
print('\n' + '=' * 100)
print('📊 冠军票因子差异分析（成功 vs 失败）')
print('=' * 100)

# 哪些因子要分析
FACTOR_NAMES = {
    'p': '当日涨幅%', 'cl': 'CL位置', 'vr': '量比', 'wr': 'WR威廉',
    'dif': 'DIF', 'hsl': '换手率%', 'ma5_slope': 'MA5斜率',
    't4_shadow': '4日影线', 'slope5': '5日斜率', 'cons_up': '连涨天数',
    'peak_decay': '峰值衰减', 'amp': '振幅%', 'body_pct': '实体%',
    'body_to_amp': '实体/振幅比', 'p_times_vr': '涨幅×量比',
    'amp_to_p': '振幅/涨幅比', 'cl_vs_amp': 'CL×振幅',
    'is_yang': '阳线', 'vol': '成交量', 'd1': '前1日涨幅',
    'd2': '前2日涨幅', 'd3': '前3日涨幅',
}

# 先从冠军票分析
winners = [r for r in champ_records if r['success']]
losers = [r for r in champ_records if not r['success']]

def calc_stats(values):
    """计算基本统计量"""
    n = len(values)
    if n == 0: return {'n': 0, 'mean': 0, 'median': 0, 'std': 0, 'pct5': 0, 'pct25': 0, 'pct75': 0, 'pct95': 0}
    sv = sorted(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(variance)
    return {
        'n': n, 'mean': mean, 'median': sv[n // 2],
        'std': std,
        'pct5': sv[int(n * 0.05)],
        'pct25': sv[int(n * 0.25)],
        'pct75': sv[int(n * 0.75)],
        'pct95': sv[int(n * 0.95)],
    }

def cohens_d(w, l):
    """Cohen's d 效果量"""
    if len(w) < 2 or len(l) < 2: return 0
    s1, s2 = sum(w) / len(w), sum(l) / len(l)
    v1 = sum((v - s1) ** 2 for v in w) / (len(w) - 1)
    v2 = sum((v - s2) ** 2 for v in l) / (len(l) - 1)
    sp = math.sqrt((v1 + v2) / 2)
    if sp < 0.0001: return 0
    return (s1 - s2) / sp

results = []
for fkey, fname in FACTOR_NAMES.items():
    w_vals = [r['factors'].get(fkey, 0) or 0 for r in winners]
    l_vals = [r['factors'].get(fkey, 0) or 0 for r in losers]
    if not w_vals or not l_vals: continue
    ws = calc_stats(w_vals)
    ls = calc_stats(l_vals)
    d = cohens_d(w_vals, l_vals)
    mean_diff = ws['mean'] - ls['mean']
    mean_diff_pct = mean_diff / max(abs(ls['mean']), 0.001) * 100 if abs(ls['mean']) > 0.001 else 0
    med_diff = ws['median'] - ls['median']
    results.append({
        'factor': fkey, 'name': fname,
        'win_mean': ws['mean'], 'lose_mean': ls['mean'],
        'win_med': ws['median'], 'lose_med': ls['median'],
        'diff_mean': mean_diff, 'diff_mean_pct': mean_diff_pct,
        'diff_med': med_diff,
        'win_pct25': ws['pct25'], 'win_pct75': ws['pct75'],
        'lose_pct25': ls['pct25'], 'lose_pct75': ls['pct75'],
        'cohens_d': d,
        'n_win': ws['n'], 'n_lose': ls['n'],
    })

# 按 |cohens_d| 排序（效果量越大=区分度越高）
results.sort(key=lambda r: -abs(r['cohens_d']))

# 打印
print(f'\n{"因子":<18} {"胜均值":>7} {"败均值":>7} {"胜中位":>7} {"败中位":>7} {"均值差":>7} {"差%":>7} {"d值":>7} | 胜者分布')
print('-' * 100)
for r in results:
    star = ' ★' if abs(r['cohens_d']) > 0.8 else (' ☆' if abs(r['cohens_d']) > 0.5 else '  ')
    print(f'{r["name"]:<18} {r["win_mean"]:>7.2f} {r["lose_mean"]:>7.2f} '
          f'{r["win_med"]:>7.2f} {r["lose_med"]:>7.2f} '
          f'{r["diff_mean"]:>+7.2f} {r["diff_mean_pct"]:>+6.1f}% '
          f'{r["cohens_d"]:>+6.2f}{star} | '
          f'胜[{r["win_pct25"]:.1f}~{r["win_pct75"]:.1f}] 败[{r["lose_pct25"]:.1f}~{r["lose_pct75"]:.1f}]')

print('')
print('=== 效果量标杆 ===')
print('  |d| > 0.8 = 大差异 (巨大突破潜力) ★')
print('  |d| > 0.5 = 中差异 (有效改进方向) ☆')
print('  |d| < 0.2 = 几乎无差异 (此因子无法区分胜负)')

# ===== 按行情分类分析 =====
print('\n' + '=' * 100)
print('📊 按行情分类——各因子差异')
print('=' * 100)

for mk in ['真实涨日', '虚涨日', '跌日', '横盘']:
    mw = [r for r in champ_records if r['success'] and r['market'] == mk]
    ml = [r for r in champ_records if not r['success'] and r['market'] == mk]
    if len(mw) < 3 or len(ml) < 3: continue
    print(f'\n--- {mk}: 胜{len(mw)}/败{len(ml)} ---')

    m_results = []
    for fkey, fname in FACTOR_NAMES.items():
        wv = [r['factors'].get(fkey, 0) or 0 for r in mw]
        lv = [r['factors'].get(fkey, 0) or 0 for r in ml]
        if len(wv) < 3 or len(lv) < 3: continue
        d = cohens_d(wv, lv)
        wm = sum(wv) / len(wv)
        lm = sum(lv) / len(lv)
        m_results.append({'name': fname, 'd': d, 'wm': wm, 'lm': lm})

    m_results.sort(key=lambda r: -abs(r['d']))
    print(f'{"因子":<16} {"胜均值":>7} {"败均值":>7} {"d值":>6}')
    for r in m_results[:5]:
        print(f'{r["name"]:<16} {r["wm"]:>7.2f} {r["lm"]:>7.2f} {r["d"]:>+6.2f}')


# ===== 新因子4个专项报告 =====
print('\n' + '=' * 100)
print('🔬 新因子4个专项报告——在成功票vs失败票中的具体表现')
print('=' * 100)

new_factors = [
    ('amp', '振幅%'),
    ('body_to_amp', '实体/振幅比'),
    ('p_times_vr', '涨幅×量比'),
    ('amp_to_p', '振幅/涨幅比'),
]

for fkey, fname in new_factors:
    wv = [r['factors'].get(fkey, 0) or 0 for r in winners]
    lv = [r['factors'].get(fkey, 0) or 0 for r in losers]
    if not wv or not lv: continue

    # 分10个桶看胜率
    all_vals = [(v, 1) for v in wv] + [(v, 0) for v in lv]
    all_vals.sort()
    bucket_size = max(1, len(all_vals) // 10)

    print(f'\n【{fname}】成功率分段:')
    for i in range(0, len(all_vals), bucket_size):
        chunk = all_vals[i:i + bucket_size]
        if len(chunk) < 5: continue
        chunk_vals = [c[0] for c in chunk]
        chunk_wins = sum(c[1] for c in chunk)
        wr = chunk_wins / len(chunk) * 100
        low, high = min(chunk_vals), max(chunk_vals)
        print(f'  {low:>7.2f}~{high:>7.2f}: {len(chunk):>3d}只 胜率{wr:>5.1f}%')

# ===== 冠军 vs 亚军 vs 季军 =====
print('\n' + '=' * 100)
print('📊 冠军/亚军/季军胜率对比')
print('=' * 100)
rank_wins = {1: 0, 2: 0, 3: 0}
rank_total = {1: 0, 2: 0, 3: 0}
for r in all_records:
    rk = r['rank']
    rank_total[rk] += 1
    if r['success']:
        rank_wins[rk] += 1

for rk in [1, 2, 3]:
    wr = rank_wins[rk] / max(rank_total[rk], 1) * 100
    print(f'  #{rk}: {rank_wins[rk]}/{rank_total[rk]}={wr:.1f}%')

# 保存结果
import json
result_path = os.path.join(DIR, '_factor_analysis_result.json')
with open(result_path, 'w', encoding='utf-8') as f:
    json.dump({
        'total_days': total_days,
        'win_days': win_days,
        'win_rate': round(win_days / max(total_days, 1) * 100, 1),
        'champ_samples': {'winners': len(winners), 'losers': len(losers)},
        'factor_rankings': [{
            'factor': r['name'],
            'factor_key': r['factor'],
            'cohens_d': round(r['cohens_d'], 3),
            'mean_diff': round(r['diff_mean'], 2),
            'mean_diff_pct': round(r['diff_mean_pct'], 1),
            'win_mean': round(r['win_mean'], 2),
            'lose_mean': round(r['lose_mean'], 2),
        } for r in results],
        'new_factors': [{
            'factor': fn,
            'cohens_d': round(cohens_d(
                [r['factors'].get(fk, 0) or 0 for r in winners],
                [r['factors'].get(fk, 0) or 0 for r in losers]
            ), 3),
            'win_mean': round(sum(r['factors'].get(fk, 0) or 0 for r in winners) / max(len(winners), 1), 2),
            'lose_mean': round(sum(r['factors'].get(fk, 0) or 0 for r in losers) / max(len(losers), 1), 2),
        } for fk, fn in new_factors],
    }, f, ensure_ascii=False, indent=2)

print(f'\n💾 结果已保存: {result_path}')
print('✅ 分析完成!')
