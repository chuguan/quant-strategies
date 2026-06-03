"""V10完整报告 — 所有历史战绩+介绍"""
import sys, os, pickle

SCRIPTS_DIR = r"C:\Users\12546\AppData\Local\hermes\scripts"
sys.path.insert(0, SCRIPTS_DIR)
for k in list(sys.modules):
    if "V10" in k: del sys.modules[k]

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

MN = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
SM = {"real_up":rs,"fake_up":xs,"down":ds,"flat":fs}
LM = {"real_up":rl,"fake_up":xl,"down":dl,"flat":fl}
dates = sorted(dt for dt in data if "2025-01-01" <= dt < "2026-06-01")[-30:]

# 每个交易日详细记录
print("DT|行情|冠军|编码|p%|nh%|评分|cl|vr|hsl|wrv|dif|mg|kdjg")
print("-" * 95)

all_rows = []
mk_stats = {}

for dt in dates:
    ss = data.get(dt, [])
    if not ss: continue
    m = cls(ss)
    if m not in SM: continue
    
    fn = SM[m]; lvls = LM[m]
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
    
    # 给所有票评分
    scored = []
    for s in pool:
        st = {"p":s.get("p",0) or 0,"cl":s.get("cl",0),"vr":s.get("vol_ratio",0) or 0,"hsl":(real.get(s["code"],{}).get("hsl",0) or 0),"dif":s.get("dif_val",0) or 0,"mg":s.get("macd_golden",0),"a5":s.get("above_ma5",0) or 0,"wrv":s.get("wr_val",0) or 50,"jv":s.get("j_val",0) or 0,"kv":s.get("k_val",0) or 0,"dv":s.get("d_val",0) or 0,"kdj_g":s.get("kdj_golden",0) or 0,"pos_in_day":s.get("pos_in_day",50) or 50}
        sc = fn(st)
        nh = (s.get("n",0) or 0)
        scored.append({"sc":sc,"nh":nh,"code":s["code"],"nm":names.get(s["code"],""),"p":s.get("p",0) or 0,"cl":s.get("cl",0),"vr":s.get("vol_ratio",0) or 0,"hsl":(real.get(s["code"],{}).get("hsl",0) or 0),"wrv":s.get("wr_val",0) or 50,"dif":s.get("dif_val",0) or 0,"mg":s.get("macd_golden",0),"kdj_g":s.get("kdj_golden",0) or 0})
    
    scored.sort(key=lambda x: -x["sc"])
    champ = scored[0]
    win = "W" if champ["nh"] >= 2.5 else "L"
    
    print(f"{dt}|{MN[m]:4s}|{champ['nm'][:8]}|{champ['code'][-6:]}|{champ['p']:5.1f}%|{champ['nh']:5.1f}%|{champ['sc']:5.1f}|{champ['cl']:4.0f}|{champ['vr']:4.2f}|{champ['hsl']:4.1f}|{champ['wrv']:4.0f}|{champ['dif']:5.3f}|{champ['mg']}|{champ['kdj_g']}|{win}")
    
    all_rows.append({"dt":dt,"mk":MN[m],"nm":champ["nm"],"code":champ["code"],"p":champ["p"],"nh":champ["nh"],"sc":champ["sc"],"cl":champ["cl"],"vr":champ["vr"],"hsl":champ["hsl"],"wrv":champ["wrv"],"dif":champ["dif"],"mg":champ["mg"],"kdj_g":champ["kdj_g"],"win":win})

# 行情统计
print("\n\n=== 行情统计 ===")
for m in ["真实涨日","虚涨日","跌日","横盘"]:
    rows = [r for r in all_rows if r["mk"] == m]
    w = sum(1 for r in rows if r["win"] == "W")
    t = len(rows)
    r = round(w*100/t,1) if t else 0
    print(f"{m}: {r}% ({w}/{t})")

# 近30天各票详情（排名靠前的）
print("\n\n=== 近30天各票特征 ===")
for r in all_rows:
    print(f"{r['dt']} {r['mk']} {r['nm']:>8}({r['code'][-6:]}) p={r['p']:.1f}% nh={r['nh']:.1f}% sc={r['sc']:.1f} cl={r['cl']:.0f} vr={r['vr']:.2f} hsl={r['hsl']:.1f} wrv={r['wrv']:.0f} dif={r['dif']:.3f} {'✅' if r['win']=='W' else '❌'}")
