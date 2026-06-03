"""V9 30天回测 — 用新缓存（全量含负涨幅）"""
import sys, os, pickle, importlib

SCRIPTS_DIR = r"C:\Users\12546\AppData\Local\hermes\scripts"
sys.path.insert(0, os.path.join(SCRIPTS_DIR, "archive", "V9"))

# 强制清除模块缓存
for mod in list(sys.modules.keys()):
    if "V9" in mod: del sys.modules[mod]

# 加载V9评分策略
from archive.V9 import 分而治之_V9_真实涨日_评分策略 as zzr_mod
from archive.V9 import 分而治之_V9_跌日_评分策略 as dr_mod
from archive.V9 import 分而治之_V9_横盘_评分策略 as hp_mod
from archive.V9 import 分而治之_V9_虚涨日_评分策略 as xzr_mod

# 加载新缓存
d = pickle.load(open(os.path.join(SCRIPTS_DIR, "big_cache_full.pkl"), "rb"))
data, real, names = d["data"], d["real"], d["names"]

def cls(stocks):
    """行情分类 — 用全量数据（含负涨幅）"""
    if not stocks: return "flat"
    ps = [s.get("p",0) or 0 for s in stocks if abs(s.get("p",0) or 0) < 15]
    vrs = [s.get("vol_ratio",0) or 0 for s in stocks if (s.get("vol_ratio",0) or 0) > 0]
    if not ps: return "flat"
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if ap > 0.5:
        return "fake_up" if hot < 15 or av < 0.9 else "real_up"
    if ap < -0.5:
        return "down"
    return "flat"

MKT_NAMES = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
MODS = {"real_up": zzr_mod, "fake_up": xzr_mod, "down": dr_mod, "flat": hp_mod}

dates = sorted(dt for dt in data if "2025-01-01" <= dt < "2026-06-01")[-30:]
print(f"最近30天: {dates[0]} ~ {dates[-1]}")
print()

# 统计各行情天数
mkt_counts = {}
for dt in dates:
    ss = data.get(dt, [])
    m = cls(ss)
    mkt_counts[m] = mkt_counts.get(m, 0) + 1
print("行情分布（30天）:")
for k, v in sorted(mkt_counts.items(), key=lambda x: -x[1]):
    print(f"  {MKT_NAMES.get(k,k)}: {v}天")

print()
print("="*65)
print(f"  V9 30天回测")
print("="*65)

all_results = []
for mkt_key, mod in MODS.items():
    lvls = mod.LEVELS
    fn = mod.score
    wins = 0; total = 0
    fail_days = []
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
            nh = s.get("n",0) or 0
            nm = names.get(code, "")
            scored.append({"sc":sc,"nh":nh,"code":code,"nm":nm,"p":s.get("p",0),"dt":dt})
        
        if not scored: continue
        scored.sort(key=lambda x: (-x["sc"], -x["p"]))
        total += 1
        champ = scored[0]
        win = champ["nh"] >= 2.5
        if win: wins += 1
        else:
            fail_days.append(f"  ❌ {champ['dt']} {champ['nm']}({champ['code']}) p={champ['p']:.1f}% nh={champ['nh']:.1f}% sc={champ['sc']:.1f}")
    
    mkt_name = MKT_NAMES.get(mkt_key, mkt_key)
    if total == 0:
        print(f"\n📊 {mkt_name}: ⚠️ 30天内无交易日")
        all_results.append({"name": mkt_name, "wins":0,"total":0,"rate":0,"fail_days":[]})
        continue
    rate = round(wins*100/total, 1)
    print(f"\n📊 {mkt_name}: {rate}% ({wins}/{total})")
    bar = "█" * int(rate/5) + "░" * (20 - int(rate/5))
    print(f"   {bar} {rate}%")
    if fail_days:
        print(f"  失败日 ({len(fail_days)}):")
        for f in fail_days[:5]:
            print(f)
    all_results.append({"name": mkt_name, "wins":wins,"total":total,"rate":rate})

print()
print("="*65)
print("  V9 30天汇总")
print("="*65)
tw = sum(r["wins"] for r in all_results)
tt = sum(r["total"] for r in all_results)
if tt > 0:
    print(f"  总冠军胜率: {round(tw*100/tt,1)}% ({tw}/{tt})")
for r in all_results:
    if r["total"] > 0:
        bar = "█" * int(r["rate"]/5) + "░" * (20 - int(r["rate"]/5))
        print(f"  {r['name']:6s} {bar} {r['rate']:5.1f}% ({r['wins']:2d}/{r['total']:2d})")
print()
