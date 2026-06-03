
#!/usr/bin/env python3
"""全量3427只 — 快速对比不同条件组合，找2026年胜率最高"""
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
print("📡 加载全部3427只(仅计算标志位，轻量化)...")
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files=[f for f in all_files if f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2')]

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
        
        for i in range(80, len(c)-1):
            dt=recs[i]["date"]
            if not (dt.startswith("2025") or dt.startswith("2026")): continue
            cl=c[i]; op=o[i]; hi=h[i]; lo=l[i]; vo=v[i]
            
            flags={"dt":dt,"code":code}
            
            # 核心条件
            flags["p"]=cl<80
            flags["ma"]=bool(mas[5][i] and mas[10][i] and mas[20][i] and mas[60][i] and mas[5][i]>mas[10][i]>mas[20][i]>mas[60][i])
            flags["mc"]=bool(dif[i] and dea[i] and dif[i]>0 and dif[i]>dea[i])
            atr_p=atr[i]/cl*100 if atr[i] and cl>0 else 0
            flags["at"]=atr_p>3
            flags["m6"]=bool(mas[60][i] and cl>mas[60][i])
            
            # 额外条件
            flags["yn"]=cl>op  # 阳线
            vr=vo/(mas["v5"][i] or 1)
            flags["vr1"]=1<=vr<=3  # 量比1~3
            flags["v2"]=1.2<=vr<=2.5  # 量比1.2~2.5
            flags["v3"]=vr>0.7  # 量比活跃
            flags["j5"]=bool(j[i] and j[i]>50)  # J>50
            flags["jo"]=bool(j[i] and 50<j[i]<90)  # J适中
            flags["b1"]=abs(cl-op)/op*100>1.5  # 实体>1.5%
            flags["kd"]=bool(k[i] and d[i] and k[i]>d[i])  # K>D
            srt=(hi-max(cl,op))/(hi-lo+0.001)*100
            flags["ns"]=srt<30  # 上影<30%
            p20=pos20[i] if pos20[i] else 50
            flags["p35"]=35<=p20<=70  # 位置35~70
            flags["pct_ok"]=-2<=pct[i]<=6
            flags["pct_pos"]=pct[i]>0
            
            # 未来表现
            next_h=(recs[i+1]["high"]/cl-1)*100
            next_c=(recs[i+1]["close"]/cl-1)*100
            flags["w"]=next_h>=2.5
            
            # 评分
            sc=0; sc+=atr_p*2
            if pct[i]>0: sc+=10
            if 1<vr<2: sc+=15
            elif vr>2: sc+=8
            sc+=p20*0.2
            if flags["jo"]: sc+=10
            flags["sc"]=sc
            
            stock_days.append(flags)
        
        loaded+=1
        if loaded%500==0: print(f"  {loaded}/{len(main_files)} ({len(stock_days)} rows)")
    except: pass

print(f"✅ {loaded}只, {len(stock_days)}条")

by_date=defaultdict(list)
for sd in stock_days:
    by_date[sd["dt"]].append(sd)

def test(flist, yr="2026", mc=10):
    dates=sorted(set(sd["dt"] for sd in stock_days if sd["dt"].startswith(yr)))
    pd_=0; wc=0; h5=0; h10=0; sc=0
    for dt in dates:
        cand=[sd for sd in by_date[dt] if all(sd[f] for f in flist)]
        if len(cand)>=mc:
            pd_+=1
            cand.sort(key=lambda x:x["sc"],reverse=True)
            if cand[0]["w"]: wc+=1
    wr=wc/pd_*100 if pd_ else 0
    pr=pd_/len(dates)*100
    return wr,pr

# M1基线
M1=["p","ma","mc","at","m6"]

# 各种条件组合
tests=[
    ("M1基线",M1),
    ("M1+阳线",M1+["yn"]),
    ("M1+量比1~3",M1+["vr1"]),
    ("M1+J>50",M1+["j5"]),
    ("M1+实体>1.5",M1+["b1"]),
    ("M1+阳线+量比1~3",M1+["yn","vr1"]),
    ("M1+阳线+J>50",M1+["yn","j5"]),
    ("M1+阳线+量比1~3+J>50",M1+["yn","vr1","j5"]),
    ("M1+阳线+量比1~3+J中",M1+["yn","vr1","jo"]),
    ("M1+阳线+量比1.2~2.5+J>50",M1+["yn","v2","j5"]),
    ("M1+阳线+实体>1.5+J>50",M1+["yn","b1","j5"]),
    ("M1+阳线+量比1~3+实体>1.5",M1+["yn","vr1","b1"]),
    ("M1+阳线+量比1.2~2.5+实体>1.5",M1+["yn","v2","b1"]),
    ("M1+阳线+位置35~70",M1+["yn","p35"]),
    ("M1+阳线+量比1~3+位置35~70",M1+["yn","vr1","p35"]),
    ("M1+阳线+K>D+J>50",M1+["yn","kd","j5"]),
    ("M1+阳线+实体+J>50+K>D",M1+["yn","b1","j5","kd"]),
    ("M1+阳线+量比1~3+实体>1.5",M1+["yn","vr1","b1"]),
    ("M1+阳线+无上影+量比1~3",M1+["yn","ns","vr1"]),
    ("M1+阳线+无上影",M1+["yn","ns"]),
]

print(f"\n{'='*80}")
print("🔥 全量3427只 — 2026年条件对比（目标→突破60%）")
print(f"{'='*80}")
print(f"\n{'条件':<35} {'2026胜率':>10} {'出票':>8} {'2025胜率':>10} {'出票':>8}")
print("-"*73)

best=[]; best_w26=0
for name, flist in tests:
    w26,p26=test(flist,"2026")
    w25,p25=test(flist,"2025")
    print(f"{name:<35} {w26:>6.1f}% {p26:>5.0f}% {w25:>6.1f}% {p25:>5.0f}%")
    best.append((w26,w25,name,flist))
    if w26>best_w26:
        best_w26=w26

print(f"\n{'='*70}")
print(f"🏆 2026最高胜率: {best_w26:.1f}%")
print(f"{'='*70}")

# 如果还不够高，再试更严的组合
if best_w26 < 64:
    print(f"\n🔥 继续加严…")
    strict_tests=[
        ("M1+阳线+量比1~3+J>50+实体",M1+["yn","vr1","j5","b1"]),
        ("M1+阳线+量比1~3+J>50+K>D",M1+["yn","vr1","j5","kd"]),
        ("M1+阳线+量比1~3+J>50+位置35~70",M1+["yn","vr1","j5","p35"]),
        ("M1+阳线+量比1~3+J>50+无上影",M1+["yn","vr1","j5","ns"]),
        ("M1+阳线+量比1~3+子+J>50+实体",M1+["yn","vr1","j5","b1","kd"]),
        ("M1+阳线+量比1~3+J>50+实体+K>D",M1+["yn","vr1","j5","b1","kd"]),
        ("M1+阳线+量比1.2~2.5+J>50+K>D",M1+["yn","v2","j5","kd"]),
        ("M1+阳线+量比1.2~2.5+J>50+实体",M1+["yn","v2","j5","b1"]),
        # 去掉VR限制只保留核心
        ("M1+阳线+J>50+实体",M1+["yn","j5","b1"]),
        ("M1+阳线+J>50+K>D",M1+["yn","j5","kd"]),
        ("M1+阳线+J>50+无上影",M1+["yn","j5","ns"]),
        ("M1+阳线+J>50+位置35~70",M1+["yn","j5","p35"]),
    ]
    for name, flist in strict_tests:
        w26,p26=test(flist,"2026")
        w25,p25=test(flist,"2025")
        print(f"{name:<35} {w26:>6.1f}% {p26:>5.0f}% {w25:>6.1f}% {p25:>5.0f}%")
        best.append((w26,w25,name,flist))

print(f"\n⏱ {(time.time()-t0)/60:.1f}分")
