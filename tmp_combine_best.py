#!/usr/bin/env python3
"""
最优组合搜索 — 每个行情独立选最高胜率评分方案
"""
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

def cls(stocks):
    if not stocks: return "flat"
    ps = [s.get("p",0) or 0 for s in stocks if abs(s.get("p",0) or 0) < 15]
    vrs = [s.get("vol_ratio",0) or 0 for s in stocks if (s.get("vol_ratio",0) or 0) > 0]
    if not ps: return "flat"
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5: return "fake_up" if hot < 15 or av < 0.9 else "real_up"
    if ap < -0.5: return "down"
    return "flat"

MKT_NAMES = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}

# ====== 老司机评分 ======
def laosiji_score(stock, mkt_key):
    p = stock.get("p", 0)
    dif = stock.get("dif", 0)
    wrv = stock.get("wrv", 50)
    cl = stock.get("cl", 50)
    hsl = stock.get("hsl", 0)
    dv = stock.get("dv", 50)
    vr = stock.get("vr", 0)
    pos = stock.get("pos_in_day", 50)
    a5 = stock.get("a5", 0)
    mg = stock.get("mg", 0)
    kdj_g = stock.get("kdj_g", 0)
    
    score = 0
    
    # 通用权重
    p_w = 7; dif_w = 5; wr_w = 3; cl_w = 3
    hsl_w = 2; d_w = 2; vr_w = 2; pos_w = 1; a5_w = 1
    
    # 行情特异性调权
    if mkt_key == "real_up":
        pass  # 默认
    elif mkt_key == "fake_up":
        cl_w = 5; dif_w = 4; mg = mg * 8  # CL和MACD更重要
    elif mkt_key == "down":
        dif_w = 7; p_w = 5  # DIF权重加倍
    elif mkt_key == "flat":
        p_w = 11; dif_w = 8  # 横盘p和DIF最关键
    
    p_score = min(p / 3.0, 1.0) * 10; score += p_score * p_w
    dif_score = min(dif / 0.5, 1.0) * 10; score += dif_score * dif_w
    wr_score = max(0, min((50 - wrv) / 30, 1.0)) * 10; score += wr_score * wr_w
    cl_score = min(cl / 80, 1.0) * 10; score += cl_score * cl_w
    hsl_score = min(hsl / 8, 1.0) * 10; score += hsl_score * hsl_w
    d_score = min(dv / 65, 1.0) * 10; score += d_score * d_w
    vr_score = min(vr / 1.3, 1.0) * 10; score += vr_score * vr_w
    pos_score = max(0, min((100 - pos) / 50, 1.0)) * 10; score += pos_score * pos_w
    if a5: score += 8 * a5_w
    
    # 共振加分
    if dif > 0.3 and p > 2.0: score += 8
    if wrv < 30 and cl > 75: score += 5
    if hsl > 5 and vr > 1.1: score += 5
    if mg and kdj_g: score += 3
    
    return score

def run_backtest(dates, mods_and_fns):
    """跑回测，返回{mkt: (wins, total, rate)}"""
    results = {}
    for mkt_key in mods_and_fns:
        mod, fn = mods_and_fns[mkt_key]
        lvls = mod.LEVELS
        wins = 0; total = 0
        for dt in dates:
            ss = data.get(dt, [])
            if not ss: continue
            m = cls(ss)
            if m != mkt_key: continue
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
                sc = fn(st)
                nh = (s.get("n",0) or 0)
                scored.append({"sc":sc, "nh":nh})
            if not scored: continue
            scored.sort(key=lambda x: -x["sc"])
            total += 1
            if scored[0]["nh"] >= 2.5: wins += 1
        r = round(wins*100/total, 1) if total else 0
        results[mkt_key] = (wins, total, r)
    return results

# ====== 定义方案 ======
V9_FNS = {
    "real_up": (zzr_mod, zzr_mod.score),
    "fake_up": (xzr_mod, xzr_mod.score),
    "down": (dr_mod, dr_mod.score),
    "flat": (hp_mod, hp_mod.score),
}

LAOSIJI_FNS = {}
for mk, (mod, _) in V9_FNS.items():
    LAOSIJI_FNS[mk] = (mod, lambda st, k=mk: laosiji_score(st, k))

all_dates = sorted(dt for dt in data if "2025-01-01" <= dt < "2026-06-01")
for period_name, max_days in [("近30天", 30), ("333天全周期", 333)]:
    dates = all_dates[-max_days:]
    print(f"\n{'='*65}")
    print(f"  {period_name} — V9 vs 老司机 逐行情对比")
    print(f"{'='*65}")
    
    V9_FNS2 = {mk: (mod, lambda st, fn=fn: fn(st)) for mk, (mod, fn) in V9_FNS.items()}
    LSJ_FNS2 = {mk: (mod, lambda st, k=mk: laosiji_score(st, k)) for mk, (mod, _) in LAOSIJI_FNS.items()}
    r1 = run_backtest(dates, V9_FNS2)
    r2 = run_backtest(dates, LSJ_FNS2)
    
    print(f"\n{'行情':>8} {'V9':>10} {'老司机':>10} {'胜方':>10} {'t/天':>5}")
    print(f"{'─'*8} {'─'*10} {'─'*10} {'─'*10} {'─'*5}")
    
    best_picks = {}
    for mk, mn in MKT_NAMES.items():
        w1, t1, r1v = r1.get(mk, (0,0,0))
        w2, t2, r2v = r2.get(mk, (0,0,0))
        if t1 == 0 and t2 == 0:
            print(f"{mn:>8} {'—':>10} {'—':>10} {'—':>10} {'0':>5}")
            continue
        if r1v >= r2v:
            winner = "V9 ✅"
            best_picks[mk] = "V9"
        else:
            winner = "老司机 ✅"
            best_picks[mk] = "老司机"
        days = max(t1, t2)
        print(f"{mn:>8} {r1v:>8.1f}%({w1}) {r2v:>8.1f}%({w2}) {winner:>10} {days:>4d}")
    
    # 最优组合
    best_fns = {}
    for mk in V9_FNS:
        if best_picks.get(mk) == "老司机":
            best_fns[mk] = LSJ_FNS2[mk]
        else:
            best_fns[mk] = V9_FNS2[mk]
    
    r_best = run_backtest(dates, best_fns)
    
    print(f"\n── 最优组合方案 ──")
    tw, tt = 0, 0
    for mk, mn in MKT_NAMES.items():
        w, t, r = r_best.get(mk, (0,0,0))
        if t > 0:
            bar = "█"*int(r/5)+"░"*(20-int(r/5))
            pick = best_picks.get(mk, "V9")
            print(f"  {mn:6s} {bar} {r:5.1f}% ({w}/{t}) ← {pick}")
            tw += w; tt += t
    if tt > 0:
        print(f"  {'总':6s} {'█'*int(tw*100/tt/5)+'░'*(20-int(tw*100/tt/5))} {round(tw*100/tt,1)}% ({tw}/{tt})")
    
    print(f"\n最优选择:")
    for mk, mn in MKT_NAMES.items():
        print(f"  {mn}: {best_picks.get(mk, 'V9')}")

print()
