#!/usr/bin/env python3
"""惩罚评分快速测试 — 基于已有v14 + 惩罚项"""
import json, os, time
from collections import defaultdict

CACHE_DIR=r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

def calc_ma(s,p):
    n=len(s); r={}
    for pd in p:
        ma=[None]*n
        for i in range(pd-1,n): ma[i]=sum(s[i-pd+1:i+1])/pd
        r[pd]=ma
    return r
def calc_macd(ps):
    n=len(ps); dif=[None]*n; dea=[None]*n; macd=[None]*n
    if n<26: return dif,dea,macd
    e12=[ps[0]]; e26=[ps[0]]
    for i in range(1,n):
        e12.append(e12[-1]*11/13+ps[i]*2/13); e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i]=e12[i]-e26[i]
    dea[0]=dif[0] if dif[0] else 0
    for i in range(1,n): dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    for i in range(n):
        if dif[i] is not None and dea[i] is not None: macd[i]=dif[i]-dea[i]
    return dif,dea,macd

print("📡 加载数据..."); t0=time.time()
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
all_codes={}
for fn in all_files:
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<80: continue
        if recs[-1]["date"]<"2020": continue
        code=fn.replace('.json','')
        c=[r['close'] for r in recs]; h=[r['high'] for r in recs]; l=[r['low'] for r in recs]
        o=[r['open'] for r in recs]; v=[r['volume'] for r in recs]
        mas=calc_ma(c,[5,10,20,60]); mas['v5']=calc_ma(v,[5])[5]
        dif,dea,macd=calc_macd(c)
        pct=[0.0]
        for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr_l)/14
        all_codes[code]={"c":c,"h":h,"l":l,"o":o,"v":v,"mas":mas,"dif":dif,"dea":dea,
                        "pct":pct,"recs":recs,"atr":atr}
    except: pass
print(f"✅ {len(all_codes)}只, {time.time()-t0:.0f}秒")

dates_2025=sorted(set(r["date"] for s in all_codes.values() for r in s["recs"] if r["date"].startswith("2025")))
dates_2026=sorted(set(r["date"] for s in all_codes.values() for r in s["recs"] if r["date"].startswith("2026")))

def pass_M1(c,s,d):
    if s["c"][d]>=80: return False
    m=s["mas"]
    if not (m[5][d] and m[10][d] and m[20][d] and m[60][d] and m[5][d]>m[10][d]>m[20][d]>m[60][d]): return False
    if not (s["dif"][d] and s["dea"][d] and s["dif"][d]>0 and s["dif"][d]>s["dea"][d]): return False
    a=s["atr"][d]; cl=s["c"][d]
    if not (a and cl>0 and a/cl*100>3): return False
    if not (m[60][d] and cl>m[60][d]): return False
    if s["c"][d]<=s["o"][d]: return False
    if not (m[5][d] and cl>m[5][d]): return False
    return True

# ── 收集候选并打标 ──
print("📝 收集候选...")
all_cands=[]
for yr, dates in [("2025",dates_2025),("2026",dates_2026)]:
    for dt in sorted(dates):
        cand=[]
        for code,sd in all_codes.items():
            di=next((i for i,r in enumerate(sd["recs"]) if r["date"]==dt), None)
            if di is None or di<80: continue
            if not pass_M1(code,sd,di): continue
            cl=sd["c"][di]; op=sd["o"][di]; hi=sd["h"][di]; lo=sd["l"][di]; vo=sd["v"][di]
            rng=hi-lo; shadow=(hi-max(cl,op))/(rng+0.001)*100 if rng>0 else 0
            body=abs(cl-op)/op*100
            atr_p=sd["atr"][di]/cl*100 if sd["atr"][di] and cl>0 else 0
            v5=sd["mas"]["v5"][di] if sd["mas"]["v5"][di] else 0
            vr=vo/v5 if v5>0 else 0
            rpos=(cl-lo)/(rng+0.001)*100 if rng>0 else 0
            next_h=round((sd["recs"][di+1]["high"]/cl-1)*100,2) if di+1<len(sd["recs"]) else None
            
            feat={"dt":dt,"yr":yr,"code":code,"shadow":shadow,"body":body,"atr_p":atr_p,
                  "vr":vr,"rpos":rpos,"pct":sd["pct"][di],"next_h":next_h}
            cand.append(feat)
        if len(cand)>=5:
            all_cands.append(cand)

print(f"✅ {len(all_cands)}天有候选")

# ── 各种评分方案 ──
def v14(d): return (max(0,35-d["shadow"]*1.2) if d["shadow"]<30 else 0) + min(d["body"]*3,25) + min(d["atr_p"]*2,16)

def make(penalties):
    """penalties = [cond1, amt1, cond2, amt2, ...]"""
    def s(d):
        sc=v14(d)
        for i in range(0,len(penalties),2):
            if penalties[i](d): sc+=penalties[i+1]
        return sc
    return s

penalty_schemes = [
    ("v14(基准)", []),
    ("+上影>20%-15", [lambda d: d["shadow"]>20, -15]),
    ("+涨>7%-15", [lambda d: d["pct"]>7, -15]),
    ("+收盘<60%-15", [lambda d: d["rpos"]<60, -15]),
    ("+上影>20%-15+涨>7%-10", [lambda d: d["shadow"]>20, -15, lambda d: d["pct"]>7, -10]),
    ("+上影>20%-20+涨>8%-10", [lambda d: d["shadow"]>20, -20, lambda d: d["pct"]>8, -10]),
    ("+上影>20%-10+收盘<60%-10", [lambda d: d["shadow"]>20, -10, lambda d: d["rpos"]<60, -10]),
    ("+涨>7%-10+收盘<60%-10", [lambda d: d["pct"]>7, -10, lambda d: d["rpos"]<60, -10]),
    ("+影20-15+涨7-10+收盘60-10", [lambda d: d["shadow"]>20, -15, lambda d: d["pct"]>7, -10, lambda d: d["rpos"]<60, -10]),
    ("+影25-20+涨8-15+收盘50-15", [lambda d: d["shadow"]>25, -20, lambda d: d["pct"]>8, -15, lambda d: d["rpos"]<50, -15]),
    ("+影15-20+涨6-15+收盘65-10", [lambda d: d["shadow"]>15, -20, lambda d: d["pct"]>6, -15, lambda d: d["rpos"]<65, -10]),
    ("+影20-25+涨8-20", [lambda d: d["shadow"]>20, -25, lambda d: d["pct"]>8, -20]),
    ("+影20-30(重罚上影)", [lambda d: d["shadow"]>20, -30]),
    ("+影25-15+涨7-10+收盘55-10", [lambda d: d["shadow"]>25, -15, lambda d: d["pct"]>7, -10, lambda d: d["rpos"]<55, -10]),
    ("+上影>15%-15+涨>6%-10+收盘<70%-10", [lambda d: d["shadow"]>15, -15, lambda d: d["pct"]>6, -10, lambda d: d["rpos"]<70, -10]),
]

# ═══ 跑测试 ═══
print()
print("="*80)
print("🏆 惩罚规则测试")
print("="*80)
print(f"{'方案':<40} {'2025':>14} {'2026':>14} {'平均':>8}")
print("-"*76)

results=[]
for sname, penalties in penalty_schemes:
    scorer=make(penalties)
    res={}
    for yn in ["2025","2026"]:
        wins=0; total=0
        for cand in all_cands:
            if cand[0]["yr"]!=yn: continue
            cand.sort(key=scorer, reverse=True)
            champ=cand[0]
            total+=1
            if champ["next_h"] and champ["next_h"]>=2.5: wins+=1
        res[yn]=(wins/total*100 if total else 0, total)
    
    avg=(res["2025"][0]+res["2026"][0])/2
    results.append((avg,res["2025"][0],res["2025"][1],res["2026"][0],res["2026"][1],sname))
    mk="🔥" if avg>=85 else ("✅" if avg>=83 else "")
    print(f"{sname:<40} {res['2025'][0]:>5.1f}%/{res['2025'][1]:>3}d {res['2026'][0]:>5.1f}%/{res['2026'][1]:>3}d {avg:>5.1f}% {mk}")

print(f"\n⏱ {time.time()-t0:.0f}秒")
