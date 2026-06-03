"""03-06 虚涨日详细分解"""
import pickle, os, sys, importlib
sys.path.insert(0, "release/V13")

V13_DIR = "release/V13"
with open(os.path.join(V13_DIR, "big_cache_full.pkl"), "rb") as f:
    d = pickle.load(f)
data, real, names = d["data"], d["real"], d["names"]

def load_mod(name):
    fp = "release/V14/评分策略/" + f"分而治之_V10_{name}_评分策略.py"
    spec = importlib.util.spec_from_file_location(name, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

mod = load_mod("虚涨日")
LO = ["L0","L1","L2","L3","L4"]

def compute_7day_penalty(code, dt, p_today):
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
    return penalty, gains[-7:]

dt = "2026-03-06"
ss = data.get(dt, [])
ss = [s for s in ss if (s.get("p",0) or 0) < 15]

lv = {"name":"L1","p_min":4,"p_max":7,"vr_min":0.6,"vr_max":2.0,"hs_min":5,"hs_max":20,"sz_max":200,"cl_min":30,"cl_max":90}
cand = []
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

print(f"03-06 虚涨日 池={len(cand)}只")
print()

scored = []
for s in cand:
    code = s["code"]
    p_val = s.get("p",0) or 0
    cl_val = s.get("cl",50)
    vr_val = s.get("vol_ratio",1) or s.get("vr",1)
    wr_val = s.get("wr_val",50) or s.get("wrv",50)
    hsl_val = real.get(code,{}).get("hsl",0) or 0
    dif_val = s.get("dif_val",0) or s.get("dif",0)
    mg_val = s.get("macd_golden",0) or s.get("mg",0)
    a5_val = s.get("above_ma5",0)
    pos_val = s.get("pos_in_day",50)
    nh = s.get("n",0) or 0
    
    stock_dict = {
        "p": p_val, "cl": cl_val, "vr": vr_val,
        "dif": dif_val, "mg": mg_val, "wrv": wr_val,
        "jv": s.get("j_val",0) or s.get("jv",50),
        "kv": s.get("k_val",0) or s.get("kv",50),
        "dv": s.get("d_val",0) or s.get("dv",50),
        "a5": a5_val, "kdj_g": s.get("kdj_golden",0) or s.get("kdj_g",0),
        "pos_in_day": pos_val,
        "nm": names.get(code,""), "hsl": hsl_val,
        "d1": 0, "d2": 0, "d3": 0,
    }
    raw_sc = mod.score(stock_dict)
    penalty, gains_7d = compute_7day_penalty(code, dt, p_val)
    final_sc = round(raw_sc + penalty, 1)
    
    p_contrib = round(p_val * 1.5, 1)
    cl_contrib = round(cl_val * 0.05, 1)
    vr_contrib = 5 if 1.2 <= vr_val < 2.0 else (8 if vr_val >= 2.0 else 0)
    wr_pen = -5 if wr_val > 50 else 0
    hsl_pen = -8 if hsl_val > 12 else 0
    dif_bonus = 3 if dif_val > 0.5 else 0
    
    scored.append({
        "code": code, "name": names.get(code,"?"),
        "p": p_val, "cl": cl_val, "nh": nh, "raw": raw_sc, "pen": penalty, "final": final_sc,
        "p_con": p_contrib, "cl_con": cl_contrib, "vr_con": vr_contrib,
        "wr_pen": wr_pen, "hsl_pen": hsl_pen, "dif_con": dif_bonus,
        "wr": wr_val, "vr": vr_val, "hsl": hsl_val, "dif": dif_val,
        "mg": mg_val, "a5": a5_val, "pos": pos_val,
        "gains_7d": gains_7d,
    })

scored.sort(key=lambda x: -x["final"])

print(f"{'排名':>4} {'代码':>8} {'名称':>10} {'nh%':>5} {'结果':>4} {'总分':>6} {'扣分':>4} {'p×1.5':>6} {'CL×0.05':>8} {'VR':>4} {'WR罚':>4} {'HSL':>4} {'DIF':>4} {'WR':>4} {'VR':>4} {'HSL%':>5} {'MG':>2}")
print("-"*100)
for i, r in enumerate(scored[:15]):
    flag = "✅" if r["nh"] >= 2.5 else "❌"
    g7 = r["gains_7d"]
    g7_str = " ".join(f"{x:+.1f}" for x in g7)
    print(f' #{i+1:>2} {r["code"]:>8} {r["name"]:>10} {r["nh"]:>+5.1f} {flag} {r["final"]:>6.1f} {r["pen"]:>4} {r["p_con"]:>6.1f} {r["cl_con"]:>8.1f} {r["vr_con"]:>4} {r["wr_pen"]:>4} {r["hsl_pen"]:>4} {r["dif_con"]:>4} {r["wr"]:>4.0f} {r["vr"]:>4.2f} {r["hsl"]:>5.1f} {r["mg"]:>2}')

# 华胜天成 vs 可立克 : why?
print()
for code in ["600410", "002782", "600391", "002800"]:
    r = next((x for x in scored if x["code"] == code), None)
    if r:
        g7 = r["gains_7d"]
        g7_str = " -> ".join(f"{x:+.1f}" for x in g7)
        print(f'{r["name"]}({code}): 评分={r["final"]} 扣分={r["pen"]} nh={r["nh"]:+.1f}%')
        print(f'  7天: {g7_str}')
