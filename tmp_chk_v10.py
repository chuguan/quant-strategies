import sys, os, pickle
for k in list(sys.modules):
    if "V10" in k: del sys.modules[k]
SCRIPTS_DIR = r"C:\Users\12546\AppData\Local\hermes\scripts"
sys.path.insert(0, SCRIPTS_DIR)

from 分而治之_V10_真实涨日_评分策略 import score as rs, LEVELS as rl
from 分而治之_V10_跌日_评分策略 import score as ds, LEVELS as dl
from 分而治之_V10_横盘_评分策略 import score as fs, LEVELS as fl
from 分而治之_V10_虚涨日_评分策略 import score as xs, LEVELS as xl

d = pickle.load(open(os.path.join(SCRIPTS_DIR, "big_cache_full.pkl"), "rb"))
data, real, names = d["data"], d["real"], d["names"]

def cls(ss):
    if not ss: return "flat"
    ps = [s.get("p",0) or 0 for s in ss if abs(s.get("p",0) or 0) < 15]
    vrs = [s.get("vol_ratio",0) or 0 for s in ss if (s.get("vol_ratio",0) or 0) > 0]
    if not ps: return "flat"
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5: return "fake_up" if hot < 15 or av < 0.9 else "real_up"
    if ap < -0.5: return "down"
    return "flat"

mn = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
sm = {"real_up":rs,"fake_up":xs,"down":ds,"flat":fs}
lm = {"real_up":rl,"fake_up":xl,"down":dl,"flat":fl}
dates = sorted(dt for dt in data if "2025-01-01" <= dt < "2026-06-01")[-30:]

print("V10生产版 30天回测")
print("=" * 40)
tw, tt = 0, 0
for mk in ["real_up","fake_up","down","flat"]:
    fn = sm[mk]; lvls = lm[mk]; wi = 0; to = 0
    for dt in dates:
        ss = data.get(dt, [])
        if not ss: continue
        m = cls(ss)
        if m != mk: continue
        pool = None
        for lv in lvls:
            pool = []
            for s in ss:
                code = s.get("code","")
                p = (s.get("p",0) or 0)
                if p < lv["p_min"] or p > lv["p_max"]: continue
                if p >= 8: continue
                vr = (s.get("vol_ratio",0) or 0)
                if vr < lv["vr_min"] or vr > lv["vr_max"]: continue
                ri = real.get(code)
                if not ri: continue
                hsl = (ri.get("hsl",0) or 0)
                if hsl < lv["hs_min"] or hsl > lv["hs_max"]: continue
                if (ri.get("shizhi",0) or 0) >= lv["sz_max"]: continue
                nm = names.get(code,"")
                if "ST" in nm or "*ST" in nm or "退" in nm: continue
                cl = s.get("cl",0)
                if cl < lv["cl_min"] or cl > lv["cl_max"]: continue
                if (s.get("n",0) or 0) <= 0: continue
                pool.append(s)
            if len(pool) > 8: break
            pool = None
        if not pool or len(pool) <= 8: continue
        scd = []
        for s in pool:
            st = {"p":s.get("p",0) or 0,"cl":s.get("cl",0),"vr":s.get("vol_ratio",0) or 0,"hsl":(real.get(s["code"],{}).get("hsl",0) or 0),"dif":s.get("dif_val",0) or 0,"mg":s.get("macd_golden",0),"a5":s.get("above_ma5",0) or 0,"wrv":s.get("wr_val",0) or 50,"jv":s.get("j_val",0) or 0,"kv":s.get("k_val",0) or 0,"dv":s.get("d_val",0) or 0,"kdj_g":s.get("kdj_golden",0) or 0,"pos_in_day":s.get("pos_in_day",50) or 50}
            sc = fn(st)
            nh = (s.get("n",0) or 0)
            scd.append({"sc":sc,"nh":nh})
        if not scd: continue
        scd.sort(key=lambda x: -x["sc"])
        to += 1
        if scd[0]["nh"] >= 2.5: wi += 1
    r = round(wi*100/to,1) if to else 0
    b = "X" * int(r/5) + "-" * (20 - int(r/5))
    print(f"  {mn[mk]:6s} {b} {r:5.1f}% ({wi:2d}/{to:2d})")
    tw += wi; tt += to
r = round(tw*100/tt,1)
print(f"  {'总':>6s} {'X'*int(r/5)+'-'*(20-int(r/5))} {r:.1f}% ({tw}/{tt})")
