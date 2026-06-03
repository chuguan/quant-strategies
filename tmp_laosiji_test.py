#!/usr/bin/env python3
"""老司机加分测试 — 把模式识别加入评分"""
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
    if not ps: return "flat"
    ap = sum(ps)/len(ps)
    if ap > 0.5: return "fake_up" if sum(1 for p in ps if 5 <= p <= 8) < 15 else "real_up"
    if ap < -0.5: return "down"
    return "flat"

MKT_NAMES = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
MODS = {"real_up": zzr_mod, "fake_up": xzr_mod, "down": dr_mod, "flat": hp_mod}

# ====== 老司机加分函数 ======
def laosiji_bonus(stock, mkt_key):
    """
    基于统计分析的老司机加分
    赢家 vs 输家区分度最大的特征
    """
    bonus = 0
    p = stock.get("p",0)
    cl = stock.get("cl",50)
    wrv = stock.get("wrv",50)
    dif = stock.get("dif",0)
    hsl = stock.get("hsl",0)
    pos = stock.get("pos_in_day",50)
    kdj_g = stock.get("kdj_g",0)
    mg = stock.get("mg",0)
    kv = stock.get("kv",50)
    dv = stock.get("dv",50)
    jv = stock.get("jv",50)
    
    # ⭐ DIF > 0.3 = 最强区分度指标(19.9%)
    if dif > 0.3:
        bonus += 10
    if dif > 0.5:
        bonus += 8
    if dif > 1.0:
        bonus += 5
    
    # ⭐ WR偏低 = 没超买 区分度好
    if wrv < 30:
        bonus += 8
    if wrv < 20:
        bonus += 6
    if wrv < 10:
        bonus += 4  # 超买极端
    
    # ⭐ CL偏高 = 强势位置
    if cl > 75:
        bonus += 6
    if cl > 85:
        bonus += 5
    
    # ⭐ 涨幅偏高（在筛选范围内）
    if p > 2.0:
        bonus += 5
    if p > 3.0:
        bonus += 3
    
    # ⭐ 换手率偏高 = 活跃
    if hsl > 5:
        bonus += 3
    if hsl > 8:
        bonus += 3
    
    # ⭐ 日内位置偏低 = 早上拉的不是尾盘偷袭
    if pos < 60:
        bonus += 3
    if pos < 45:
        bonus += 2
    
    # 行情特异性加分
    if mkt_key in ["real_up", "down"]:
        # 涨日和跌日: K/D值高强
        if kv > 65 and dv > 60:
            bonus += 4
    elif mkt_key == "fake_up":
        # 虚涨日: MACD金叉特别重要
        if mg:
            bonus += 5
        if kdj_g:
            bonus += 3
        # CL和WR更重要
        if cl > 65 and wrv < 35:
            bonus += 5
    elif mkt_key == "flat":
        # 横盘: p和DIF是关键
        if p > 2.0 and dif > 0.3:
            bonus += 5
    
    return bonus

# ====== 测试：原始V9评分 vs V9+老司机加分 ======
dates = sorted(dt for dt in data if "2025-01-01" <= dt < "2026-06-01")[-30:]

print("=" * 70)
print(f"  V9 vs V9+老司机 30天对比")
print("=" * 70)

for suffix, add_bonus in [("V9原版", False), ("V9+老司机", True)]:
    print(f"\n--- {suffix} ---")
    tw, tt = 0, 0
    for mkt_key, mod in MODS.items():
        lvls = mod.LEVELS
        fn = mod.score
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
                    p = s.get("p",0) or 0
                    if p < lv["p_min"] or p > lv["p_max"]: continue
                    if p >= 8: continue
                    vr = s.get("vol_ratio",0) or 0
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
                code = s["code"]
                st = {
                    "p": s.get("p",0) or 0,
                    "cl": s.get("cl",0),
                    "vr": s.get("vol_ratio",0) or 0,
                    "hsl": (real.get(code,{}).get("hsl",0) or 0),
                    "dif": s.get("dif_val",0) or 0,
                    "mg": s.get("macd_golden",0),
                    "a5": s.get("above_ma5",0) or 0,
                    "wrv": s.get("wr_val",0) or 50,
                    "jv": s.get("j_val",0) or 0,
                    "kv": s.get("k_val",0) or 0,
                    "dv": s.get("d_val",0) or 0,
                    "kdj_g": s.get("kdj_golden",0) or 0,
                    "buy_c": s.get("close",0) or 0,
                    "pos_in_day": s.get("pos_in_day",50) or 50,
                }
                sc = fn(st)
                if add_bonus:
                    sc += laosiji_bonus(st, mkt_key)
                nh = s.get("n",0) or 0
                scored.append({"sc":sc, "nh":nh})
            
            if not scored: continue
            scored.sort(key=lambda x: -x["sc"])
            total += 1
            if scored[0]["nh"] >= 2.5: wins += 1
        
        if total > 0:
            rate = round(wins*100/total, 1)
            bar = "█"*int(rate/5)+"░"*(20-int(rate/5))
            print(f"  {MKT_NAMES[mkt_key]:6s} {bar} {rate:5.1f}% ({wins:2d}/{total:2d})")
            tw += wins; tt += total
    
    if tt > 0:
        rate = round(tw*100/tt, 1)
        bar = "█"*int(rate/5)+"░"*(20-int(rate/5))
        print(f"  {'总':6s} {bar} {rate:5.1f}% ({tw:2d}/{tt:2d})")

print()
