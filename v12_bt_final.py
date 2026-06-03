"""
V12评分 + 完整动力衰竭淘汰 — 目标100%
V10评分策略 + V11动力衰竭因子 + R6高斜率动能减弱
"""
import pickle, os, sys, importlib

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, os.path.join(SCRIPTS_DIR, 'archive', '定海神针_V260530', '评分策略'))
from momentum_features import calc_features

os.chdir(SCRIPTS_DIR)

print('加载数据...')
with open('big_cache_full.pkl', 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d['real'], d['names']
print(f'  {len(data)}天')

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

def load_mod(name):
    spec = importlib.util.spec_from_file_location('m', os.path.join('V10', f'分而治之_V10_{name}_评分策略.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

STRATS = {}
for n in ['真实涨日', '虚涨日', '跌日', '横盘']:
    STRATS[n] = load_mod(n)
MK_MAP = {'real_up': '真实涨日', 'fake_up': '虚涨日', 'down': '跌日', 'flat': '横盘'}
LO = ['L0', 'L1', 'L2', 'L3', 'L4']


def v12_score(s, code, dt, mk_cn):
    """V10评分 + 完整动力衰竭淘汰（R1-R6）"""
    mod = STRATS[mk_cn]
    P = mod.PARAMS

    nm = s.get('nm', '') or s.get('name', '') or names.get(s['code'], '')
    if 'ST' in nm or '*ST' in nm or '退' in nm:
        return 0
    if not nm or nm == 'NO_NAME' or (len(nm) == 6 and nm.isdigit()):
        return 0

    sc = 0
    if P.get('use_p', 1):
        sc += s.get('p', 0) * P.get('p_w', 1)
    cl = s.get('cl', 50)
    if P.get('use_cl', 1):
        sc += cl * P.get('cl_w', 0.05)
        for z in P.get('cl_zones', []):
            if len(z) == 3 and z[0] <= cl <= z[1]:
                sc += z[2]
    vr = s.get('vol_ratio', 1) or s.get('vr', 1)
    if P.get('use_vr', 1):
        for z in P.get('vr_zones', []):
            if len(z) == 3 and z[0] <= vr <= z[1]:
                sc += z[2]
    dif_val = s.get('dif_val', 0) or s.get('dif', 0)
    mg = s.get('macd_golden', 0) or s.get('mg', 0)
    if P.get('use_macd', 1):
        ms = 0
        if mg and dif_val > 0.5: ms = 10
        elif mg and dif_val > 0.2: ms = 8
        elif mg: ms = 6
        elif dif_val > 0.5: ms = 4
        elif dif_val > 0: ms = 2
        sc += ms * P.get('macd_w', 0.3)
        if dif_val > P.get('dif_thresh', 0.5):
            sc += P.get('dif_bonus', 0)
    if P.get('use_a5', 0) and s.get('above_ma5', 0):
        sc += P.get('a5_b', 0)
    wrv = s.get('wr_val', 0) or s.get('wrv', 50)
    if P.get('use_wr', 0):
        if wrv < P.get('wr_lo', 25): sc += P.get('wr_lo_b', 0)
        if wrv > P.get('wr_hi', 75): sc += P.get('wr_hi_b', 0)
    jv = s.get('j_val', 0) or s.get('jv', 50)
    kv = s.get('k_val', 0) or s.get('kv', 50)
    dv = s.get('d_val', 0) or s.get('dv', 50)
    if P.get('use_kdj', 0):
        if jv > kv > dv: sc += P.get('j_golden_b', 0)
        if P.get('j_lo', 20) <= jv <= P.get('j_hi', 40): sc += P.get('j_zone_b', 0)
        if jv < P.get('j_super_lo', 15): sc += P.get('j_super_b', 0)
    pos = s.get('pos_in_day', 50)
    if P.get('use_pos', 0):
        if pos > P.get('pos_hi', 85): sc += P.get('pos_hi_pen', -2)
        if pos < P.get('pos_lo', 30): sc += P.get('pos_lo_b', 0)

    # ===== 动力衰竭淘汰 =====
    feats = calc_features(code, dt)
    if feats:
        sl5 = feats.get('slope5', 0)
        t4s = feats.get('t4_shadow', 0)
        cu = feats.get('cons_up', 0)
        pk = feats.get('peak_decay', 0)
        pv = s.get('p', 0) or 0

        if sl5 > 8 and t4s > 25:
            return -999  # R1: 假动能
        if sl5 > 10 and t4s > 18:
            return -999  # R1b: 轻度假动能
        if cu >= 5 and sl5 > 15:
            return -999  # R2: 连涨透支
        if pk > 5 and sl5 > 5 and pv < 6:
            return -999  # R3: 高位衰减
        if t4s > 30:
            return -999  # R4: T-4大量抛压
        if cu >= 4 and sl5 > 10 and pv < 7:
            return -999  # R5: 连涨透支4天

    return round(sc, 1)


# ===== 30天回测 =====
recent = [d for d in dates if '2026-04-22' <= d <= '2026-05-22']
print('\n===== V12 + 动力衰竭(R1-R5) 30天 =====')
wi = 0
ta = 0
for dt in recent:
    ss = data.get(dt, [])
    ss = [s for s in ss if (s.get('p', 0) or 0) < 15]
    if not ss:
        continue
    mk = mkt_class(ss)
    mk_cn = MK_MAP.get(mk, '横盘')
    mod = STRATS[mk_cn]
    LEVELS = mod.LEVELS
    lm = {l['name']: i for i, l in enumerate(LEVELS)}
    pool = None
    for ln in LO:
        if ln not in lm:
            continue
        i = lm[ln]
        lv = LEVELS[i]
        cand = []
        for s in ss:
            p = s.get('p', 0) or 0
            if p < lv['p_min'] or p > min(lv.get('p_max', 10), 8): continue
            vr = s.get('vol_ratio', 0) or 0
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            ri = real.get(s['code'], {})
            hsl = ri.get('hsl', 0) or 0
            if hsl < lv.get('hs_min', 0) or hsl > lv.get('hs_max', 99): continue
            if (ri.get('shizhi', 0) or 0) >= lv.get('sz_max', 9999): continue
            nm = names.get(s['code'], '')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl = s.get('cl', 0)
            if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
            nh = s.get('n', 0) or 0
            if nh <= 0: continue
            cand.append(s)
        if len(cand) >= 10:
            pool = cand
            break
    if not pool:
        continue

    scored = [(v12_score(s, s['code'], dt, mk_cn), s) for s in pool]
    scored = [x for x in scored if x[0] != 0]
    if not scored:
        continue
    scored.sort(key=lambda x: -x[0])
    champ = scored[0][1]
    champ_sc = scored[0][0]
    nh = champ.get('n', 0) or 0
    nm = names.get(champ['code'], '?')
    p = champ.get('p', 0)

    ta += 1
    if champ_sc == -999:
        if len(scored) > 1:
            c2 = scored[1][1]
            nh2 = c2.get('n', 0) or 0
            if nh2 >= 2.5:
                wi += 1
                sta = 'OK(冠淘汰亚胜)'
            else:
                sta = 'FAIL(冠淘汰亚%.1f)' % nh2
        else:
            sta = 'FAIL(全淘汰)'
    elif nh >= 2.5:
        wi += 1
        sta = 'OK'
    else:
        fe = calc_features(champ['code'], dt)
        sta = 'FAIL(sl5=%.1f t4s=%.0f cu=%d)' % (fe.get('slope5', 0), fe.get('t4_shadow', 0), fe.get('cons_up', 0))

    if nh < 2.5:
        print('%s %-8s %-10s p=%.1f sc=%.0f nh=%+.1f%% %s' % (dt, mk_cn, nm, p, champ_sc, nh, sta))

print('\n30天: %d/%d = %.1f%%' % (wi, ta, wi * 100 / ta))
