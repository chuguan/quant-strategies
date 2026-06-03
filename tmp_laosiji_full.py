"""老司机V2 — 真涨日特化版（其他行情保留V9），全周期验证"""
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

# ====== 老司机V2真涨日特化 ======
def laosiji_score_real_up(stock):
    """专门给真实涨日的评分"""
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
    # p: 涨日重要特征
    p_score = min(p / 3.0, 1.0) * 10
    score += p_score * 7  # 权重7
    
    # DIF: 强动量
    dif_score = min(dif / 0.5, 1.0) * 10
    score += dif_score * 5
    
    # WR低好
    wr_score = max(0, min((50 - wrv) / 30, 1.0)) * 10
    score += wr_score * 3
    
    # CL高好
    cl_score = min(cl / 80, 1.0) * 10
    score += cl_score * 3
    
    # 换手活跃
    hsl_score = min(hsl / 8, 1.0) * 10
    score += hsl_score * 2
    
    # D值
    d_score = min(dv / 65, 1.0) * 10
    score += d_score * 2
    
    # 量比
    vr_score = min(vr / 1.3, 1.0) * 10
    score += vr_score * 2
    
    # 日内位置（低好 — 不是尾盘拉的）
    pos_score = max(0, min((100 - pos) / 50, 1.0)) * 10
    score += pos_score * 1
    
    # 站上MA5
    if a5: score += 8
    
    # 共振加分
    if dif > 0.3 and p > 2.0: score += 8
    if wrv < 30 and cl > 75: score += 5
    if hsl > 5 and vr > 1.1: score += 5
    if mg and kdj_g: score += 3  # MACD+KDJ双金叉
    
    return score

# ====== 全面测试 ======
for test_name, max_days in [("30天", 30), ("全周期333天", 333)]:
    dates = sorted(dt for dt in data if "2025-01-01" <= dt < "2026-06-01")[-max_days:]
    
    print(f"\n{'='*65}")
    print(f"  {test_name} 对比")
    print(f"{'='*65}")
    
    # 方案A: 全V9原版
    # 方案B: 真实涨日→老司机, 其他→V9
    # 方案C: 全老司机V2
    
    schemes = [
        ("全部V9原版", {"real_up":zzr_mod.score, "fake_up":xzr_mod.score, "down":dr_mod.score, "flat":hp_mod.score}),
        ("真涨日老司机+其余V9", {"real_up":laosiji_score_real_up, "fake_up":xzr_mod.score, "down":dr_mod.score, "flat":hp_mod.score}),
        ("全部老司机V2", None),  # 全部用laosiji_score_real_up
    ]
    
    for sname, sfuncs in schemes:
        tw, tt = 0, 0
        print(f"\n── {sname} ──")
        for mkt_key, mod in MODS.items():
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
                    st = {
                        "p": s.get("p",0) or 0,
                        "cl": s.get("cl",0),
                        "vr": s.get("vol_ratio",0) or 0,
                        "hsl": (real.get(s["code"],{}).get("hsl",0) or 0),
                        "dif": s.get("dif_val",0) or 0,
                        "mg": s.get("macd_golden",0),
                        "a5": s.get("above_ma5",0) or 0,
                        "wrv": s.get("wr_val",0) or 50,
                        "jv": s.get("j_val",0) or 0,
                        "kv": s.get("k_val",0) or 0,
                        "dv": s.get("d_val",0) or 0,
                        "kdj_g": s.get("kdj_golden",0) or 0,
                        "pos_in_day": s.get("pos_in_day",50) or 50,
                    }
                    if sfuncs:
                        fn = sfuncs[mkt_key]
                    else:
                        fn = laosiji_score_real_up
                    sc = fn(st)
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
            print(f"  {'总':6s} {'█'*int(rate/5)+'░'*(20-int(rate/5))} {rate:5.1f}% ({tw:2d}/{tt:2d})")
    
    # 方案D: 逐个行情挑最优
    print(f"\n── 最优组合（逐行情挑最高） ──")
    tw, tt = 0, 0
    for mkt_key, mod in MODS.items():
        lvls = mod.LEVELS
        best_rate = 0; best_name = ""
        for sname, sfuncs in [("V9", {"real_up":zzr_mod.score, "fake_up":xzr_mod.score, "down":dr_mod.score, "flat":hp_mod.score}),
                              ("老司机", None)]:
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
                    st = {
                        "p": s.get("p",0) or 0,
                        "cl": s.get("cl",0),
                        "vr": s.get("vol_ratio",0) or 0,
                        "hsl": (real.get(s["code"],{}).get("hsl",0) or 0),
                        "dif": s.get("dif_val",0) or 0,
                        "mg": s.get("macd_golden",0),
                        "a5": s.get("above_ma5",0) or 0,
                        "wrv": s.get("wr_val",0) or 50,
                        "jv": s.get("j_val",0) or 0,
                        "kv": s.get("k_val",0) or 0,
                        "dv": s.get("d_val",0) or 0,
                        "kdj_g": s.get("kdj_golden",0) or 0,
                        "pos_in_day": s.get("pos_in_day",50) or 50,
                    }
                    if sfuncs:
                        fn = sfuncs[mkt_key]
                    else:
                        fn = laosiji_score_real_up
                    sc = fn(st)
                    nh = s.get("n",0) or 0
                    scored.append({"sc":sc, "nh":nh})
                
                if not scored: continue
                scored.sort(key=lambda x: -x["sc"])
                total += 1
                if scored[0]["nh"] >= 2.5: wins += 1
            
            if total > 0:
                rate = round(wins*100/total, 1)
                if rate > best_rate:
                    best_rate = rate
                    best_name = sname
        
        bar = "█"*int(best_rate/5)+"░"*(20-int(best_rate/5))
        print(f"  {MKT_NAMES[mkt_key]:6s} {bar} {best_rate:5.1f}% ➜ 选用{best_name}")
    
print()
