#!/usr/bin/env python3
"""M1+阳线+站MA5 候选池 → 每天评分TOP1的冠军胜率"""
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
        all_codes[code]={"c":c,"o":o,"h":h,"l":l,"v":v,"mas":mas,"dif":dif,"dea":dea,"macd":macd,"pct":pct,"recs":recs,"atr":atr,"k":k,"d":d,"j":j,"pos20":pos20}
    except: pass

dates_2026=sorted(set(r["date"] for code,sd in all_codes.items() for r in sd["recs"] if r["date"].startswith("2026")))

# ── 条件 ──
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

def score_v1(c,s,d):
    """评分函数"""
    sc=0; cl=s["c"][d]
    atr_v=s["atr"][d]; sc+=(atr_v/cl*100)*2 if atr_v and cl>0 else 0
    if s["pct"][d]>0: sc+=10
    v5=s["mas"]["v5"][d] if s["mas"]["v5"][d] else 0
    vr=s["v"][d]/v5 if v5>0 else 0
    if 1<vr<2: sc+=15; sc+=10
    elif vr>2: sc+=8
    sc+=(s["pos20"][d] or 50)*0.2
    if s["j"][d] and s["j"][d]>50: sc+=10
    return sc

# ── 测试不同过滤方案 ──
schemes = [
    ("M1+阳线+站MA5(无涨幅限制)", [lambda c,s,d: pass_M1(c,s,d)]),
    ("M1+阳线+站MA5+涨0~9.8%", [lambda c,s,d: pass_M1(c,s,d) and 0<=s["pct"][d]<=9.8]),
    ("M1+阳线+站MA5+涨2~8%", [lambda c,s,d: pass_M1(c,s,d) and 2<=s["pct"][d]<=8]),
    ("M1+阳线+站MA5+涨3~7%", [lambda c,s,d: pass_M1(c,s,d) and 3<=s["pct"][d]<=7]),
    ("M1+阳线+站MA5+涨4~6%", [lambda c,s,d: pass_M1(c,s,d) and 4<=s["pct"][d]<=6]),
    ("M1+阳线+站MA5+涨4~5.5%", [lambda c,s,d: pass_M1(c,s,d) and 4<=s["pct"][d]<=5.5]),
    ("M1+阳线+站MA5+涨4~7.5%", [lambda c,s,d: pass_M1(c,s,d) and 4<=s["pct"][d]<=7.5]),
    ("M1+阳线+站MA5+涨5~8%", [lambda c,s,d: pass_M1(c,s,d) and 5<=s["pct"][d]<=8]),
]

print(f"\n{'='*80}")
print("🏆 冠军分析（每天评分TOP1的胜率）")
print(f"{'='*80}")

for name, checkers in schemes:
    # 逐天收集
    champ_results=[]
    days_with_candidates=0
    total_cand=0
    
    for dt in sorted(dates_2026):
        cand=[]
        for code,sd in all_codes.items():
            try:
                di=None
                for idx,r in enumerate(sd["recs"]):
                    if r["date"]==dt: di=idx; break
                if di is None or di<80: continue
                ok=True
                for cond in checkers:
                    if not cond(code,sd,di): ok=False; break
                if not ok: continue
                sc=score_v1(code,sd,di)
                
                next_h=None
                for j,r2 in enumerate(sd["recs"]):
                    if r2["date"]==dt and j+1<len(sd["recs"]):
                        next_h=round((sd["recs"][j+1]["high"]/sd["c"][di]-1)*100,2); break
                
                cand.append({"code":code,"score":sc,"pct":sd["pct"][di],"next_h":next_h})
            except: continue
        
        total_cand+=len(cand)
        cand.sort(key=lambda x:x["score"],reverse=True)
        
        if len(cand)>=10:
            days_with_candidates+=1
            champ=cand[0]
            champ_results.append(champ)
    
    # 统计冠军胜率
    total_champ=len(champ_results)
    champ_wins=sum(1 for c in champ_results if c["next_h"] and c["next_h"]>=2.5)
    champ_win_rate=champ_wins/total_champ*100 if total_champ else 0
    
    print(f"\n{name}")
    print(f"  ─{'─'*60}")
    print(f"  出票天数: {days_with_candidates}/{len(dates_2026)}天 ({days_with_candidates/len(dates_2026)*100:.1f}%)")
    print(f"  冠军胜率: {champ_wins}/{total_champ} = {champ_win_rate:.1f}%")
    print(f"  日均候选: {total_cand/len(dates_2026):.0f}只")
    
    # 标记
    mk="🔥" if champ_win_rate>=70 else ("✅" if champ_win_rate>=60 else "")
    print(f"  评价: {mk}")

print(f"\n{'='*80}")
print("📋 最佳方案一览")
print(f"{'='*80}")
print(f"{'方案':<36} {'出票率':>10} {'冠军胜率':>10} {'日均候选':>10}")
print("-"*66)
