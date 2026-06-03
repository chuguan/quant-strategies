#!/usr/bin/env python3
"""上影线权重调整 — 测试各种扣分力度"""
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

# 收集候选（快照所有必要数据）
print("📝 收集候选...")
all_cands=[]  # list of (year, date_list_of_candidates)
for dt in sorted(set(dates_2025+dates_2026)):
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
        cand.append({"yr":dt[:4],"shadow":shadow,"body":body,"atr_p":atr_p,"next_h":next_h})
    if len(cand)>=5:
        all_cands.append(cand)

print(f"✅ {len(all_cands)}天有候选")

# ── 各种上影权重方案 ──
# 基准：v14 原版 35-1.2x
# 每种方案 = (名称, 上影函数(shadow->分), 是否保留实体+ATR不变)
schemes = [
    # 原版
    ("v14原版(35-1.2x)", lambda s: max(0,35-s*1.2) if s<30 else 0),
    
    # 更陡的线性扣分（每1%上影扣更多）
    ("A:40-2x(满分40,扣更快)", lambda s: max(0,40-s*2) if s<20 else 0),
    ("B:30-1.5x(满分30,中等)", lambda s: max(0,30-s*1.5) if s<20 else 0),
    ("C:50-2.5x(满分50,超快)", lambda s: max(0,50-s*2.5) if s<20 else 0),
    
    # 分段扣分
    ("D:分段-上影<5%满分,每5%扣10", lambda s: 40-s//5*10 if s<20 else 0),
    
    # 指数级扣分（超过15%直接扣光）
    ("E:上影<5%=30,10%=20,15%=10,>15%=0", lambda s: 30 if s<5 else (20 if s<10 else (10 if s<15 else 0))),
    
    # 只有上影极短的才给高分
    ("F:20-1x(满分20,扣到0为止)", lambda s: max(0,20-s) if s<20 else 0),
    
    # 温和版（原来的基础上加大力度但不断崖）
    ("G:38-1.5x(满分38,扣更快)", lambda s: max(0,38-s*1.5) if s<25 else 0),
    
    # 砍掉所有>20%的票
    ("H:上影>20%直接0分", lambda s: 35-s*1.2 if s<20 else 0),
    
    # 最严格
    ("I:上影>15%=0,<5%得30,其余20-1.5x", lambda s: 30 if s<5 else (max(0,28-s*1.5) if s<15 else 0)),
]

# 跑测试
print(f"\n{'='*80}")
print("🏆 上影权重测试 — 只改上影公式，实体+ATR不变")
print(f"{'='*80}")
print(f"{'方案':<40} {'2025胜率':>14} {'2026胜率':>14} {'两年平均':>10} {'变化':>8}")
print("-"*86)

baseline_avg=0
results=[]
for sname, shadow_fn in schemes:
    res={}
    for yn in ["2025","2026"]:
        wins=0; total=0
        for cand in all_cands:
            if cand[0]["yr"]!=yn: continue
            # 评分
            scored=[]
            for d in cand:
                sc=shadow_fn(d["shadow"]) + min(d["body"]*3,25) + min(d["atr_p"]*2,16)
                scored.append((sc,d))
            scored.sort(key=lambda x:x[0], reverse=True)
            champ=scored[0][1]
            total+=1
            if champ["next_h"] and champ["next_h"]>=2.5: wins+=1
        res[yn]=(wins/total*100 if total else 0, total)
    
    avg=(res["2025"][0]+res["2026"][0])/2
    if sname=="v14原版(35-1.2x)": baseline_avg=avg
    change=avg-baseline_avg if baseline_avg else 0
    results.append((avg,change,res["2025"][0],res["2025"][1],res["2026"][0],res["2026"][1],sname))
    mk="🔥" if change>0 else ("✅" if change>=-0.5 else "❌")
    print(f"{sname:<40} {res['2025'][0]:>5.1f}%/{res['2025'][1]:>3}d {res['2026'][0]:>5.1f}%/{res['2026'][1]:>3}d {avg:>6.2f}% {change:>+5.1f}% {mk}")

# 排序看最佳
results.sort(reverse=True)
print(f"\n{'='*80}")
print("🏆 排名（按两年平均胜率）")
print(f"{'='*80}")
for avg,chg,w25,t25,w26,t26,sname in results:
    mk="🔥" if chg>0 else ""
    print(f"  {sname:<40} 平均{avg:.2f}% (变化{chg:+.1f}%) {mk}")

print(f"\n⏱ {time.time()-t0:.0f}秒")
