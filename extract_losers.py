#!/usr/bin/env python3
"""提取所有输家冠军 — 2025+2026"""
import json, os
from collections import defaultdict

CACHE_DIR=r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

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
        dif[i]=e12[i]-e26[i]
    dea[0]=dif[0] if dif[0] else 0
    for i in range(1,n): dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    for i in range(n):
        if dif[i] is not None and dea[i] is not None: macd[i]=dif[i]-dea[i]
    return dif,dea,macd

print("📡 加载数据...")
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
all_codes={}
for fn in all_files:
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f:
            recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<80: continue
        if recs[-1]["date"]<"2020": continue
        code=fn.replace('.json','')
        c=[r['close'] for r in recs]; h=[r['high'] for r in recs]; l=[r['low'] for r in recs]
        o=[r['open'] for r in recs]; v=[r['volume'] for r in recs]
        mas=calc_ma(c,[5,10,20,60]); mas['v5']=calc_ma(v,[5])[5]
        dif,dea,macd=calc_macd(c)
        pct=[0.0]
        for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr_l)/14
        all_codes[code]={"c":c,"h":h,"l":l,"o":o,"v":v,"mas":mas,"dif":dif,"dea":dea,
                        "pct":pct,"recs":recs,"atr":atr}
    except: pass
print(f"✅ {len(all_codes)}只")

def pass_M1(c,s,d):
    if s["c"][d]>=80: return False
    m=s["mas"]
    if not (m[5][d] and m[10][d] and m[20][d] and m[60][d] and m[5][d]>m[10][d]>m[20][d]>m[60][d]): return False
    if not (s["dif"][d] and s["dea"][d] and s["dif"][d]>0 and s["dif"][d]>s["dea"][d]): return False
    a=s["atr"][d]; cl=s["c"][d]
    if not (a and cl>0 and a/cl*100>3): return False
    if not (m[60][d] and cl>m[60][d]): return False
    if s["c"][d]<=s["o"][d]: return False
    if not (m[5][d] and cl>m[5][d]): return False
    return True

dates_2025=sorted(set(r["date"] for s in all_codes.values() for r in s["recs"] if r["date"].startswith("2025")))
dates_2026=sorted(set(r["date"] for s in all_codes.values() for r in s["recs"] if r["date"].startswith("2026")))

# v14评分
def v14_score(c,s,d):
    cl=s["c"][d]; op=s["o"][d]; hi=s["h"][d]; lo=s["l"][d]
    rng=hi-lo; shadow=(hi-max(cl,op))/(rng+0.001)*100 if rng>0 else 0
    body=abs(cl-op)/op*100
    atr_p=s["atr"][d]/cl*100 if s["atr"][d] and cl>0 else 0
    return (max(0,35-shadow*1.2) if shadow<30 else 0) + min(body*3,25) + min(atr_p*2,16)

# 收集所有输家
losers=[]; winners=[]; total_days=0
for dt in sorted(set(dates_2025+dates_2026)):
    cand=[]
    for code,sd in all_codes.items():
        di=next((i for i,r in enumerate(sd["recs"]) if r["date"]==dt), None)
        if di is None or di<80: continue
        if not pass_M1(code,sd,di): continue
        
        cl=sd["c"][di]; op=sd["o"][di]; hi=sd["h"][di]; lo=sd["l"][di]; vo=sd["v"][di]
        rng=hi-lo; shadow=(hi-max(cl,op))/(rng+0.001)*100 if rng>0 else 0
        body=abs(cl-op)/op*100
        atr_p=sd["atr"][di]/cl*100 if sd["atr"][di] and cl>0 else 0
        v5=sd["mas"]["v5"][di] if sd["mas"]["v5"][di] else 0
        vr=vo/v5 if v5>0 else 0
        rpos=(cl-lo)/(rng+0.001)*100 if rng>0 else 0
        # 评分分解
        shadow_score=max(0,35-shadow*1.2) if shadow<30 else 0
        body_score=min(body*3,25)
        atr_score=min(atr_p*2,16)
        total_score=shadow_score+body_score+atr_score
        
        next_h=round((sd["recs"][di+1]["high"]/cl-1)*100,2) if di+1<len(sd["recs"]) else None
        
        cand.append({"code":code,"score":total_score,"shadow":shadow,"body":body,"atr_p":atr_p,
                     "pct":sd["pct"][di],"vr":vr,"rpos":rpos,"next_h":next_h,
                     "shadow_sc":shadow_score,"body_sc":body_score,"atr_sc":atr_score})
    
    if len(cand)>=5:
        total_days+=1
        cand.sort(key=lambda x:x["score"],reverse=True)
        champ=cand[0]
        yr=dt[:4]
        if champ["next_h"] and champ["next_h"]>=2.5:
            winners.append({"yr":yr,"dt":dt,**champ})
        else:
            losers.append({"yr":yr,"dt":dt,**champ})

# 输家按照日期排序
losers.sort(key=lambda x:x["dt"])

# ═══ 输出 = ═══
print(f"\n{'='*120}")
print(f"❌ 2025+2026年 所有输家冠军 ({len(losers)}个)")
print(f"{'='*120}")
print(f"{'日期':<12} {'代码':<10} {'总分':>5} {'上影分':>6} {'实体分':>6} {'ATR分':>6} {'上影%':>6} {'实体%':>6} {'ATR%':>6} {'涨%':>6} {'量比':>5} {'收盘位':>6} {'次日高':>7}")
print("-"*120)
for r in losers:
    nh=r["next_h"] if r["next_h"] else 0
    print(f"{r['dt']:<12} {r['code']:<10} {r['score']:>5.0f} {r['shadow_sc']:>5.1f} {r['body_sc']:>5.1f} {r['atr_sc']:>5.1f} "
          f"{r['shadow']:>5.1f}% {r['body']:>5.1f}% {r['atr_p']:>5.1f}% {r['pct']:>5.2f}% {r['vr']:>4.1f} {r['rpos']:>5.1f}% {nh:>+5.2f}%")

# 赢家统计摘要
print(f"\n{'='*120}")
print(f"✅ 赢家冠军 ({len(winners)}个)")
print(f"{'='*120}")

# 赢家平均值
print(f"\n📊 赢家 vs 输家 特征对比")
print(f"{'指标':<12} {'赢家均值':>10} {'输家均值':>10} {'差距':>10}")
print("-"*42)
w_avg=lambda k: sum(r[k] or 0 for r in winners)/len(winners)
l_avg=lambda k: sum(r[k] or 0 for r in losers)/len(losers)
for key,name in [("shadow","上影%"),("body","实体%"),("atr_p","ATR%"),
                  ("pct","涨幅%"),("vr","量比"),("rpos","收盘位%"),
                  ("shadow_sc","上影分"),("body_sc","实体分"),("atr_sc","ATR分")]:
    print(f"{name:<12} {w_avg(key):>9.2f} {l_avg(key):>9.2f} {w_avg(key)-l_avg(key):>+9.2f}")

print(f"\n📊 输家主要输在哪？")
# 评分构成对比
for part in ["shadow_sc","body_sc","atr_sc"]:
    wp=w_avg(part)/w_avg("score")*100
    lp=l_avg(part)/l_avg("score")*100
    print(f"  {part}: 赢家占{wp:.0f}% vs 输家占{lp:.0f}%")

print(f"\n总天数:{total_days} 赢家:{len(winners)} 输家:{len(losers)} 胜率:{len(winners)/(len(winners)+len(losers))*100:.1f}%")
