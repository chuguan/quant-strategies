#!/usr/bin/env python3
"""CG-13 动量突破版 — M1+阳线+站MA5 + 动量突破评分因子"""
import json, os, time

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
        dif[i]=e12[i]-e26[i]
    dea[0]=dif[0] if dif[0] else 0
    for i in range(1,n): dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    for i in range(n):
        if dif[i] is not None and dea[i] is not None: macd[i]=dif[i]-dea[i]
    return dif,dea,macd

t0=time.time()
print("📡 加载数据…")
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files=[f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
all_codes={}
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
        pct=[0.0]
        for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr_l)/14
        pos20=[None]*len(c); ma5_sl=[None]*len(c)
        for i in range(19,len(c)):
            h20=max(h[i-19:i+1]); l20=min(l[i-19:i+1])
            pos20[i]=(c[i]-l20)/(h20-l20+0.001)*100
        for i in range(4,len(c)):
            if mas[5][i] and mas[5][i-4]: ma5_sl[i]=(mas[5][i]-mas[5][i-4])/mas[5][i-4]*100
        all_codes[code]={"c":c,"o":o,"h":h,"l":l,"v":v,"mas":mas,"dif":dif,"dea":dea,"pct":pct,"recs":recs,"atr":atr,"pos20":pos20,"ma5_sl":ma5_sl}
    except: pass
print(f"✅ {len(all_codes)}只, {time.time()-t0:.0f}秒")

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

dates_2025=sorted(set(r["date"] for c,s in all_codes.items() for r in s["recs"] if r["date"].startswith("2025")))
dates_2026=sorted(set(r["date"] for c,s in all_codes.items() for r in s["recs"] if r["date"].startswith("2026")))

print("📝 收集M1全池候选…")
daily_cand={}
for dt in sorted(set(dates_2025+dates_2026)):
    cand=[]
    for code,sd in all_codes.items():
        try:
            di=None
            for idx,r in enumerate(sd["recs"]):
                if r["date"]==dt: di=idx; break
            if di is None or di<80: continue
            if not pass_M1(code,sd,di): continue
            cl=sd["c"][di]; op=sd["o"][di]; hi=sd["h"][di]; lo=sd["l"][di]; vo=sd["v"][di]
            pct_v=sd["pct"][di]; atr_v=sd["atr"][di]
            v5=sd["mas"]["v5"][di] if sd["mas"]["v5"][di] else 0
            vr=vo/v5 if v5>0 else 0
            atr_pct=atr_v/cl*100 if atr_v and cl>0 else 0
            body_pct=abs(cl-op)/op*100
            shadow_pct=(hi-max(cl,op))/(hi-lo+0.001)*100
            rpos=(cl-lo)/(hi-lo+0.001)*100
            ma5_sl_v=sd["ma5_sl"][di] if sd["ma5_sl"][di] else 0
            
            # ★ 动量突破因子 ★
            # 1. 突破5日最高价
            if di>=4:
                high5=max(sd["h"][di-4:di+1])
                break5=(cl/high5-1)*100  # >0表示突破
            else: break5=0
            # 2. 突破10日最高价
            if di>=9:
                high10=max(sd["h"][di-9:di+1])
                break10=(cl/high10-1)*100
            else: break10=0
            
            next_h=None
            for j,r2 in enumerate(sd["recs"]):
                if r2["date"]==dt and j+1<len(sd["recs"]):
                    next_h=round((sd["recs"][j+1]["high"]/cl-1)*100,2); break
            
            cand.append({"code":code,"pct":pct_v,"atr_pct":atr_pct,"vr":vr,
                        "body_pct":body_pct,"shadow_pct":shadow_pct,"rpos":rpos,
                        "ma5_sl":ma5_sl_v,"next_h":next_h,
                        "break5":break5,"break10":break10})
        except: continue
    daily_cand[dt]=cand

# ═══ 测试各种评分版本（含动量突破因子） ═══
scorers = {}

# v14基准
scorers["v14(基准)"] = lambda d: (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0) + min(d["body_pct"]*3,25) + min(d["atr_pct"]*2,16)

# 动量突破版（在v14基础上加分）
scorers["CG-13a(突破5d+放量+c收)"] = lambda d: (
    (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0)    # 上影
    + min(d["body_pct"]*3,25)                                          # 实体
    + min(d["atr_pct"]*2,16)                                           # ATR
    + (20 if d["break5"]>0 else 0)                                     # 突破5日高+20
    + (15 if d["vr"]>=1.3 else 0)                                      # 量比>1.3+15
    + (15 if d["rpos"]>80 else 0)                                      # 强势收盘+15
    + (15 if 3<=d["pct"]<=5 else 10 if d["pct"]<3 else -10 if d["pct"]>7 else 0)  # 涨幅3~5%+15
)

# 只用动量(不要v14基础)
scorers["CG-13b(纯动量·不用v14)"] = lambda d: (
    (25 if d["break5"]>0 else 5 if d["break10"]>0 else 0)              # 突破
    + (20 if d["vr"]>=1.3 else 10 if d["vr"]>=1 else 0)                # 量比
    + (25 if d["rpos"]>80 else 10 if d["rpos"]>65 else 0)              # 收盘位置
    + (20 if 3<=d["pct"]<=5 else 10 if d["pct"]<3 else 5 if d["pct"]<=7 else 0)  # 涨幅
    + (15 if d["shadow_pct"]<15 else 5 if d["shadow_pct"]<30 else 0)   # 上影(辅助)
)

# v14+突破(只加突破，不要其他)
scorers["CG-13c(v14+突破5d)"] = lambda d: (
    (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0)
    + min(d["body_pct"]*3,25) + min(d["atr_pct"]*2,16)
    + (30 if d["break5"]>0 else 10 if d["break10"]>0 else 0)          # 突破重奖
)

# v14+突破+放量+强势
scorers["CG-13d(v14+突破+放量+强势)"] = lambda d: (
    (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0)
    + min(d["body_pct"]*3,25) + min(d["atr_pct"]*2,16)
    + (25 if d["break5"]>0 else 5 if d["break10"]>0 else 0)          # 突破
    + (15 if d["vr"]>=1.3 else 0)                                     # 放量
    + (15 if d["rpos"]>80 else 0)                                     # 强势收盘
)

# 突破+涨幅3~5%+上影
scorers["CG-13e(突破+涨3~5+上影)"] = lambda d: (
    (25 if d["break5"]>0 else 5 if d["break10"]>0 else 0)
    + (20 if 3<=d["pct"]<=5 else 10 if d["pct"]<3 else -5)
    + (20 if d["shadow_pct"]<10 else 10 if d["shadow_pct"]<20 else 0)
    + (10 if d["vr"]>=1.3 else 0)
)

# 严格动量（要求突破+放量+强势全部满足才高分）
scorers["CG-13f(严格突破·三点全满足)"] = lambda d: (
    (40 if d["break5"]>0 and d["vr"]>=1.3 and d["rpos"]>80 else        # 三点全满足+40
     20 if d["break5"]>0 and d["vr"]>=1.3 else                          # 突破+放量+20
     10 if d["break5"]>0 else 0)                                        # 仅突破+10
    + (max(0,30-d["shadow_pct"]*1.2) if d["shadow_pct"]<25 else 0)    # 上影
    + (15 if 3<=d["pct"]<=5 else 5 if d["pct"]<3 else 0)              # 涨幅
)

# ═══ 跑回测 ═══
print(f"\n{'='*90}")
print("🏆 CG-13 动量突破版 — 回测结果")
print(f"{'='*90}")
print(f"\n{'评分方案':<36} {'2025':>12} {'2026':>12} {'平均':>8}")
print("-"*70)

results = []
for sname, scorer in scorers.items():
    wins5_25=0; tot5_25=0; wins5_26=0; tot5_26=0
    wins10_25=0; tot10_25=0; wins10_26=0; tot10_26=0
    all_cands_25=0; all_cands_26=0
    
    for dt in dates_2025:
        cds=daily_cand.get(dt,[])
        all_cands_25+=len(cds)
        if len(cds)>=5:
            champ=sorted(cds, key=scorer, reverse=True)[0]
            tot5_25+=1
            if champ["next_h"] and champ["next_h"]>=2.5: wins5_25+=1
        if len(cds)>=10:
            champ=sorted(cds, key=scorer, reverse=True)[0]
            tot10_25+=1
            if champ["next_h"] and champ["next_h"]>=2.5: wins10_25+=1
    
    for dt in dates_2026:
        cds=daily_cand.get(dt,[])
        all_cands_26+=len(cds)
        if len(cds)>=5:
            champ=sorted(cds, key=scorer, reverse=True)[0]
            tot5_26+=1
            if champ["next_h"] and champ["next_h"]>=2.5: wins5_26+=1
        if len(cds)>=10:
            champ=sorted(cds, key=scorer, reverse=True)[0]
            tot10_26+=1
            if champ["next_h"] and champ["next_h"]>=2.5: wins10_26+=1
    
    wr5_25=wins5_25/tot5_25*100 if tot5_25 else 0
    wr5_26=wins5_26/tot5_26*100 if tot5_26 else 0
    wr10_25=wins10_25/tot10_25*100 if tot10_25 else 0
    wr10_26=wins10_26/tot10_26*100 if tot10_26 else 0
    avg5=(wr5_25+wr5_26)/2; avg10=(wr10_25+wr10_26)/2
    
    pick5_25=tot5_25/len(dates_2025)*100
    pick5_26=tot5_26/len(dates_2026)*100
    pick10_25=tot10_25/len(dates_2025)*100
    pick10_26=tot10_26/len(dates_2026)*100
    
    results.append((avg5, wr5_25, wr5_26, pick5_25, pick5_26, tot5_25, tot5_26, 
                    wr10_25, wr10_26, pick10_25, pick10_26, tot10_25, tot10_26, sname))
    
    mk="🔥" if avg5>=75 else ("✅" if avg5>=70 else "")
    print(f"{sname:<36} {wr5_25:>5.1f}%/{tot5_25:>3}d {wr5_26:>5.1f}%/{tot5_26:>3}d {avg5:>5.1f}% {mk}")

# ═══ 展示最佳 ═══
print(f"\n{'='*90}")
print("🏆🏆 各维度最佳（含≥5和≥10票数据）")
print(f"{'='*90}")
print(f"\n{'排名':>4} {'方案':<36} {'≥5票胜率':>14} {'≥5票出票':>12} {'≥10票胜率':>14} {'≥10票出票':>12}")
print("-"*92)

results.sort(reverse=True)
for i,(avg5,wr25,wr26,p25,p26,t25,t26,wr10_25,wr10_26,p10_25,p10_26,t10_25,t10_26,sname) in enumerate(results):
    avg_25_5=wr25; avg_26_5=wr26
    avg_25_10=wr10_25; avg_26_10=wr10_26
    avg10=(avg_25_10+avg_26_10)/2
    mk5="🔥" if avg5>=75 else ("✅" if avg5>=70 else "")
    mk10="🔥" if avg10>=75 else ("✅" if avg10>=70 else "")
    print(f"{i+1:>3}. {sname:<36} {avg5:>5.1f}%({t25:>3},{t26:>3}) {p25:>4.0f}%/{p26:>4.0f}% {avg10:>5.1f}%({t10_25:>3},{t10_26:>3}) {p10_25:>4.0f}%/{p10_26:>4.0f}%")

# 原始v14对比
print(f"\n{'─'*70}")
print("对比基准 v14(上影+实体+ATR): 2025=78.9%(133d) 2026=86.7%(90d) 平均82.8%")

print(f"\n⏱ {time.time()-t0:.0f}秒")
