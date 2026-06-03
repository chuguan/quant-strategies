#!/usr/bin/env python3
"""分析输家冠军 — 为什么评分给了它们高分"""
import json, os, time
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
def calc_kdj(h,l,c,n=9):
    L=len(c); k=[50.0]*L; d=[50.0]*L; j=[50.0]*L
    if L<n: return k,d,j
    for i in range(n-1,L):
        hh=max(h[i-n+1:i+1]); ll=min(l[i-n+1:i+1])
        rsv=50.0 if hh==ll else (c[i]-ll)/(hh-ll)*100
        if i>n-1: k[i]=2/3*k[i-1]+1/3*rsv; d[i]=2/3*d[i-1]+1/3*k[i]
        j[i]=3*k[i]-2*d[i]
    return k,d,j

print("📡 加载数据..."); t0=time.time()
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
all_codes={}
for fn in all_files:
    fp=os.path.join(CACHE_DIR,fn)
    try:
        with open(fp,'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<80: continue
        if recs[-1]["date"]<"2020": continue
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
        pos20=[None]*len(c); ma5_sl=[None]*len(c)
        for i in range(19,len(c)):
            h20=max(h[i-19:i+1]); l20=min(l[i-19:i+1])
            pos20[i]=(c[i]-l20)/(h20-l20+0.001)*100
        for i in range(4,len(c)):
            if mas[5][i] and mas[5][i-4]: ma5_sl[i]=(mas[5][i]-mas[5][i-4])/mas[5][i-4]*100
        all_codes[code]={"c":c,"h":h,"l":l,"o":o,"v":v,"mas":mas,"dif":dif,"dea":dea,"macd":macd,
                        "pct":pct,"recs":recs,"atr":atr,"k":k,"d":d,"j":j,"pos20":pos20,"ma5_sl":ma5_sl}
    except: pass
print(f"✅ {len(all_codes)}只, {time.time()-t0:.0f}秒")

dates_2025=sorted(set(r["date"] for s in all_codes.values() for r in s["recs"] if r["date"].startswith("2025")))
dates_2026=sorted(set(r["date"] for s in all_codes.values() for r in s["recs"] if r["date"].startswith("2026")))

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

# 收集赢家/输家冠军的特征
winners=[]; losers=[]

for yr_name, dates in [("2025",dates_2025),("2026",dates_2026)]:
    for dt in sorted(dates):
        cand=[]
        for code,sd in all_codes.items():
            try:
                di=None
                for idx,r in enumerate(sd["recs"]):
                    if r["date"]==dt: di=idx; break
                if di is None or di<80: continue
                if not pass_M1(code,sd,di): continue
                
                cl=sd["c"][di]; op=sd["o"][di]; hi=sd["h"][di]; lo=sd["l"][di]; vo=sd["v"][di]
                rng=hi-lo; shadow=(hi-max(cl,op))/(rng+0.001)*100 if rng>0 else 0
                body=abs(cl-op)/op*100
                atr_p=sd["atr"][di]/cl*100 if sd["atr"][di] and cl>0 else 0
                v5=sd["mas"]["v5"][di] if sd["mas"]["v5"][di] else 0
                vr=vo/v5 if v5>0 else 0
                rpos=(cl-lo)/(rng+0.001)*100 if rng>0 else 0
                
                sc=0
                if shadow<30: sc+=max(0,35-shadow*1.2)
                sc+=min(body*3,25)
                sc+=min(atr_p*2,16)
                
                next_h=None
                for j,r2 in enumerate(sd["recs"]):
                    if r2["date"]==dt and j+1<len(sd["recs"]):
                        next_h=round((sd["recs"][j+1]["high"]/cl-1)*100,2); break
                
                cand.append({"code":code,"score":sc,"pct":sd["pct"][di],"next_h":next_h,
                           "shadow":shadow,"body":body,"atr_p":atr_p,"vr":vr,"rpos":rpos,
                           "pos20":sd["pos20"][di],"ma5_sl":sd["ma5_sl"][di],
                           "j":sd["j"][di],"dif":sd["dif"][di]})
            except: continue
        
        if len(cand)>=5:
            cand.sort(key=lambda x:x["score"],reverse=True)
            champ=cand[0]
            win=champ["next_h"] and champ["next_h"]>=2.5
            rec={"year":yr_name,"date":dt,**champ}
            if win: winners.append(rec)
            else: losers.append(rec)

# ═══ 分析 ═══
print(f"\n{'='*80}")
print(f"🔍 输家冠军分析 — {len(winners)}赢家 vs {len(losers)}输家")
print(f"{'='*80}")

# 1. 对比平均值
metrics=[("score","总评分"),("shadow","上影线%"),("body","实体%"),("atr_p","ATR%"),
         ("pct","当日涨幅%"),("vr","量比"),("rpos","收盘位置%"),("pos20","20日位置%"),
         ("ma5_sl","MA5斜率%"),("j","J值"),("dif","DIF值")]

print(f"\n📊 特征对比")
print(f"{'指标':<16} {'赢家均值':>10} {'输家均值':>10} {'差距':>10} {'说明'}")
print("-"*70)
for key,name in metrics:
    w_avg=sum(r[key] or 0 for r in winners)/len(winners)
    l_avg=sum(r[key] or 0 for r in losers)/len(losers)
    diff=w_avg-l_avg
    note=""
    if abs(diff)>1: note="⚠️"
    if abs(diff)>3: note="🔥"
    print(f"{name:<16} {w_avg:>9.2f} {l_avg:>9.2f} {diff:>+9.2f} {note}")

# 2. 输家冠军详细清单
print(f"\n{'='*80}")
print(f"❌ {len(losers)}个输家冠军详细清单")
print(f"{'='*80}")
print(f"{'日期':<12} {'代码':<10} {'评分':>6} {'上影':>6} {'实体':>6} {'ATR':>6} {'涨%':>6} {'量比':>5} {'收盘位':>6} {'次日高':>6}")
print("-"*80)
losers.sort(key=lambda x:x["date"])
for r in losers:
    nh=r["next_h"] if r["next_h"] else 0
    print(f"{r['date']:<12} {r['code']:<10} {r['score']:>6.0f} {r['shadow']:>5.1f}% {r['body']:>5.1f}% "
          f"{r['atr_p']:>5.1f}% {r['pct']:>5.2f}% {r['vr']:>4.1f} {r['rpos']:>5.1f}% {nh:>+5.2f}%")

# 3. 输家中最突出的模式
print(f"\n{'='*80}")
print("🔎 输家冠军的典型模式")
print(f"{'='*80}")

# 输家评分构成分析
print(f"\n📊 输家评分构成（看看哪项虚高了）")
for key,name in [("shadow","上影分"),("body","实体分"),("atr_p","ATR分")]:
    w_avg=sum(((35-r["shadow"]*1.2) if r["shadow"]<30 else 0) for r in winners)/len(winners)
    l_avg=sum(((35-r["shadow"]*1.2) if r["shadow"]<30 else 0) for r in losers)/len(losers)
    print(f"  {name}: 赢家{w_avg:.1f}分 vs 输家{l_avg:.1f}分 (差{w_avg-l_avg:+.1f})")

# 输家共性：高上影+高涨幅 vs 低上影+低涨幅
print(f"\n📊 输家共性分析")
# 看输家里有多少是上影>20%的
hi_shadow=sum(1 for r in losers if r["shadow"]>20)
hi_pct=sum(1 for r in losers if r["pct"]>7)
low_rpos=sum(1 for r in losers if r["rpos"]<60)
extreme_atr=sum(1 for r in losers if r["atr_p"]>8)
print(f"  上影>20%: {hi_shadow}/{len(losers)} = {hi_shadow/len(losers)*100:.0f}%")
print(f"  涨幅>7%: {hi_pct}/{len(losers)} = {hi_pct/len(losers)*100:.0f}%")
print(f"  收盘位<60%: {low_rpos}/{len(losers)} = {low_rpos/len(losers)*100:.0f}%")
print(f"  ATR>8%: {extreme_atr}/{len(losers)} = {extreme_atr/len(losers)*100:.0f}%")

# 找最佳惩罚规则
print(f"\n📊 惩罚规则效果测试")
rules=[
    ("上影>20%扣20分", lambda r: -20 if r["shadow"]>20 else 0),
    ("涨幅>7%扣15分", lambda r: -15 if r["pct"]>7 else 0),
    ("收盘位<60%扣15分", lambda r: -15 if r["rpos"]<60 else 0),
    ("量比<0.8扣10分", lambda r: -10 if r["vr"]<0.8 else 0),
    ("J值>90扣10分", lambda r: -10 if r["j"] and r["j"]>90 else 0),
    ("上影>20% 或 涨幅>7%扣20", lambda r: -20 if (r["shadow"]>20 or r["pct"]>7) else 0),
    ("组合:上影>20%+涨幅>7%扣30", lambda r: -30 if (r["shadow"]>20 and r["pct"]>7) else (-15 if (r["shadow"]>20 or r["pct"]>7) else 0)),
]

for rname, rfn in rules:
    # 测试在输家上的效果
    l_affected=sum(1 for r in losers if rfn(r)!=0)
    w_affected=sum(1 for r in winners if rfn(r)!=0)
    print(f"  {rname:<30}: 输家{l_affected}/{len(losers)} ({l_affected/len(losers)*100:.0f}%) | 误伤赢家{w_affected}/{len(winners)} ({w_affected/len(winners)*100:.0f}%)")

print(f"\n⏱ {time.time()-t0:.0f}秒")
