#!/usr/bin/env python3
"""简洁版 — 每日候选数+冠军结果"""
import json, os
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
        dif[i]=e12[i]-e26[i]
    dea[0]=dif[0] if dif[0] else 0
    for i in range(1,n): dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    for i in range(n):
        if dif[i] is not None and dea[i] is not None: macd[i]=dif[i]-dea[i]
    return dif,dea,macd

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
        all_codes[code]={"c":c,"o":o,"h":h,"l":l,"v":v,"mas":mas,"dif":dif,"dea":dea,"macd":macd,"pct":pct,"recs":recs,"atr":atr}
    except: pass

dates_2026=sorted(set(r["date"] for code,sd in all_codes.items() for r in sd["recs"] if r["date"].startswith("2026")))

def cond_price(c,s,d): return s["c"][d]<80
def cond_ma_bullish(c,s,d):
    m=s["mas"]
    return bool(m[5][d] and m[10][d] and m[20][d] and m[60][d] and m[5][d]>m[10][d]>m[20][d]>m[60][d])
def cond_macd_above(c,s,d): return bool(s["dif"][d] and s["dea"][d] and s["dif"][d]>0 and s["dif"][d]>s["dea"][d])
def cond_atr(c,s,d):
    a=s["atr"][d]; cl=s["c"][d]
    return bool(a and cl>0 and a/cl*100>3)
def cond_ma60(c,s,d): return bool(s["mas"][60][d] and s["c"][d]>s["mas"][60][d])
def cond_yang(c,s,d): return s["c"][d]>s["o"][d]
def cond_ma5_up(c,s,d): return bool(s["mas"][5][d] and s["c"][d]>s["mas"][5][d])
def cond_pct_4_5(c,s,d):
    p=s["pct"][d]; return 4.0<=p<=5.5

M1=[cond_price,cond_ma_bullish,cond_macd_above,cond_atr,cond_ma60]
BEST=M1+[cond_yang,cond_ma5_up,cond_pct_4_5]

# ═══ 也测一下 4.0~7.5% ═══
BEST2=M1+[cond_yang,cond_ma5_up, lambda c,s,d: 4.0<=s["pct"][d]<=7.5]
BEST3=M1+[cond_yang,cond_ma5_up, lambda c,s,d: 0<=s["pct"][d]<=9.8]

for label, conds in [("⭐ 4.0~5.5% (最优)", BEST), ("   4.0~7.5% (宽)", BEST2), ("   0~9.8% (最宽)", BEST3)]:
    print(f"\n{label}")
    print("─"*75)
    print(f"{'日期':<12} {'候选':>6} {'冠军涨%':>8} {'次日高%':>8} {'结果':>6}")
    print("─"*40)
    
    total_days=len(dates_2026)
    pick_days=0; wins=0; total_cand=0
    pick_days_list=[]
    
    for dt in sorted(dates_2026):
        cand=[]
        for code,sd in all_codes.items():
            try:
                di=None
                for idx,r in enumerate(sd["recs"]):
                    if r["date"]==dt: di=idx; break
                if di is None or di<80: continue
                ok=True
                for cond in conds:
                    if not cond(code,sd,di): ok=False; break
                if not ok: continue
                # 简单评分
                sc=0; cl=sd["c"][di]
                a=sd["atr"][di]; sc+=(a/cl*100)*2 if a and cl>0 else 0
                if sd["pct"][di]>0: sc+=10
                v5=sd["mas"]["v5"][di] if sd["mas"]["v5"][di] else 0
                vr=sd["v"][di]/v5 if v5>0 else 0
                if 1<vr<2: sc+=15; sc+=10
                elif vr>2: sc+=8
                
                next_h=None
                for j,r2 in enumerate(sd["recs"]):
                    if r2["date"]==dt and j+1<len(sd["recs"]):
                        next_h=round((sd["recs"][j+1]["high"]/cl-1)*100,2); break
                cand.append((code,sd["pct"][di],next_h,sc))
            except: continue
        
        total_cand+=len(cand)
        
        if len(cand)>=10:
            pick_days+=1
            pick_days_list.append(dt)
            cand.sort(key=lambda x:x[3],reverse=True)
            ch=cand[0]
            win=ch[2] and ch[2]>=2.5
            if win: wins+=1
            mk="✅" if win else "❌"
            nh=ch[2] if ch[2] else 0
            print(f"{dt:<12} {len(cand):>6} {ch[1]:>+7.2f}% {nh:>+7.2f}% {mk:>6}")
        else:
            print(f"{dt:<12} {len(cand):>6} {'—':>8} {'—':>8} {'<10':>6}")
    
    wr=wins/pick_days*100 if pick_days else 0
    avg=total_cand/total_days
    print(f"\n  出票{pick_days}/{total_days}天 ({pick_days/total_days*100:.1f}%)")
    print(f"  胜率 {wins}/{pick_days} = {wr:.1f}%")
    print(f"  日均候选 {avg:.0f}只")
    print(f"  出票日候选 {total_cand/max(pick_days,1):.0f}只/天")
