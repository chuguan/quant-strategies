
#!/usr/bin/env python3
"""全市场推高胜率 — 利用采样缩放因子估算"""
import json, os, sys, time, random
from collections import defaultdict
import math

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
SCALE_FACTOR = 3427 / 800  # 全市场/采样比例 ≈ 4.28

print("📡 加载800只采样...")
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files=[f for f in all_files if f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2')]
random.seed(42); sample_files=sorted(random.sample(main_files,800))

stock_days=[]; loaded=0
for fn in sample_files:
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
        
        for i in range(80, len(c)-1):
            dt=recs[i]["date"]
            if not dt.startswith("2026"): continue
            cl=c[i]; op=o[i]; hi=h[i]; lo=l[i]; vo=v[i]
            
            flags={"date":dt,"code":code}
            flags["price"]=cl<80
            flags["ma_full"]=bool(mas[5][i] and mas[10][i] and mas[20][i] and mas[60][i] and mas[5][i]>mas[10][i]>mas[20][i]>mas[60][i])
            flags["macd_strict"]=bool(dif[i] and dea[i] and dif[i]>0 and dif[i]>dea[i])
            atr_p=atr[i]/cl*100 if atr[i] and cl>0 else 0
            flags["atr3"]=atr_p>3
            flags["atr25"]=atr_p>2.5
            flags["ma60"]=bool(mas[60][i] and cl>mas[60][i])
            flags["yang"]=cl>op
            vr=vo/(mas["v5"][i] or 1)
            flags["vr12"]=1.2<=vr<=2.5
            flags["vr1_3"]=1<=vr<=3
            flags["vr15"]=1.5<=vr<=3
            flags["pct0_6"]=-2<=pct[i]<=6
            flags["pct2_6"]=2<=pct[i]<=6
            flags["pos20"]=pos20[i] if pos20[i] else 50
            flags["pos35_70"]=pos20[i] is not None and 35<=pos20[i]<=70
            flags["pos40_70"]=pos20[i] is not None and 40<=pos20[i]<=70
            sr=(hi-max(cl,op))/(hi-lo+0.001)*100
            flags["no_shadow"]=sr<30
            flags["short_shadow"]=sr<40
            flags["j_ok"]=bool(j[i] and 50<j[i]<90)
            flags["j_50"]=bool(j[i] and j[i]>50)
            flags["k_over_d"]=bool(k[i] and d[i] and k[i]>d[i])
            flags["body15"]=abs(cl-op)/op*100>1.5
            
            next_h=(recs[i+1]["high"]/cl-1)*100
            flags["next_win"]=next_h>=2.5
            
            # 预计算评分
            sc=0; sc+=atr_p*2
            if pct[i]>0: sc+=10
            if 1<vr<2: sc+=15
            elif vr>2: sc+=8
            sc+=(pos20[i] or 50)*0.2
            if flags["j_ok"]: sc+=10
            flags["score"]=sc
            
            stock_days.append(flags)
        
        loaded+=1
        if loaded%200==0: print(f"  {loaded}/800 ({len(stock_days)} rows)")
    except: pass

print(f"✅ {loaded}只, {len(stock_days)}条")

by_date=defaultdict(list)
for sd in stock_days:
    by_date[sd["date"]].append(sd)

def evaluate(flags, min_c=10, scale=True):
    """评估组合。scale=True时用全市场估算"""
    dates=sorted(by_date.keys())
    pd_=0; wc=0
    for dt in dates:
        cand=[sd for sd in by_date[dt] if all(sd[f] for f in flags)]
        n_real=len(cand)
        n_scaled=int(n_real*SCALE_FACTOR) if scale else n_real
        
        if n_scaled>=min_c:
            pd_+=1
            cand.sort(key=lambda x:x["score"],reverse=True)
            if cand[0]["next_win"]: wc+=1
    
    wr=wc/pd_*100 if pd_ else 0
    pr=pd_/len(dates)*100
    return wr, pr

# ═══ 系统搜索最优组合 ═══
# M1基础
M1=["price","ma_full","macd_strict","atr3","ma60"]

# 所有可用额外条件（排除基础条件和元数据）
extra_pool={
    "yang":"阳线","vr12":"量比1.2~2.5","vr1_3":"量比1~3","vr15":"量比1.5~3",
    "pct0_6":"涨跌-2~6%","pos35_70":"位置35~70%","pos40_70":"位置40~70%",
    "no_shadow":"上影<30%","short_shadow":"上影<40%",
    "j_ok":"J50~90","j_50":"J>50","k_over_d":"K>D","body15":"实体>1.5%",
    "atr25":"ATR>2.5%","pct2_6":"涨2~6%"
}

print(f"\n{'='*80}")
print(f"🏆 搜索最佳组合（M1基础上加条件，全市场≥10候选）")
print(f"{'='*80}")
print(f"\n  缩放因子: {SCALE_FACTOR:.2f} (800采样→3427全市场)")
print(f"  条件: M1 + 额外条件")
print(f"  目标: 最大化胜率，同时全市场每天≥10候选")
print(f"\n{'组合':<40} {'胜率':>8} {'出票':>8}")
print("-"*58)

best_combos = []

# 1. 逐个加条件
for ek, ename in extra_pool.items():
    flags=M1+[ek]
    wr,pr=evaluate(flags,10,True)
    print(f"M1+{ename:<30} {wr:>6.1f}% {pr:>6.1f}%")
    best_combos.append((wr,pr,f"M1+{ename}",flags))

# 2. 两两组合
print(f"\n{'─'*58}")
print("🏆 两两组合（测试最佳搭配）")
print(f"{'─'*58}")

pair_conds = ["yang","vr12","vr1_3","pos35_70","j_ok","no_shadow","k_over_d","body15"]
tested_pairs=set()
for i in range(len(pair_conds)):
    for j in range(i+1, len(pair_conds)):
        c1,c2=pair_conds[i],pair_conds[j]
        if (c1,c2) in tested_pairs: continue
        tested_pairs.add((c1,c2))
        flags=M1+[c1,c2]
        wr,pr=evaluate(flags,10,True)
        n1=extra_pool[c1]; n2=extra_pool[c2]
        print(f"M1+{n1}+{n2:<20} {wr:>6.1f}% {pr:>6.1f}%")
        best_combos.append((wr,pr,f"M1+{n1}+{n2}",flags))

# 3. 三三组合（只测有潜力的）
print(f"\n{'─'*58}")
print("🏆 三三组合")
print(f"{'─'*58}")

triple_conds = ["yang","vr12","vr1_3","j_ok","pos35_70"]
tested_triples=set()
for i in range(len(triple_conds)):
    for j in range(i+1, len(triple_conds)):
        for k in range(j+1, len(triple_conds)):
            c1,c2,c3=triple_conds[i],triple_conds[j],triple_conds[k]
            key=tuple(sorted([c1,c2,c3]))
            if key in tested_triples: continue
            tested_triples.add(key)
            flags=M1+[c1,c2,c3]
            wr,pr=evaluate(flags,10,True)
            n1=extra_pool[c1]; n2=extra_pool[c2]; n3=extra_pool[c3]
            print(f"M1+{n1}+{n2}+{n3:<14} {wr:>6.1f}% {pr:>6.1f}%")
            best_combos.append((wr,pr,f"M1+{n1}+{n2}+{n3}",flags))

# 最终排名
print(f"\n{'='*80}")
print(f"🏆🏆🏆 最终排名（胜率从高到低，只显示出票>80%的）")
print(f"{'='*80}")
print(f"\n{'排名':<4} {'组合':<40} {'胜率':>8} {'出票':>8}")
print("-"*62)

sorted_combos = sorted([c for c in best_combos if c[1]>=80], reverse=True)
for rank, (wr,pr,name,_) in enumerate(sorted_combos[:20], 1):
    mark="🔥" if wr>=75 else ("✅" if wr>=70 else "")
    print(f"#{rank:<2} {name:<40} {wr:>5.1f}% {pr:>6.1f}% {mark}")

print(f"\n⏱ {(time.time()-t0)/60:.1f}分")
