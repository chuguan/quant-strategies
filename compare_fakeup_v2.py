"""完整V13管道对比：V13原版评分 vs V14优化版评分（虚涨日专项）"""
import pickle, os, sys, importlib
sys.path.insert(0, "release/V13")

V13_DIR = "release/V13"
with open(os.path.join(V13_DIR, "big_cache_full.pkl"), "rb") as f:
    d = pickle.load(f)
data, real, names = d["data"], d["real"], d["names"]
with open(os.path.join(V13_DIR, "features_30d.pkl"), "rb") as f:
    precomputed = pickle.load(f)

def mkt_class(stocks):
    if not stocks: return "flat"
    ps = [s.get("p",0) or 0 for s in stocks]
    vrs = [s.get("vol_ratio",0) or 0 for s in stocks if s.get("vol_ratio",0)]
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return "fake_up" if hot<15 or av<0.9 else "real_up"
    if ap<-0.5: return "down"
    return "flat"

def load_mod_v13(name):
    fp = os.path.join(V13_DIR, "评分策略", f"分而治之_V10_{name}_评分策略.py")
    spec = importlib.util.spec_from_file_location(f"v13_{name}", fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def load_mod_v14(name):
    fp = "release/V14/评分策略/" + f"分而治之_V10_{name}_评分策略.py"
    spec = importlib.util.spec_from_file_location(f"v14_{name}", fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

STRATS_V13 = {}
STRATS_V14 = {}
for n in ["真实涨日", "虚涨日", "跌日", "横盘"]:
    STRATS_V13[n] = load_mod_v13(n)
    STRATS_V14[n] = load_mod_v14(n)

MK_MAP = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
LO = ["L0","L1","L2","L3","L4"]

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

def get_feats(code, dt):
    return precomputed.get((code, dt), {})

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

def run_backtest(STRATS, label):
    dates = sorted(k for k in data.keys() if "2026-01-01" <= k <= "2026-05-28")
    results = []
    for dt in dates:
        ss = data.get(dt, [])
        ss = [s for s in ss if (s.get("p",0) or 0) < 15]
        if not ss: continue
        mk = mkt_class(ss)
        if mk != "fake_up": continue
        mk_cn = "虚涨日"
        mod = STRATS[mk_cn]; LEVELS = mod.LEVELS
        lm = {l["name"]: i for i, l in enumerate(LEVELS)}
        pool = None; eliminated = 0
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
                if is_momentum_exhausted(s, s["code"], dt):
                    eliminated += 1; continue
                cand.append(s)
            if len(cand) >= 10: pool = cand; break
        if not pool: continue
        
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
            "d1": get_feats(s["code"], dt).get("d1",0),
            "d2": get_feats(s["code"], dt).get("d2",0),
            "d3": get_feats(s["code"], dt).get("d3",0),
        }) + compute_7day_decay_penalty(s["code"], dt, s.get("p",0) or 0), s)
        for s in pool]
        scored.sort(key=lambda x: -x[0])
        champ = scored[0][1]; champ_sc = scored[0][0]
        nh = champ.get("n",0) or 0
        nm = names.get(champ["code"],"?")
        p = champ.get("p",0)
        code = champ["code"]
        win = 1 if nh >= 2.5 else 0
        results.append({
            "date":dt,"code":code,"name":nm,"p":p,"score":champ_sc,"nh":nh,"win":win,
        })
    return results

r13 = run_backtest(STRATS_V13, "V13")
r14 = run_backtest(STRATS_V14, "V14")

print(f"{'='*65}")
print(f"虚涨日对比: V13原版 vs V14优化版 (完整管道+动量过滤+7天扣分)")
print(f"{'='*65}")
print(f"{'日期':>12} {'代码':>8} {'名称':>10} {'p%':>5} {'V13评分':>7} {'V14评分':>7} {'nh%':>5} {'V13':>4} {'V14':>4}")
print(f"{'-'*65}")
for r13_i in r13:
    r14_i = next((r for r in r14 if r["date"] == r13_i["date"]), None)
    v13_sc = r13_i["score"]; v14_sc = r14_i["score"] if r14_i else 0
    v13_f = "✅" if r13_i["win"] else "❌"
    v14_f = "✅" if r14_i and r14_i["win"] else "❌"
    diff = v14_sc - v13_sc
    arrow = "↑" if diff>0 else "↓" if diff<0 else "="
    print(f'{r13_i["date"]} {r13_i["code"]:>8} {r13_i["name"]:>10} {r13_i["p"]:>5.1f} {v13_sc:>7.1f} {v14_sc:>7.1f}({arrow}{diff:+.0f}) {r13_i["nh"]:>+5.1f} {v13_f:>4} {v14_f:>4}')

w13 = sum(1 for r in r13 if r["win"])
w14 = sum(1 for r in r14 if r["win"])
print(f"\nV13: {w13}/{len(r13)} = {w13*100/len(r13):.1f}%")
print(f"V14: {w14}/{len(r14)} = {w14*100/len(r14):.1f}%")

# 冠军不同分析
same_champ = sum(1 for r13_i in r13 for r14_i in r14 if r13_i["date"]==r14_i["date"] and r13_i["code"]==r14_i["code"])
print(f"\n冠军相同: {same_champ}/{len(r13)}")
print(f"冠军不同: {len(r13)-same_champ}/{len(r13)}")
if len(r13)-same_champ > 0:
    print("不同时:")
    for r13_i in r13:
        r14_i = next((r for r in r14 if r["date"] == r13_i["date"]), None)
        if r14_i and r13_i["code"] != r14_i["code"]:
            print(f'  {r13_i["date"]}: V13={r13_i["name"]}(sc={r13_i["score"]:.0f} nh={r13_i["nh"]:+.1f}% {r13_i["win"]}) → V14={r14_i["name"]}(sc={r14_i["score"]:.0f} nh={r14_i["nh"]:+.1f}% {r14_i["win"]})')
