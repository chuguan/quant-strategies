#!/usr/bin/env python3
"""带惩罚规则的v14评分测试"""
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
def calc_kdj(h,l,c,n=9):
    L=len(c); k=[50.0]*L; d=[50.0]*L; j=[50.0]*L
    if L<n: return k,d,j
    for i in range(n-1,L):
        hh=max(h[i-n+1:i+1]); ll=min(l[i-n+1:i+1])
        rsv=50.0 if hh==ll else (c[i]-ll)/(hh-ll)*100
        if i>n-1: k[i]=2/3*k[i-1]+1/3*rsv; d[i]=2/3*d[i-1]+1/3*k[i]
        j[i]=3*k[i]-2*d[i]
    return k,d,j

print("📡 加载数据..."); t0=time.time()
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
all_codes={}
for fn in all_files:
    fp=os.path.join(CACHE_DIR,fn)
    try:
        with open(fp,'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<80: continue
        if recs[-1]["date"]<"2020": continue
        code=fn.replace('.json','')
        c=[r['close'] for r in recs]; h=[r['high'] for r in recs]; l=[r['low'] for r in recs]
        o=[r['open'] for r in recs]; v=[r['volume'] for r in recs]
        mas=calc_ma(c,[5,10,20,60]); mas['v5']=calc_ma(v,[5])[5]
        dif,dea,macd=calc_macd(c)
        k,d,j=calc_kdj(h,l,c)
        pct=[0.0]
        for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr_l)/14
        pos20=[None]*len(c); ma5_sl=[None]*len(c)
        for i in range(19,len(c)):
            h20=max(h[i-19:i+1]); l20=min(l[i-19:i+1])
            pos20[i]=(c[i]-l20)/(h20-l20+0.001)*100
        for i in range(4,len(c)):
            if mas[5][i] and mas[5][i-4]: ma5_sl[i]=(mas[5][i]-mas[5][i-4])/mas[5][i-4]*100
        all_codes[code]={"c":c,"h":h,"l":l,"o":o,"v":v,"mas":mas,"dif":dif,"dea":dea,
                        "pct":pct,"recs":recs,"atr":atr,"k":k,"d":d,"j":j,
                        "pos20":pos20,"ma5_sl":ma5_sl}
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

# ── 预收集候选数据 ──
print("📝 收集候选...")
stock_days=[]  # 扁平列表
for dt in sorted(set(dates_2025+dates_2026)):
    for code,sd in all_codes.items():
        try:
            di=None
            for idx,r in enumerate(sd["recs"]):
                if r["date"]==dt: di=idx; break
            if di is None or di<80: continue
            if not pass_M1(code,sd,di): continue
            
            cl=sd["c"][di]; op=sd["o"][di]; hi=sd["h"][di]; lo=sd["l"][di]; vo=sd["v"][di]
            rng=hi-lo; shadow=(hi-max(cl,op))/(rng+0.001)*100 if rng>0 else 0
            body=abs(cl-op)/op*100
            atr_p=sd["atr"][di]/cl*100 if sd["atr"][di] and cl>0 else 0
            v5=sd["mas"]["v5"][di] if sd["mas"]["v5"][di] else 0
            vr=vo/v5 if v5>0 else 0
            rpos=(cl-lo)/(rng+0.001)*100 if rng>0 else 0
            
            next_h=None
            for j,r2 in enumerate(sd["recs"]):
                if r2["date"]==dt and j+1<len(sd["recs"]):
                    next_h=round((sd["recs"][j+1]["high"]/cl-1)*100,2); break
            
            stock_days.append({"date":dt,"code":code,"year":dt[:4],
                "pct":sd["pct"][di],"shadow":shadow,"body":body,"atr_p":atr_p,
                "vr":vr,"rpos":rpos,"pos20":sd["pos20"][di],
                "ma5_sl":sd["ma5_sl"][di],"j":sd["j"][di],"next_h":next_h})
        except: continue

print(f"✅ {len(stock_days)}条候选记录")

# 按日期分组
from collections import defaultdict
by_date=defaultdict(list)
for sd in stock_days:
    by_date[sd["date"]].append(sd)

# ── 定义评分方案 ──
def make_scorer(shadow_penalty_threshold, shadow_penalty_amount,
                pct_penalty_threshold, pct_penalty_amount,
                rpos_penalty_threshold, rpos_penalty_amount):
    """工厂函数：生成带惩罚规则的评分"""
    def scorer(d):
        # v14基础分
        sc=0
        if d["shadow"]<30: sc+=max(0,35-d["shadow"]*1.2)
        sc+=min(d["body"]*3,25)
        sc+=min(d["atr_p"]*2,16)
        # 惩罚
        if d["shadow"]>shadow_penalty_threshold: sc+=shadow_penalty_amount
        if d["pct"]>pct_penalty_threshold: sc+=pct_penalty_amount
        if d["rpos"]<rpos_penalty_threshold: sc+=rpos_penalty_amount
        return sc
    return scorer

# 各种惩罚组合
schemes = []

# 基准
schemes.append(("v14(基准·无惩罚)", make_scorer(999,0,999,0,0,0)))

# 单惩罚
schemes.append(("v14+上影>20%-15", make_scorer(20,-15,999,0,0,0)))
schemes.append(("v14+涨幅>7%-15", make_scorer(999,0,7,-15,0,0)))
schemes.append(("v14+收盘<60%-15", make_scorer(999,0,999,0,60,-15)))

# 双惩罚
schemes.append(("v14+上影>20%-15+涨>7%-15", make_scorer(20,-15,7,-15,0,0)))
schemes.append(("v14+上影>20%-20+涨>8%-10", make_scorer(20,-20,8,-10,0,0)))
schemes.append(("v14+上影>20%-10+收盘<60%-10", make_scorer(20,-10,999,0,60,-10)))
schemes.append(("v14+涨>7%-10+收盘<60%-10", make_scorer(999,0,7,-10,60,-10)))

# 三惩罚（不同力度）
schemes.append(("v14+上影>20%-15+涨>7%-10+收盘<60%-10", make_scorer(20,-15,7,-10,60,-10)))
schemes.append(("v14+上影>25%-20+涨>8%-15+收盘<50%-15", make_scorer(25,-20,8,-15,50,-15)))
schemes.append(("v14+上影>15%-20+涨>6%-15+收盘<65%-10", make_scorer(15,-20,6,-15,65,-10)))

# 惩罚力度大
schemes.append(("v14+上影>20%-25+涨>8%-20", make_scorer(20,-25,8,-20,0,0)))
schemes.append(("v14+上影>20%-30(重罚)", make_scorer(20,-30,999,0,0,0)))
schemes.append(("v14+上影>25%-15+涨>7%-10+收盘<55%-10", make_scorer(25,-15,7,-10,55,-10)))

# ═══ 跑测试 ═══
print(f"\n{'='*90}")
print("🏆 惩罚规则测试 — 2025+2026")
print(f"{'='*90}")
print(f"\n{'评分方案':<44} {'2025胜率':>10} {'2026胜率':>10} {'平均':>8}")
print("-"*72)

results=[]
for sname, scorer in schemes:
    wr_25=0; tot_25=0; wr_26=0; tot_26=0
    for yr, dates in [("2025",dates_2025),("2026",dates_2026)]:
        wins=0; total=0
        for dt in sorted(dates):
            cds=by_date.get(dt,[])
            if len(cds)<5: continue
            cds.sort(key=scorer, reverse=True)
            champ=cds[0]
            total+=1
            if champ["next_h"] and champ["next_h"]>=2.5: wins+=1
        wr=wins/total*100 if total else 0
        if yr=="2025": wr_25=wr; tot_25=total
        else: wr_26=wr; tot_26=total
    
    avg=(wr_25+wr_26)/2
    results.append((avg,wr_25,wr_26,sname))
    mk="🔥" if avg>=85 else ("✅" if avg>=82 else "")
    print(f"{sname:<44} {wr_25:>6.1f}%/{tot_25:>3}d {wr_26:>6.1f}%/{tot_26:>3}d {avg:>5.1f}% {mk}")

print(f"\n⏱ {time.time()-t0:.0f}秒")
