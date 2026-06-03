
#!/usr/bin/env python3
"""更多新组合测试 — 全量3427只，突破70.8%"""
import json, os, sys, time, random
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
print("📡 加载全量数据...")
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
            if not dt.startswith("2026"): continue
            cl=c[i]; op=o[i]; hi=h[i]; lo=l[i]; vo=v[i]; dts=recs[i]["date"]
            
            flags={"date":dt,"code":code}
            flags["price"]=cl<80
            flags["ma_full"]=bool(mas[5][i] and mas[10][i] and mas[20][i] and mas[60][i] and mas[5][i]>mas[10][i]>mas[20][i]>mas[60][i])
            flags["macd_strict"]=bool(dif[i] and dea[i] and dif[i]>0 and dif[i]>dea[i])
            atr_p=atr[i]/cl*100 if atr[i] and cl>0 else 0
            flags["atr3"]=atr_p>3; flags["atr25"]=atr_p>2.5; flags["atr4"]=atr_p>4
            flags["ma60"]=bool(mas[60][i] and cl>mas[60][i])
            flags["yang"]=cl>op
            vr=vo/(mas["v5"][i] or 1)
            flags["vr1_3"]=1<=vr<=3; flags["vr12_25"]=1.2<=vr<=2.5; flags["vr08_2"]=0.8<=vr<=2
            flags["vr15_3"]=1.5<=vr<=3; flags["vr_1_2"]=1<=vr<=2
            flags["body15"]=abs(cl-op)/op*100>1.5; flags["body2"]=abs(cl-op)/op*100>2
            flags["body1"]=abs(cl-op)/op*100>1; flags["body08"]=abs(cl-op)/op*100>0.8
            
            sr=(hi-max(cl,op))/(hi-lo+0.001)*100
            flags["no_shadow"]=sr<30; flags["shadow40"]=sr<40; flags["shadow20"]=sr<20
            flags["shadow30"]=sr<30; flags["shadow10"]=sr<10
            
            flags["j_50"]=bool(j[i] and j[i]>50); flags["j_60"]=bool(j[i] and j[i]>60)
            flags["j_40"]=bool(j[i] and j[i]>40); flags["j_55_85"]=bool(j[i] and 55<j[i]<85)
            flags["k_over_d"]=bool(k[i] and d[i] and k[i]>d[i])
            flags["kdj_golden"]=bool(i>=1 and k[i] and d[i] and k[i-1] and d[i-1] and k[i-1]<=d[i-1] and k[i]>d[i])
            
            flags["pct0_6"]=-2<=pct[i]<=6; flags["pct1_5"]=1<=pct[i]<=5
            flags["pct0_4"]=0<=pct[i]<=4; flags["pct_4_7"]=4<=pct[i]<=7
            flags["pct_pos"]=pct[i]>0; flags["pct15_pos"]=1<=pct[i] or (pct[i]>0 and pct[i]<=4)
            
            flags["pos35_70"]=pos20[i] is not None and 35<=pos20[i]<=70
            flags["pos30_75"]=pos20[i] is not None and 30<=pos20[i]<=75
            flags["pos40_65"]=pos20[i] is not None and 40<=pos20[i]<=65
            
            flags["ma5_up"]=bool(mas[5][i] and cl>mas[5][i])
            flags["ma5_slope"]=bool(i>=4 and mas[5][i] and mas[5][i-4] and mas[5][i]>mas[5][i-4])
            
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
        if loaded%500==0: print(f"  {loaded}/{len(main_files)} ({len(stock_days)} rows)")
    except: pass

print(f"✅ {loaded}只, {len(stock_days)}条")

by_date=defaultdict(list)
for sd in stock_days:
    by_date[sd["date"]].append(sd)

def evaluate(flags, mc=10):
    dates=sorted(by_date.keys())
    pd_=0; wc=0
    for dt in dates:
        cand=[sd for sd in by_date[dt] if all(sd[f] for f in flags)]
        if len(cand)>=mc:
            pd_+=1
            cand.sort(key=lambda x:x["score"],reverse=True)
            if cand[0]["next_win"]: wc+=1
    wr=wc/pd_*100 if pd_ else 0
    pr=pd_/len(dates)*100
    return wr, pr

M1=["price","ma_full","macd_strict","atr3","ma60"]

# 更丰富的组合测试
new_combos = [
    # 最佳组合合并
    ("M1+阳线+实体>1.5+量比1~3+J>50", M1+["yang","body15","vr1_3","j_50"]),
    ("M1+阳线+实体>1.5+量比1~3", M1+["yang","body15","vr1_3"]),
    ("M1+阳线+实体>1.5+J>50", M1+["yang","body15","j_50"]),
    ("M1+阳线+实体2%+J>50", M1+["yang","body2","j_50"]),
    
    # 实体+量比不同组合
    ("M1+阳线+实体>1%+量比1~3", M1+["yang","body1","vr1_3"]),
    ("M1+阳线+实体>2%+量比1~2", M1+["yang","body2","vr_1_2"]),
    ("M1+阳线+实体>0.8%+量比0.8~2", M1+["yang","body08","vr08_2"]),
    
    # 量比收紧
    ("M1+阳线+量比1~2", M1+["yang","vr_1_2"]),
    ("M1+阳线+量比1.5~3", M1+["yang","vr15_3"]),
    
    # J值不同范围
    ("M1+阳线+J>60", M1+["yang","j_60"]),
    ("M1+阳线+J>40", M1+["yang","j_40"]),
    ("M1+阳线+J55~85", M1+["yang","j_55_85"]),
    
    # 加上影线
    ("M1+阳线+无上影(<20%)", M1+["yang","shadow20"]),
    ("M1+阳线+实>1.5+无上影", M1+["yang","body15","shadow30"]),
    
    # 位置
    ("M1+阳线+位置30~75%", M1+["yang","pos30_75"]),
    ("M1+阳线+位置40~65%", M1+["yang","pos40_65"]),
    
    # MA5
    ("M1+阳线+站上MA5", M1+["yang","ma5_up"]),
    ("M1+阳线+MA5向上", M1+["yang","ma5_slope"]),
    
    # KDJ金叉
    ("M1+阳线+KDJ金叉", M1+["yang","kdj_golden"]),
    ("M1+阳线+KDJ金叉+J>50", M1+["yang","kdj_golden","j_50"]),
    
    # 涨幅优化
    ("M1+涨0~4%+阳线", M1+["pct0_4","yang"]),
    ("M1+涨1~5%+阳线", M1+["pct1_5","yang"]),
    ("M1+涨4~7%+阳线", M1+["pct_4_7","yang"]),
    
    # ATR收紧
    ("M1+阳线+ATR>4%", M1+["yang","atr4"]),
    ("M1+阳线+ATR>2.5%", M1+["yang","atr25"]),
    
    # 4条件组合
    ("M1+阳线+实>1.5+量比1~3+J>50+无上影", M1+["yang","body15","vr1_3","j_50","shadow30"]),
    ("M1+阳线+实>1.5+量比1~3+位置30~75%", M1+["yang","body15","vr1_3","pos30_75"]),
    ("M1+阳线+实>1.5+J>50+站MA5", M1+["yang","body15","j_50","ma5_up"]),
    
    # 5条件组合
    ("M1+阳线+实>1.5+量比1~3+J>50+站MA5", M1+["yang","body15","vr1_3","j_50","ma5_up"]),
]

print(f"\n{'='*80}")
print(f"🔥 新组合测试 — 目标：超越70.8%！（全量3427只×2026年）")
print(f"{'='*80}")
print(f"\n{'组合':<42} {'胜率':>8} {'出票':>8}")
print("-"*60)

results = []
for name, flags in new_combos:
    wr, pr = evaluate(flags, 10)
    results.append((wr, pr, name, flags))
    mark = "🔥" if wr >= 71 else ("✅" if wr >= 68 else "")
    print(f"{name:<42} {wr:>5.1f}% {pr:>6.1f}% {mark}")

# 排名
print(f"\n{'='*80}")
print(f"🏆🥇🥈🥉 排名")
print(f"{'='*80}")
print(f"\n{'排名':<4} {'组合':<42} {'胜率':>8} {'出票':>8}")
print("-"*64)
results.sort(reverse=True)
for rank, (wr, pr, name, _) in enumerate(results, 1):
    mark = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else ""))
    print(f"#{rank:<2}{mark:<2}{name:<42} {wr:>5.1f}% {pr:>6.1f}%")

print(f"\n⏱ {(time.time()-t0)/60:.1f}分")
