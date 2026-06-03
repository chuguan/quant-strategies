#!/usr/bin/env python3
"""最优组合V3 — 各行情分别取最优"""
import sys, os, pickle

SCRIPTS_DIR = r"C:\Users\12546\AppData\Local\hermes\scripts"
sys.path.insert(0, os.path.join(SCRIPTS_DIR, "archive", "V9"))
for mod in list(sys.modules.keys()):
    if "V9" in mod: del sys.modules[mod]

from archive.V9 import 分而治之_V9_真实涨日_评分策略 as zzr_mod
from archive.V9 import 分而治之_V9_跌日_评分策略 as dr_mod
from archive.V9 import 分而治之_V9_横盘_评分策略 as hp_mod
from archive.V9 import 分而治之_V9_虚涨日_评分策略 as xzr_mod

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

MKT = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}

# ====== 老司机真实涨日评分（上次90.0%版） ======
def laosiji_real_up(stock):
    p = stock.get("p", 0); dif = stock.get("dif", 0); wrv = stock.get("wrv", 50)
    cl = stock.get("cl", 50); hsl = stock.get("hsl", 0); dv = stock.get("dv", 50)
    vr = stock.get("vr", 0); pos = stock.get("pos_in_day", 50)
    a5 = stock.get("a5", 0); mg = stock.get("mg", 0); kdj_g = stock.get("kdj_g", 0)
    
    score = 0
    # p(权重7), dif(权重5), wr(权重3), cl(权重3), hsl(权重2), d(权重2), vr(权重2), pos(权重1)
    score += min(p / 3.0, 1.0) * 10 * 7
    score += min(dif / 0.5, 1.0) * 10 * 5
    score += max(0, min((50 - wrv) / 30, 1.0)) * 10 * 3
    score += min(cl / 80, 1.0) * 10 * 3
    score += min(hsl / 8, 1.0) * 10 * 2
    score += min(dv / 65, 1.0) * 10 * 2
    score += min(vr / 1.3, 1.0) * 10 * 2
    score += max(0, min((100 - pos) / 50, 1.0)) * 10 * 1
    if a5: score += 8
    if dif > 0.3 and p > 2.0: score += 8
    if wrv < 30 and cl > 75: score += 5
    if hsl > 5 and vr > 1.1: score += 5
    if mg and kdj_g: score += 3
    return score

# ====== 横盘加分版（上次77.8%版） ======
def flat_bonus_score(stock):
    v9_score = hp_mod.score(stock)
    dif = stock.get("dif", 0); wrv = stock.get("wrv", 50); cl = stock.get("cl", 50)
    p = stock.get("p", 0); hsl = stock.get("hsl", 0); pos = stock.get("pos_in_day", 50)
    kv = stock.get("kv", 50); dv = stock.get("dv", 50); vr = stock.get("vr", 0)
    bonus = 0
    if dif > 0.3: bonus += 10
    if dif > 0.5: bonus += 8
    if dif > 1.0: bonus += 5
    if wrv < 30: bonus += 8
    if wrv < 20: bonus += 6
    if wrv < 10: bonus += 4
    if cl > 75: bonus += 6
    if cl > 85: bonus += 5
    if p > 2.0: bonus += 5
    if p > 3.0: bonus += 3
    if hsl > 5: bonus += 3
    if hsl > 8: bonus += 3
    if pos < 60: bonus += 3
    if pos < 45: bonus += 2
    if kv > 65 and dv > 60: bonus += 4
    if p > 2.0 and dif > 0.3: bonus += 5
    if dif > 0.3 and wrv < 30: bonus += 3
    if cl > 75 and hsl > 5: bonus += 3
    if p > 2.0 and vr > 1.1: bonus += 3
    return v9_score + bonus

# ====== 方案定义 ======
SCHEMES = {
    "V9原版": {
        "real_up": zzr_mod.score,
        "fake_up": xzr_mod.score,
        "down": dr_mod.score,
        "flat": hp_mod.score,
    },
    "最优组合": {
        "real_up": laosiji_real_up,
        "fake_up": xzr_mod.score,
        "down": dr_mod.score,
        "flat": flat_bonus_score,
    },
    "全老司机": {
        "real_up": laosiji_real_up,
        "fake_up": laosiji_real_up,  # fallback
        "down": laosiji_real_up,
        "flat": flat_bonus_score,
    },
}

def run_bt(dates, fns):
    results = {}
    for mk in fns:
        mod = {"real_up":zzr_mod,"fake_up":xzr_mod,"down":dr_mod,"flat":hp_mod}[mk]
        lvls = mod.LEVELS; fn = fns[mk]
        wins = 0; total = 0
        for dt in dates:
            ss = data.get(dt, []); 
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
            scored = []
            for s in pool:
                st = {"p":s.get("p",0) or 0,"cl":s.get("cl",0),"vr":s.get("vol_ratio",0) or 0,
                      "hsl":(real.get(s["code"],{}).get("hsl",0) or 0),
                      "dif":s.get("dif_val",0) or 0,"mg":s.get("macd_golden",0),
                      "a5":s.get("above_ma5",0) or 0,"wrv":s.get("wr_val",0) or 50,
                      "jv":s.get("j_val",0) or 0,"kv":s.get("k_val",0) or 0,
                      "dv":s.get("d_val",0) or 0,"kdj_g":s.get("kdj_golden",0) or 0,
                      "pos_in_day":s.get("pos_in_day",50) or 50}
                sc = fn(st); nh = (s.get("n",0) or 0)
                scored.append({"sc":sc,"nh":nh})
            if not scored: continue
            scored.sort(key=lambda x: -x["sc"])
            total += 1
            if scored[0]["nh"] >= 2.5: wins += 1
        results[mk] = (wins, total, round(wins*100/total,1) if total else 0)
    return results

all_dates = sorted(dt for dt in data if "2025-01-01" <= dt < "2026-06-01")

for period, days in [("近30天", 30), ("333天全周期", 333)]:
    dates = all_dates[-days:]
    print(f"\n{'='*65}")
    print(f"  {period}")
    print(f"{'='*65}")
    
    for sname, fns in SCHEMES.items():
        res = run_bt(dates, fns)
        print(f"\n── {sname} ──")
        tw, tt = 0, 0
        for mk in ["real_up","fake_up","down","flat"]:
            w,t,r = res.get(mk,(0,0,0))
            if t > 0:
                print(f"  {MKT[mk]:6s} {'█'*int(r/5)+'░'*(20-int(r/5))} {r:5.1f}% ({w}/{t})")
                tw += w; tt += t
        if tt > 0:
            print(f"  {'总':>6s} {'█'*int(tw*100/tt/5)+'░'*(20-int(tw*100/tt/5))} {round(tw*100/tt,1)}% ({tw}/{tt})")

print()
