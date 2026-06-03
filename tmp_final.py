#!/usr/bin/env python3
"""最终版 — 各行情独立取最优"""
import sys, os, pickle
SCRIPTS_DIR = r"C:\Users\12546\AppData\Local\hermes\scripts"
sys.path.insert(0, os.path.join(SCRIPTS_DIR, "archive", "V9"))
for mod in list(sys.modules.keys()):
    if "V9" in mod: del sys.modules[mod]
from archive.V9 import 分而治之_V9_真实涨日_评分策略 as zzr
from archive.V9 import 分而治之_V9_跌日_评分策略 as dr
from archive.V9 import 分而治之_V9_横盘_评分策略 as hp
from archive.V9 import 分而治之_V9_虚涨日_评分策略 as xzr

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

# 真实涨日老司机（90%）
def lsj_real_up(st):
    p=st.get("p",0);d=st.get("dif",0);w=st.get("wrv",50);c=st.get("cl",50)
    h=st.get("hsl",0);dv=st.get("dv",50);v=st.get("vr",0);po=st.get("pos_in_day",50)
    a5=st.get("a5",0);mg=st.get("mg",0);kg=st.get("kdj_g",0)
    s=min(p/3.0,1)*70+min(d/0.5,1)*50+max(0,min((50-w)/30,1))*30+min(c/80,1)*30
    s+=min(h/8,1)*20+min(dv/65,1)*20+min(v/1.3,1)*20+max(0,min((100-po)/50,1))*10
    if a5: s+=8
    if d>0.3 and p>2.0: s+=8
    if w<30 and c>75: s+=5
    if h>5 and v>1.1: s+=5
    if mg and kg: s+=3
    return s

# 横盘加分版（77.8%）
def flat_bonus(st):
    bs=hp.score(st)
    d=st.get("dif",0);w=st.get("wrv",50);c=st.get("cl",50);p=st.get("p",0)
    h=st.get("hsl",0);po=st.get("pos_in_day",50);kv=st.get("kv",50);dv=st.get("dv",50);v=st.get("vr",0)
    if d>0.3: bs+=10
    if d>0.5: bs+=8
    if d>1.0: bs+=5
    if w<30: bs+=8
    if w<20: bs+=6
    if w<10: bs+=4
    if c>75: bs+=6
    if c>85: bs+=5
    if p>2.0: bs+=5
    if p>3.0: bs+=3
    if h>5: bs+=3
    if h>8: bs+=3
    if po<60: bs+=3
    if po<45: bs+=2
    if kv>65 and dv>60: bs+=4
    if p>2.0 and d>0.3: bs+=5
    if d>0.3 and w<30: bs+=3
    if c>75 and h>5: bs+=3
    if p>2.0 and v>1.1: bs+=3
    return bs

SCO = {
    "real_up": lambda st: lsj_real_up(st),
    "fake_up": lambda st: xzr.score(st),
    "down": lambda st: dr.score(st),
    "flat": lambda st: flat_bonus(st),
}
MKT = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
MOD = {"real_up":zzr,"fake_up":xzr,"down":dr,"flat":hp}

def runner(dates):
    tw,tt=0,0
    for mk in ["real_up","fake_up","down","flat"]:
        mod=MOD[mk];fn=SCO[mk];lvls=mod.LEVELS;wi,to=0,0
        for dt in dates:
            ss=data.get(dt,[])
            if not ss: continue
            m=cls(ss)
            if m!=mk: continue
            pool=None
            for lv in lvls:
                pool=[]
                for s in ss:
                    code=s.get("code","")
                    p=(s.get("p",0) or 0)
                    if p<lv["p_min"] or p>lv["p_max"]: continue
                    if p>=8: continue
                    vr=(s.get("vol_ratio",0) or 0)
                    if vr<lv["vr_min"] or vr>lv["vr_max"]: continue
                    ri=real.get(code)
                    if not ri: continue
                    hsl=(ri.get("hsl",0) or 0)
                    if hsl<lv["hs_min"] or hsl>lv["hs_max"]: continue
                    if (ri.get("shizhi",0) or 0)>=lv["sz_max"]: continue
                    nm=names.get(code,"")
                    if "ST" in nm or "*ST" in nm or "退" in nm: continue
                    cl=s.get("cl",0)
                    if cl<lv["cl_min"] or cl>lv["cl_max"]: continue
                    if (s.get("n",0) or 0)<=0: continue
                    pool.append(s)
                if len(pool)>8: break
                pool=None
            if not pool or len(pool)<=8: continue
            scd=[]
            for s in pool:
                st_=dict(p=s.get("p",0) or 0,cl=s.get("cl",0),vr=s.get("vol_ratio",0) or 0,hsl=(real.get(s["code"],{}).get("hsl",0) or 0),dif=s.get("dif_val",0) or 0,mg=s.get("macd_golden",0),a5=s.get("above_ma5",0) or 0,wrv=s.get("wr_val",0) or 50,jv=s.get("j_val",0) or 0,kv=s.get("k_val",0) or 0,dv=s.get("d_val",0) or 0,kdj_g=s.get("kdj_golden",0) or 0,pos_in_day=s.get("pos_in_day",50) or 50)
                sc=fn(st_);nh=(s.get("n",0) or 0)
                scd.append({"sc":sc,"nh":nh})
            if not scd: continue
            scd.sort(key=lambda x:-x["sc"]);to+=1
            if scd[0]["nh"]>=2.5: wi+=1
        r=round(wi*100/to,1) if to else 0
        bar="█"*int(r/5)+"░"*(20-int(r/5))
        print(f"  {MKT[mk]:6s} {bar} {r:5.1f}% ({wi:2d}/{to:2d})")
        tw+=wi;tt+=to
    r=round(tw*100/tt,1)
    print(f"  {'总':>6s} {'█'*int(r/5)+'░'*(20-int(r/5))} {r:.1f}% ({tw}/{tt})")

all_dates = sorted(dt for dt in data if "2025-01-01" <= dt < "2026-06-01")
print("== 最优组合（真实涨日老司机+横盘加分+其他V9） ==")
print("--- 30天 ---")
runner(all_dates[-30:])
print("--- 333天 ---")
runner(all_dates[:-1][-333:])
