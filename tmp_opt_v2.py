#!/usr/bin/env python3
"""最优组合V2 — 横盘用V1加分版，其他V9原版"""
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

MKT_NAMES = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
MODS = {"real_up": zzr_mod, "fake_up": xzr_mod, "down": dr_mod, "flat": hp_mod}

# ====== V1加分版（仅横盘用） ======
def flat_bonus_score(stock):
    """V9原版score + 老司机加分（专为横盘优化的参数）"""
    # 先用V9原版评分
    v9_score = hp_mod.score(stock)
    
    # 老司机加分
    dif = stock.get("dif", 0)
    wrv = stock.get("wrv", 50)
    cl = stock.get("cl", 50)
    p = stock.get("p", 0)
    hsl = stock.get("hsl", 0)
    pos = stock.get("pos_in_day", 50)
    kv = stock.get("kv", 50)
    dv = stock.get("dv", 50)
    vr = stock.get("vr", 0)
    a5 = stock.get("a5", 0)
    
    bonus = 0
    
    # 通用加分（统计验证的强特征）
    if dif > 0.3: bonus += 10
    if dif > 0.5: bonus += 8
    if dif > 1.0: bonus += 5
    
    if wrv < 30:  bonus += 8  # 未超买
    if wrv < 20:  bonus += 6
    if wrv < 10:  bonus += 4  # 超买区但可能更强
    
    if cl > 75:   bonus += 6  # 强势位置
    if cl > 85:   bonus += 5
    
    if p > 2.0:   bonus += 5  # 当日涨幅
    if p > 3.0:   bonus += 3
    
    if hsl > 5:   bonus += 3  # 活跃换手
    if hsl > 8:   bonus += 3
    
    if pos < 60:  bonus += 3  # 日内位置偏低（早上拉的）
    if pos < 45:  bonus += 2
    
    if kv > 65 and dv > 60: bonus += 4  # KDJ强势
    
    # 横盘特异性加分 — 涨幅+DIF双强
    if p > 2.0 and dif > 0.3: bonus += 5
    
    # 共振加分
    if dif > 0.3 and wrv < 30: bonus += 3
    if cl > 75 and hsl > 5: bonus += 3
    if p > 2.0 and vr > 1.1: bonus += 3
    
    return v9_score + bonus

# ====== 测试方案 ======
schemes = {
    "原版V9": {
        "real_up": zzr_mod.score,
        "fake_up": xzr_mod.score,
        "down": dr_mod.score,
        "flat": hp_mod.score,
    },
    "横盘加分+其他V9": {
        "real_up": zzr_mod.score,
        "fake_up": xzr_mod.score,
        "down": dr_mod.score,
        "flat": flat_bonus_score,
    },
}

all_dates = sorted(dt for dt in data if "2025-01-01" <= dt < "2026-06-01")

for period_name, max_days in [("近30天", 30), ("333天全周期", 333)]:
    dates = all_dates[-max_days:]
    print(f"\n{'='*65}")
    print(f"  {period_name}")
    print(f"{'='*65}")
    
    for sname, sfuncs in schemes.items():
        print(f"\n── {sname} ──")
        tw, tt = 0, 0
        for mk, mod in MODS.items():
            lvls = mod.LEVELS
            fn = sfuncs[mk]
            wins = 0; total = 0
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
                    scored.append({"sc":sc,"nh":nh})
                if not scored: continue
                scored.sort(key=lambda x: -x["sc"])
                total += 1
                if scored[0]["nh"] >= 2.5: wins += 1
            
            if total > 0:
                r = round(wins*100/total, 1)
                diff = ""
                if sname == "横盘加分+其他V9":
                    # 与原版V9对比
                    pass
                bar = "█"*int(r/5)+"░"*(20-int(r/5))
                print(f"  {MKT_NAMES[mk]:6s} {bar} {r:5.1f}% ({wins:2d}/{total:2d})")
                tw += wins; tt += total
        
        if tt > 0:
            r = round(tw*100/tt, 1)
            print(f"  {'总':>6s} {'█'*int(r/5)+'░'*(20-int(r/5))} {r:5.1f}% ({tw:2d}/{tt:2d})")

print()
