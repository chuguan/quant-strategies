#!/usr/bin/env python3
"""涨幅从硬过滤→评分项：挽留所有好票，提胜率"""
import json, os, time, random
from collections import defaultdict

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

def ma(s,pd):
    n=len(s); r=[None]*n
    for i in range(pd-1,n): r[i]=sum(s[i-pd+1:i+1])/pd
    return r

def macd(ps):
    n=len(ps); d=[None]*n; e=[None]*n; m=[None]*n
    if n<26: return d,e,m
    e12=[ps[0]]; e26=[ps[0]]
    for i in range(1,n):
        e12.append(e12[-1]*11/13+ps[i]*2/13); e26.append(e26[-1]*25/27+ps[i]*2/27)
        d[i]=e12[i]-e26[i]; e[0]=d[0] if d[0] else 0
    for i in range(1,n): e[i]=e[i-1]*8/10+(d[i] if d[i] else 0)*2/10
    for i in range(n):
        if d[i] is not None and e[i] is not None: m[i]=d[i]-e[i]
    return d,e,m

def kdj(h,l,c,n=9):
    L=len(c); k=[50.0]*L; dv=[50.0]*L; j=[50.0]*L
    if L<n: return k,dv,j
    for i in range(n-1,L):
        hh=max(h[i-n+1:i+1]); ll=min(l[i-n+1:i+1])
        rsv=50.0 if hh==ll else (c[i]-ll)/(hh-ll)*100
        if i>n-1: k[i]=2/3*k[i-1]+1/3*rsv; dv[i]=2/3*dv[i-1]+1/3*k[i]
        j[i]=3*k[i]-2*dv[i]
    return k,dv,j

t0=time.time()
print("加载3427只...")
fs=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
mfs=[f for f in fs if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]

rows=[]; n=0
for fn in mfs:
    fp=os.path.join(CACHE_DIR,fn)
    try:
        with open(fp,'rb') as f: rs=json.loads(f.read().decode('utf-8'))
        if len(rs)<80: continue
        cd=fn.replace('.json','')
        c=[r['close'] for r in rs]; h=[r['high'] for r in rs]; l=[r['low'] for r in rs]
        o=[r['open'] for r in rs]; v=[r['volume'] for r in rs]
        m5=ma(c,5); m10=ma(c,10); m20=ma(c,20); m60=ma(c,60)
        v5=ma(v,5); dif,dea,_=macd(c)
        k,dv,j=kdj(h,l,c)
        p=[0.0]
        for idx in range(1,len(c)): p.append((c[idx]/c[idx-1]-1)*100)
        at=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                at[i]=sum(tr)/14
        p20=[None]*len(c)
        for i in range(19,len(c)):
            h20=max(h[i-19:i+1]); l20=min(l[i-19:i+1])
            p20[i]=(c[i]-l20)/(h20-l20+0.001)*100
        
        for i in range(80,len(c)-1):
            dt=rs[i]["date"]
            if not dt.startswith("2026"): continue
            cl=c[i]; op=o[i]; hi=h[i]; lo=l[i]; vo=v[i]
            vr=vo/(v5[i] or 1); atr=at[i]/cl*100 if at[i] and cl>0 else 0
            sr=(hi-max(cl,op))/(hi-lo+0.001)*100; bd=abs(cl-op)/op*100
            
            fl={"dt":dt,"cd":cd,"pct":p[i]}
            fl["ok"]=(cl<80 and m5[i] and m10[i] and m20[i] and m60[i] and
                     m5[i]>m10[i]>m20[i]>m60[i] and
                     dif[i] and dea[i] and dif[i]>0 and dif[i]>dea[i] and
                     atr>3 and m60[i] and cl>m60[i] and cl>op and m5[i] and cl>m5[i])
            fl["nw"]=(rs[i+1]["high"]/cl-1)*100>=2.5
            
            # 基础评分(不含涨幅)
            sc=0; sc+=atr*2
            if 1<vr<2: sc+=15
            elif vr>2: sc+=8
            sc+=(p20[i] or 50)*0.2
            if j[i] and 50<j[i]<90: sc+=10
            if sr>50: sc-=10
            elif sr>30: sc-=3
            fl["base"]=sc
            rows.append(fl)
        
        n+=1
        if n%500==0: print(f"  {n}/{len(mfs)}")
    except: pass
print(f"加载{n}只, {len(rows)}条")

bd={}
for r in rows: bd.setdefault(r["dt"],[]).append(r)
dates=sorted(bd.keys())

# ═══ 测试不同评分方案 ═══
def eval_score(score_fn, mc=10):
    pd_=0; wc=0
    for dt in dates:
        cand=[r for r in bd[dt] if r["ok"]]
        for r in cand:
            r["sc"]=r["base"]+score_fn(r["pct"])
        cand.sort(key=lambda x:x["sc"],reverse=True)
        if len(cand)>=mc:
            pd_+=1
            if cand[0]["nw"]: wc+=1
    wr=wc/pd_*100 if pd_ else 0
    return wr, pd_

print()
print("="*70)
print("涨幅从硬过滤→评分项 方案对比")
print("="*70)

# 方案0: 无涨幅评分（基准）
def s0(p): return 0
wr0,pd0=eval_score(s0)
print(f"\n【基准】无涨幅评分: {wr0:.1f}% ({pd0}天)")

# 方案1: 4.0~5.5%加分
def s1(p):
    if 4.0<=p<=5.5: return 20
    elif 2<=p<4 or 5.5<p<=7: return 10
    elif 0<=p<2 or 7<p<=9.8: return 5
    elif p<0: return -10
    else: return -20

wr1,pd1=eval_score(s1)
print(f"【方案1】4~5.5%+20分,2~7%+10分: {wr1:.1f}% ({pd1}天)")

# 方案2: 不同权重
weight_tests=[
    ("4~5.5%+30",[(4,5.5,30),(2,7,10),(0,9.8,5),(-99,0,-10),(9.8,99,-20)]),
    ("4~5.5%+25",[(4,5.5,25),(2,7,12),(0,9.8,5),(-99,0,-10),(9.8,99,-20)]),
    ("4~5.5%+20",[(4,5.5,20),(2,7,10),(0,9.8,5),(-99,0,-10),(9.8,99,-20)]),
    ("4~5.5%+15,3~7%+10",[(4,5.5,15),(3,7,10),(0,9.8,3),(-99,0,-10),(9.8,99,-20)]),
    ("4~5.5%+20,3~7%+10,0~9.8%+3",[(4,5.5,20),(3,7,10),(0,9.8,3),(-99,0,-10),(9.8,99,-20)]),
    ("3~7%+15,0~9.8%+5",[(3,7,15),(0,9.8,5),(-99,0,-10),(9.8,99,-20)]),
    ("只扣不分:负-10,涨≥9.8-20",[(0,99,0),(-99,0,-10),(9.8,99,-20)]),
    ("倒扣:4~5.5%+0,外圈-5",[(4,5.5,0),(2,7,-5),(0,9.8,-10),(-99,0,-15),(9.8,99,-25)]),
]

for name,wts in weight_tests:
    def make_fn(wts):
        def fn(p):
            for lo,hi,val in wts:
                if lo<=p<hi: return val
            return 0
        return fn
    wr,pd_=eval_score(make_fn(wts))
    print(f"【{name}】: {wr:.1f}% ({pd_}天)")

# 方案3: 连续函数（不是分段，是连续加分）
def cont_scoring(p):
    """最佳区间4~5.5%做中心，向两边递减"""
    import math
    center=4.75; width=1.5  # 中心4.75, 半宽1.5
    diff=abs(p-center)
    if diff<=width:
        return 20*(1-diff/width)  # 线性递减
    elif diff<=width+3:
        return 5*(1-(diff-width)/3)  # 继续递减
    elif p<0: return -10
    elif p>=9.8: return -20
    else: return 0

wr,pd_=eval_score(cont_scoring)
print(f"【连续评分(中心4.75)】: {wr:.1f}% ({pd_}天)")

# 方案4: 最优分段（自动搜索）
print(f"\n{'─'*70}")
print("搜索最优分段权重...")
print(f"{'─'*70}")

best={"sc":0}
zones=[(4,5.5),(3.5,5.5),(3,6),(4,6),(3.5,6.5),(3,7)]
for lo,hi in zones:
    for b1 in [30,25,20,15]:
        for b2 in [15,12,10,8,5]:
            for b3 in [8,5,3,0]:
                def fn(p,lo=lo,hi=hi,b1=b1,b2=b2,b3=b3):
                    if lo<=p<=hi: return b1
                    elif lo-2<=p<lo or hi<p<=hi+2: return b2
                    elif 0<=p<lo-2 or hi+2<p<=9.8: return b3
                    elif p<0: return -10
                    else: return -20
                wr,pd_=eval_score(fn)
                sc=wr*2+pd_
                if sc>best["sc"]:
                    best={"sc":sc,"wr":wr,"pd":pd_,"zone":f"{lo}~{hi}","b1":b1,"b2":b2,"b3":b3}

print(f"\n🏆 最优: {best['zone']} 中心{best['b1']}分, 次区{best['b2']}分, 外区{best['b3']}分")
print(f"   胜率: {best['wr']:.1f}% | 出票: {best['pd']}天")

# 最终对比表
print(f"\n{'='*70}")
print("最终对比")
print(f"{'='*70}")
print(f"{'方案':<40} {'胜率':>8} {'出票':>6}")
print("-"*56)
print(f"{'硬过滤 4.0~5.5%':<40} {70.5:>7.1f}% {78:>4}")
print(f"{'硬过滤 4.0~7.5%':<40} {65.5:>7.1f}% {87:>4}")
print(f"{'无涨幅评分(基准)':<40} {wr0:>7.1f}% {pd0:>4}")
print(f"{'方案1(4~5.5%+20)':<40} {wr1:>7.1f}% {pd1:>4}")

for name,wts in weight_tests:
    def fn(p,wts=wts):
        for l,h,v in wts:
            if l<=p<h: return v
        return 0
    wr,pd_=eval_score(fn)
    print(f"{f'评分-{name}':<40} {wr:>7.1f}% {pd_:>4}")

print(f"\n🏆 最优评分方案: {best['zone']} 中心{best['b1']}分")
print(f"   胜率: {best['wr']:.1f}% | 出票: {best['pd']}天")

print(f"\n⏱ {(time.time()-t0)/60:.1f}分")
