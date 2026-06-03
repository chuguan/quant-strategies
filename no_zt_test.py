
#!/usr/bin/env python3
"""加涨停过滤 — 重新优化"""
import json, os, time, random
from collections import defaultdict

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

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
print("📡 加载3427只…")
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files=[f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]

stock_days=[]
loaded=0
for fn in main_files:
    fp=os.path.join(CACHE_DIR,fn)
    try:
        with open(fp,'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<80: continue
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
            
            flags={"date":dt,"code":code}
            flags["price"]=cl<80
            flags["ma_full"]=bool(mas[5][i] and mas[10][i] and mas[20][i] and mas[60][i] and mas[5][i]>mas[10][i]>mas[20][i]>mas[60][i])
            flags["macd_strict"]=bool(dif[i] and dea[i] and dif[i]>0 and dif[i]>dea[i])
            atr_p=atr[i]/cl*100 if atr[i] and cl>0 else 0
            flags["atr3"]=atr_p>3
            flags["ma60"]=bool(mas[60][i] and cl>mas[60][i])
            flags["yang"]=cl>op
            vr=vo/(mas["v5"][i] or 1)
            flags["vr1_3"]=1<=vr<=3; flags["vr_1_2"]=1<=vr<=2
            flags["body15"]=abs(cl-op)/op*100>1.5
            flags["j_50"]=bool(j[i] and j[i]>50)
            flags["ma5_up"]=bool(mas[5][i] and cl>mas[5][i])
            flags["shadow20"]=(hi-max(cl,op))/(hi-lo+0.001)*100<20
            
            # ⭐ 涨停过滤 ⭐
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
        if loaded%500==0: print(f"  {loaded}/{len(main_files)} ({len(stock_days)})")
    except: pass

print(f"✅ {loaded}只, {len(stock_days)}条")

by_date=defaultdict(list)
for sd in stock_days:
    by_date[sd["date"]].append(sd)

M1=["price","ma_full","macd_strict","atr3","ma60"]

def evaluate(flags, min_c=10):
    dates=sorted(by_date.keys())
    pd_=0; wc=0
    for dt in dates:
        cand=[sd for sd in by_date[dt] if all(sd[f] for f in flags)]
        if len(cand)>=min_c:
            pd_+=1
            cand.sort(key=lambda x:x["score"],reverse=True)
            if cand[0]["next_win"]: wc+=1
    wr=wc/pd_*100 if pd_ else 0
    pr=pd_/len(dates)*100
    return wr, pr

# 冠军 M1+阳线+站MA5
BEST=M1+["yang","ma5_up"]

# 测试不同涨停过滤阈值
print(f"\n{'='*70}")
print(f"🔥 涨停过滤测试 — 冠军M1+阳线+站MA5")
print(f"{'='*70}")
print(f"\n{'条件':<42} {'胜率':>8} {'出票':>8}")
print("-"*60)

# 不加涨停过滤
wr,pr=evaluate(BEST,10)
print(f"{'M1+阳线+站MA5(无涨停过滤)':<42} {wr:>5.1f}% {pr:>5.1f}%")

# 加不同阈值
for limit in [9.0, 8.0, 7.0, 6.5, 6.0, 5.5, 5.0, 4.5, 4.0, 3.5]:
    def cond_zt(sd, lim=limit):
        return sd["pct"] < lim
    # Can't easily create dynamic condition - use approach with a lambda
    
print("\n使用标志位方式...")

# 直接在筛选时加条件
def evaluate_with_filter(base_flags, extra_filter, min_c=10):
    dates=sorted(by_date.keys())
    pd_=0; wc=0
    for dt in dates:
        cand=[sd for sd in by_date[dt] if all(sd[f] for f in base_flags) and extra_filter(sd)]
        if len(cand)>=min_c:
            pd_+=1
            cand.sort(key=lambda x:x["score"],reverse=True)
            if cand[0]["next_win"]: wc+=1
    wr=wc/pd_*100 if pd_ else 0
    pr=pd_/len(dates)*100
    return wr, pr

for limit in [9.0, 8.5, 8.0, 7.5, 7.0, 6.5, 6.0, 5.5, 5.0]:
    flt=lambda sd,lim=limit: sd["pct"]<lim
    wr,pr=evaluate_with_filter(BEST, flt, 10)
    print(f"{f'M1+阳线+站MA5+涨<{limit}%':<42} {wr:>5.1f}% {pr:>5.1f}%")

# 试试其他组合+涨停过滤
print(f"\n{'─'*60}")
print("最佳冠军组合 + 涨停过滤 排名")
print(f"{'─'*60}")

zt_limit=7.0
all_combos_with_zt=[
    ("M1+阳线+站MA5+涨<7%", BEST+["ma5_up"]),
    ("M1+阳线+量比1~2+涨<7%", M1+["yang","vr_1_2"]),
    ("M1+阳线+实体>1.5+涨<7%", M1+["yang","body15"]),
    ("M1+阳线+J>50+涨<7%", M1+["yang","j_50"]),
    ("M1+阳线+站MA5+无上影+涨<7%", M1+["yang","ma5_up","shadow20"]),
    ("M1+阳线+量比1~2+实体>1.5+涨<7%", M1+["yang","vr_1_2","body15"]),
    ("M1+阳线+量比1~3+涨<7%", M1+["yang","vr1_3"]),
    ("M1+阳线+量比1~3+J>50+涨<7%", M1+["yang","vr1_3","j_50"]),
]

for name, flags in all_combos_with_zt:
    flt=lambda sd: sd["pct"]<zt_limit
    wr,pr=evaluate_with_filter(flags, flt, 10)
    mark="🔥" if wr>=70 else ("✅" if wr>=65 else "")
    print(f"{name:<42} {wr:>5.1f}% {pr:>5.1f}% {mark}")

print(f"\n⏱ {(time.time()-t0)/60:.1f}分")
