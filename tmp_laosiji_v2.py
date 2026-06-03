#!/usr/bin/env python3
"""
老司机V2 — 基于区分度的加权评分
用Cohen's d确定权重，按行情分别调参
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
    if not ps: return "flat"
    ap = sum(ps)/len(ps)
    if ap > 0.5: return "fake_up" if sum(1 for p in ps if 5 <= p <= 8) < 15 else "real_up"
    if ap < -0.5: return "down"
    return "flat"

MKT_NAMES = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
MODS = {"real_up": zzr_mod, "fake_up": xzr_mod, "down": dr_mod, "flat": hp_mod}

# ====== 老司机V2评分函数 ======
# 基于统计数据：各特征区分度权重
# 每个特征的得分 = 归一化值 × 权重
# 总分 = sum(各项得分) + 阈值加分

WEIGHTS = {
    # 特征: (权重, 方向, 目标值)
    # 方向: "high" = 越高越好, "low" = 越低越好
    "p":    (5,  "high", 3.0),   # 涨幅2-3%最佳
    "dif":  (4,  "high", 0.5),   # DIF > 0.3 区分度极强
    "wrv":  (3,  "low",  25),    # WR < 30 更好
    "cl":   (3,  "high", 75),    # CL > 75 强势
    "hsl":  (2,  "high", 6),     # 换手活跃
    "dv":   (2,  "high", 60),    # D值偏高
    "vr":   (2,  "high", 1.1),   # 量比 > 1.1
    "pos":  (1,  "low",  55),    # 日内位置偏低
    "a5":   (1,  "high", 1),     # 站上MA5
}

# 各行情特异性加分权重
MKT_BONUS = {
    "real_up": {
        "p_weight_up": 2,   # 涨日涨幅权重加倍
        "dif_weight_up": 1,
        "wrv_weight_up": 0,
    },
    "fake_up": {
        "mg_bonus": 8,      # MACD金叉加分
        "kdj_g_bonus": 5,   # KDJ金叉加分
        "wrv_weight_up": 0,  # WR不重要
        "cl_weight_up": 2,   # CL加倍
    },
    "down": {
        "dif_weight_up": 2,  # 跌日DIF权重大
        "p_weight_up": 1,
    },
    "flat": {
        "p_weight_up": 4,   # 横盘涨幅权重极大
        "dif_weight_up": 3,  # DIF权重加大
        "hsl_weight_up": 1,
    },
}

def laosiji_score_v2(stock, mkt_key):
    """老司机V2数据驱动评分"""
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
    mb = MKT_BONUS.get(mkt_key, {})
    
    # 1. p (涨幅) — 最強特徵
    pw = WEIGHTS["p"][0] + mb.get("p_weight_up", 0)
    # 用sigmoid-like映射: p越大越好,但到3%以上递减
    p_score = min(p / 3.0, 1.0) * 10
    score += p_score * pw
    
    # 2. DIF — 第二強
    dw = WEIGHTS["dif"][0] + mb.get("dif_weight_up", 0)
    dif_score = min(dif / 0.5, 1.0) * 10
    score += dif_score * dw
    
    # 3. WR — 越低越好
    ww = WEIGHTS["wrv"][0] + mb.get("wrv_weight_up", 0)
    wr_score = max(0, min((50 - wrv) / 30, 1.0)) * 10
    score += wr_score * ww
    
    # 4. CL — 位置高好
    cw = WEIGHTS["cl"][0] + mb.get("cl_weight_up", 0)
    cl_score = min(cl / 80, 1.0) * 10
    score += cl_score * cw
    
    # 5. 换手率
    hw = WEIGHTS["hsl"][0] + mb.get("hsl_weight_up", 0)
    hsl_score = min(hsl / 8, 1.0) * 10
    score += hsl_score * hw
    
    # 6. D值
    d_score = min(dv / 65, 1.0) * 10
    score += d_score * WEIGHTS["dv"][0]
    
    # 7. 量比
    vr_score = min(vr / 1.3, 1.0) * 10
    score += vr_score * WEIGHTS["vr"][0]
    
    # 8. 日内位置（低好）
    pos_score = max(0, min((100 - pos) / 50, 1.0)) * 10
    score += pos_score * WEIGHTS["pos"][0]
    
    # 9. 站上MA5
    if a5:
        score += 8 * WEIGHTS["a5"][0]
    
    # 行情特异性加分
    # MACD金叉
    if mg:
        score += mb.get("mg_bonus", 2)
    # KDJ金叉
    if kdj_g:
        score += mb.get("kdj_g_bonus", 2)
    
    # 组合加分 (多因子共振)
    combo_score = 0
    if dif > 0.3 and p > 2.0:
        combo_score += 5  # DIF+涨幅双强
    if wrv < 30 and cl > 75:
        combo_score += 3  # WR低+CL高
    if hsl > 5 and vr > 1.1:
        combo_score += 3  # 活跃放量
    score += combo_score
    
    return round(score, 1)


# ====== 对比测试 ======
dates = sorted(dt for dt in data if "2025-01-01" <= dt < "2026-06-01")[-30:]

print("=" * 70)
print("  V9 vs 老司机V2 30天对比")
print("=" * 70)

for suffix, use_fn in [("V9原版", False), ("老司机V2", True)]:
    print(f"\n── {suffix} ──")
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
                if use_fn:
                    sc = laosiji_score_v2(st, mkt_key)
                else:
                    sc = fn(st)
                nh = s.get("n",0) or 0
                scored.append({"sc":sc, "nh":nh})
            
            if not scored: continue
            scored.sort(key=lambda x: -x["sc"])
            total += 1
            if scored[0]["nh"] >= 2.5: wins += 1
            
            # 打印前3评分
            if suffix == "老司机V2" and total <= 3:
                pass  # 简略输出
        
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
