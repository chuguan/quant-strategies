#!/usr/bin/env python3
"""前三名74%组合 + 多涨幅区间回撤优化"""
import json, os, time, random
from collections import defaultdict

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

def calc_ma_full(s,pd):
    n=len(s); r=[None]*n
    for i in range(pd-1,n): r[i]=sum(s[i-pd+1:i+1])/pd
    return r

def calc_macd(ps):
    n=len(ps); dif=[None]*n; dea=[None]*n; macd=[None]*n
    if n<26: return dif,dea,macd
    e12=[ps[0]]; e26=[ps[0]]
    for i in range(1,n):
        e12.append(e12[-1]*11/13+ps[i]*2/13); e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i]=e12[i]-e26[i]; dea[0]=dif[0] if dif[0] else 0
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

t0=time.time()
print("加载3427只...")
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files=[f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]

stock_days=[]; loaded=0
for fn in main_files:
    fp=os.path.join(CACHE_DIR,fn)
    try:
        with open(fp,'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<80: continue
        code=fn.replace('.json','')
        c=[r['close'] for r in recs]; h=[r['high'] for r in recs]; l=[r['low'] for r in recs]
        o=[r['open'] for r in recs]; v=[r['volume'] for r in recs]
        mas5=calc_ma_full(c,5); mas10=calc_ma_full(c,10); mas20=calc_ma_full(c,20); mas60=calc_ma_full(c,60)
        v5=calc_ma_full(v,5)
        dif,dea,macd=calc_macd(c); k,d,j=calc_kdj(h,l,c)
        pct=[0.0]
        for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for n in range(14,len(c)):
                tr=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(n-13,n+1)]
                atr[n]=sum(tr)/14
        pos20=[None]*len(c)
        for n in range(19,len(c)):
            h20=max(h[n-19:n+1]); l20=min(l[n-19:n+1])
            pos20[n]=(c[n]-l20)/(h20-l20+0.001)*100
        
        for i in range(80,len(c)-1):
            dt=recs[i]["date"]
            if not dt.startswith("2026"): continue
            cl=c[i]; op=o[i]; hi=h[i]; lo=l[i]; vo=v[i]
            vr=vo/(v5[i] or 1)
            atr_p=atr[i]/cl*100 if atr[i] and cl>0 else 0
            sr=(hi-max(cl,op))/(hi-lo+0.001)*100
            body=abs(cl-op)/op*100
            
            flags={"date":dt,"code":code}
            flags["price"]=cl<80
            flags["ma_full"]=bool(mas5[i] and mas10[i] and mas20[i] and mas60[i] and mas5[i]>mas10[i]>mas20[i]>mas60[i])
            flags["macd_strict"]=bool(dif[i] and dea[i] and dif[i]>0 and dif[i]>dea[i])
            flags["atr3"]=atr_p>3
            flags["ma60"]=bool(mas60[i] and cl>mas60[i])
            flags["yang"]=cl>op
            flags["ma5_up"]=bool(mas5[i] and cl>mas5[i])
            flags["vr12"]=1<=vr<=2
            flags["body15"]=body>1.5
            flags["j_50"]=bool(j[i] and j[i]>50)
            flags["shadow20"]=sr<20
            flags["pct"]=pct[i]
            next_h=(recs[i+1]["high"]/cl-1)*100
            flags["next_win"]=next_h>=2.5
            # v1评分
            sc=0; sc+=atr_p*2
            if pct[i]>0: sc+=10
            if 1<vr<2: sc+=15
            elif vr>2: sc+=8
            sc+=(pos20[i] or 50)*0.2
            if flags["j_50"]: sc+=10
            flags["score"]=sc
            stock_days.append(flags)
        
        loaded+=1
        if loaded%500==0: print(f"  {loaded}/{len(main_files)}")
    except: pass
print(f"加载{loaded}只, {len(stock_days)}条")

by_date=defaultdict(list)
for sd in stock_days: by_date[sd["date"]].append(sd)

M1=["price","ma_full","macd_strict","atr3","ma60"]

TOP3 = [
    ("#1 M1+阳线+站MA5", M1+["yang","ma5_up"]),
    ("#2 M1+阳线+量比1~2", M1+["yang","vr12"]),
    ("#3 M1+阳线+实>1.5+量1~3+J>50+站MA5", M1+["yang","body15","vr12","j_50","ma5_up"]),
]

def eval_with_pct(flags, pmin=None, pmax=None, mc=10):
    dates=sorted(by_date.keys())
    pd_=0; wc=0; tc=0
    for dt in dates:
        cand=[sd for sd in by_date[dt] if all(sd[f] for f in flags)]
        if pmin is not None: cand=[sd for sd in cand if sd["pct"]>=pmin]
        if pmax is not None: cand=[sd for sd in cand if sd["pct"]<=pmax]
        tc+=len(cand)
        if len(cand)>=mc:
            pd_+=1
            cand.sort(key=lambda x:x["score"],reverse=True)
            if cand[0]["next_win"]: wc+=1
    wr=wc/pd_*100 if pd_ else 0; pr=pd_/len(dates)*100; ac=tc/len(dates)
    return wr,pr,ac

PCT_TESTS = [
    ("全部(含涨停)",None,100),("<9.8%",None,9.8),("<9%",None,9),
    ("<8.5%",None,8.5),("<8%",None,8),("<7.5%",None,7.5),
    ("<7%",None,7),("<6.5%",None,6.5),("<6%",None,6),("<5%",None,5),
    ("0~3%",0,3),("1~4%",1,4),("3~7%",3,7),("2~6%",2,6),
    ("0~5%",0,5),("4~9.8%",4,9.8),("0~9.8%",0,9.8),
    ("1~9.8%",1,9.8),("-2~9.8%",-2,9.8),
    ("3~8%",3,8),("2~7%",2,7),("4~7%",4,7),
    ("2~8.5%",2,8.5),("0~7%",0,7),
]

print()
print("="*90)
print("前三名组合 + 多涨幅区间优化")
print("="*90)

best_ever={"score":0}

for combo_name, flags in TOP3:
    sep="="*90
    print(f"\n{sep}")
    print(f"组合: {combo_name}")
    print(f"{sep}")
    print(f"{'涨幅区间':<20} {'胜率':>8} {'出票':>8} {'候选':>6} {'提升'}")
    print("-"*50)
    
    base_wr,base_pr,base_ac=eval_with_pct(flags,None,100)
    print(f"{'无限制(含涨停)':<20} {base_wr:>6.1f}% {base_pr:>6.1f}% {base_ac:>5.0f} 0%")
    
    for name, pmin, pmax in PCT_TESTS:
        wr,pr,ac=eval_with_pct(flags,pmin,pmax,10)
        lift=wr-base_wr
        mark="🔥" if wr>65 else ("✅" if wr>60 else "")
        print(f"{name:<20} {wr:>6.1f}% {pr:>6.1f}% {ac:>5.0f} {lift:>+5.1f}% {mark}")
        
        score=wr*2+pr+ac
        if score>best_ever["score"] and wr>=58:
            best_ever={"score":score,"name":combo_name,"thr":name,"wr":wr,"pr":pr,"ac":ac,
                      "flags":flags,"pmin":pmin,"pmax":pmax}

sep="="*90
print(f"\n{sep}")
print(f"🏆 最终最优: {best_ever['name']} + {best_ever['thr']}")
print(f"   胜率: {best_ever['wr']:.1f}% | 出票: {best_ever['pr']:.1f}% | 候选: {best_ever['ac']:.0f}")

# 精细调优
flags=best_ever["flags"]
print(f"\n{'─'*90}")
print(f"精细调优 — 在最优组合附近微调涨幅上限")
print(f"{'─'*90}")
print(f"{'涨幅上限':<20} {'胜率':>8} {'出票':>8} {'候选':>6}")
print("-"*44)
for pc in [x/10 for x in range(60,100)]:
    wr,pr,ac=eval_with_pct(flags,None,pc,10)
    if pr>85:
        mark="🔥" if wr>63 else ("✅" if wr>60 else "")
        print(f"{'<'+str(pc)+'%':<20} {wr:>6.1f}% {pr:>6.1f}% {ac:>5.0f} {mark}")

# 也看涨幅下限
print(f"\n{'─'*90}")
print(f"精细调优 — 涨幅下限（排除太低涨幅）")
print(f"{'─'*90}")
print(f"{'涨幅下限':<20} {'胜率':>8} {'出票':>8} {'候选':>6}")
print("-"*44)
for pc in [x/10 for x in range(0,50)]:
    wr,pr,ac=eval_with_pct(flags,pc,9.8,10)
    if pr>80:
        mark="🔥" if wr>63 else ("✅" if wr>60 else "")
        print(f"{'≥'+str(pc)+'%':<20} {wr:>6.1f}% {pr:>6.1f}% {ac:>5.0f} {mark}")

# 最后：二维网格搜索 (下限×上限)
print(f"\n{'─'*90}")
print(f"二维搜索 — 最优涨幅区间（下限×上限）")
print(f"{'─'*90}")
print(f"{'下限~上限':<20} {'胜率':>8} {'出票':>8} {'候选':>5}")
print("-"*43)
best_2d={"score":0}
for lo in range(0,50,5):
    for hi in range(lo+5,100,5):
        pmin=lo/10; pmax=hi/10 if hi<100 else None
        wr,pr,ac=eval_with_pct(flags,pmin,pmax,10)
        if pr>=85:
            mark="🔥" if wr>63 else ("✅" if wr>60 else "")
            print(f"{pmin:.1f}~{pmax if pmax else '∞':<6} {wr:>6.1f}% {pr:>6.1f}% {ac:>4.0f} {mark}")
            score=wr*2+pr
            if score>best_2d["score"]:
                best_2d={"score":score,"lo":pmin,"hi":pmax,"wr":wr,"pr":pr,"ac":ac}

print(f"\n🏆 二维最优: [{best_2d['lo']:.1f}%, {best_2d['hi'] if best_2d['hi'] else '不限'}%)")
print(f"   胜率: {best_2d['wr']:.1f}% | 出票: {best_2d['pr']:.1f}%")

print(f"\n⏱ {(time.time()-t0)/60:.1f}分")
