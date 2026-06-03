#!/usr/bin/env python3
"""赢家vs输家特征分析 — M1+阳线+站MA5 候选池中，胜者有何特征？"""
import json, os
from collections import defaultdict, Counter

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

all_codes={}; loaded=0
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
        # 位置
        pos20=[None]*len(c); pos60=[None]*len(c)
        for i in range(19,len(c)):
            h20=max(h[i-19:i+1]); l20=min(l[i-19:i+1])
            pos20[i]=(c[i]-l20)/(h20-l20+0.001)*100
        for i in range(59,len(c)):
            h60=max(h[i-59:i+1]); l60=min(l[i-59:i+1])
            pos60[i]=(c[i]-l60)/(h60-l60+0.001)*100
        # MA5斜率
        ma5_sl=[None]*len(c)
        for i in range(4,len(c)):
            if mas[5][i] and mas[5][i-4]: ma5_sl[i]=(mas[5][i]-mas[5][i-4])/mas[5][i-4]*100
        all_codes[code]={"c":c,"o":o,"h":h,"l":l,"v":v,"mas":mas,"dif":dif,"dea":dea,"macd":macd,"pct":pct,"recs":recs,"atr":atr,"k":k,"d":d,"j":j,"pos20":pos20,"pos60":pos60,"ma5_sl":ma5_sl}
        loaded+=1
        if loaded%500==0: print(f"  {loaded}/{len(main_files)}")
    except: pass
print(f"✅ {loaded}只")

dates_2026=sorted(set(r["date"] for code,sd in all_codes.items() for r in sd["recs"] if r["date"].startswith("2026")))

# ═══ 收集 M1+阳线+站MA5 候选的全部数据 ═══
print("\n📝 收集候选池数据（M1+阳线+站MA5 + 各种涨幅范围）...")

# M1条件
def pass_M1(code,sd,di):
    if sd["c"][di]>=80: return False
    m=sd["mas"]
    if not (m[5][di] and m[10][di] and m[20][di] and m[60][di] and m[5][di]>m[10][di]>m[20][di]>m[60][di]): return False
    if not (sd["dif"][di] and sd["dea"][di] and sd["dif"][di]>0 and sd["dif"][di]>sd["dea"][di]): return False
    a=sd["atr"][di]; cl=sd["c"][di]
    if not (a and cl>0 and a/cl*100>3): return False
    if not (m[60][di] and cl>m[60][di]): return False
    # 阳线
    if sd["c"][di]<=sd["o"][di]: return False
    # 站MA5
    if not (m[5][di] and cl>m[5][di]): return False
    return True

# 收集
winners=[]; losers=[]  # 各存特征dict

for code,sd in all_codes.items():
    recs=sd["recs"]
    for i in range(80,len(recs)-1):
        dt=recs[i]["date"]
        if not dt.startswith("2026"): continue
        cl=sd["c"][i]; pct=sd["pct"][i]
        if not pass_M1(code,sd,i): continue
        
        # 次日高
        nh=(recs[i+1]["high"]/cl-1)*100
        is_win=nh>=2.5
        
        m=sd["mas"]; cl=sd["c"][i]; op=sd["o"][i]; hi=sd["h"][i]; lo=sd["l"][i]; vo=sd["v"][i]
        a=sd["atr"][i]; k=sd["k"][i]; d=sd["d"][i]; jv=sd["j"][i]
        pos20=sd["pos20"][i]; pos60=sd["pos60"][i]; ma5_sl=sd["ma5_sl"][i]
        v5=m["v5"][i] if m["v5"][i] else 0
        vr=vo/v5 if v5>0 else 0
        atr_pct=a/cl*100 if a and cl>0 else 0
        body_pct=abs(cl-op)/op*100
        shadow_pct=(hi-max(cl,op))/(hi-lo+0.001)*100  # 上影线比例
        rpos=(cl-lo)/(hi-lo+0.001)*100  # 收盘位置
        
        feat={"code":code,"date":dt,"pct":pct,"nh":nh,"win":is_win,
              "vr":vr,"atr_pct":atr_pct,"body_pct":body_pct,
              "pos20":pos20,"pos60":pos60,"ma5_sl":ma5_sl,
              "shadow_pct":shadow_pct,"rpos":rpos,
              "j":jv,"k":k,"d":d,
              "macd_val":sd["macd"][i] if sd["macd"][i] else 0,
              "dif_val":sd["dif"][i] if sd["dif"][i] else 0}
        
        if is_win: winners.append(feat)
        else: losers.append(feat)

total=len(winners)+len(losers)
print(f"\n✅ 共{total}条候选记录: 赢家{len(winners)}({len(winners)/total*100:.1f}%), 输家{len(losers)}({len(losers)/total*100:.1f}%)")

# ═══ ═══ ═══ 核心分析 ═══ ═══ ═══
print(f"\n{'='*80}")
print("🔍 赢家 vs 输家 特征对比")
print(f"{'='*80}")

metrics=[
    ("pct","当日涨幅%"),
    ("vr","量比"),
    ("atr_pct","ATR波动率%"),
    ("body_pct","阳线实体%"),
    ("pos20","20日位置%"),
    ("pos60","60日位置%"),
    ("ma5_sl","MA5斜率%"),
    ("shadow_pct","上影线占比%"),
    ("rpos","日内收盘位置%"),
    ("j","KDJ-J值"),
    ("dif_val","DIF值"),
]

def calc_avg(lst, k):
    vals=[f[k] for f in lst if f[k] is not None]
    return sum(vals)/len(vals) if vals else 0

def calc_med(lst, k):
    vals=sorted([f[k] for f in lst if f[k] is not None])
    return vals[len(vals)//2] if vals else 0

print(f"\n{'指标':<16} {'赢家均值':>10} {'输家均值':>10} {'差':>10}")
print("-"*46)
for key,name in metrics:
    wa=calc_avg(winners,key); la=calc_avg(losers,key); diff=wa-la
    print(f"{name:<16} {wa:>9.2f} {la:>9.2f} {diff:>+9.2f}")

# ═══ 各指标的区分度分析（找最佳阈值）═══
print(f"\n{'='*80}")
print("🔎 逐个指标找最佳过滤阈值（目标：提高胜率，砍掉输家）")
print(f"{'='*80}")

all_data=winners+losers

def find_best_threshold(data, key, ranges, min_count=5):
    """在候选数据中，找最好（或最差）的阈值区间"""
    best_th=("",0,0,0)  # (条件, 区间内胜率, 区间外胜率, 区间内样本数)
    worst_th=("",0,0,0)
    vals=[d[key] for d in data if d[key] is not None]
    if not vals: return None
    
    for lo,hi,label in ranges:
        inside=[d for d in data if d[key] is not None and lo<=d[key]<=hi]
        outside=[d for d in data if d[key] is not None and (d[key]<lo or d[key]>hi)]
        if len(inside)<min_count: continue
        ins_win=sum(1 for d in inside if d["win"])/len(inside)*100
        out_win=sum(1 for d in outside if d["win"])/len(outside)*100 if outside else 0
        if ins_win>best_th[1]: best_th=(label,ins_win,out_win,len(inside))
        if ins_win<worst_th[1] or worst_th[1]==0: 
            worst_th=(label,ins_win,out_win,len(inside))
    return best_th, worst_th

# 各指标的最佳/最差区间
threshold_tests=[
    ("当日涨幅%", "pct", [(0,1,"涨0~1%"),
                          (1,2,"涨1~2%"), (2,3,"涨2~3%"),
                          (3,4,"涨3~4%"), (4,5,"涨4~5%"),
                          (5,6,"涨5~6%"), (6,7,"涨6~7%"),
                          (7,8,"涨7~8%"), (8,10,"涨8~10%"),
                          (0,4,"涨0~4%"), (4,6,"涨4~6%"),
                          (6,10,"涨6~10%")]),
    ("量比", "vr", [(0,1,"量比<1"), (1,1.5,"量比1~1.5"),
                    (1.5,2,"量比1.5~2"), (2,3,"量比2~3"),
                    (3,5,"量比3~5"), (5,10,"量比5~10"),
                    (1,2,"量比1~2"), (1,3,"量比1~3")]),
    ("阳线实体%", "body_pct", [(0,1,"实体<1%"), (1,2,"实体1~2%"),
                               (2,3,"实体2~3%"), (3,5,"实体3~5%"),
                               (5,10,"实体5~10%"), (1,3,"实体1~3%"),
                               (0,1.5,"实体<1.5%"), (1.5,3,"实体1.5~3%")]),
    ("20日位置%", "pos20", [(0,30,"低位<30%"), (30,50,"中低位30~50%"),
                            (50,70,"中高位50~70%"), (70,100,"高位70~100%"),
                            (30,60,"30~60%"), (40,60,"40~60%")]),
    ("MA5斜率%", "ma5_sl", [(0,4,"斜率0~4"), (4,8,"斜率4~8"),
                             (8,12,"斜率8~12"), (12,20,"斜率12~20"),
                             (0,8,"斜率0~8"), (8,20,"斜率8~20")]),
    ("上影线比%", "shadow_pct", [(0,10,"上影<10%"), (10,20,"上影10~20%"),
                                (20,30,"上影20~30%"), (30,50,"上影30~50%"),
                                (50,100,"上影>50%"), (0,15,"上影<15%"),
                                (15,30,"上影15~30%")]),
    ("KDJ-J值", "j", [(0,20,"J<20"), (20,50,"J20~50"),
                      (50,70,"J50~70"), (70,90,"J70~90"),
                      (90,120,"J>90"), (50,80,"J50~80"),
                      (20,80,"J20~80"), (80,120,"J>80")]),
    ("量比+涨幅组合", None, None),  # 特殊处理
]

for name, key, ranges in threshold_tests:
    if key is None: continue
    res=find_best_threshold(all_data,key,ranges)
    if res is None: continue
    best,worst=res
    print(f"\n📊 {name}")
    print(f"  🔥 最佳区间: {best[0]} → 区间胜率{best[1]:.1f}%, 外部胜率{best[2]:.1f}%, 样本{best[3]}条")
    print(f"  ❌ 最差区间: {worst[0]} → 区间胜率{worst[1]:.1f}%, 样本{worst[3]}条")

# ═══ 量比 × 涨幅 交叉分析 ═══
print(f"\n{'='*80}")
print("🔎 量比 × 涨幅 交叉分析")
print(f"{'='*80}")
vr_ranges=[(0,1,"<1"),(1,1.5,"1~1.5"),(1.5,2,"1.5~2"),(2,3,"2~3"),(3,10,">3")]
pct_ranges=[(0,3,"0~3%"),(3,4,"3~4%"),(4,5,"4~5%"),(5,6,"5~6%"),(6,8,"6~8%"),(8,10,"8~10%")]
print("\n",end=""); print(f"{'量比/涨幅':<12}",end="")
for pl,ph,pn in pct_ranges:
    print(f"{pn:>10}",end="")
print(f"{'合计':>10}")

for vl,vh,vn in vr_ranges:
    print(f"{vn:<12}",end="")
    row_total=0; row_win=0
    for pl,ph,pn in pct_ranges:
        cells=[d for d in all_data if d["vr"] and vl<=d["vr"]<=vh and d["pct"] and pl<=d["pct"]<=ph]
        if cells:
            wr=sum(1 for c in cells if c["win"])/len(cells)*100
            print(f"{wr:>6.1f}%({len(cells):>3})",end=" ")
        else:
            print(f"{' -':>10}",end=" ")
        row_total+=len(cells); row_win+=sum(1 for c in cells if c["win"])
    row_wr=row_win/row_total*100 if row_total else 0
    print("{:>5.1f}%({:>3})".format(row_wr,row_total))
print()

# ═══ 最佳复合过滤条件组合 ═══
print(f"\n{'='*80}")
print("🔥 复合条件过滤（多个条件叠在一起）")
print(f"{'='*80}")

# 基于上面分析，构建逐步过滤
from itertools import combinations

# 定义候选过滤规则
filters_def = {
    "涨幅4~5%": lambda d: d["pct"] and 4<=d["pct"]<=5,
    "涨幅4~6%": lambda d: d["pct"] and 4<=d["pct"]<=6,
    "涨幅3~5%": lambda d: d["pct"] and 3<=d["pct"]<=5,
    "量比1~2": lambda d: d["vr"] and 1<=d["vr"]<=2,
    "量比1~1.5": lambda d: d["vr"] and 1<=d["vr"]<=1.5,
    "量比1.5~2": lambda d: d["vr"] and 1.5<=d["vr"]<=2,
    "上影<15%": lambda d: d["shadow_pct"] is not None and d["shadow_pct"]<15,
    "上影<20%": lambda d: d["shadow_pct"] is not None and d["shadow_pct"]<20,
    "MA5斜>4": lambda d: d["ma5_sl"] is not None and d["ma5_sl"]>4,
    "MA5斜4~12": lambda d: d["ma5_sl"] and 4<=d["ma5_sl"]<=12,
    "bod>1.5%": lambda d: d["body_pct"] and d["body_pct"]>1.5,
    "bod>2%": lambda d: d["body_pct"] and d["body_pct"]>2,
    "J50~80": lambda d: d["j"] and 50<=d["j"]<=80,
    "J50~90": lambda d: d["j"] and 50<=d["j"]<=90,
    "位40~70": lambda d: d["pos20"] and 40<=d["pos20"]<=70,
    "位30~60": lambda d: d["pos20"] and 30<=d["pos20"]<=60,
    "ATR>4%": lambda d: d["atr_pct"] and d["atr_pct"]>4,
}

# 测试已有优势区间
base_conditions = [
    ("无额外过滤（M1+阳线+站MA5基线）", []),
    ("+涨幅4~5%", ["涨幅4~5%"]),
    ("+涨幅4~6%", ["涨幅4~6%"]),
    ("+涨幅4~5%+量比1~2", ["涨幅4~5%","量比1~2"]),
    ("+涨幅4~5%+量比1~1.5", ["涨幅4~5%","量比1~1.5"]),
    ("+涨幅4~6%+量比1~2", ["涨幅4~6%","量比1~2"]),
    ("+涨幅4~5%+上影<15%", ["涨幅4~5%","上影<15%"]),
    ("+涨幅4~5%+MA5斜4~12", ["涨幅4~5%","MA5斜4~12"]),
    ("+涨幅4~5%+J50~80", ["涨幅4~5%","J50~80"]),
    ("+涨幅4~5%+bod>1.5%", ["涨幅4~5%","bod>1.5%"]),
    ("+涨幅4~5%+量比1~2+上影<15%", ["涨幅4~5%","量比1~2","上影<15%"]),
    ("+涨幅4~5%+量比1~2+MA5斜4~12", ["涨幅4~5%","量比1~2","MA5斜4~12"]),
    ("+涨幅4~5%+量比1~2+bod>1.5%", ["涨幅4~5%","量比1~2","bod>1.5%"]),
    ("+涨幅4~5%+量比1~2+J50~80", ["涨幅4~5%","量比1~2","J50~80"]),
    ("+涨幅4~5%+量比1~1.5+上影<15%", ["涨幅4~5%","量比1~1.5","上影<15%"]),
    # 超严格
    ("+涨幅4~5%+量比1~2+MA5斜>4+bod>1.5%", ["涨幅4~5%","量比1~2","MA5斜>4","bod>1.5%"]),
    ("+涨幅4~5%+量比1~2+J50~80+上影<15%", ["涨幅4~5%","量比1~2","J50~80","上影<15%"]),
]

print(f"\n{'复合条件':<42} {'胜率':>8} {'总数':>8} {'输家':>8} {'每日均':>8}")
print("-"*74)
for name, filters in base_conditions:
    filtered=[d for d in all_data if all(filters_def[f](d) for f in filters)]
    if not filtered: continue
    win_cnt=sum(1 for d in filtered if d["win"])
    los_cnt=len(filtered)-win_cnt
    wr=win_cnt/len(filtered)*100
    # 日均候选（按交易日）
    dates_set=set(d["date"] for d in filtered)
    per_day=len(filtered)/max(len(dates_2026),1)
    mark="🔥" if wr>=70 else ("✅" if wr>=65 else "")
    print(f"{name:<42} {wr:>6.1f}% {len(filtered):>6} {los_cnt:>6} {per_day:>5.1f} {mark}")
