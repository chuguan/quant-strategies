"""V40 独立管道回测 — 横盘自控，其他3个照旧用外部动量"""
import pickle, os, sys, importlib.util

V40_DIR = "release/V40"
sys.path.insert(0, V40_DIR)

with open(os.path.join(V40_DIR, "big_cache_full.pkl"), "rb") as f:
    d = pickle.load(f)
data, real, names = d["data"], d["real"], d["names"]
with open(os.path.join(V40_DIR, "features_30d.pkl"), "rb") as f:
    precomputed = pickle.load(f)
all_dates = sorted(data.keys())

def mkt_class(stocks):
    if not stocks: return "flat"
    ps = [s.get("p",0) or 0 for s in stocks]
    vrs = [s.get("vol_ratio",0) or 0 for s in stocks if s.get("vol_ratio",0)]
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if ap > 0.5: return "fake_up" if hot < 15 or av < 0.9 else "real_up"
    if ap < -0.5: return "down"
    return "flat"

def load_mod(name):
    fp = os.path.join(V40_DIR, "评分策略", f"分而治之_V10_{name}_评分策略.py")
    spec = importlib.util.spec_from_file_location(name + "_v40b", fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

STRATS = {}
MK_MAP = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
LO = ["L0","L1","L2","L3","L4"]
for n in ["真实涨日","虚涨日","跌日","横盘"]:
    STRATS[n] = load_mod(n)

# 全局动量过滤（仅真实涨日/虚涨日/跌日用，横盘不用）
def is_momentum_exhausted(s, code, dt):
    feats = precomputed.get((code, dt), {})
    if not feats: return False
    sl5 = feats.get("slope5",0); t4s = feats.get("t4_shadow",0)
    cu = feats.get("cons_up",0); pk = feats.get("peak_decay",0); pv = s.get("p",0) or 0
    if sl5>8 and t4s>25: return True
    if sl5>10 and t4s>18: return True
    if cu>=5 and sl5>15: return True
    if pk>5 and sl5>5 and pv<6: return True
    if sl5>5 and t4s>30: return True
    if cu>=4 and sl5>10 and pv<7: return True
    return False

def compute_7day_penalty(code, dt, p_today):
    """仅真实涨日/虚涨日/跌日用，横盘不用"""
    idx = all_dates.index(dt)
    prev = all_dates[max(0, idx-6):idx]
    gains = []
    for pd in prev:
        found = False
        for s in data[pd]:
            if s["code"] == code:
                gains.append(s.get("p",0) or 0); found = True; break
        if not found: gains.append(0)
    gains.append(p_today); n = len(gains)
    if n < 5: return 0
    d6,d5,d4,d3,d2,d1,pt = gains[-7:] if n>=7 else [0]*(7-n)+gains
    p_is_max = pt>=max(gains[:-1]) if len(gains)>1 else True; avg_7d = sum(gains)/n
    wrv = 50
    for s in data.get(dt,[]):
        if s["code"]==code: wrv = s.get("wr_val",50) or s.get("wrv",50); break
    penalty = 0
    if wrv<10 and p_is_max and avg_7d<2.0 and pt<6: penalty -= 8
    if p_is_max and avg_7d<0.8 and pt<8:
        if avg_7d<0: penalty -= 15
        elif avg_7d<0.3: penalty -= 12
        elif avg_7d<0.7: penalty -= 8
        else: penalty -= 5
    if d1<-1.5 and d2<-1.0 and pt>3 and avg_7d<1.0: penalty -= 8
    if max(d4,d3,d2)>5 and d1<0 and d2<0: penalty -= 10
    if n>=5 and d5>d1 and d5>d2 and pt<=d5:
        recent = (d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
        if recent<=2: penalty -= 8
    if n>=5:
        last5 = gains[-5:]
        if all(last5[i]>=last5[i+1] for i in range(len(last5)-1)): penalty -= 10
    return penalty

def build_stock_dict(s, code, dt):
    """构建传给score()的完整字典（含特征+7天数据）"""
    stock = {}
    stock["code"] = code
    stock["p"] = s.get("p",0) or 0; stock["cl"] = s.get("cl",50)
    stock["vr"] = s.get("vol_ratio",1) or s.get("vr",1)
    stock["dif"] = s.get("dif_val",0) or s.get("dif",0)
    stock["mg"] = s.get("macd_golden",0) or s.get("mg",0)
    stock["wrv"] = s.get("wr_val",0) or s.get("wrv",50)
    stock["jv"] = s.get("j_val",0) or s.get("jv",50)
    stock["kv"] = s.get("k_val",0) or s.get("kv",50)
    stock["dv"] = s.get("d_val",0) or s.get("dv",50)
    stock["a5"] = s.get("above_ma5",0); stock["kdj_g"] = s.get("kdj_golden",0) or s.get("kdj_g",0)
    stock["pos_in_day"] = s.get("pos_in_day",50)
    stock["nm"] = s.get("nm","") or s.get("name","") or names.get(code,"")
    ri = real.get(code,{}); stock["hsl"] = ri.get("hsl",0) or 0
    
    feats = precomputed.get((code, dt), {})
    stock["t4_shadow"] = feats.get("t4_shadow",0); stock["slope5"] = feats.get("slope5",0)
    stock["cons_up"] = feats.get("cons_up",0); stock["peak_decay"] = feats.get("peak_decay",0)
    stock["d1"] = feats.get("d1",0); stock["d2"] = feats.get("d2",0); stock["d3"] = feats.get("d3",0)
    stock["feats_ok"] = bool(feats)
    
    # 7天数据
    idx = all_dates.index(dt)
    prev = all_dates[max(0, idx-6):idx]
    gains_7d = []
    for pd in prev:
        found = False
        for sx in data[pd]:
            if sx["code"] == code:
                gains_7d.append(sx.get("p",0) or 0); found = True; break
        if not found: gains_7d.append(0)
    gains_7d.append(stock["p"])
    stock["gains_7d"] = gains_7d
    stock["_7d_avg"] = sum(gains_7d) / len(gains_7d)
    stock["_7d_p_is_max"] = stock["p"] >= max(gains_7d[:-1]) if len(gains_7d) > 1 else True
    
    return stock

# ═══ 4行情独立回测 ═══
dates = sorted(k for k in data.keys() if "2026-02-01" <= k <= "2026-05-28")
by = {}
flat_self_controlled = True  # 横盘自控

for dt in dates:
    ss = data.get(dt, [])
    ss = [s for s in ss if (s.get("p",0) or 0) < 15]
    if not ss: continue
    
    mk = mkt_class(ss); mc = MK_MAP.get(mk, "横盘")
    mod = STRATS[mc]
    LEVELS = mod.LEVELS
    lm = {l["name"]: i for i, l in enumerate(LEVELS)}
    pool = None; used_level = ""
    
    is_flat = (mc == "横盘")
    
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
            if lv.get("a5_req",0) and not s.get("above_ma5",0): continue
            if lv.get("kdj_g_req",0) and not (s.get("kdj_golden",0) or s.get("kdj_g",0)): continue
            # 动量过滤：横盘不用外部过滤
            if not is_flat and is_momentum_exhausted(s, s["code"], dt):
                continue
            cand.append(s)
        if len(cand) >= 10: pool = cand; used_level = ln; break
    if not pool: continue
    
    scored = []
    for s in pool:
        sd = build_stock_dict(s, s["code"], dt)
        base_sc = mod.score(sd)
        # 7天扣分：横盘不用外部扣分
        if not is_flat:
            penalty = compute_7day_penalty(s["code"], dt, s.get("p",0) or 0)
        else:
            penalty = 0
        scored.append((round(base_sc + penalty, 1), s))
    
    scored.sort(key=lambda x: -x[0])
    nh = scored[0][1].get("n",0) or 0
    win = 1 if nh >= 2.5 else 0
    if mc not in by: by[mc] = {"w":0,"t":0}
    by[mc]["w"] += win; by[mc]["t"] += 1

print("V40 独立管道 (横盘自控, 其他照旧):")
print()
tw = 0; tt = 0
for mk in ["真实涨日","虚涨日","跌日","横盘"]:
    if mk in by:
        w = by[mk]["w"]; t = by[mk]["t"]
        tw += w; tt += t
        print(f"  {mk}: {w}/{t} = {w*100/t:.0f}%")
print(f"  总计: {tw}/{tt} = {tw*100/tt:.1f}%")
print(f"  V39(横盘原版): 59/74=79.7%")
