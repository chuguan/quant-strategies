"""虚涨日17天：两步搜索·快速版 - 涨幅<8%限定"""
import pickle, os, sys

os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
print("Loading cache...", flush=True)
d = pickle.load(open('big_cache_full.pkl', 'rb'))
print("Loaded!", flush=True)
data, real, names = d['data'], d['real'], d['names']
dates = [x for x in sorted(data.keys()) if '2025-01-01' <= x < '2026-06-01']

def classify_market(dt):
    stocks = data.get(dt, [])
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    avg_p = sum(ps) / len(ps)
    avg_vr = sum(vrs) / len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5:
        return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    elif avg_p < -0.5: return 'down'
    else: return 'flat'

fakes = [dt for dt in dates if classify_market(dt) == 'fake_up']
print(f"虚涨日共{len(fakes)}天", flush=True)

# ===== Step 1: 选股条件（涨幅<8%固定） =====
print(f"\n{'='*60}")
print("Step1: 搜选股条件", flush=True)

best_w = 0
best_cond = None
cond_seen = 0

for p_min, p_max in [(0,5),(0,6),(0,7),(-1,5),(-1,6),(-1,7),(2,7)]:
    for vr_min, vr_max in [(0.6,2.5),(0.6,3.0),(0.8,2.5)]:
        for hs_min, hs_max in [(3,20),(3,25),(5,20)]:
            for sz in [200, 300]:
                for cm, cx in [(30,95),(40,95),(50,95)]:
                    wins = nd = 0
                    for dt in fakes:
                        cand = []
                        for s in data.get(dt, []):
                            code = s['code']
                            p = s.get('p', 0) or 0
                            if p < p_min or p > p_max: continue
                            vr = s.get('vol_ratio', 0) or 0
                            if vr < vr_min or vr > vr_max: continue
                            ri = real.get(code)
                            if not ri: continue
                            hsl = (ri.get('hsl', 0) or 0)
                            if hsl < hs_min or hsl > hs_max: continue
                            if (ri.get('shizhi', 0) or 0) >= sz: continue
                            nm = names.get(code, '')
                            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                            cl = s.get('cl', 0)
                            if cl < cm or cl > cx: continue
                            nh = s.get('n', 0) or 0
                            if nh <= 0: continue
                            cand.append((p, nh, code))
                        if cand:
                            cand.sort(key=lambda x: -x[0])
                            nd += 1
                            if cand[0][1] >= 2.5:
                                wins += 1
                    cond_seen += 1
                    rate = wins * 100 / nd if nd else 0
                    if rate > best_w:
                        best_w = rate
                        best_cond = (p_min, p_max, vr_min, vr_max, hs_min, hs_max, sz, cm, cx, wins, nd)
                        print(f"  [{cond_seen}] {wins}/{nd}={rate:.1f}% | 涨{p_min}~{p_max}% 量{vr_min}~{vr_max} 换{hs_min}~{hs_max}% CL{cm}~{cx}% sz<{sz}亿", flush=True)

if not best_cond:
    print("无结果！", flush=True)
    sys.exit(1)

p_min, p_max, vr_min, vr_max, hs_min, hs_max, sz, cm, cx, wins, nd = best_cond
print(f"\n** Step1最优: 涨{p_min}~{p_max}% 量{vr_min}~{vr_max} 换{hs_min}~{hs_max}% CL{cm}~{cx}% 市值<{sz}亿 → 胜率{best_w:.1f}%")

# ===== Step 2: 评分权重 =====
print(f"\n{'='*60}")
print("Step2: 搜评分权重", flush=True)

best_w2 = 0
best_score = None
score_seen = 0

for p_w in [1.0, 1.5, 2.0, 2.5]:
    for cl_w in [0.05, 0.1, 0.15]:
        for j_b in [0, 2, 3, 5]:
            for j_low_b in [0, 2, 3, 5]:
                for hsl_b in [0, 0.3]:
                    for ma5_b in [0, 3, 5]:
                        for macd_w in [0.3, 0.5, 0.8, 1.0]:
                            for wr_b in [0, 2]:
                                wins = nd = 0
                                for dt in fakes:
                                    cand = []
                                    for s in data.get(dt, []):
                                        code = s['code']
                                        p = s.get('p', 0) or 0
                                        if p < p_min or p > p_max: continue
                                        vr = s.get('vol_ratio', 0) or 0
                                        if vr < vr_min or vr > vr_max: continue
                                        ri = real.get(code)
                                        if not ri: continue
                                        hsl = (ri.get('hsl', 0) or 0)
                                        if hsl < hs_min or hsl > hs_max: continue
                                        if (ri.get('shizhi', 0) or 0) >= sz: continue
                                        nm = names.get(code, '')
                                        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                                        cl = s.get('cl', 0)
                                        if cl < cm or cl > cx: continue
                                        nh = s.get('n', 0) or 0
                                        if nh <= 0: continue
                                        jv = s.get('j_val', 0) or 0
                                        dif = s.get('dif_val', 0) or 0
                                        macd_g = s.get('macd_golden', 0)
                                        above5 = s.get('above_ma5', 0)
                                        wr = s.get('wr_val', 0) or 0

                                        macd_s = 0
                                        if macd_g and dif > 0.5: macd_s = 10
                                        elif macd_g and dif > 0.2: macd_s = 8
                                        elif macd_g: macd_s = 6
                                        elif dif > 0.5: macd_s = 4
                                        elif dif > 0: macd_s = 2

                                        buy = s.get('close', 0) or 0
                                        ps2 = min(10, max(1, 11 - buy / 10)) if buy else 0
                                        hsl_plus = hsl_b * 2 if 5 <= hsl <= 7 else 0
                                        j_plus = j_b if jv > 70 else 0
                                        j_low = j_low_b if jv < 20 else 0
                                        wr_plus = wr_b if wr < -80 else 0

                                        score = p * p_w + cl * cl_w + ps2 * 0.3 + macd_s * macd_w
                                        score += ma5_b * above5 + hsl_plus + j_plus + j_low + wr_plus
                                        cand.append((score, nh, p, nm, code))
                                    if cand:
                                        cand.sort(key=lambda x: (-x[0], -x[2]))
                                        nd += 1
                                        if cand[0][1] >= 2.5:
                                            wins += 1
                                score_seen += 1
                                rate = wins * 100 / nd if nd else 0
                                if rate > best_w2:
                                    best_w2 = rate
                                    best_score = (p_w, cl_w, j_b, j_low_b, hsl_b, ma5_b, macd_w, wr_b, wins, nd)
                                    print(f"  [{score_seen}] {wins}/{nd}={rate:.1f}% | 涨x{p_w}+CLx{cl_w}+J>70+{j_b}+J<20+{j_low_b}+换5-7+{hsl_b}+WR{wr_b}+MA5+{ma5_b}+MACDx{macd_w}", flush=True)

if not best_score:
    print("评分搜索无结果！", flush=True)
    sys.exit(1)

p_w, cl_w, j_b, j_low_b, hsl_b, ma5_b, macd_w, wr_b, wins, nd = best_score

print(f"\n{'='*60}")
print(f"** 虚涨日最终最优 **")
print(f"选股: 涨{p_min}~{p_max}% 量{vr_min}~{vr_max} 换{hs_min}~{hs_max}% CL{cm}~{cx}% 市值<{sz}亿")
print(f"评分: 涨x{p_w}+CLx{cl_w}+J>70+{j_b}+J<20+{j_low_b}+换5-7+{hsl_b}+WR<-80+{wr_b}+MA5+{ma5_b}+MACDx{macd_w}")
print(f"冠军胜率: {wins}/{nd}={best_w2:.1f}% [{len(fakes)}天]")

# 每日明细
print(f"\n每日冠军:")
for dt in fakes:
    cand = []
    for s in data.get(dt, []):
        code = s['code']
        p = s.get('p', 0) or 0
        if p < p_min or p > p_max: continue
        vr = s.get('vol_ratio', 0) or 0
        if vr < vr_min or vr > vr_max: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl', 0) or 0)
        if hsl < hs_min or hsl > hs_max: continue
        if (ri.get('shizhi', 0) or 0) >= sz: continue
        nm = names.get(code, '')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        cl = s.get('cl', 0)
        if cl < cm or cl > cx: continue
        nh = s.get('n', 0) or 0
        if nh <= 0: continue
        jv = s.get('j_val', 0) or 0
        dif = s.get('dif_val', 0) or 0
        macd_g = s.get('macd_golden', 0)
        above5 = s.get('above_ma5', 0)
        wr = s.get('wr_val', 0) or 0
        buy = s.get('close', 0) or 0

        macd_s = 0
        if macd_g and dif > 0.5: macd_s = 10
        elif macd_g and dif > 0.2: macd_s = 8
        elif macd_g: macd_s = 6
        elif dif > 0.5: macd_s = 4
        elif dif > 0: macd_s = 2
        ps2 = min(10, max(1, 11 - buy / 10)) if buy else 0
        hsl_plus = hsl_b * 2 if 5 <= hsl <= 7 else 0
        j_plus = j_b if jv > 70 else 0
        j_low = j_low_b if jv < 20 else 0
        wr_plus = wr_b if wr < -80 else 0

        score = p * p_w + cl * cl_w + ps2 * 0.3 + macd_s * macd_w
        score += ma5_b * above5 + hsl_plus + j_plus + j_low + wr_plus
        cand.append((score, nh, p, nm, code, cl, vr, hsl, jv, wr))
    if cand:
        cand.sort(key=lambda x: (-x[0], -x[2]))
        c = cand[0]
        tag = 'A' if c[1] >= 5 else ('B' if c[1] >= 2.5 else 'C')
        print(f"  {dt}: {c[3][:10]:<10} {c[4]} 涨{c[2]:+.1f}% CL{c[5]:.0f}% 量{c[6]:.2f} J{c[8]:.0f} → +{c[1]:.1f}% [{tag}]", flush=True)

# Top3
wins3 = 0
for dt in fakes:
    cand = []
    for s in data.get(dt, []):
        code = s['code']
        p = s.get('p', 0) or 0
        if p < p_min or p > p_max: continue
        vr = s.get('vol_ratio', 0) or 0
        if vr < vr_min or vr > vr_max: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl', 0) or 0)
        if hsl < hs_min or hsl > hs_max: continue
        if (ri.get('shizhi', 0) or 0) >= sz: continue
        nm = names.get(code, '')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        cl = s.get('cl', 0)
        if cl < cm or cl > cx: continue
        nh = s.get('n', 0) or 0
        if nh <= 0: continue
        jv = s.get('j_val', 0) or 0
        dif = s.get('dif_val', 0) or 0
        macd_g = s.get('macd_golden', 0)
        above5 = s.get('above_ma5', 0)
        wr = s.get('wr_val', 0) or 0
        buy = s.get('close', 0) or 0

        macd_s = 0
        if macd_g and dif > 0.5: macd_s = 10
        elif macd_g and dif > 0.2: macd_s = 8
        elif macd_g: macd_s = 6
        elif dif > 0.5: macd_s = 4
        elif dif > 0: macd_s = 2
        ps2 = min(10, max(1, 11 - buy / 10)) if buy else 0
        hsl_plus = hsl_b * 2 if 5 <= hsl <= 7 else 0
        j_plus = j_b if jv > 70 else 0
        j_low = j_low_b if jv < 20 else 0
        wr_plus = wr_b if wr < -80 else 0

        score = p * p_w + cl * cl_w + ps2 * 0.3 + macd_s * macd_w
        score += ma5_b * above5 + hsl_plus + j_plus + j_low + wr_plus
        cand.append((score, nh, p, nm, code))
    if cand:
        cand.sort(key=lambda x: (-x[0], -x[2]))
        top3_nh = [c[1] for c in cand[:3]]
        if any(nh >= 2.5 for nh in top3_nh):
            wins3 += 1

print(f"\nTop3任意达标: {wins3}/{len(fakes)}={wins3*100/len(fakes):.1f}%")
