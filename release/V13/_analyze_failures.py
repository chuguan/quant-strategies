"""V13 失败分析：详细输出每个失败日的完整特征数据"""
import pickle, os, sys, importlib
from collections import Counter

V13_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, V13_DIR)

print("加载数据...")
with open(os.path.join(V13_DIR, "big_cache_full.pkl"), "rb") as f:
    d = pickle.load(f)
data, real, names = d["data"], d["real"], d["names"]
with open(os.path.join(V13_DIR, "features_30d.pkl"), "rb") as f:
    precomputed = pickle.load(f)
print(f"  big_cache: {len(data)}天, 特征: {len(precomputed)}条")


def mkt_class(stocks):
    if not stocks:
        return "flat"
    ps = [s.get("p", 0) or 0 for s in stocks]
    vrs = [s.get("vol_ratio", 0) or 0 for s in stocks if s.get("vol_ratio", 0)]
    ap = sum(ps) / len(ps)
    av = sum(vrs) / len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5:
        return "fake_up" if hot < 15 or av < 0.9 else "real_up"
    if ap < -0.5:
        return "down"
    return "flat"


def load_mod(name):
    fp = os.path.join(V13_DIR, "评分策略", f"分而治之_V10_{name}_评分策略.py")
    spec = importlib.util.spec_from_file_location("m", fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


STRATS = {}
for n in ["真实涨日", "虚涨日", "跌日", "横盘"]:
    STRATS[n] = load_mod(n)
MK_MAP = {"real_up": "真实涨日", "fake_up": "虚涨日", "down": "跌日", "flat": "横盘"}
LO = ["L0", "L1", "L2", "L3", "L4"]


def is_momentum_exhausted(s, code, dt):
    feats = precomputed.get((code, dt), {})
    if not feats:
        return False
    sl5 = feats.get("slope5", 0)
    t4s = feats.get("t4_shadow", 0)
    cu = feats.get("cons_up", 0)
    pk = feats.get("peak_decay", 0)
    pv = s.get("p", 0) or 0
    if sl5 > 8 and t4s > 25:
        return True
    if sl5 > 10 and t4s > 18:
        return True
    if cu >= 5 and sl5 > 15:
        return True
    if pk > 5 and sl5 > 5 and pv < 6:
        return True
    if sl5 > 5 and t4s > 30:
        return True
    if cu >= 4 and sl5 > 10 and pv < 7:
        return True
    return False


def get_feats(code, dt):
    return precomputed.get((code, dt), {})


def compute_7day_decay_penalty(code, dt, p_today):
    all_dates = sorted(data.keys())
    idx = all_dates.index(dt)
    prev = all_dates[max(0, idx - 6) : idx]
    gains = []
    for pd in prev:
        found = False
        for s in data[pd]:
            if s["code"] == code:
                gains.append(s.get("p", 0) or 0)
                found = True
                break
        if not found:
            gains.append(0)
    gains.append(p_today)
    n = len(gains)
    if n < 5:
        return 0
    d6, d5, d4, d3, d2, d1, p = (
        gains[-7:] if n >= 7 else [0] * (7 - n) + gains
    )
    p_is_max = p >= max(gains[:-1]) if len(gains) > 1 else True
    avg_7d = sum(gains) / n
    had_big_spike = max(d6, d5, d4) > 5 if n >= 4 else False
    penalty = 0
    wrv = 50
    for s in data.get(dt, []):
        if s["code"] == code:
            wrv = s.get("wr_val", 50) or s.get("wrv", 50)
            break
    if wrv < 10 and p_is_max and avg_7d < 2.0 and p < 6:
        penalty -= 8
    if p_is_max and avg_7d < 0.8 and p < 8:
        if avg_7d < 0:
            penalty -= 15
        elif avg_7d < 0.3:
            penalty -= 12
        elif avg_7d < 0.7:
            penalty -= 8
        else:
            penalty -= 5
    if d1 < -1.5 and d2 < -1.0 and p > 3 and avg_7d < 1.0:
        penalty -= 8
    if max(d4, d3, d2) > 5 and d1 < 0 and d2 < 0:
        penalty -= 10
    if n >= 5 and d5 > d1 and d5 > d2 and p <= d5:
        recent_sum = (d4 + d3 + d2 + d1) if n >= 6 else (d3 + d2 + d1)
        if recent_sum <= 2:
            penalty -= 8
    if n >= 5:
        last5 = gains[-5:]
        if all(last5[i] >= last5[i + 1] for i in range(len(last5) - 1)):
            penalty -= 10
    return penalty


def v10_score(s, code, dt, mk_cn):
    mod = STRATS[mk_cn]
    stock = {}
    stock["p"] = s.get("p", 0) or 0
    stock["cl"] = s.get("cl", 50)
    stock["vr"] = s.get("vol_ratio", 1) or s.get("vr", 1)
    stock["dif"] = s.get("dif_val", 0) or s.get("dif", 0)
    stock["mg"] = s.get("macd_golden", 0) or s.get("mg", 0)
    stock["wrv"] = s.get("wr_val", 0) or s.get("wrv", 50)
    stock["jv"] = s.get("j_val", 0) or s.get("jv", 50)
    stock["kv"] = s.get("k_val", 0) or s.get("kv", 50)
    stock["dv"] = s.get("d_val", 0) or s.get("dv", 50)
    stock["a5"] = s.get("above_ma5", 0)
    stock["kdj_g"] = s.get("kdj_golden", 0) or s.get("kdj_g", 0)
    stock["pos_in_day"] = s.get("pos_in_day", 50)
    stock["nm"] = s.get("nm", "") or s.get("name", "") or names.get(s["code"], "")
    ri = real.get(s["code"], {})
    stock["hsl"] = ri.get("hsl", 0) or 0
    feats = get_feats(code, dt)
    stock["t4_shadow"] = feats.get("t4_shadow", 0)
    stock["slope5"] = feats.get("slope5", 0)
    stock["cons_up"] = feats.get("cons_up", 0)
    stock["d1"] = feats.get("d1", 0)
    stock["d2"] = feats.get("d2", 0)
    stock["d3"] = feats.get("d3", 0)
    seven_day_penalty = compute_7day_decay_penalty(code, dt, s.get("p", 0) or 0)
    return round(mod.score(stock) + seven_day_penalty, 1)


# 回测 30天
dates = sorted(k for k in data.keys() if "2026-04-14" <= k <= "2026-05-28")
all_results = []

for dt in dates:
    ss = data.get(dt, [])
    ss = [s for s in ss if (s.get("p", 0) or 0) < 15]
    if not ss:
        continue
    mk = mkt_class(ss)
    mk_cn = MK_MAP.get(mk, "横盘")
    mod = STRATS[mk_cn]
    LEVELS = mod.LEVELS
    lm = {l["name"]: i for i, l in enumerate(LEVELS)}
    pool = None
    eliminated = 0
    for ln in LO:
        if ln not in lm:
            continue
        i = lm[ln]
        lv = LEVELS[i]
        cand = []
        for s in ss:
            p = s.get("p", 0) or 0
            if p < lv["p_min"] or p > min(lv.get("p_max", 10), 8):
                continue
            vr = s.get("vol_ratio", 0) or 0
            if vr < lv["vr_min"] or vr > lv["vr_max"]:
                continue
            ri = real.get(s["code"], {})
            hsl = ri.get("hsl", 0) or 0
            if hsl < lv.get("hs_min", 0) or hsl > lv.get("hs_max", 99):
                continue
            if (ri.get("shizhi", 0) or 0) >= lv.get("sz_max", 9999):
                continue
            nm = names.get(s["code"], "")
            if "ST" in nm or "*ST" in nm or "退" in nm:
                continue
            cl = s.get("cl", 0)
            if cl < lv.get("cl_min", 0) or cl > lv.get("cl_max", 100):
                continue
            if is_momentum_exhausted(s, s["code"], dt):
                eliminated += 1
                continue
            cand.append(s)
        if len(cand) >= 10:
            pool = cand
            break
    if not pool:
        continue

    scored = [(v10_score(s, s["code"], dt, mk_cn), s) for s in pool]
    scored.sort(key=lambda x: -x[0])
    champ = scored[0][1]
    champ_sc = scored[0][0]
    nh = champ.get("n", 0) or 0
    nm = names.get(champ["code"], "?")
    p = champ.get("p", 0)
    code = champ["code"]

    # 完整特征
    feats = get_feats(code, dt)
    wrv = champ.get("wr_val", 50) or champ.get("wrv", 50)
    vr = champ.get("vol_ratio", 1) or champ.get("vr", 1)
    cl = champ.get("cl", 50)
    hsl = real.get(code, {}).get("hsl", 0) or 0

    # 7天涨幅序列
    all_dates = sorted(data.keys())
    idx = all_dates.index(dt)
    prev_dates = all_dates[max(0, idx - 6) : idx]
    gains_7d = []
    for pd in prev_dates:
        found = False
        for s in data[pd]:
            if s["code"] == code:
                gains_7d.append(round(s.get("p", 0) or 0, 1))
                found = True
                break
        if not found:
            gains_7d.append(0)
    gains_7d.append(round(p, 1))

    # 7天扣分检查
    penalty = compute_7day_decay_penalty(code, dt, p)

    win = 1 if nh >= 2.5 else 0

    all_results.append(
        {
            "date": dt,
            "mk": mk_cn,
            "code": code,
            "name": nm,
            "p": p,
            "score": champ_sc,
            "nh": nh,
            "win": win,
            "wr": wrv,
            "vr": vr,
            "cl": cl,
            "hsl": hsl,
            "slope5": feats.get("slope5", 0),
            "t4_shadow": feats.get("t4_shadow", 0),
            "cons_up": feats.get("cons_up", 0),
            "peak_decay": feats.get("peak_decay", 0),
            "d1": feats.get("d1", 0),
            "d2": feats.get("d2", 0),
            "d3": feats.get("d3", 0),
            "gains_7d": gains_7d,
            "penalty": penalty,
            "pool_size": len(pool),
            "eliminated": eliminated,
        }
    )

failures = [r for r in all_results if not r["win"]]
successes = [r for r in all_results if r["win"]]

print(f"总: {len(successes)}/{len(all_results)} = {len(successes)*100/len(all_results):.1f}%")
print(f"\n{'='*140}")
print(f"{'日期':>10} {'行情':>5} {'代码':>8} {'名称':>10} {'p%':>5} {'评分':>6} {'nh%':>5} {'WR':>5} {'VR':>4} {'CL':>4} {'HSL':>5} {'sl5':>5} {'t4s':>5} {'cu':>3} {'pk':>4} {'扣分':>4}")
print(f"{'='*140}")

for r in all_results:
    flag = "❌" if not r["win"] else "✅"
    print(
        f'{r["date"]} {r["mk"]:>5} {r["code"]:>8} {r["name"]:>10} {r["p"]:>5.1f} {r["score"]:>6.1f} {r["nh"]:>+5.1f} {flag} {r["wr"]:>5.0f} {r["vr"]:>4.2f} {r["cl"]:>4.0f} {r["hsl"]:>5.1f} {r["slope5"]:>5.1f} {r["t4_shadow"]:>5.0f} {r["cons_up"]:>3.0f} {r["peak_decay"]:>4.1f} {r["penalty"]:>4}'
    )

print(f"\n{'='*80}")
print(f"❌ 失败日详细分析 ({len(failures)}天)")
print(f"{'='*80}")

for r in failures:
    print(f"\n【{r['date']} {r['mk']}】{r['name']}({r['code']})")
    print(f"  评分={r['score']:.1f}  p={r['p']:+.1f}%  nh={r['nh']:+.1f}%  候选池={r['pool_size']}只  淘汰={r['eliminated']}只")
    print(f"  WR={r['wr']:.0f}  VR={r['vr']:.2f}  CL={r['cl']:.0f}  HSL={r['hsl']:.1f}%")
    print(f"  slope5={r['slope5']:.1f}  t4_shadow={r['t4_shadow']:.0f}  cons_up={r['cons_up']:.0f}  peak_decay={r['peak_decay']:.1f}")
    print(f"  d1={r['d1']:.1f}  d2={r['d2']:.1f}  d3={r['d3']:.1f}")
    g = r["gains_7d"]
    g_str = " → ".join(f"{x:+.1f}" for x in g)
    print(f"  7天: {g_str}  (avg={sum(g)/len(g):+.2f})")

    # 动量过滤穿透检查
    missed = []
    sl5, t4s, cu, pk, pv = r["slope5"], r["t4_shadow"], r["cons_up"], r["peak_decay"], r["p"]
    if sl5 > 8 and t4s > 25:
        missed.append("R1(假动能)")
    if sl5 > 10 and t4s > 18:
        missed.append("R1b(轻度假动能)")
    if cu >= 5 and sl5 > 15:
        missed.append("R2(连涨透支)")
    if pk > 5 and sl5 > 5 and pv < 6:
        missed.append("R3(高位衰减)")
    if sl5 > 5 and t4s > 30:
        missed.append("R4(T4抛压)")
    if cu >= 4 and sl5 > 10 and pv < 7:
        missed.append("R5(连涨4天)")
    if missed:
        print(f"  ⚠ 动量过滤阈值差一点: {' | '.join(missed)}")
    else:
        print(f"  ✅ 动量过滤正确放行(无衰竭特征)")

    print(f"  7天扣分: {r['penalty']}")

    # 失败原因分类
    if r["nh"] < -1:
        print(f"  🎯 原因: 次日大跌({r['nh']:+.1f}%)")
    elif r["nh"] < 0:
        print(f"  🎯 原因: 次日微跌({r['nh']:+.1f}%)")
    else:
        print(f"  🎯 原因: 次日涨幅不足({r['nh']:+.1f}% < 2.5%)")

print(f"\n{'='*80}")
print("📊 失败共性统计")
print(f"{'='*80}")

print(f"\n【按行情】")
mk_fail = Counter(r["mk"] for r in failures)
mk_all = Counter(r["mk"] for r in all_results)
for mk in sorted(set(r["mk"] for r in all_results)):
    f = mk_fail.get(mk, 0)
    t = mk_all.get(mk, 0)
    print(f"  {mk}: {f}/{t} = {100*f/max(t,1):.0f}%")

print(f"\n【按次日涨幅】")
low_nh = [r for r in failures if r["nh"] < 0]
mid_nh = [r for r in failures if 0 <= r["nh"] < 2.5]
print(f"  次日大跌(<0%): {len(low_nh)}天")
for r in low_nh:
    print(f"    {r['date']} {r['name']}({r['code']}) nh={r['nh']:+.1f}% p={r['p']:+.1f}% 行情={r['mk']}")
print(f"  次日微涨(0~2.5%): {len(mid_nh)}天")
for r in mid_nh:
    print(f"    {r['date']} {r['name']}({r['code']}) nh={r['nh']:+.1f}% p={r['p']:+.1f}% 行情={r['mk']}")

print(f"\n【动量特征分布】")
high_slope = sum(1 for r in failures if r["slope5"] > 5)
high_t4 = sum(1 for r in failures if r["t4_shadow"] > 15)
high_cu = sum(1 for r in failures if r["cons_up"] >= 3)
high_pk = sum(1 for r in failures if r["peak_decay"] > 3)
low_wr = sum(1 for r in failures if r["wr"] < 15)
high_vr = sum(1 for r in failures if r["vr"] > 2.0)
print(f"  slope5>5:     {high_slope}/{len(failures)}")
print(f"  t4_shadow>15: {high_t4}/{len(failures)}")
print(f"  cons_up>=3:   {high_cu}/{len(failures)}")
print(f"  peak_decay>3: {high_pk}/{len(failures)}")
print(f"  WR<15:        {low_wr}/{len(failures)}")
print(f"  VR>2.0:       {high_vr}/{len(failures)}")

# 对比成功日的特征
print(f"\n【成功vs失败特征对比】")
for feat_name, key in [("p%", "p"), ("WR", "wr"), ("VR", "vr"), ("CL", "cl"), ("HSL", "hsl"), ("slope5", "slope5"), ("t4_shadow", "t4_shadow"), ("cons_up", "cons_up"), ("peak_decay", "peak_decay"), ("扣分", "penalty")]:
    fail_avg = round(sum(r[key] for r in failures) / len(failures), 1)
    succ_avg = round(sum(r[key] for r in successes) / len(successes), 1)
    diff = fail_avg - succ_avg
    arrow = "⬆" if diff > 0 else "⬇" if diff < 0 else "="
    print(f"  {feat_name:>10}: 失败={fail_avg:>8}  成功={succ_avg:>8}  差={diff:>+7.1f}{arrow}")
