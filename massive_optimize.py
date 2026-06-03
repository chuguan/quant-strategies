#!/usr/bin/env python3
"""v14在2025+2026全量验证 + 参数网格搜索"""
import json, os, time
from itertools import product

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
print("📡 加载3427只股票…")
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

def pass_M1(code,sd,di):
    if sd["c"][di]>=80: return False
    m=sd["mas"]
    if not (m[5][di] and m[10][di] and m[20][di] and m[60][di] and m[5][di]>m[10][di]>m[20][di]>m[60][di]): return False
    if not (sd["dif"][di] and sd["dea"][di] and sd["dif"][di]>0 and sd["dif"][di]>sd["dea"][di]): return False
    a=sd["atr"][di]; cl=sd["c"][di]
    if not (a and cl>0 and a/cl*100>3): return False
    if not (m[60][di] and cl>m[60][di]): return False
    if sd["c"][di]<=sd["o"][di]: return False
    if not (m[5][di] and cl>m[5][di]): return False
    return True

# 收集候选数据（2025+2026）
print("📝 收集候选数据…")
dates_2025=sorted(set(r["date"] for code,sd in all_codes.items() for r in sd["recs"] if r["date"].startswith("2025")))
dates_2026=sorted(set(r["date"] for code,sd in all_codes.items() for r in sd["recs"] if r["date"].startswith("2026")))
print(f"  2025: {len(dates_2025)}天, 2026: {len(dates_2026)}天")

def collect_candidates(dates):
    """收集M1+阳线+站MA5候选数据"""
    daily={}
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
                pct=sd["pct"][di]; atr_v=sd["atr"][di]
                v5=sd["mas"]["v5"][di] if sd["mas"]["v5"][di] else 0
                vr=vo/v5 if v5>0 else 0
                atr_pct=atr_v/cl*100 if atr_v and cl>0 else 0
                body_pct=abs(cl-op)/op*100
                shadow_pct=(hi-max(cl,op))/(hi-lo+0.001)*100
                rpos=(cl-lo)/(hi-lo+0.001)*100
                ma5_sl=sd["ma5_sl"][di] if sd["ma5_sl"][di] else 0
                pos20=sd["pos20"][di] if sd["pos20"][di] else 0
                
                next_h=None
                for j,r2 in enumerate(sd["recs"]):
                    if r2["date"]==dt and j+1<len(sd["recs"]):
                        next_h=round((sd["recs"][j+1]["high"]/cl-1)*100,2); break
                
                cand.append({"code":code,"pct":pct,"atr_pct":atr_pct,"vr":vr,
                            "body_pct":body_pct,"shadow_pct":shadow_pct,"rpos":rpos,
                            "ma5_sl":ma5_sl,"pos20":pos20,"next_h":next_h})
            except: continue
        if len(cand)>=10:
            daily[dt]=cand
    return daily

cand_2025=collect_candidates(dates_2025)
cand_2026=collect_candidates(dates_2026)
print(f"  2025: {len(cand_2025)}天出票, 2026: {len(cand_2026)}天出票")
print(f"  ⏱ {time.time()-t0:.0f}秒")

# ═══ 阶段1: top方案在2025+2026上验证 ═══
print(f"\n{'='*90}")
print("阶段1: TOP方案跨年验证（看看是不是过拟合）")
print(f"{'='*90}")

# 定义top方案（含v14变种）
schemes = {
    "v14(原版)": lambda d: (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0
                  + min(d["body_pct"]*3,25) + d["rpos"]*0.15 + min(d["atr_pct"],8)*2),
    "v14-1 (上影权重加大)": lambda d: (max(0,40-d["shadow_pct"]*1.5) if d["shadow_pct"]<27 else 0
                  + min(d["body_pct"]*3,25) + d["rpos"]*0.15 + min(d["atr_pct"],8)*2),
    "v14-2 (实体权重加大)": lambda d: (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0
                  + min(d["body_pct"]*4,30) + d["rpos"]*0.15 + min(d["atr_pct"],8)*1.5),
    "v14-3 (加入涨幅)": lambda d: max(0,d["pct"])*1.5 + (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0
                  + min(d["body_pct"]*3,25) + d["rpos"]*0.1 + min(d["atr_pct"],7)*2),
    "v14-4 (ATR加大)": lambda d: (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0
                  + min(d["body_pct"]*2.5,20) + d["rpos"]*0.2 + min(d["atr_pct"],8)*3),
    "v14-5 (纯上影+实体)": lambda d: (max(0,40-d["shadow_pct"]*1.5) if d["shadow_pct"]<27 else 0
                  + min(d["body_pct"]*4,30)),
    "v10(三因子)": lambda d: max(0,d["pct"])*3 + (25 if d["shadow_pct"]<12 else 5) + min(d["ma5_sl"]*2,20),
    "v1(原版)": lambda d: d["atr_pct"]*2 + (10 if d["pct"]>0 else 0)
                  + (25 if 1<d["vr"]<2 else 8 if d["vr"]>2 else 0) + d["pos20"]*0.2 + (10 if d["j"]>50 else 0),
}

# 注意: v1需要j值，但当前数据没传j...这里先跳过
del schemes["v1(原版)"]

print(f"\n{'方案':<32} {'2025胜率':>10} {'2025天':>8} {'2026胜率':>10} {'2026天':>8} {'平均':>8}")
print("-"*76)

for name, scorer in schemes.items():
    res={}
    for yr_name, cand in [("2025", cand_2025), ("2026", cand_2026)]:
        wins=0; total=0
        for dt, cds in cand.items():
            if not cds: continue
            ranked=sorted(cds, key=scorer, reverse=True)
            champ=ranked[0]
            total+=1
            if champ["next_h"] and champ["next_h"]>=2.5: wins+=1
        res[yr_name]=(wins/total*100 if total else 0, total)
    
    avg=round((res["2025"][0]+res["2026"][0])/2,1)
    short_name = name[:30]
    print(f"{short_name:<32} {res['2025'][0]:>6.1f}% {res['2025'][1]:>5}天 {res['2026'][0]:>6.1f}% {res['2026'][1]:>5}天 {avg:>5.1f}%")

# ═══ 阶段2: 网格搜索 ═══
print(f"\n{'='*90}")
print("阶段2: 参数网格搜索（在2025数据上训练）")
print(f"{'='*90}")

# 定义搜索网格
# 公式: score = shadow_bonus + body_bonus + rpos_bonus + atr_bonus + [pct_bonus]
# shadow_bonus = max(0, SHADOW_A - shadow_pct * SHADOW_B) if shadow_pct < SHADOW_C else 0
# body_bonus = min(body_pct * BODY_W, BODY_CAP)
# atr_bonus = min(atr_pct * ATR_W, ATR_CAP)
# rpos_bonus = rpos * RPOS_W
# pct_bonus = max(0, pct) * PCT_W (optional)

shadow_params = [
    ("上影A30-B1.0-C30", 30, 1.0, 30),
    ("上影A35-B1.0-C30", 35, 1.0, 30),
    ("上影A35-B1.2-C30", 35, 1.2, 30),
    ("上影A35-B1.5-C27", 35, 1.5, 27),
    ("上影A40-B1.2-C30", 40, 1.2, 30),
    ("上影A40-B1.5-C27", 40, 1.5, 27),
    ("上影A45-B1.5-C25", 45, 1.5, 25),
    ("上影A45-B2.0-C23", 45, 2.0, 23),
    ("上影A50-B2.0-C20", 50, 2.0, 20),
]
body_w = [2, 2.5, 3, 3.5, 4, 5]
body_cap = [20, 25, 30]
atr_w = [1.5, 2, 2.5, 3]
atr_cap = [12, 16, 20]
rpos_w = [0, 0.1, 0.15, 0.2]
pct_w = [0, 1, 1.5, 2]

# 限制搜索总量（避免爆炸）
total_combos = len(shadow_params)*len(body_w)*len(body_cap)*len(atr_w)*len(atr_cap)*len(rpos_w)*len(pct_w)
print(f"  总组合数: {len(shadow_params)}×{len(body_w)}×{len(body_cap)}×{len(atr_w)}×{len(atr_cap)}×{len(rpos_w)}×{len(pct_w)} = {total_combos:,}")
if total_combos > 2000:
    # 减少搜索空间
    body_w = [2, 3, 4]
    body_cap = [20, 25]
    atr_w = [2, 2.5, 3]
    atr_cap = [16]
    pct_w = [0, 1, 2]
    total_combos = len(shadow_params)*len(body_w)*len(body_cap)*len(atr_w)*len(atr_cap)*len(rpos_w)*len(pct_w)
    print(f"  缩减至: {total_combos:,}种组合")

print(f"  在2025上训练（{len(cand_2025)}天），2026验证（{len(cand_2026)}天）")
print(f"\n{'搜索进度':<30}", end="", flush=True)

grid_results = []
combo_cnt=0
best_2025_wr=0

for (sname, sa, sb, sc), bw, bcap, aw, acap, rw, pw in product(
    shadow_params, body_w, body_cap, atr_w, atr_cap, rpos_w, pct_w):
    
    combo_cnt+=1
    if combo_cnt%50==0:
        print(f"▌", end="", flush=True)
    
    def make_scorer(sa=sa, sb=sb, sc=sc, bw=bw, bcap=bcap, aw=aw, acap=acap, rw=rw, pw=pw):
        return lambda d: (max(0, sa - d["shadow_pct"]*sb) if d["shadow_pct"]<sc else 0) \
               + min(d["body_pct"]*bw, bcap) \
               + min(d["atr_pct"]*aw, acap) \
               + d["rpos"]*rw \
               + max(0, d["pct"])*pw
    
    scorer=make_scorer()
    
    # 在2025上测试
    wins25=0; total25=0
    for dt, cds in cand_2025.items():
        if not cds: continue
        champ=sorted(cds, key=scorer, reverse=True)[0]
        total25+=1
        if champ["next_h"] and champ["next_h"]>=2.5: wins25+=1
    wr25=wins25/total25*100 if total25 else 0
    
    # 在2026上验证
    wins26=0; total26=0
    for dt, cds in cand_2026.items():
        if not cds: continue
        champ=sorted(cds, key=scorer, reverse=True)[0]
        total26+=1
        if champ["next_h"] and champ["next_h"]>=2.5: wins26+=1
    wr26=wins26/total26*100 if total26 else 0
    
    grid_results.append((wr25, wr26, sname, bw, bcap, aw, acap, rw, pw))

print(f"\n\n🏆 2025 TOP5（在2025上表现最好）")
print(f"{'上影参数':<18} {'实体W':>5} {'上限':>5} {'ATRW':>5} {'上限':>5} {'收盘W':>5} {'涨W':>4} {'2025':>8} {'2026':>8}")
print("-"*70)
for wr25, wr26, sname, bw, bcap, aw, acap, rw, pw in sorted(grid_results, reverse=True)[:5]:
    print(f"{sname:<18} {bw:>5.0f} {bcap:>5.0f} {aw:>5.1f} {acap:>5.0f} {rw:>5.2f} {pw:>4.0f} {wr25:>6.1f}% {wr26:>6.1f}%")

# 找跨年最稳定的
print(f"\n🏆 跨年最稳定（2025+2026平均最高）")
stable=sorted(grid_results, key=lambda x: (x[0]+x[1])/2, reverse=True)[:5]
print(f"{'上影参数':<18} {'实体W':>5} {'上限':>5} {'ATRW':>5} {'上限':>5} {'收盘W':>5} {'涨W':>4} {'2025':>8} {'2026':>8} {'平均':>8}")
print("-"*80)
for wr25, wr26, sname, bw, bcap, aw, acap, rw, pw in stable:
    avg=(wr25+wr26)/2
    diff=abs(wr25-wr26)
    mark="🔥" if avg>=75 and diff<=5 else ("✅" if avg>=70 else "")
    print(f"{sname:<18} {bw:>5.0f} {bcap:>5.0f} {aw:>5.1f} {acap:>5.0f} {rw:>5.2f} {pw:>4.0f} {wr25:>6.1f}% {wr26:>6.1f}% {avg:>5.1f}% {mark}")

print(f"\n⏱总用时: {time.time()-t0:.0f}秒")
