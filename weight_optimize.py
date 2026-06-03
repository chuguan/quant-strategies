#!/usr/bin/env python3
"""评分权重优化 — 多版本测试不同权重组合，找出最佳冠军胜率"""
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
        pos20=[None]*len(c); ma5_sl=[None]*len(c)
        for i in range(19,len(c)):
            h20=max(h[i-19:i+1]); l20=min(l[i-19:i+1])
            pos20[i]=(c[i]-l20)/(h20-l20+0.001)*100
        for i in range(4,len(c)):
            if mas[5][i] and mas[5][i-4]: ma5_sl[i]=(mas[5][i]-mas[5][i-4])/mas[5][i-4]*100
                
        all_codes[code]={"c":c,"o":o,"h":h,"l":l,"v":v,"mas":mas,"dif":dif,"dea":dea,"macd":macd,"pct":pct,"recs":recs,"atr":atr,"k":k,"d":d,"j":j,"pos20":pos20,"ma5_sl":ma5_sl}
    except: pass

dates_2026=sorted(set(r["date"] for code,sd in all_codes.items() for r in sd["recs"] if r["date"].startswith("2026")))

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

# ── 预收集所有候选数据 ──
print("📝 收集候选数据...")
daily_candidates = {}  # date -> [(code, features, next_h), ...]

for dt in sorted(dates_2026):
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
            j_v=sd["j"][di] if sd["j"][di] else 0
            pos20=sd["pos20"][di] if sd["pos20"][di] else 0
            
            next_h=None
            for j,r2 in enumerate(sd["recs"]):
                if r2["date"]==dt and j+1<len(sd["recs"]):
                    next_h=round((sd["recs"][j+1]["high"]/cl-1)*100,2); break
            
            cand.append({"code":code,"pct":pct,"atr_pct":atr_pct,"vr":vr,
                        "body_pct":body_pct,"shadow_pct":shadow_pct,"rpos":rpos,
                        "ma5_sl":ma5_sl,"j":j_v,"pos20":pos20,"next_h":next_h})
        except: continue
    
    if len(cand)>=10:
        daily_candidates[dt] = cand

print(f"✅ {len(daily_candidates)}天有10+候选")

# ── 定义各种评分方案 ──
# 每个方案: (名称, 权重因子列表)
# 权重因子: (名称, 函数(cand_data)->分值)

scoring_schemes = []

# ====== 方案1: 原始v1（当前在用）======
def score_v1(d):
    sc=d["atr_pct"]*2
    if d["pct"]>0: sc+=10
    if 1<d["vr"]<2: sc+=25
    elif d["vr"]>2: sc+=8
    sc+=d["pos20"]*0.2
    if d["j"]>50: sc+=10
    return sc
scoring_schemes.append(("v1(原版) ATRe2 + 涨+10 + VR1~2+25 + pos×0.2 + J>50+10", score_v1))

# ====== 方案2: 涨跌幅加权版 ======
def score_v2(d):
    # 涨幅越高分越高，但不奖励涨停
    pct_bonus = max(0, d["pct"]) * 3
    # 量比1~1.5最好
    vr_bonus = 20 if 1<=d["vr"]<=1.5 else (10 if 1.5<d["vr"]<=2.5 else 0)
    # 上影线越短越好
    shadow_bonus = 20 if d["shadow_pct"]<10 else (10 if d["shadow_pct"]<20 else 0)
    # MA5斜率加分
    ma5_bonus = max(0, min(d["ma5_sl"]*1.5, 25))
    # ATR加分
    atr_bonus = d["atr_pct"]*1.5
    return pct_bonus + vr_bonus + shadow_bonus + ma5_bonus + atr_bonus
scoring_schemes.append(("v2 涨×3 + VR1~1.5+20 + 上影<10+20 + MA5×1.5", score_v2))

# ====== 方案3: 实体+收盘位置版 ======
def score_v3(d):
    body_ok = d["pct"]>0
    # 实体大加分
    body_bonus = min(d["body_pct"]*3, 25) if body_ok else 0
    # 收盘位置高
    rpos_bonus = d["rpos"]*0.2
    # 上影线惩罚
    shadow_penalty = -d["shadow_pct"]*0.3
    # 量比
    vr_bonus = 15 if 1<=d["vr"]<=2 else 0
    # ATR
    atr_bonus = d["atr_pct"]*2
    # J值范围加分
    j_bonus = 10 if 50<=d["j"]<=80 else (5 if d["j"]>80 else 0)
    return body_bonus + rpos_bonus + shadow_penalty + vr_bonus + atr_bonus + j_bonus
scoring_schemes.append(("v3 实体×3 + 收盘位×0.2 - 上影×0.3 + ATR×2 + J50~80+10", score_v3))

# ====== 方案4: 综合全面版 ======
def score_v4(d):
    pct_bonus = max(0, d["pct"]) * 2.5
    atr_bonus = d["atr_pct"] * 2
    vr_bonus = 20 if 1<=d["vr"]<=1.5 else (10 if 1.5<d["vr"]<=2 else 5 if d["vr"]<=3 else 0)
    body_bonus = min(d["body_pct"]*2, 20)
    shadow_penalty = -max(0, d["shadow_pct"]-10)*0.5
    ma5_bonus = min(d["ma5_sl"], 15)
    pos_bonus = d["pos20"]*0.1
    j_bonus = 10 if 50<=d["j"]<=85 else 0
    return pct_bonus + atr_bonus + vr_bonus + body_bonus + shadow_penalty + ma5_bonus + pos_bonus + j_bonus
scoring_schemes.append(("v4(综合) 涨×2.5 + ATR×2 + VR1~1.5+20 + 实体×2 - 上影罚 + MA5", score_v4))

# ====== 方案5: 上影线主导版 ======
def score_v5(d):
    # 上影线是第一优先级
    if d["shadow_pct"] < 8: shadow_bonus = 35
    elif d["shadow_pct"] < 15: shadow_bonus = 20
    elif d["shadow_pct"] < 25: shadow_bonus = 5
    else: shadow_bonus = -15
    
    pct_bonus = max(0, d["pct"]) * 2
    vr_bonus = 15 if 1<=d["vr"]<=1.5 else (8 if 1.5<d["vr"]<=3 else 0)
    atr_bonus = d["atr_pct"] * 1.5
    pos_bonus = d["pos20"] * 0.15
    return shadow_bonus + pct_bonus + vr_bonus + atr_bonus + pos_bonus
scoring_schemes.append(("v5 上影<8+35/<15+20/<25+5/>25-15 + 涨×2 + VR", score_v5))

# ====== 方案6: MA5斜率主导版 ======
def score_v6(d):
    ma5_bonus = min(d["ma5_sl"]*2, 30)
    pct_bonus = max(0, d["pct"]) * 2
    vr_bonus = 15 if 1<=d["vr"]<=2 else 0
    body_bonus = min(d["body_pct"], 15)
    atr_bonus = d["atr_pct"] * 1.5
    if d["shadow_pct"]<15: shadow_bonus = 10
    elif d["shadow_pct"]>30: shadow_bonus = -10
    else: shadow_bonus = 0
    return ma5_bonus + pct_bonus + vr_bonus + body_bonus + atr_bonus + shadow_bonus
scoring_schemes.append(("v6 MA5×2(≤30) + 涨×2 + 实体≤15 + 上影条", score_v6))

# ====== 方案7: ATR波动主导版 ======
def score_v7(d):
    atr_bonus = max(0, (d["atr_pct"]-3)*5)  # 超过3%越多分越高
    pct_bonus = max(0, d["pct"]) * 2.5
    vr_bonus = 20 if 1<=d["vr"]<=1.5 else 0
    shadow_bonus = 15 if d["shadow_pct"]<15 else (5 if d["shadow_pct"]<25 else -5)
    rpos_bonus = (d["rpos"]-50)*0.3
    return atr_bonus + pct_bonus + vr_bonus + shadow_bonus + rpos_bonus
scoring_schemes.append(("v7 ATR(>3)×5 + 涨×2.5 + VR1~1.5+20 + 上影<15+15", score_v7))

# ====== 方案8: 极简版 ======
def score_v8(d):
    # 只用3个关键指标
    pct_bonus = max(0, d["pct"]) * 4
    shadow_bonus = 25 if d["shadow_pct"]<10 else (10 if d["shadow_pct"]<20 else 0)
    vr_bonus = 15 if 1<=d["vr"]<=1.5 else 0
    return pct_bonus + shadow_bonus + vr_bonus
scoring_schemes.append(("v8(极简) 涨×4 + 上影<10+25 + VR1~1.5+15", score_v8))

# ====== 方案9: 双因子版(涨幅+上影) ======
def score_v9(d):
    pct_bonus = max(0, d["pct"]) * 5
    shadow_bonus = 30 if d["shadow_pct"]<8 else (20 if d["shadow_pct"]<15 else 5 if d["shadow_pct"]<25 else -10)
    return pct_bonus + shadow_bonus
scoring_schemes.append(("v9(双因子) 涨×5 + 上影<8+30/<15+20/<25+5", score_v9))

# ====== 方案10: 三因子版 ======
def score_v10(d):
    pct_bonus = max(0, d["pct"]) * 3
    shadow_bonus = 25 if d["shadow_pct"]<12 else 5
    ma5_bonus = min(d["ma5_sl"]*2, 20)
    return pct_bonus + shadow_bonus + ma5_bonus
scoring_schemes.append(("v10(三因子) 涨×3 + 上影<12+25 + MA5×2(≤20)", score_v10))

# ====== 方案11: 实体+收盘位置+上影 ======
def score_v11(d):
    body_bonus = min(d["body_pct"]*4, 30)
    rpos_bonus = max(0, d["rpos"]-60)*0.5
    shadow_penalty = -max(0, d["shadow_pct"]-12)*0.8
    vr_bonus = 15 if 1<=d["vr"]<=1.5 else 0
    return body_bonus + rpos_bonus + shadow_penalty + vr_bonus
scoring_schemes.append(("v11 实体×4(≤30) + 收盘位>60×0.5 - 上影罚", score_v11))

# ====== 方案12: 完全新权重 ======
def score_v12(d):
    pct_bonus = max(0, d["pct"]) * 3.5
    atr_bonus = d["atr_pct"] * 1.2
    vr_bonus = 18 if 1<=d["vr"]<=1.5 else (8 if 1.5<d["vr"]<=2.5 else 0)
    if d["shadow_pct"]<10: shadow_bonus = 22
    elif d["shadow_pct"]<18: shadow_bonus = 10
    elif d["shadow_pct"]<30: shadow_bonus = 0
    else: shadow_bonus = -12
    ma5_bonus = min(d["ma5_sl"], 15) * 1.2
    body_bonus = min(d["body_pct"], 10) * 1.5
    return pct_bonus + atr_bonus + vr_bonus + shadow_bonus + ma5_bonus + body_bonus
scoring_schemes.append(("v12 涨×3.5 + ATR×1.2 + VR1~1.5+18 + 上影条", score_v12))

# ====== 方案13: 涨幅分区加权 ======
def score_v13(d):
    pct = d["pct"]
    if 4<=pct<=5.5: pct_bonus = 35  # 最优区间
    elif 3<=pct<4: pct_bonus = 25
    elif 5.5<pct<=7: pct_bonus = 28
    elif 2<=pct<3: pct_bonus = 15
    elif 7<pct<=10: pct_bonus = 20
    elif 0<pct<2: pct_bonus = 8
    else: pct_bonus = 0
    
    vr_bonus = 20 if 1<=d["vr"]<=1.5 else (10 if 0.7<=d["vr"]<1 else 5)
    shadow_bonus = 20 if d["shadow_pct"]<10 else (10 if d["shadow_pct"]<20 else 0)
    atr_bonus = d["atr_pct"] * 1.5
    return pct_bonus + vr_bonus + shadow_bonus + atr_bonus
scoring_schemes.append(("v13(涨幅分区) 4~5.5+35/7~10+20 + VR1~1.5+20 + 上影", score_v13))

# ====== 方案14: 纯上影+实体 ======
def score_v14(d):
    shadow_score = max(0, 35 - d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0
    body_score = min(d["body_pct"]*3, 25)
    rpos_score = d["rpos"]*0.15
    atr_score = min(d["atr_pct"], 8) * 2
    return shadow_score + body_score + rpos_score + atr_score
scoring_schemes.append(("v14 上影罚(35-1.2x) + 实体×3 + ATR×2", score_v14))

# ====== 方案15: 涨幅+上影+MA5+ATR ======
def score_v15(d):
    pct_bonus = max(0, d["pct"]-2)*4  # 超过2%的部分才计分
    shadow_bonus = 20 if d["shadow_pct"]<12 else (10 if d["shadow_pct"]<20 else 0)
    ma5_bonus = min(d["ma5_sl"], 20) * 0.8
    atr_bonus = d["atr_pct"] * 2.5
    vr_bonus = 10 if 1<=d["vr"]<=2 else 0
    return pct_bonus + shadow_bonus + ma5_bonus + atr_bonus + vr_bonus
scoring_schemes.append(("v15 (涨-2%)×4 + 上影<12+20 + MA5×0.8 + ATR×2.5", score_v15))

# ====== 方案16: J值重视版 ======
def score_v16(d):
    j = d["j"]
    if 50<=j<=80: j_bonus = 20
    elif 40<=j<50: j_bonus = 10
    elif 80<j<=95: j_bonus = 15
    elif j>95: j_bonus = 5
    else: j_bonus = 0
    
    pct_bonus = max(0, d["pct"]) * 3
    shadow_bonus = 20 if d["shadow_pct"]<12 else 5
    vr_bonus = 15 if 1<=d["vr"]<=1.5 else 0
    body_bonus = min(d["body_pct"]*2, 15)
    return j_bonus + pct_bonus + shadow_bonus + vr_bonus + body_bonus
scoring_schemes.append(("v16 J50~80+20/J>95+5 + 涨×3 + 上影<12+20", score_v16))

# ═══ 跑所有方案 ═══
print(f"\n{'='*85}")
print("🏆 评分权重优化 — 各方案下#1冠军胜率")
print(f"{'='*85}")
print(f"{'方案':<42} {'冠军胜率':>10} {'冠军数':>8} {'出票天':>8} {'输家数':>8} {'平均次日':>8}")
print("-"*85)

results = []
for name, scorer in scoring_schemes:
    champ_wins=0; champ_total=0; total_next_h=0.0
    loser_champs = 0
    days_cnt=0
    
    for dt, cand in daily_candidates.items():
        # 评分排序
        ranked = sorted(cand, key=scorer, reverse=True)
        champ = ranked[0]
        days_cnt+=1; champ_total+=1
        
        if champ["next_h"] and champ["next_h"]>=2.5:
            champ_wins+=1
        else:
            loser_champs+=1
        
        if champ["next_h"]: total_next_h+=champ["next_h"]
    
    wr = champ_wins/champ_total*100 if champ_total else 0
    avg_nh = total_next_h/champ_total if champ_total else 0
    results.append((wr, name, champ_total, days_cnt, loser_champs, avg_nh))

# 排序
results.sort(reverse=True)
for wr, name, total, days, losers, avg_nh in results:
    mk="🔥" if wr>=65 else ("✅" if wr>=60 else ("⚠️" if wr>=50 else "❌"))
    # 显示前15字符+...
    short_name = name if len(name)<=40 else name[:39]+"…"
    print(f"{short_name:<42} {wr:>6.1f}% {total:>6} {days:>6}天 {losers:>6} {avg_nh:>+6.2f}% {mk}")

# 显示最佳
print(f"\n{'='*85}")
best = results[0]
print(f"🏆 冠军方案: {best[1]}")
print(f"   胜率: {best[0]:.1f}% (总{best[2]}天, 输{best[4]}天)")
print(f"   平均次日高: {best[5]:+.2f}%")
