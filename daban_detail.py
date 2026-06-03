
#!/usr/bin/env python3
"""CG打板 — 次日涨幅分布详细分析"""
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
            flags["is_zt"]=pct[i]>=9.5
            
            # 次日详细数据
            nr=recs[i+1]
            flags["d1_open"]=(nr["open"]/cl-1)*100
            flags["d1_high"]=(nr["high"]/cl-1)*100
            flags["d1_low"]=(nr["low"]/cl-1)*100
            flags["d1_close"]=(nr["close"]/cl-1)*100
            
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

# 打板选冠军
M1=["price","ma_full","macd_strict","atr3","ma60"]

def run_backtest(mode="daban"):
    """返回每天冠军的明细数据"""
    dates=sorted(by_date.keys())
    champions=[]
    for dt in dates:
        if mode=="daban":
            cand=[sd for sd in by_date[dt] if sd["is_zt"] and all(sd[f] for f in M1)]
        else:
            # CG-06: M1 + yang + ma5_up (no涨停 filter)
            cand=[sd for sd in by_date[dt] if sd["yang"] and all(sd[f] for f in M1)]
            # use the champion CG-06 conditions
            
        if cand:
            cand.sort(key=lambda x:x["score"],reverse=True)
            champ=cand[0]
            champions.append({
                "date":dt,"code":champ["code"],
                "d1_open":champ["d1_open"],"d1_high":champ["d1_high"],
                "d1_low":champ["d1_low"],"d1_close":champ["d1_close"],
                "score":champ["score"]
            })
    return champions

print()
print("="*70)
print("🔥 CG打板 — 次日涨幅分布分析")
print("="*70)

# 打板
champs=run_backtest("daban")
print(f"\n📅 2026年共{len(champs)}个交易日有涨停板冠军")

# 分布统计
stats=defaultdict(int)
highs=[c["d1_high"] for c in champs]
opens=[c["d1_open"] for c in champs]
closes=[c["d1_close"] for c in champs]
lows=[c["d1_low"] for c in champs]

print(f"\n📊 次日冲高幅度分布")
print(f"{'阈值':>12} {'命中次数':>10} {'概率':>10} {'累计':>10}")
print("-"*44)
thresholds=[0,1,2,2.5,3,4,5,6,7,8,9,10,12,15]
for t in thresholds:
    n=sum(1 for h in highs if h>=t)
    cum=sum(1 for h in highs if h>=t)/len(highs)*100
    print(f"{f'≥{t}%':>12} {n:>4}/{len(highs):<6} {n/len(highs)*100:>7.1f}% {cum:>6.1f}%")

print(f"\n📊 统计摘要")
print(f"{'指标':<20} {'值':>10}")
print("-"*32)
print(f"{'平均冲高':<20} {sum(highs)/len(highs):>+7.2f}%")
print(f"{'中位冲高':<20} {sorted(highs)[len(highs)//2]:>+7.2f}%")
print(f"{'最大冲高':<20} {max(highs):>+7.2f}%")
print(f"{'最小冲高':<20} {min(highs):>+7.2f}%")
print(f"{'平均开盘':<20} {sum(opens)/len(opens):>+7.2f}%")
print(f"{'平均收盘':<20} {sum(closes)/len(closes):>+7.2f}%")
print(f"{'平均最低':<20} {sum(lows)/len(lows):>+7.2f}%")

# 次日亏损分析
lose_days=sum(1 for h in highs if h<0)
print(f"\n📊 风险分析")
print(f"{'次日最高为负(亏)':<20} {lose_days}/{len(highs)}天 ({lose_days/len(highs)*100:.1f}%)")
print(f"{'开盘即亏(开<0)':<20} {sum(1 for o in opens if o<0)}/{len(opens)}天 ({sum(1 for o in opens if o<0)/len(opens)*100:.1f}%)")
max_loss=min(lows)
print(f"{'最大从买入到最低':<20} {max_loss:+.2f}%")

# 分布直方图
print(f"\n📊 分布直方图")
hist_ranges=[(-5,-2),(-2,0),(0,2),(2,4),(4,6),(6,8),(8,10),(10,15),(15,999)]
for lo,hi in hist_ranges:
    n=sum(1 for h in highs if lo<=h<hi)
    bar="█"*max(1,int(n/len(highs)*100/2))
    print(f"{f'{lo}~{hi}%':<10} {n:>3}天 {bar}")

# 打板 vs CG-06对比
print(f"\n{'='*70}")
print(f"⚡ 打板 vs 🐷 CG-06 对比")
print(f"{'='*70}")

# CG-06（含涨停）
champs_cg=run_backtest("cg06")  # just use same function differently
# Actually let me just pick the original CG-06 champion from earlier data
# CG-06 = M1 + yang + ma5_up
cg_highs=[]
for dt in sorted(by_date.keys()):
    cand=[sd for sd in by_date[dt] if sd["yang"] and sd["ma_full"] and sd["macd_strict"] and sd["price"] and sd["atr3"] and sd["ma60"] and sd["yang"]]
    if cand:
        cand.sort(key=lambda x:x["score"],reverse=True)
        cg_highs.append(cand[0]["d1_high"])

print(f"\n{'指标':<20} {'⚡打板':>10} {'🐷CG-06':>10}")
print("-"*42)
for t in [2.5,5,8,10]:
    db=sum(1 for h in highs if h>=t)/len(highs)*100
    cg=sum(1 for h in cg_highs if h>=t)/len(cg_highs)*100
    print(f"{f'≥{t}%':>10}{'概率':<10} {db:>7.1f}% {cg:>7.1f}%")
print(f"{'平均冲高':<20} {sum(highs)/len(highs):>+7.2f}% {sum(cg_highs)/len(cg_highs):>+7.2f}%")

print(f"\n⏱ {(time.time()-t0)/60:.1f}分")
