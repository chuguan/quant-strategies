#!/usr/bin/env python3
"""CG打板 — 涨停板策略测试"""
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
            flags["pct"]=pct[i]
            flags["vr_12"]=1<=vr<=2
            flags["ma5_up"]=bool(mas[5][i] and cl>mas[5][i])
            sr=(hi-max(cl,op))/(hi-lo+0.001)*100
            flags["shadow20"]=sr<20
            body_pct=abs(cl-op)/op*100
            flags["body15"]=body_pct>1.5
            
            next_h=(recs[i+1]["high"]/cl-1)*100
            flags["next_win"]=next_h>=2.5
            
            sc=0; sc+=atr_p*2
            if pct[i]>0: sc+=10
            if 1<vr<2: sc+=15
            elif vr>2: sc+=8
            sc+=(pos20[i] or 50)*0.2
            if j[i] and 50<j[i]<90: sc+=10
            flags["score"]=sc
            
            stock_days.append(flags)
        
        loaded+=1
        if loaded%500==0: print(f"  {loaded}/{len(main_files)}")
    except: pass
print(f"加载{loaded}只, {len(stock_days)}条")

by_date=defaultdict(list)
for sd in stock_days:
    by_date[sd["date"]].append(sd)

M1=["price","ma_full","macd_strict","atr3","ma60"]

def evaluate_with_zt(zt_min, extra_flags=None, min_c=1):
    """评估打板策略"""
    dates=sorted(by_date.keys())
    pd_=0; wc=0; tot=0
    extra=extra_flags or []
    for dt in dates:
        cand=[sd for sd in by_date[dt] if sd["pct"]>=zt_min and all(sd[f] for f in (M1+extra))]
        tot+=len(cand)
        if len(cand)>=min_c:
            pd_+=1
            cand.sort(key=lambda x:x["score"],reverse=True)
            if cand[0]["next_win"]: wc+=1
    wr=wc/pd_*100 if pd_ else 0
    pr=pd_/len(dates)*100
    ac=tot/len(dates)
    return wr,pr,ac

print()
print("="*70)
print("测试打板策略 — 全量3427只×2026年")
print("="*70)
header = "{:<42} {:>8} {:>8} {:>8}".format("组合","胜率","出票","日均")
print(header)
print("-"*70)

# 1. 纯打板（无M1底仓）
dates=sorted(by_date.keys())
pd_=0; wc=0; tot=0
for dt in dates:
    cand=[sd for sd in by_date[dt] if sd["pct"]>=9.5]
    tot+=len(cand)
    if cand:
        pd_+=1
        cand.sort(key=lambda x:x["score"],reverse=True)
        if cand[0]["next_win"]: wc+=1
wr=wc/pd_*100 if pd_ else 0
print(f"{'纯涨停(无底仓)≥9.5%':<42} {wr:>5.1f}% {pd_/len(dates)*100:>6.1f}% {tot/len(dates):>5.0f}")

# 2. 不同阈值
for zt in [9.0,9.3,9.5,9.8,10.0]:
    wr,pr,ac=evaluate_with_zt(zt)
    print(f"{f'M1+涨停≥{zt}%':<42} {wr:>5.1f}% {pr:>6.1f}% {ac:>5.0f}")

# 3. M1+涨停≥9.5%+额外条件
print()
print("─"*70)
print("M1+涨停≥9.5% + 额外条件")
print("─"*70)
extras=[
    ([],"无"),
    (["yang"],"+阳线"),
    (["ma5_up"],"+站MA5"),
    (["vr_12"],"+量比1~2"),
    (["yang","ma5_up"],"+阳+站MA5"),
    (["yang","vr_12"],"+阳+量1~2"),
    (["yang","ma5_up","vr_12"],"+阳+站MA5+量1~2"),
    (["yang","ma5_up","shadow20"],"+阳+站MA5+无上影"),
    (["yang","ma5_up","body15"],"+阳+站MA5+实>1.5%"),
    (["yang","ma5_up","vr_12","shadow20"],"+阳+站MA5+量1~2+无上影"),
]
for ex,name in extras:
    wr,pr,ac=evaluate_with_zt(9.5,ex)
    print(f"{f'M1+涨停≥9.5%{name}':<42} {wr:>5.1f}% {pr:>6.1f}% {ac:>5.0f}")

# 4. 涨停票数量统计
print()
print("─"*70)
print("每日涨停票统计(M1底仓+涨停≥9.5%)")
print("─"*70)
dates=sorted(by_date.keys())
zts=[]
for dt in dates:
    n=len([sd for sd in by_date[dt] if all(sd[f] for f in M1) and sd["pct"]>=9.5])
    zts.append(n)
avg=sum(zts)/len(zts)
print(f"日均候选: {avg:.1f}只 | 最多: {max(zts)} | 最少: {min(zts)}")
print(f"有票天数: {sum(1 for n in zts if n>0)}/{len(zts)} ({sum(1 for n in zts if n>0)/len(zts)*100:.0f}%)")
print(f">=3只: {sum(1 for n in zts if n>=3)}天 | >=5只: {sum(1 for n in zts if n>=5)}天")

print(f"\n⏱ {(time.time()-t0)/60:.1f}分")
