#!/usr/bin/env python3
"""上影多权重快速测试 — 三引线方案"""
import json, os, time
CACHE_DIR=r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# ── 高效加载（只算必要的）──
def calc_ma(s,p):
    n=len(s); r={}
    for pd in p:
        ma=[None]*n
        for i in range(pd-1,n): ma[i]=sum(s[i-pd+1:i+1])/pd
        r[pd]=ma
    return r
def calc_macd(ps):
    n=len(ps); dif=[None]*n; dea=[None]*n
    if n<26: return dif,dea
    e12=[ps[0]]; e26=[ps[0]]
    for i in range(1,n):
        e12.append(e12[-1]*11/13+ps[i]*2/13); e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i]=e12[i]-e26[i]
    dea[0]=dif[0] if dif[0] else 0
    for i in range(1,n): dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    return dif,dea

print("📡 加载..."); t0=time.time()
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
        mas=calc_ma(c,[5,10,20,60])
        dif,dea=calc_macd(c)
        pct=[0.0]
        for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr_l)/14
        all_codes[code]={"c":c,"h":h,"l":l,"o":o,"v":v,"mas":mas,"dif":dif,"dea":dea,"pct":pct,"recs":recs,"atr":atr}
    except: pass
print(f"✅ {len(all_codes)}只, {time.time()-t0:.0f}秒")

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

# ── 只加载2025+2026日期 ──
dates_2025=sorted(set(r["date"] for s in all_codes.values() for r in s["recs"] if r["date"].startswith("2025")))
dates_2026=sorted(set(r["date"] for s in all_codes.values() for r in s["recs"] if r["date"].startswith("2026")))
all_dates=sorted(set(dates_2025+dates_2026))
print(f"📅 2025:{len(dates_2025)}天 2026:{len(dates_2026)}天")

# ═══ 一次性收集所有候选（只保存关键特征）═══
print("📝 收集特征...")
# 按年分组：list of (year, list_of_candidate_features)
data_by_year={"2025":[],"2026":[]}

for dt in all_dates:
    cand=[]
    for code,sd in all_codes.items():
        di=next((i for i,r in enumerate(sd["recs"]) if r["date"]==dt), None)
        if di is None or di<80: continue
        if not pass_M1(code,sd,di): continue
        cl=sd["c"][di]; op=sd["o"][di]; hi=sd["h"][di]; lo=sd["l"][di]
        rng=hi-lo; shadow=(hi-max(cl,op))/(rng+0.001)*100 if rng>0 else 0
        body=abs(cl-op)/op*100
        atr_p=sd["atr"][di]/cl*100 if sd["atr"][di] and cl>0 else 0
        next_h=round((sd["recs"][di+1]["high"]/cl-1)*100,2) if di+1<len(sd["recs"]) else None
        cand.append({"s":shadow,"b":body,"a":atr_p,"n":next_h})
    if len(cand)>=5:
        yr=dt[:4]
        data_by_year[yr].append(cand)

print(f"  2025:{len(data_by_year['2025'])}天  2026:{len(data_by_year['2026'])}天")

# ═══ 上影权重方案（三引线及其变体）═══
# 每种方案 = (名称, 上影得分函数)
import sys
weight_schemes = [
    # ── 三引线基础版 ──
    ("v14(35-1.2x)", lambda s: max(0,35-s*1.2) if s<30 else 0),
    ("A(40-2x)", lambda s: max(0,40-s*2) if s<20 else 0),
    ("B(30-1.5x)", lambda s: max(0,30-s*1.5) if s<20 else 0),
    # ── 更多力度 ──
    ("C(50-2.5x)", lambda s: max(0,50-s*2.5) if s<20 else 0),
    ("D(25-1x)", lambda s: max(0,25-s) if s<20 else 0),
    ("E(20-0.8x)", lambda s: max(0,20-s*0.8) if s<25 else 0),
    ("F(分段:5%内30,10%20,15%10)", lambda s: 30 if s<5 else (20 if s<10 else (10 if s<15 else 0))),
    ("G(45-1.8x)", lambda s: max(0,45-s*1.8) if s<25 else 0),
    ("H(38-1.5x)", lambda s: max(0,38-s*1.5) if s<25 else 0),
    ("I(极严:15%以上0分)", lambda s: max(0,30-s*2) if s<15 else 0),
    ("J(55-2x)", lambda s: max(0,55-s*2) if s<27 else 0),
    ("K(极简:上影<10%+20)", lambda s: 20 if s<10 else 0),
    # ── 更多变体 ──
    ("L(100-4x)", lambda s: max(0,100-s*4) if s<25 else 0),
    ("M(60-3x)", lambda s: max(0,60-s*3) if s<20 else 0),
    ("N(28-1.2x)", lambda s: max(0,28-s*1.2) if s<23 else 0),
]

# ═══ 跑全部方案 ═══
print(f"\n{'='*90}")
print("🏆 三引线权重测试 — 所有方案#1冠军胜率")
print(f"{'='*90}")
print(f"{'方案':<20} {'2025胜率':>14} {'2026胜率':>14} {'平均':>8}")
print("-"*56)

baseline_avg=0
all_results=[]

for sname, shadow_fn in weight_schemes:
    res={}
    for yn in ["2025","2026"]:
        wins=0; total=0
        for cand in data_by_year[yn]:
            scored=[(shadow_fn(d["s"])+min(d["b"]*3,25)+min(d["a"]*2,16), d) for d in cand]
            scored.sort(key=lambda x:x[0], reverse=True)
            total+=1
            if scored[0][1]["n"] and scored[0][1]["n"]>=2.5: wins+=1
        res[yn]=(wins/total*100 if total else 0,total)
    avg=(res["2025"][0]+res["2026"][0])/2
    if "v14" in sname: baseline_avg=avg
    change=avg-baseline_avg if baseline_avg else 0
    all_results.append((avg,change,sname,res["2025"][0],res["2025"][1],res["2026"][0],res["2026"][1]))
    mk="🔥" if change>0.5 else ("✅" if change>=-0.5 else "❌")
    print(f"{sname:<20} {res['2025'][0]:>5.1f}%/{res['2025'][1]:>3}d {res['2026'][0]:>5.1f}%/{res['2026'][1]:>3}d {avg:>5.2f}% {mk}")

# 排名
print(f"\n{'='*90}")
print("🏆 排名（比v14好的标🔥）")
print(f"{'='*90}")
all_results.sort(reverse=True)
for avg,chg,sname,w25,t25,w26,t26 in all_results:
    mk="🔥" if chg>0 else ("✅" if chg>=0 else "")
    print(f"  {sname:<20} 平均{avg:.2f}% (vs v14:{chg:+.1f}%) 2025:{w25:.1f}%/{t25}d 2026:{w26:.1f}%/{t26}d {mk}")

print(f"\n⏱ {time.time()-t0:.0f}秒")
