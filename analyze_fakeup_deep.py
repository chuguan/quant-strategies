"""深析虚涨日V13 vs V14：失败日和成功日特征对比"""
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

def load_mod_v14(name):
    fp = "release/V14/评分策略/" + f"分而治之_V10_{name}_评分策略.py"
    spec = importlib.util.spec_from_file_location(f"v14_{name}", fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

STRATS_V14 = {}
for n in ["真实涨日", "虚涨日", "跌日", "横盘"]:
    STRATS_V14[n] = load_mod_v14(n)

MK_MAP = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
LO = ["L0","L1","L2","L3","L4"]

# 直接对每个虚涨日分析TOP10评分分解
fake_up_dates = []
for dt in sorted(data.keys()):
    if dt < "2026-01-01" or dt > "2026-05-28": continue
    ss = data.get(dt, [])
    ss = [s for s in ss if (s.get("p",0) or 0) < 15]
    if not ss: continue
    mk = mkt_class(ss)
    if mk == "fake_up":
        fake_up_dates.append(dt)

print("=== 虚涨日逐日TOP5对比：V13原版评分 vs V14优化版评分（无动量+扣分，纯评分函数对比） ===\n")

for dt in fake_up_dates:
    ss = data.get(dt, [])
    ss = [s for s in ss if (s.get("p",0) or 0) < 15]
    
    # 用LEVELS L1选池（统一池子）
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
    
    if len(cand) < 5: continue
    
    # 对每个候选股算V13评分和V14评分
    mod = STRATS_V14["虚涨日"]
    scored_info = []
    
    # Also compute V13-style simple score for comparison
    def v13_score_simple(s):
        """V13原版虚涨日评分：p*0.5 + cl*0.05 + macd_score*1 + dif_bonus(2)"""
        p = s.get("p",0) or 0
        cl = s.get("cl",50)
        dif = s.get("dif_val",0) or s.get("dif",0)
        mg = s.get("macd_golden",0) or s.get("mg",0)
        dif_ = dif; mg_ = mg
        ms = 0
        if mg_ and dif_>0.5: ms=10
        elif mg_ and dif_>0.2: ms=8
        elif mg_: ms=6
        elif dif_>0.5: ms=4
        elif dif_>0: ms=2
        return round(p*0.5 + cl*0.05 + ms*1 + (2 if dif_>0.5 else 0), 1)
    
    for s in cand:
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
        v13_sc = v13_score_simple(s)
        v14_sc = mod.score(stock_dict)
        nh = s.get("n",0) or 0
        scored_info.append({
            "code": s["code"], "name": names.get(s["code"],"?"),
            "p": s.get("p",0) or 0, "nh": nh, "v13_sc": v13_sc, "v14_sc": v14_sc,
            "wr": s.get("wr_val",50) or s.get("wrv",50),
            "vr": s.get("vol_ratio",1) or s.get("vr",1),
            "cl": s.get("cl",50),
            "hsl": real.get(s["code"],{}).get("hsl",0) or 0,
            "dif": s.get("dif_val",0) or s.get("dif",0),
            "mg": s.get("macd_golden",0) or s.get("mg",0),
            "a5": s.get("above_ma5",0),
            "pos_in_day": s.get("pos_in_day",50),
            "shizhi": real.get(s["code"],{}).get("shizhi",0) or 0,
        })
    
    # Sort by V13
    by_v13 = sorted(scored_info, key=lambda x: -x["v13_sc"])
    by_v14 = sorted(scored_info, key=lambda x: -x["v14_sc"])
    
    print(f"【{dt} 虚涨日】池={len(cand)}只")
    print(f"{'排名':>4} {'代码':>8} {'名称':>10} {'p%':>5} {'nh%':>5} {'V13':>6} {'V14':>6} {'WR':>4} {'VR':>4} {'CL':>3} {'HSL':>5} {'DIF':>5} {'MG':>2} {'A5':>2} {'POS':>3}")
    print("-"*90)
    
    for i in range(min(10, len(scored_info))):
        v13_top = by_v13[i]
        v14_match = next((x for x in by_v14 if x["code"] == v13_top["code"]), None)
        v14_rank = next((j for j,x in enumerate(by_v14) if x["code"] == v13_top["code"]), -1) + 1
        
        flag = "✅" if v13_top["nh"] >= 2.5 else "❌"
        print(f' #{i+1:>2}/{v14_rank:>2} {v13_top["code"]:>8} {v13_top["name"]:>10} {v13_top["p"]:>5.1f} {v13_top["nh"]:>+5.1f} {flag} {v13_top["v13_sc"]:>6.1f} {v14_match["v14_sc"] if v14_match else 0:>6.1f} {v13_top["wr"]:>4.0f} {v13_top["vr"]:>4.2f} {v13_top["cl"]:>3.0f} {v13_top["hsl"]:>5.1f} {v13_top["dif"]:>+5.2f} {v13_top["mg"]:>2} {v13_top["a5"]:>2} {v13_top["pos_in_day"]:>3.0f}')
    
    # Show V14冠军
    v14_champ = by_v14[0]
    v13_champ = by_v13[0]
    print(f"\n  V13#1: {v13_champ['name']}({v13_champ['code']}) sc={v13_champ['v13_sc']} nh={v13_champ['nh']:+.1f}%")
    print(f"  V14#1: {v14_champ['name']}({v14_champ['code']}) sc={v14_champ['v14_sc']} nh={v14_champ['nh']:+.1f}%")
    print(f"  V14为什么选{v14_champ['name']}？")
    if v14_champ["code"] != v13_champ["code"]:
        # 评分分解
        p_contrib = v14_champ["p"]*2.0  # p_w=2.0
        cl_contrib = v14_champ["cl"]*0.05
        vr_contrib = 0
        if v14_champ["vr"] >= 1.2: vr_contrib = 8
        if v14_champ["vr"] >= 2.0: vr_contrib = 12
        wr_pen = -8 if v14_champ["wr"] < 15 else 0
        hsl_pen = -8 if v14_champ["hsl"] > 12 else 0
        dif_bonus = 5 if v14_champ["dif"] > 0.5 else 0
        print(f"    p×2.0={p_contrib:.0f} + CL×0.05={cl_contrib:.1f} + VR={vr_contrib} + DIF={dif_bonus} + WRpen={wr_pen} + HSLpen={hsl_pen}")
    else:
        print(f"    与V13相同冠军")
    print()
