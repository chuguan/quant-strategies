"""
V13 — 最高版
V10评分(纯加分减分) + 动力衰竭提前过滤(入池前淘汰)
"""
import pickle, os, sys, importlib

V13_DIR = os.path.dirname(os.path.abspath(__file__))

print('加载数据...')
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d['real'], d['names']
with open(os.path.join(V13_DIR, 'features_30d.pkl'), 'rb') as f:
    precomputed = pickle.load(f)
print(f'  big_cache: {len(data)}天, 特征: {len(precomputed)}条')


def mkt_class(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    ap = sum(ps) / len(ps); av = sum(vrs) / len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'


def load_mod(name):
    fp = os.path.join(V13_DIR, '评分策略', f'分而治之_V10_{name}_评分策略.py')
    spec = importlib.util.spec_from_file_location('m', fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


STRATS = {}
for n in ['真实涨日', '虚涨日', '跌日', '横盘']:
    STRATS[n] = load_mod(n)
MK_MAP = {'real_up': '真实涨日', 'fake_up': '虚涨日', 'down': '跌日', 'flat': '横盘'}
LO = ['L0', 'L1', 'L2', 'L3', 'L4']


# ═══ 动力衰竭检查（独立于评分，入池前过滤）═══
def is_momentum_exhausted(s, code, dt):
    """检查股票是否有动力衰竭特征，是则返回True（不入池）"""
    feats = precomputed.get((code, dt), {})
    if not feats:
        return False
    
    sl5 = feats.get('slope5', 0)
    t4s = feats.get('t4_shadow', 0)
    cu = feats.get('cons_up', 0)
    pk = feats.get('peak_decay', 0)
    pv = s.get('p', 0) or 0
    
    if sl5 > 8 and t4s > 25: return True   # R1: 假动能
    if sl5 > 10 and t4s > 18: return True  # R1b: 轻度假动能
    if cu >= 5 and sl5 > 15: return True   # R2: 连涨透支
    if pk > 5 and sl5 > 5 and pv < 6: return True  # R3: 高位衰减
    if sl5 > 5 and t4s > 30: return True   # R4: T-4抛压+有一定涨幅
    if cu >= 4 and sl5 > 10 and pv < 7: return True  # R5: 连涨透支4天
    
    return False


def get_feats(code, dt):
    return precomputed.get((code, dt), {})


# ═══ V10评分（字段映射版，纯加分减分）═══
def v10_score(s, code, dt, mk_cn):
    """V10评分(纯加分减分)，字段已映射"""
    mod = STRATS[mk_cn]; P = mod.PARAMS
    
    # 字段映射 big_cache → V10命名
    stock = {}
    stock['p'] = s.get('p', 0) or 0
    stock['cl'] = s.get('cl', 50)
    stock['vr'] = s.get('vol_ratio', 1) or s.get('vr', 1)
    stock['dif'] = s.get('dif_val', 0) or s.get('dif', 0)
    stock['mg'] = s.get('macd_golden', 0) or s.get('mg', 0)
    stock['wrv'] = s.get('wr_val', 0) or s.get('wrv', 50)
    stock['jv'] = s.get('j_val', 0) or s.get('jv', 50)
    stock['kv'] = s.get('k_val', 0) or s.get('kv', 50)
    stock['dv'] = s.get('d_val', 0) or s.get('dv', 50)
    stock['a5'] = s.get('above_ma5', 0)
    stock['kdj_g'] = s.get('kdj_golden', 0) or s.get('kdj_g', 0)
    stock['pos_in_day'] = s.get('pos_in_day', 50)
    stock['nm'] = s.get('nm', '') or s.get('name', '') or names.get(s['code'], '')
    ri = real.get(s['code'], {})
    stock['hsl'] = ri.get('hsl', 0) or 0
    
    # 传递动量特征给评分函数（用于扣分）
    feats = get_feats(code, dt)
    stock['t4_shadow'] = feats.get('t4_shadow', 0)
    stock['slope5'] = feats.get('slope5', 0)
    stock['cons_up'] = feats.get('cons_up', 0)
    stock['d1'] = feats.get('d1', 0)
    stock['d2'] = feats.get('d2', 0)
    stock['d3'] = feats.get('d3', 0)
    # 7天动量衰减检查
    seven_day_penalty = compute_7day_decay_penalty(code, dt, s.get('p',0) or 0)
    return round(mod.score(stock) + seven_day_penalty, 1)

# ═══ 7天动量衰减检查 ═══
def compute_7day_decay_penalty(code, dt, p_today):
    """检查7天涨幅序列是否显示动量衰减。返回负分（扣分）"""
    all_dates = sorted(data.keys())
    idx = all_dates.index(dt)
    prev = all_dates[max(0,idx-6):idx]
    
    # 获取T-6到T-1的涨跌幅
    gains = []
    for pd in prev:
        found = False
        for s in data[pd]:
            if s['code'] == code:
                gains.append(s.get('p',0) or 0)
                found = True
                break
        if not found:
            gains.append(0)
    gains.append(p_today)  # [d6,d5,d4,d3,d2,d1,p]
    
    n = len(gains)
    if n < 5: return 0
    
    d6,d5,d4,d3,d2,d1,p = gains[-7:] if n >= 7 else [0]*(7-n) + gains
    
    # 特征1: p是7天中最高值吗？
    p_is_max = p >= max(gains[:-1]) if len(gains) > 1 else True
    
    # 特征2: 7天平均涨幅
    avg_7d = sum(gains) / n
    
    # 特征3: 最近两天总和
    d1d2_sum = d1 + d2
    
    # 特征4: 之前是否有过大涨（T-4之前有>5%的涨幅）
    had_big_spike = max(d6,d5,d4) > 5 if n >= 4 else False
    # 那次大涨后是否连续下跌
    spike_exhaust = had_big_spike and (d3 < 0 or d2 < 0) and d1 < 1
    
    penalty = 0
    
    # 规则6: 极端超买(WR<10) + 7天平均弱 + 今天是最高点
    # 从big_cache获取WR
    wrv = 50
    for s in data.get(dt, []):
        if s['code'] == code:
            wrv = s.get('wr_val', 50) or s.get('wrv', 50)
            break
    if wrv < 10 and p_is_max and avg_7d < 2.0 and p < 6:
        penalty -= 8
    
    # 规则1: p是7天最高 + 7天平均很低 — 按幅度分级扣分
    if p_is_max and avg_7d < 0.8 and p < 8:
        if avg_7d < 0:
            penalty -= 15   # 7天均跌
        elif avg_7d < 0.3:
            penalty -= 12   # 几乎没涨
        elif avg_7d < 0.7:
            penalty -= 8    # 微弱涨幅
        else:
            penalty -= 5    # 轻度警告
    
    # 规则2: 从深跌中V型反弹（前两天深跌今天大涨）
    if d1 < -1.5 and d2 < -1.0 and p > 3 and avg_7d < 1.0:
        penalty -= 8
    
    # 规则3: 近期有大涨（d4或d3>5%）后连续下跌
    if max(d4, d3, d2) > 5 and d1 < 0 and d2 < 0:
        penalty -= 10
    
    # 规则5: 5天前的涨幅大于昨今两天的涨幅（峰值早已过去）
    if n >= 5 and d5 > d1 and d5 > d2 and p <= d5:
        recent_sum = (d4+d3+d2+d1) if n >= 6 else (d3+d2+d1)
        if recent_sum <= 2:  # 近期整体偏弱
            penalty -= 8
    
    # 规则4: 严格递减4天(从T-4到T)
    if n >= 5:
        last5 = gains[-5:]  # [d3,d2,d1,p] or [d4,d3,d2,d1,p]
        if all(last5[i] >= last5[i+1] for i in range(len(last5)-1)):
            penalty -= 10
    
    return penalty


# 30天回测
dates = sorted(k for k in data.keys() if '2025-01-01' <= k <= '2026-05-22')
recent = dates[-30:]
wi = 0; ta = 0
print(f'\n===== V13 (纯V10评分+入池前过滤) ({recent[0]}~{recent[-1]}) =====')
for dt in recent:
    ss = data.get(dt, []); ss = [s for s in ss if (s.get('p', 0) or 0) < 15]
    if not ss: continue
    mk = mkt_class(ss); mk_cn = MK_MAP.get(mk, '横盘')
    mod = STRATS[mk_cn]; LEVELS = mod.LEVELS
    lm = {l['name']: i for i, l in enumerate(LEVELS)}
    pool = None
    eliminated = 0
    
    for ln in LO:
        if ln not in lm: continue
        i = lm[ln]; lv = LEVELS[i]; cand = []
        for s in ss:
            p = s.get('p', 0) or 0
            if p < lv['p_min'] or p > min(lv.get('p_max', 10), 8): continue
            vr = s.get('vol_ratio', 0) or 0
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            ri = real.get(s['code'], {}); hsl = ri.get('hsl', 0) or 0
            if hsl < lv.get('hs_min', 0) or hsl > lv.get('hs_max', 99): continue
            if (ri.get('shizhi', 0) or 0) >= lv.get('sz_max', 9999): continue
            nm = names.get(s['code'], '')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl = s.get('cl', 0)
            if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
            nh = s.get('n', 0) or 0
            # 动力衰竭过滤（入池前淘汰）
            if is_momentum_exhausted(s, s['code'], dt):
                eliminated += 1
                continue
            cand.append(s)
        if len(cand) >= 10:
            pool = cand
            break
    
    if not pool:
        nopool = '(淘汰过多)' if eliminated > 5 else '(池不足)'
        print(f'{dt} {mk_cn:>5} 候选池<10只(淘汰{eliminated}) {nopool}')
        continue

    # V10评分（纯加分减分）
    scored = [(v10_score(s, s['code'], dt, mk_cn), s) for s in pool]
    scored.sort(key=lambda x: -x[0])
    champ = scored[0][1]; champ_sc = scored[0][0]
    nh = champ.get('n', 0) or 0; nm = names.get(champ['code'], '?'); p = champ.get('p', 0)

    ta += 1
    if nh >= 2.5:
        wi += 1; sta = 'OK'
    else:
        fe = precomputed.get((champ['code'], dt), {})
        sta = f'FAIL(sl5={fe.get("slope5",0):.1f} t4s={fe.get("t4_shadow",0):.0f})'

    print(f'{dt} {mk_cn:>5} {nm:>10} p={p:.1f}% sc={champ_sc:.0f} nh={nh:+.1f}% {sta}')

print(f'\n30天: {wi}/{ta} = {wi * 100 / ta:.1f}%')
