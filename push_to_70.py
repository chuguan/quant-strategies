
#!/usr/bin/env python3
"""在M1基础上加更多条件，推高2026胜率"""
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
print("📡 加载数据...")
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files=[f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
random.seed(42); sample_files=sorted(random.sample(main_files,800))

stock_days=[]
loaded=0
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
            for i in range(14,len(c)):
                tr=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr)/14
        pos20=[None]*len(c)
        for i in range(19,len(c)):
            h20=max(h[i-19:i+1]); l20=min(l[i-19:i+1])
            pos20[i]=(c[i]-l20)/(h20-l20+0.001)*100
        
        for i in range(80, len(c)-1):
            dt=recs[i]["date"]
            if not (dt.startswith("2025") or dt.startswith("2026")): continue
            cl=c[i]; op=o[i]; hi=h[i]; lo=l[i]; vo=v[i]
            
            flags={}
            flags["price"]=cl<80
            flags["ma_full"]=bool(mas[5][i] and mas[10][i] and mas[20][i] and mas[60][i] and mas[5][i]>mas[10][i]>mas[20][i]>mas[60][i])
            flags["ma_med"]=bool(mas[5][i] and mas[10][i] and mas[20][i] and mas[5][i]>mas[10][i]>mas[20][i])
            flags["macd_strict"]=bool(dif[i] and dea[i] and dif[i]>0 and dif[i]>dea[i])
            flags["atr3"]=bool(atr[i] and cl>0 and atr[i]/cl*100>3)
            flags["ma60"]=bool(mas[60][i] and cl>mas[60][i])
            flags["yang"]=cl>op
            flags["vr"]=vo/(mas["v5"][i] or 1)
            flags["vr_ok"]=1<=flags["vr"]<=3
            flags["vr_active"]=flags["vr"]>0.7
            flags["vr_high"]=flags["vr"]>1.2
            flags["pos20"]=pos20[i] if pos20[i] else 50
            flags["pos20_ok"]=pos20[i] is not None and 20<=pos20[i]<=85
            flags["pos20_mid"]=pos20[i] is not None and 35<=pos20[i]<=70
            flags["no_shadow"]=(hi-max(cl,op))/(hi-lo+0.001)*100<30
            flags["j_good"]=bool(j[i] and 50<j[i]<90)
            flags["k_over_d"]=bool(k[i] and d[i] and k[i]>d[i])
            flags["ma5_slope_pos"]=bool(cl>mas[5][i]) if mas[5][i] else False
            
            next_h=(recs[i+1]["high"]/cl-1)*100
            flags["next_win"]=next_h>=2.5
            
            # 基础评分
            atr_pct=atr[i]/cl*100 if atr[i] and cl>0 else 0
            score=0; score+=atr_pct*2
            if pct[i]>0: score+=10
            if 1<flags["vr"]<2: score+=15
            elif flags["vr"]>2: score+=8
            score+=pos20[i]*0.2 if pos20[i] else 10
            if flags["j_good"]: score+=10
            
            stock_days.append({"date":dt,"code":code,"score":score,**flags})
        
        loaded+=1
        if loaded%200==0: print(f"  {loaded}/{len(sample_files)} ({len(stock_days)} rows)")
    except: pass

print(f"✅ {loaded}只, {len(stock_days)}条")

by_date=defaultdict(list)
for sd in stock_days:
    by_date[sd["date"]].append(sd)

def evaluate(flags, min_c=10, year="2026"):
    dates=sorted(set(sd["date"] for sd in stock_days if sd["date"].startswith(year)))
    pd_=0; wc=0; counts=[]
    for dt in dates:
        cand=[sd for sd in by_date[dt] if all(sd[f] for f in flags)]
        counts.append(len(cand))
        if len(cand)>=min_c:
            pd_+=1
            cand.sort(key=lambda x:x["score"],reverse=True)
            if cand[0]["next_win"]: wc+=1
    pr=pd_/len(dates)*100 if dates else 0
    wr=wc/pd_*100 if pd_ else 0
    ac=sum(counts)/len(counts) if counts else 0
    mc=min(counts) if counts else 0
    return pr,ac,mc,wr

# M1基础
M1=["price","ma_full","macd_strict","atr3","ma60"]

# 在M1基础上加额外条件
print(f"\n{'='*80}")
print(f"🔥 在M1基础上加条件 → 推高2026胜率 (基础: 69.7%)")
print(f"{'='*80}")

# 先评估M1
print(f"\n{'条件':<36} {'出票':>8} {'候选':>6} {'最低':>4} {'胜率':>8}")
print("-"*62)

p26,c26,m26,w26=evaluate(M1,10,"2026")
print(f"{'M1基线':<36} {p26:>6.1f}% {c26:>5.0f} {m26:>3} {w26:>6.1f}%")

# 逐个加条件测试
extra_conds = [
    ("+阳线", ["yang"]),
    ("+量比活跃(>0.7)", ["vr_active"]),
    ("+量比适中(1~3)", ["vr_ok"]),
    ("+量比>1.2", ["vr_high"]),
    ("+位置适中(35~70%)", ["pos20_mid"]),
    ("+位置20~85%", ["pos20_ok"]),
    ("+无上影(上影<30%)", ["no_shadow"]),
    ("+J值适中(50~90)", ["j_good"]),
    ("+K>D", ["k_over_d"]),
    ("+站上MA5", ["ma5_slope_pos"]),
]

for ename, econds in extra_conds:
    full_flags = M1 + econds
    p,c,m,w = evaluate(full_flags, 10, "2026")
    print(f"{ename:<36} {p:>6.1f}% {c:>5.0f} {m:>3} {w:>6.1f}%")

# 组合条件测试
print(f"\n{'='*80}")
print(f"🧪 组合条件（多个一起加）")
print(f"{'='*80}")
print(f"\n{'条件':<36} {'出票':>8} {'候选':>6} {'最低':>4} {'胜率':>8}")
print("-"*62)

combos = [
    ("M1+阳线+量比>1.2", M1+["yang","vr_high"]),
    ("M1+阳线+量比1~3", M1+["yang","vr_ok"]),
    ("M1+阳线+位置35~70%", M1+["yang","pos20_mid"]),
    ("M1+阳线+J好+K>D", M1+["yang","j_good","k_over_d"]),
    ("M1+阳线+无上影", M1+["yang","no_shadow"]),
    ("M1+阳线+量比1~3+位置35~70%", M1+["yang","vr_ok","pos20_mid"]),
    ("M1+阳线+量比1~3+J好", M1+["yang","vr_ok","j_good"]),
    ("M1+阳线+量比>1.2+位置35~70%", M1+["yang","vr_high","pos20_mid"]),
    ("M1+阳线+量比1~3+J好+K>D", M1+["yang","vr_ok","j_good","k_over_d"]),
    ("M1+阳线+量比>1.2+无上影+J好", M1+["yang","vr_high","no_shadow","j_good"]),
    ("M1+阳线+量比1~3+位置35~70%+J好", M1+["yang","vr_ok","pos20_mid","j_good"]),
    ("M1+全部(%):最佳组合", M1+["yang","vr_high","pos20_mid","j_good"]),
    ("M1+全部+站MA5+K>D", M1+["yang","vr_high","pos20_mid","j_good","ma5_slope_pos","k_over_d"]),
]

for cname, cflags in combos:
    p,c,m,w = evaluate(cflags, 10, "2026")
    print(f"{cname:<36} {p:>6.1f}% {c:>5.0f} {m:>3} {w:>6.1f}%")

print(f"\n⏱ {(time.time()-t0)/60:.1f}分")
