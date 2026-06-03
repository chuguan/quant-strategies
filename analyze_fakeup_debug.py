"""虚涨日TOP10完整评分分解（含7天扣分）"""
import pickle, os, sys, importlib
sys.path.insert(0, "release/V13")

V13_DIR = "release/V13"
with open(os.path.join(V13_DIR, "big_cache_full.pkl"), "rb") as f:
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

def load_mod(name):
    fp = "release/V14/评分策略/" + f"分而治之_V10_{name}_评分策略.py"
    spec = importlib.util.spec_from_file_location(name, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

STRATS_V14 = {}
for n in ["真实涨日", "虚涨日", "跌日", "横盘"]:
    STRATS_V14[n] = load_mod(n)
MK_MAP = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
LO = ["L0","L1","L2","L3","L4"]

def compute_7day_decay_penalty(code, dt, p_today):
    all_dates = sorted(data.keys())
    idx = all_dates.index(dt)
    prev = all_dates[max(0,idx-6):idx]
    gains = []
    for pd in prev:
        found = False
        for s in data[pd]:
            if s["code"] == code:
                gains.append(s.get("p",0) or 0)
                found = True; break
        if not found: gains.append(0)
    gains.append(p_today)
    n = len(gains)
    if n < 5: return 0
    d6,d5,d4,d3,d2,d1,p = gains[-7:] if n>=7 else [0]*(7-n) + gains
    p_is_max = p >= max(gains[:-1]) if len(gains) > 1 else True
    avg_7d = sum(gains)/n
    wrv = 50
    for s in data.get(dt, []):
        if s["code"] == code: wrv = s.get("wr_val",50) or s.get("wrv",50); break
    penalty = 0
    if wrv<10 and p_is_max and avg_7d<2.0 and p<6: penalty -= 8
    if p_is_max and avg_7d<0.8 and p<8:
        if avg_7d<0: penalty -= 15
        elif avg_7d<0.3: penalty -= 12
        elif avg_7d<0.7: penalty -= 8
        else: penalty -= 5
    if d1<-1.5 and d2<-1.0 and p>3 and avg_7d<1.0: penalty -= 8
    if max(d4,d3,d2)>5 and d1<0 and d2<0: penalty -= 10
    if n>=5 and d5>d1 and d5>d2 and p<=d5:
        recent_sum = (d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
        if recent_sum<=2: penalty -= 8
    if n>=5:
        last5 = gains[-5:]
        if all(last5[i]>=last5[i+1] for i in range(len(last5)-1)): penalty -= 10
    return penalty

# Focus on 02-03 and 03-27
targets = ["2026-02-03", "2026-03-27"]

for dt in sorted(data.keys()):
    if dt not in targets: continue
    ss = data.get(dt, [])
    ss = [s for s in ss if (s.get("p",0) or 0) < 15]
    if not ss: continue
    mk = mkt_class(ss)
    if mk != "fake_up": continue
    
    mod = STRATS_V14["虚涨日"]
    LEVELS = mod.LEVELS
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
    
    if not pool or len(pool) < 5: 
        print(f"\n{dst} 池<5只，跳过")
        continue
    
    print(f"\n{'='*80}")
    print(f"【{dt} 虚涨日】池={len(pool)}只 - V14评分完全分解")
    print(f"{'='*80}")
    
    scored = []
    for s in pool:
        stock_dict = {
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
            "d1": 0, "d2": 0, "d3": 0,
        }
        raw_sc = mod.score(stock_dict)
        penalty = compute_7day_decay_penalty(s["code"], dt, s.get("p",0) or 0)
        final_sc = round(raw_sc + penalty, 1)
        nh = s.get("n",0) or 0
        
        # Score breakdown
        p_val = s.get("p",0) or 0
        cl_val = s.get("cl",50)
        vr_val = s.get("vol_ratio",1) or s.get("vr",1)
        wr_val = s.get("wr_val",50) or s.get("wrv",50)
        hsl_val = real.get(s["code"],{}).get("hsl",0) or 0
        dif_val = s.get("dif_val",0) or s.get("dif",0)
        mg_val = s.get("macd_golden",0) or s.get("mg",0)
        a5_val = s.get("above_ma5",0)
        
        scored.append({
            "code": s["code"], "name": names.get(s["code"],"?"),
            "p": p_val, "nh": nh,
            "raw_sc": raw_sc, "penalty": penalty, "final_sc": final_sc,
            "p_contrib": round(p_val * 1.5, 1),  # p_w=1.5
            "cl_contrib": round(cl_val * 0.10, 1),  # cl_w=0.10
            "vr_contrib": 5 if 1.2 <= vr_val < 2.0 else (8 if vr_val >= 2.0 else 0),
            "wr_bonus": 5 if wr_val < 15 else 0,
            "wr_pen": -5 if wr_val > 50 else 0,
            "hsl_pen": -8 if hsl_val > 12 else 0,
            "dif_bonus": 3 if dif_val > 0.5 else 0,
            "macd": mg_val,
            "wr": wr_val, "vr": vr_val, "cl": cl_val, "hsl": hsl_val,
            "dif": dif_val,
            "shizhi": real.get(s["code"],{}).get("shizhi",0) or 0,
            "a5": a5_val,
        })
    
    scored.sort(key=lambda x: -x["final_sc"])
    
    print(f"\n{'排名':>4} {'代码':>8} {'名称':>10} {'nh%':>5} {'结果':>4} {'总分':>6} {'原始分':>6} {'扣分':>4} {'p×1.5':>6} {'CL×0.1':>6} {'VR+':>4} {'WR奖':>4} {'WR罚':>4} {'HSL':>4} {'DIF':>4} {'WR':>4} {'VR':>4} {'CL':>3} {'HSL%':>5}")
    print("-"*120)
    
    for i, r in enumerate(scored):
        flag = "✅" if r["nh"] >= 2.5 else "❌"
        print(f' #{i+1:>2} {r["code"]:>8} {r["name"]:>10} {r["nh"]:>+5.1f} {flag} {r["final_sc"]:>6.1f} {r["raw_sc"]:>6.1f} {r["penalty"]:>4} {r["p_contrib"]:>6.1f} {r["cl_contrib"]:>6.1f} {r["vr_contrib"]:>4} {r["wr_bonus"]:>4} {r["wr_pen"]:>4} {r["hsl_pen"]:>4} {r["dif_bonus"]:>4} {r["wr"]:>4.0f} {r["vr"]:>4.2f} {r["cl"]:>3.0f} {r["hsl"]:>5.1f}')
        if i >= 14: break  # Show top 15 only
    
    # What if we check: best nh in pool
    best_in_pool = max(pool, key=lambda s: (s.get("n",0) or 0))
    best_nh = best_in_pool.get("n",0) or 0
    best_nm = names.get(best_in_pool["code"],"?")
    print(f"\n  池中nh最高的: {best_nm}({best_in_pool['code']}) nh={best_nh:+.1f}%")
