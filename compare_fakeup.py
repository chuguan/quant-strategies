"""V13原版 vs V14优化版 — 虚涨日对比回测"""
import pickle, os, sys, importlib
sys.path.insert(0, "release/V13")
sys.path.insert(0, ".")

with open("release/V13/big_cache_full.pkl", "rb") as f:
    d = pickle.load(f)
data, real, names = d["data"], d["real"], d["names"]

def mkt_class(stocks):
    if not stocks: return "flat"
    ps = [s.get("p",0) or 0 for s in stocks]
    vrs = [s.get("vol_ratio",0) or 0 for s in stocks if s.get("vol_ratio",0)]
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return "fake_up" if hot<15 or av<0.9 else "real_up"
    if ap<-0.5: return "down"
    return "flat"

def load_mod(path, name):
    fp = os.path.join(path, "评分策略", f"分而治之_V10_{name}_评分策略.py")
    spec = importlib.util.spec_from_file_location(name, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def run_backtest(version_dir, label):
    """Run backtest for 虚涨日 only"""
    STRATS = {}
    for n in ["真实涨日", "虚涨日", "跌日", "横盘"]:
        STRATS[n] = load_mod(version_dir, n)
    MK_MAP = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
    LO = ["L0","L1","L2","L3","L4"]
    
    dates = sorted(k for k in data.keys() if "2026-04-08" <= k <= "2026-05-28")
    results = []
    no_pool = []
    
    for dt in dates:
        ss = data.get(dt, [])
        ss = [s for s in ss if (s.get("p",0) or 0) < 15]
        if not ss: continue
        mk = mkt_class(ss)
        if mk != "fake_up": continue
        
        mk_cn = "虚涨日"
        mod = STRATS[mk_cn]; LEVELS = mod.LEVELS
        lm = {l["name"]: i for i, l in enumerate(LEVELS)}
        pool = None
        for ln in LO:
            if ln not in lm: continue
            i = lm[ln]; lv = LEVELS[i]; cand = []
            for s in ss:
                p = s.get("p",0) or 0
                if p < lv["p_min"] or p > min(lv.get("p_max",10), 8): continue
                vr = s.get("vol_ratio",0) or 0
                if vr < lv["vr_min"] or vr > lv["vr_max"]: continue
                ri = real.get(s["code"],{}); hsl = ri.get("hsl",0) or 0
                if hsl < lv.get("hs_min",0) or hsl > lv.get("hs_max",99): continue
                if (ri.get("shizhi",0) or 0) >= lv.get("sz_max",9999): continue
                nm = names.get(s["code"],"")
                if "ST" in nm or "*ST" in nm or "退" in nm: continue
                cl = s.get("cl",0)
                if cl < lv.get("cl_min",0) or cl > lv.get("cl_max",100): continue
                cand.append(s)
            if len(cand) >= 10: pool = cand; break
        if not pool: no_pool.append(dt); continue
        
        # Score with this version's scoring
        scored = [(mod.score({
            "p": s.get("p",0) or 0,
            "cl": s.get("cl",50),
            "vr": s.get("vol_ratio",1) or s.get("vr",1),
            "dif": s.get("dif_val",0) or s.get("dif",0),
            "mg": s.get("macd_golden",0) or s.get("mg",0),
            "wrv": s.get("wr_val",0) or s.get("wrv",50),
            "jv": s.get("j_val",0) or s.get("jv",50),
            "kv": s.get("k_val",0) or s.get("kv",50),
            "dv": s.get("d_val",0) or s.get("dv",50),
            "a5": s.get("above_ma5",0),
            "kdj_g": s.get("kdj_golden",0) or s.get("kdj_g",0),
            "pos_in_day": s.get("pos_in_day",50),
            "nm": s.get("nm","") or s.get("name","") or names.get(s["code"],""),
            "hsl": real.get(s["code"],{}).get("hsl",0) or 0,
            "d1": 0, "d2": 0, "d3": 0,  # V14 might use these
        }), s) for s in pool]
        scored.sort(key=lambda x: -x[0])
        champ = scored[0][1]; champ_sc = scored[0][0]
        nh = champ.get("n",0) or 0
        nm = names.get(champ["code"],"?")
        p = champ.get("p",0)
        wrv = champ.get("wr_val",50) or champ.get("wrv",50)
        vr = champ.get("vol_ratio",1) or champ.get("vr",1)
        cl_ = champ.get("cl",50)
        hsl = real.get(champ["code"],{}).get("hsl",0) or 0
        
        win = 1 if nh >= 2.5 else 0
        results.append({
            "date":dt,"code":champ["code"],"name":nm,"p":p,
            "score":champ_sc,"nh":nh,"win":win,
            "wr":wrv,"vr":vr,"cl":cl_,"hsl":hsl,"pool":len(pool),
        })
    
    wins = sum(1 for r in results if r["win"])
    return wins, len(results), results

# Run both versions
w13, t13, r13 = run_backtest("release/V13", "V13")
w14, t14, r14 = run_backtest("release/V14", "V14")

print(f"虚涨日对比: V13原版 vs V14优化版")
print(f"{'日期':>12} {'代码':>8} {'名称':>10} {'p%':>5} {'V13评分':>7} {'V14评分':>7} {'nh%':>5} {'结果':>4}")
print("-"*65)
for r13_i in r13:
    # Find matching date in V14
    r14_i = next((r for r in r14 if r["date"] == r13_i["date"]), None)
    v13_sc = r13_i["score"]
    v14_sc = r14_i["score"] if r14_i else 0
    flag = "✅" if r13_i["win"] else "❌"
    diff = v14_sc - v13_sc
    arrow = "↑" if diff>0 else "↓" if diff<0 else "="
    print(f'{r13_i["date"]} {r13_i["code"]:>8} {r13_i["name"]:>10} {r13_i["p"]:>5.1f} {v13_sc:>7.1f} {v14_sc:>7.1f}({arrow}{diff:+.0f}) {r13_i["nh"]:>+5.1f} {flag}')

# Compare DAY BY DAY who wins
print(f"\nV13: {w13}/{t13} = {w13*100/t13:.1f}% (池大小={[r['pool'] for r in r13]})")
print(f"V14: {w14}/{t14} = {w14*100/t14:.1f}% (池大小={[r['pool'] for r in r14]})")

if r13 and r14:
    same_champ = sum(1 for r13_i in r13 for r14_i in r14 if r13_i["date"]==r14_i["date"] and r13_i["code"]==r14_i["code"])
    diff_champ = t13 - same_champ
    print(f"\n冠军相同: {same_champ}天")
    print(f"冠军不同: {diff_champ}天")
    if diff_champ > 0:
        print(f"冠军不同时的明细:")
        for r13_i in r13:
            r14_i = next((r for r in r14 if r["date"] == r13_i["date"]), None)
            if r14_i and r13_i["code"] != r14_i["code"]:
                print(f'  {r13_i["date"]}: V13={r13_i["name"]}({r13_i["code"]}) sc={r13_i["score"]:.1f} nh={r13_i["nh"]:+.1f}% → V14={r14_i["name"]}({r14_i["code"]}) sc={r14_i["score"]:.1f} nh={r14_i["nh"]:+.1f}%')
