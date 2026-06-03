#!/usr/bin/env python3
"""老司机AI训练 — 分析赢家vs输家的特征模式"""
import sys, os, pickle, json
from collections import defaultdict

SCRIPTS_DIR = r"C:\Users\12546\AppData\Local\hermes\scripts"
sys.path.insert(0, os.path.join(SCRIPTS_DIR, "archive", "V9"))

# 清除缓存
for mod in list(sys.modules.keys()):
    if "V9" in mod: del sys.modules[mod]

# 加载V9评分策略（获取LEVELS）
from archive.V9 import 分而治之_V9_真实涨日_评分策略 as zzr_mod
from archive.V9 import 分而治之_V9_跌日_评分策略 as dr_mod
from archive.V9 import 分而治之_V9_横盘_评分策略 as hp_mod
from archive.V9 import 分而治之_V9_虚涨日_评分策略 as xzr_mod

# 加载新缓存
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
MODS = {"real_up": zzr_mod, "fake_up": xzr_mod, "down": dr_mod, "flat": hp_mod}
dates = sorted(dt for dt in data if "2025-01-01" <= dt < "2026-06-01")[:-1]  # 最后一天无n值

# 提取所有候选票数据（按V9的LEVELS过滤）
all_records = []  # [{mkt, dt, code, nm, p, cl, vr, hsl, dif, mg, a5, wrv, k, d, j, kdj_g, nh, ...}]
mkt_stats = defaultdict(lambda: {"winners":[], "losers":[]})

for dt in dates:
    ss = data.get(dt, [])
    if not ss: continue
    m = cls(ss)
    mkt_key = m
    mod = MODS.get(m)
    if not mod: continue
    lvls = mod.LEVELS
    
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
    
    for s in pool:
        code = s.get("code","")
        nh = s.get("n",0) or 0
        is_winner = nh >= 2.5
        rec = {
            "mkt": mkt_key,
            "dt": dt,
            "code": code,
            "nm": names.get(code, ""),
            "p": s.get("p",0) or 0,
            "cl": s.get("cl",0),
            "vr": s.get("vol_ratio",0) or 0,
            "hsl": (real.get(code,{}).get("hsl",0) or 0),
            "dif": s.get("dif_val",0) or 0,
            "mg": s.get("macd_golden",0) or 0,
            "a5": s.get("above_ma5",0) or 0,
            "wrv": s.get("wr_val",0) or 50,
            "kv": s.get("k_val",0) or 0,
            "dv": s.get("d_val",0) or 0,
            "jv": s.get("j_val",0) or 0,
            "kdj_g": s.get("kdj_golden",0) or 0,
            "pos": s.get("pos_in_day",50) or 50,
            "nh": nh,
            "win": is_winner,
        }
        all_records.append(rec)
        mkt_stats[mkt_key]["winners" if is_winner else "losers"].append(rec)

print("=" * 65)
print(f"  老司机AI训练 — 特征分析")
print("=" * 65)
print(f"\n总样本: {len(all_records)}条")
print(f"赢家(nh≥2.5): {sum(1 for r in all_records if r['win'])}条")
print(f"输家(nh<2.5): {sum(1 for r in all_records if not r['win'])}条")

FEATURES = [
    ("p", "涨幅%"),
    ("cl", "CL位置"),
    ("vr", "量比"),
    ("hsl", "换手率"),
    ("dif", "DIF值"),
    ("mg", "MACD金叉"),
    ("a5", "站上MA5"),
    ("wrv", "WR值"),
    ("kv", "K值"),
    ("dv", "D值"),
    ("jv", "J值"),
    ("kdj_g", "KDJ金叉"),
    ("pos", "日内位置"),
]

# 按行情分析
print("\n" + "=" * 65)
print(f"  各行情赢家vs输家特征对比")
print("=" * 65)

for mkt_key in ["real_up", "fake_up", "down", "flat"]:
    ws = mkt_stats[mkt_key]["winners"]
    ls = mkt_stats[mkt_key]["losers"]
    mkt_name = MKT_NAMES[mkt_key]
    
    if not ws and not ls:
        print(f"\n📊 {mkt_name}: 无数据")
        continue
    
    print(f"\n📊 {mkt_name} — 赢家{len(ws)}条 / 输家{len(ls)}条")
    
    # 计算均值对比
    gaps = []
    for feat_key, feat_name in FEATURES:
        def avg(recs, key):
            vals = [r[key] for r in recs if r[key] is not None]
            return sum(vals)/len(vals) if vals else 0
        w_avg = avg(ws, feat_key)
        l_avg = avg(ls, feat_key)
        gap = w_avg - l_avg
        pct_gap = (gap / (l_avg + 0.001)) * 100 if abs(l_avg) > 0.01 else gap * 100
        gaps.append((feat_name, feat_key, w_avg, l_avg, gap, pct_gap))
    
    # 按差异大小排序
    gaps.sort(key=lambda x: abs(x[4]), reverse=True)
    
    print(f"{'指标':>10} {'赢家均值':>10} {'输家均值':>10} {'差值':>8} {'变化%':>8}")
    print(f"{'─'*10} {'─'*10} {'─'*10} {'─'*8} {'─'*8}")
    for fn, fk, wa, la, gap, pg in gaps:
        if abs(gap) < 0.01 and fk not in ["mg","a5","kdj_g"]:
            continue
        arrow = "↑" if gap > 0 else "↓"
        print(f"{fn:>10} {wa:>8.2f}  {la:>8.2f}  {arrow}{abs(gap):>6.2f}  {pg:>+6.1f}%")
    
    # 赢家画像
    print(f"\n  赢家画像:")
    for fn, fk, wa, la, gap, pg in gaps[:5]:
        print(f"    {fn}: 赢家{wa:.1f} vs 输家{la:.1f} (差{pg:+.1f}%)")

# ====== 整体特征重要性排名 ======
print("\n" + "=" * 65)
print(f"  全域特征重要性排名")
print("=" * 65)

all_ws = [r for r in all_records if r["win"]]
all_ls = [r for r in all_records if not r["win"]]

rankings = []
for feat_key, feat_name in FEATURES:
    def calc_dist(recs, key):
        vals = [r[key] for r in recs if r[key] is not None]
        if not vals: return 0, 0
        return sum(vals)/len(vals), (sum((v - sum(vals)/len(vals))**2 for v in vals)/len(vals))**0.5
    w_mean, w_std = calc_dist(all_ws, feat_key)
    l_mean, l_std = calc_dist(all_ls, feat_key)
    
    # 用Cohen's d衡量区分度
    pooled_std = ((w_std**2 + l_std**2) / 2) ** 0.5
    cohen_d = abs(w_mean - l_mean) / (pooled_std + 0.001)
    
    direction = "↑高更好" if w_mean > l_mean else "↓低更好"
    rankings.append((cohen_d, feat_name, w_mean, l_mean, direction))

rankings.sort(key=lambda x: -x[0])
print(f"{'排名':>4} {'指标':>10} {'区分度':>8} {'赢家均值':>10} {'输家均值':>10} {'方向':>10}")
print(f"{'─'*4} {'─'*10} {'─'*8} {'─'*10} {'─'*10} {'─'*10}")
for i, (d, fn, wm, lm, dr) in enumerate(rankings, 1):
    stars = "⭐" if d > 0.3 else ("✨" if d > 0.15 else "  ")
    print(f"{i:>4d} {fn:>10} {d:>7.3f}  {wm:>8.2f}  {lm:>8.2f}  {dr:>10} {stars}")

# ====== 关键阈值分析 ======
print("\n" + "=" * 65)
print(f"  关键特征最佳阈值搜索")
print("=" * 65)

for feat_key, feat_name in FEATURES:
    if feat_key in ["mg","a5","kdj_g"]:  # 跳过布尔值
        continue
    vals_w = [r[feat_key] for r in all_ws if r[feat_key] is not None]
    vals_l = [r[feat_key] for r in all_ls if r[feat_key] is not None]
    if not vals_w or not vals_l: continue
    
    # 按百分位搜索最佳阈值
    all_vals = sorted(vals_w + vals_l)
    best_acc = 0
    best_th = 0
    for pct in range(5, 95, 2):
        th = all_vals[int(len(all_vals) * pct / 100)]
        w_pass = sum(1 for v in vals_w if v >= th) / len(vals_w) if vals_w else 0
        l_fail = len([v for v in vals_l if v >= th])
        l_rate = l_fail / len(vals_l) if vals_l else 0
        # 最大化 赢家通过率 - 输家通过率
        sep = w_pass - l_rate
        if sep > best_acc:
            best_acc = sep
            best_th = th
    
    if best_acc > 0.05:
        w_pass = sum(1 for v in vals_w if v >= best_th) / len(vals_w)
        l_fail = sum(1 for v in vals_l if v >= best_th) / len(vals_l)
        print(f"  {feat_name:>6} ≥ {best_th:>7.1f}: 赢家通过率{w_pass*100:>5.1f}% 输家通过率{l_fail*100:>5.1f}% 区分度{best_acc*100:>5.1f}%")

# ====== 保存老司机模型 ======
print("\n" + "=" * 65)
print(f"  保存老司机模型")
print("=" * 65)

model = {
    "total_samples": len(all_records),
    "winners": sum(1 for r in all_records if r["win"]),
    "losers": sum(1 for r in all_records if not r["win"]),
    "feature_rankings": [{"name":fn, "cohen_d":d, "w_mean":wm, "l_mean":lm, "direction":dr} 
                        for d,fn,wm,lm,dr in rankings],
    "mkt_stats": {},
}

for mkt_key, stats in mkt_stats.items():
    ws = stats["winners"]
    ls = stats["losers"]
    ws_avg = {fk: (sum(r[fk] for r in ws)/len(ws) if ws else 0) for fk,_ in FEATURES}
    ls_avg = {fk: (sum(r[fk] for r in ls)/len(ls) if ls else 0) for fk,_ in FEATURES}
    model["mkt_stats"][mkt_key] = {
        "winners": len(ws),
        "losers": len(ls),
        "winner_avg": ws_avg,
        "loser_avg": ls_avg,
    }

with open(os.path.join(SCRIPTS_DIR, "laosiji_model.json"), "w") as f:
    json.dump(model, f, ensure_ascii=False, indent=2)
print(f"✅ 模型已保存: laosiji_model.json")

print("\n" + "=" * 65)
print(f"  训练完成！")
print("=" * 65)
