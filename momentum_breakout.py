#!/usr/bin/env python3
"""动量突破策略（Momentum Breakout）- 多版本测试"""
import json, os, time, random
from collections import defaultdict

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

def calc_ma(s,pd):
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
        mas5=calc_ma(c,5); mas10=calc_ma(c,10); mas20=calc_ma(c,20); mas60=calc_ma(c,60)
        v5=calc_ma(v,5)
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
            vr=vo/(v5[i] or 1); atr_p=atr[i]/cl*100 if atr[i] and cl>0 else 0
            cpos=(cl-lo)/(hi-lo+0.001)*100
            
            flags={"date":dt,"code":code,"pct":pct[i],"vr":vr,"cpos":cpos}
            flags["price"]=cl<80; flags["yang"]=cl>op
            flags["ma_full"]=bool(mas5[i] and mas10[i] and mas20[i] and mas60[i] and mas5[i]>mas10[i]>mas20[i]>mas60[i])
            flags["macd_strict"]=bool(dif[i] and dea[i] and dif[i]>0 and dif[i]>dea[i])
            flags["atr3"]=atr_p>3; flags["ma60"]=bool(mas60[i] and cl>mas60[i])
            flags["ma5_up"]=bool(mas5[i] and cl>mas5[i])
            
            # 突破前高：过去N天最高价
            for nd in [5,7,10,15,20]:
                if i>=nd:
                    ph=max(h[i-nd:i])
                    flags[f"break{nd}"]=cl>=ph*0.98
            
            # 收盘位置
            flags["cpos80"]=cpos>=80; flags["cpos85"]=cpos>=85; flags["cpos90"]=cpos>=90
            
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
for sd in stock_days: by_date[sd["date"]].append(sd)

M1=["price","ma_full","macd_strict","atr3","ma60","ma5_up"]

print()
sep = "="*90
print(sep)
print("动量突破策略 — 多版本测试")
print(sep)

# 测试所有组合
break_periods=[5,7,10,15,20]
pct_ranges=[(3,5),(3,7),(3,8),(4,6),(4,7)]
cpos_thresholds=[80,85,90]
vr_thresholds=[1.2,1.5]

def do_test(base_flags, name_prefix, need_M1=False):
    """运行版本测试"""
    sep2 = "-"*90
    print(f"\n{sep2}")
    print(f"版本系列：{name_prefix}")
    print(f"{sep2}")
    print(f"{'版本':<55} {'胜率':>8} {'出票':>6}")
    print("-"*71)
    
    results=[]
    for bp in break_periods:
        for plo,phi in pct_ranges:
            for cp in cpos_thresholds:
                for vr_min in vr_thresholds:
                    name=f"{name_prefix}-突破{bp}d+涨{plo}~{phi}%+收位>{cp}%+量>{vr_min}"
                    
                    dates=sorted(by_date.keys())
                    pd_=0; wc=0
                    for dt in dates:
                        cand=[sd for sd in by_date[dt] if sd["yang"] and sd[f"break{bp}"] and sd[f"cpos{cp}"] and sd["vr"]>=vr_min and plo<=sd["pct"]<=phi]
                        if need_M1:
                            cand=[sd for sd in cand if all(sd[f] for f in M1)]
                        if len(cand)>=10:
                            pd_+=1
                            cand.sort(key=lambda x:x["score"],reverse=True)
                            if cand[0]["next_win"]: wc+=1
                    wr=wc/pd_*100 if pd_ else 0
                    mark="🔥" if wr>=70 else ("✅" if wr>=60 else "")
                    print(f"{name:<55} {wr:>5.1f}% {pd_:>4}天 {mark}")
                    results.append((wr,pd_,name))
    return results

rA = do_test([], "A-纯动量")
rB = do_test([], "B-M1+动量", need_M1=True)

# 当前最优
print(f"\n{sep}")
print("🏆 对比当前最优（硬过滤4.0~5.5%）")
print(f"{sep}")
dates=sorted(by_date.keys())
pd_=0; wc=0
for dt in dates:
    cand=[sd for sd in by_date[dt] if all(sd[f] for f in M1) and sd["yang"] and 4<=sd["pct"]<=5.5]
    if len(cand)>=10:
        pd_+=1
        cand.sort(key=lambda x:x["score"],reverse=True)
        if cand[0]["next_win"]: wc+=1
wr_best=wc/pd_*100 if pd_ else 0
print(f"{'当前最优(硬过滤4~5.5%)':<55} {wr_best:>5.1f}% {pd_:>4}天 🏆")

# Top 5
all_r=rA+rB
all_r.sort(reverse=True)
print(f"\n{sep}")
print("🏆 Top 5 动量突破版本")
print(f"{sep}")
print(f"{'排名':<4} {'版本':<55} {'胜率':>8} {'出票':>6}")
print("-"*75)
for i,(wr,pd_,name) in enumerate(all_r[:5],1):
    mark="🔥" if wr>=70 else ("✅" if wr>=60 else "")
    beat=wr-wr_best
    print(f"#{i:<2} {name:<55} {wr:>5.1f}% {pd_:>4}天 {mark}")
    if beat>0:
        print(f"     ↑ 超过当前最优+{beat:.1f}%!")

print(f"\n⏱ {(time.time()-t0)/60:.1f}分")
