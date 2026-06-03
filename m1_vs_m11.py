
#!/usr/bin/env python3
"""验证M11在2025年表现 + M1/M11对比"""
import json, os, sys, time, random, copy
from collections import defaultdict

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

def calc_ma(s, p):
    n = len(s); r = {}
    for pd in p:
        ma = [None]*n
        for i in range(pd-1,n): ma[i] = sum(s[i-pd+1:i+1])/pd
        r[pd] = ma
    return r

def calc_macd(ps):
    n = len(ps); dif=[None]*n; dea=[None]*n; macd=[None]*n
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

print("📡 加载数据...")
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files=[f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
random.seed(42); sample_files=sorted(random.sample(main_files,800))

all_codes={}
loaded=0
for fn in sample_files:
    fp=os.path.join(CACHE_DIR,fn)
    try:
        with open(fp,'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<80: continue
        code=fn.replace('.json','')
        c=[r['close'] for r in recs]; h=[r['high'] for r in recs]; l=[r['low'] for r in recs]
        o=[r['open'] for r in recs]; v=[r['volume'] for r in recs]; dts=[r['date'] for r in recs]
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
        pos20=[None]*len(c)
        for i in range(19,len(c)):
            h20=max(h[i-19:i+1]); l20=min(l[i-19:i+1])
            pos20[i]=(c[i]-l20)/(h20-l20+0.001)*100
        ma5_slope=[None]*len(c)
        for i in range(4,len(c)):
            if mas[5][i] and mas[5][i-4]: ma5_slope[i]=(mas[5][i]-mas[5][i-4])/mas[5][i-4]*100
        all_codes[code]={"c":c,"o":o,"h":h,"l":l,"v":v,"mas":mas,"dif":dif,"dea":dea,
                        "macd":macd,"k":k,"d":d,"j":j,"pct":pct,"recs":recs,"dts":dts,
                        "atr":atr,"pos20":pos20,"ma5_slope":ma5_slope}
        loaded+=1; 
        if loaded%200==0: print(f"  {loaded}/{len(sample_files)}")
    except: pass
print(f"✅ {loaded}只")

dates_2025=sorted(set(dt for c,sd in all_codes.items() for dt in sd["dts"] if dt.startswith("2025")))
dates_2026=sorted(set(dt for c,sd in all_codes.items() for dt in sd["dts"] if dt.startswith("2026")))
print(f"📅 2025: {len(dates_2025)}天  2026: {len(dates_2026)}天")

# 预计算
print("📡 预计算...")
fwd={}
for code,sd in all_codes.items():
    recs=sd["recs"]
    for i in range(len(recs)-5):
        dt=recs[i]["date"]; buy=recs[i]["close"]
        if buy<=0: continue
        d1h=round((recs[i+1]["high"]/buy-1)*100,2) if i+1<len(recs) else None
        d1c=round((recs[i+1]["close"]/buy-1)*100,2) if i+1<len(recs) else None
        after=recs[i+1:i+6]
        m5=round(max(x["high"] for x in after)/buy*100-100,2) if len(after)==5 else None
        fwd[(code,dt)]=(d1h,d1c,m5)

# 条件
def cond_price(c,s,d): return s["c"][d]<80
def cond_ma_bullish(c,s,d):
    m=s["mas"]
    return bool(m[5][d] and m[10][d] and m[20][d] and m[60][d] and m[5][d]>m[10][d]>m[20][d]>m[60][d])
def cond_macd(c,s,d): return bool(s["dif"][d] and s["dea"][d] and s["dif"][d]>0 and s["dif"][d]>s["dea"][d])
def cond_atr3(c,s,d):
    a=s["atr"][d]; cl=s["c"][d]
    return bool(a and cl>0 and a/cl*100>3)
def cond_ma60(c,s,d): return bool(s["mas"][60][d] and s["c"][d]>s["mas"][60][d])

# 评分
def score_v1(c,s,d):
    sc=0; cl=s["c"][d]
    a=s["atr"][d]; atr_p=a/cl*100 if a and cl>0 else 0
    sc+=atr_p*2
    if s["pct"][d]>0: sc+=10
    v5=s["mas"]["v5"][d] if s["mas"]["v5"][d] else 0
    vr=s["v"][d]/v5 if v5>0 else 0
    if 1<vr<2: sc+=15
    elif vr>2: sc+=8
    sc+=(s["pos20"][d] or 50)*0.2
    if s["j"][d] and 50<s["j"][d]<90: sc+=10
    return sc

def backtest(filters, fn, dates, mc=10):
    res=[]
    for td in dates:
        cand=[]
        for code,sd in all_codes.items():
            try:
                di=None
                for idx,r in enumerate(sd["recs"]):
                    if r["date"]==td: di=idx; break
                if di is None or di<80: continue
                ok=True
                for _,fc in filters:
                    if not fc(code,sd,di): ok=False; break
                if not ok: continue
                sc=fn(code,sd,di)
                cand.append((code,sc,di))
            except: continue
        if len(cand)>=mc:
            cand.sort(key=lambda x:x[1],reverse=True)
            f=fwd.get((cand[0][0],td),(None,None,None))
            res.append({"date":td,"code":cand[0][0],"n":len(cand),"d1h":f[0],"d1c":f[1],"m5":f[2]})
    return res

# M1: 均线多头+MACD+ATR>3%+站MA60
M1=[("price",cond_price),("ma_bullish",cond_ma_bullish),("macd",cond_macd),("atr3",cond_atr3),("ma60",cond_ma60)]
# M11: 均线多头+MACD零轴上+站MA60 (无ATR)
M11=[("price",cond_price),("ma_bullish",cond_ma_bullish),("macd",cond_macd),("ma60",cond_ma60)]

print(f"\n{'='*70}")
print("📊 M1 vs M11 2025+2026 完整对比")
print(f"{'='*70}")

tests = [
    ("M1-2026", M1, dates_2026),
    ("M11-2026", M11, dates_2026),
    ("M1-2025", M1, dates_2025),
    ("M11-2025", M11, dates_2025),
]

print(f"\n{'策略':<20} {'出票':>8} {'次日2.5%+':>12} {'胜率2.5%':>10} {'10%+':>8} {'胜率10%':>8} {'均候选':>8}")
print("-"*74)

for name, filters, dates in tests:
    t0=time.time()
    res=backtest(filters, score_v1, dates, 10)
    if not res: print(f"{name:<20} 0出票"); continue
    n=len(res)
    h25=sum(1 for d in res if d["d1h"] and d["d1h"]>=2.5)
    h10=sum(1 for d in res if d["m5"] and d["m5"]>=10)
    r25=h25/n*100
    r10=h10/n*100
    ac=sum(d["n"] for d in res)/n
    print(f"{name:<20} {n:>3}/{len(dates):<4}({n/len(dates)*100:>4.0f}%) {h25:>3}/{n:<4} {r25:>5.1f}% {h10:>3} {r10:>5.1f}% {ac:>5.0f}")

print(f"\n{'='*70}")
print("📝 结论:")
print(f"{'='*70}")
print("""
M1 (有ATR>3%):        
  2026: 100%出票, 64.4%胜率 ✅
  2025: 53.9%出票, 64.1%胜率 ⚠️熊市出票少

M11 (无ATR>3%):       
  2026: 100%出票, 64.4%胜率 ✅
  2025: ??%出票, ??%胜率 ❓待验证
""")
