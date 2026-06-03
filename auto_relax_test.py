
#!/usr/bin/env python3
"""自动放宽底仓条件 — 目标：每天10+候选 AND 胜率>60%"""
import json, os, time, random
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
random.seed(42); sample_files=sorted(random.sample(main_files,800))

all_codes={}; loaded=0
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
        loaded+=1
        if loaded%200==0: print(f"  {loaded}/{len(sample_files)}")
    except: pass
print(f"✅ {loaded}只")

dates_2025=sorted(set(dt for c,sd in all_codes.items() for dt in sd["dts"] if dt.startswith("2025")))
dates_2026=sorted(set(dt for c,sd in all_codes.items() for dt in sd["dts"] if dt.startswith("2026")))
print(f"📅 2025: {len(dates_2025)}天  2026: {len(dates_2026)}天")

print("📡 预计算...")
fwd={}
for code,sd in all_codes.items():
    recs=sd["recs"]
    for i in range(len(recs)-5):
        dt=recs[i]["date"]; buy=recs[i]["close"]
        if buy<=0: continue
        d1h=round((recs[i+1]["high"]/buy-1)*100,2) if i+1<len(recs) else None
        after=recs[i+1:i+6]
        m5=round(max(x["high"] for x in after)/buy*100-100,2) if len(after)==5 else None
        fwd[(code,dt)]=(d1h,m5)

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

# ═══ 自动放宽优化 ═══
# 定义条件族（从严格到宽松）
COND_GROUPS = {
    "均线多头": [
        ("MA5>MA10>MA20>MA60", lambda c,s,d: bool(s["mas"][5][d] and s["mas"][10][d] and s["mas"][20][d] and s["mas"][60][d] and s["mas"][5][d]>s["mas"][10][d]>s["mas"][20][d]>s["mas"][60][d])),
        ("MA5>MA10>MA20", lambda c,s,d: bool(s["mas"][5][d] and s["mas"][10][d] and s["mas"][20][d] and s["mas"][5][d]>s["mas"][10][d]>s["mas"][20][d])),
        ("MA5>MA10", lambda c,s,d: bool(s["mas"][5][d] and s["mas"][10][d] and s["mas"][5][d]>s["mas"][10][d])),
        ("免", lambda c,s,d: True),
    ],
    "MACD条件": [
        ("DIF>0且DIF>DEA", lambda c,s,d: bool(s["dif"][d] and s["dea"][d] and s["dif"][d]>0 and s["dif"][d]>s["dea"][d])),
        ("仅DIF>DEA", lambda c,s,d: bool(s["dif"][d] and s["dea"][d] and s["dif"][d]>s["dea"][d])),
        ("免", lambda c,s,d: True),
    ],
    "ATR": [
        (">3%", lambda c,s,d: bool(s["atr"][d] and s["c"][d]>0 and s["atr"][d]/s["c"][d]*100>3)),
        (">2%", lambda c,s,d: bool(s["atr"][d] and s["c"][d]>0 and s["atr"][d]/s["c"][d]*100>2)),
        (">1%", lambda c,s,d: bool(s["atr"][d] and s["c"][d]>0 and s["atr"][d]/s["c"][d]*100>1)),
        ("免", lambda c,s,d: True),
    ],
    "站上MA60": [
        ("严", lambda c,s,d: bool(s["mas"][60][d] and s["c"][d]>s["mas"][60][d])),
        ("免", lambda c,s,d: True),
    ],
    "价<80": [
        ("严", lambda c,s,d: s["c"][d]<80),
        ("免", lambda c,s,d: True),
    ],
}

def test_combo(ma_cond, macd_cond, atr_cond, ma60_cond, price_cond):
    """测试一个条件组合，返回(avg_candidates, pick_rate_2025, pick_rate_2026, win_rate_2025, win_rate_2026)"""
    filters = [("ma", ma_cond), ("macd", macd_cond), ("atr", atr_cond), ("ma60", ma60_cond), ("price", price_cond)]
    
    results = {}
    for yr, dates in [("2025",dates_2025), ("2026",dates_2026)]:
        daily_candidates = []
        picks = []
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
                    sc=score_v1(code,sd,di)
                    cand.append((code,sc))
                except: continue
            daily_candidates.append(len(cand))
            if len(cand)>=10:
                cand.sort(key=lambda x:x[1],reverse=True)
                f=fwd.get((cand[0][0],td),(None,None))
                picks.append({"d1h":f[0],"m5":f[1]})
        
        total_days = len(dates)
        pick_days = len(picks)
        pick_rate = pick_days/total_days*100
        avg_cand = sum(daily_candidates)/total_days
        min_cand = min(daily_candidates)
        
        if picks:
            win25 = sum(1 for p in picks if p["d1h"] and p["d1h"]>=2.5)
            win_rate = win25/pick_days*100
        else:
            win_rate = 0
        
        results[yr] = {"pick_rate":pick_rate, "avg_cand":avg_cand, "min_cand":min_cand, "win_rate":win_rate}
    
    return results

# ═══ 放宽搜索 ═══
# 从最严格开始，逐步放宽一个条件，直到达标
print(f"\n{'='*70}")
print("🔍 自动放宽搜索 — 从严格→宽松，找到最佳平衡点")
print(f"{'='*70}")

# 定义搜索路径
search_paths = [
    # (名称, ma_idx, macd_idx, atr_idx, ma60_idx, price_idx)
    ("M1(原始)", 0, 0, 0, 0, 0),  # 最严格
    ("放宽MA60", 0, 0, 0, 1, 0),  # 去掉MA60
    ("放宽ATR>2%", 0, 0, 1, 0, 0),  # ATR降到2%
    ("放宽MACD", 0, 1, 0, 0, 0),  # 仅DIF>DEA
    ("放宽均线(MA5>MA10>MA20)", 1, 0, 0, 0, 0),  # 去掉MA60的多头
    ("放宽ATR+MA60", 0, 0, 1, 1, 0),
    ("放宽MACD+ATR", 0, 1, 1, 0, 0),
    ("放宽均线+MACD", 1, 1, 0, 0, 0),
    ("放宽均线+MA60", 1, 0, 0, 1, 0),
    ("放宽均线+MACD+ATR", 1, 1, 1, 0, 0),
    ("全放宽(仅多头+MACD+MA60)", 0, 0, 3, 0, 0),  # 只有均线多头+MACD零轴上
    ("全放宽(仅多头+MACD)", 0, 0, 3, 1, 0),
    ("宽松(MA5>MA10+仅DIF>DEA)", 2, 1, 3, 1, 0),
    ("最宽松(MA5>MA10+仅DIF>DEA+ATR免)", 2, 1, 3, 1, 0),
]

print(f"\n{'路径':<24} {'2025出票率':>10} {'2025候选':>8} {'2025最低':>8} {'2025胜率':>8} {'2026出票率':>10} {'2026候选':>8} {'2026胜率':>8}")
print("-"*84)

best = {"name":"", "score":0}

for name, mi, macdi, atri, ma60i, pi in search_paths:
    ma_cond = COND_GROUPS["均线多头"][mi][1]
    macd_cond = COND_GROUPS["MACD条件"][macdi][1]
    atr_cond = COND_GROUPS["ATR"][atri][1]
    ma60_cond = COND_GROUPS["站上MA60"][ma60i][1]
    price_cond = COND_GROUPS["价<80"][pi][1]
    
    res = test_combo(ma_cond, macd_cond, atr_cond, ma60_cond, price_cond)
    
    r25 = res["2025"]["pick_rate"]
    c25 = res["2025"]["avg_cand"]
    mn25 = res["2025"]["min_cand"]
    w25 = res["2025"]["win_rate"]
    r26 = res["2026"]["pick_rate"]
    c26 = res["2026"]["avg_cand"]
    w26 = res["2026"]["win_rate"]
    
    print(f"{name:<24} {r25:>7.1f}% {c25:>6.0f} {mn25:>6} {w25:>6.1f}% {r26:>7.1f}% {c26:>6.0f} {w26:>6.1f}%")
    
    # 评分：出票率>95%+胜率>60%
    score = 0
    for yr in ["2025","2026"]:
        r = res[yr]["pick_rate"]
        w = res[yr]["win_rate"]
        c = res[yr]["avg_cand"]
        if r >= 95 and w >= 60:
            score += w + min(c,200)*0.05  # 胜率优先，候选数辅助
        elif r >= 90 and w >= 55:
            score += w*0.8 + r*0.2
    
    if score > best["score"]:
        best = {"name":name,"score":score,"res":res,
                "params":(mi,macdi,atri,ma60i,pi)}

# 最佳组合的详细信息
print(f"\n{'='*70}")
print(f"🏆 最佳组合: {best['name']}")
print(f"{'='*70}")
for yr in ["2025","2026"]:
    r = best["res"][yr]
    print(f"  {yr}: 出票率{r['pick_rate']:.1f}%, 均候选{r['avg_cand']:.0f}, 最低{r['min_cand']:.0f}, 胜率{r['win_rate']:.1f}%")

# 如果还没有>95%，继续放宽
if best["res"]["2025"]["pick_rate"] < 95 or best["res"]["2026"]["pick_rate"] < 95:
    print(f"\n⚠️ 当前最优仍未达到95%出票率，继续搜索更宽松组合...")
    
    # 尝试更多组合
    from itertools import product
    more_paths = []
    for mi in [0,1,2]:
        for macdi in [0,1]:
            for atri in [0,1,2,3]:
                for ma60i in [0,1]:
                    if mi==0 and macdi==0 and atri==0 and ma60i==0: continue
                    # 快速评估每个组合
                    ma_cond = COND_GROUPS["均线多头"][mi][1]
                    macd_cond = COND_GROUPS["MACD条件"][macdi][1]
                    atr_cond = COND_GROUPS["ATR"][atri][1]
                    ma60_cond = COND_GROUPS["站上MA60"][ma60i][1]
                    price_cond = COND_GROUPS["价<80"][0][1]
                    
                    res = test_combo(ma_cond, macd_cond, atr_cond, ma60_cond, price_cond)
                    
                    r25 = res["2025"]["pick_rate"]
                    r26 = res["2026"]["pick_rate"]
                    w25 = res["2025"]["win_rate"]
                    w26 = res["2026"]["win_rate"]
                    c25 = res["2025"]["avg_cand"]
                    
                    score_val = 0
                    if r25 >= 95 and r26 >= 95 and w25 >= 60 and w26 >= 60:
                        score_val = w25 + w26  # 都达标时最大化胜率
                    elif r25 >= 90 and r26 >= 90 and w25 >= 55 and w26 >= 55:
                        score_val = w25 + w26 + r25 + r26  # 接近达标时
                    
                    ma_name = COND_GROUPS["均线多头"][mi][0]
                    macd_name = COND_GROUPS["MACD条件"][macdi][0]
                    atr_name = COND_GROUPS["ATR"][atri][0]
                    ma60_name = COND_GROUPS["站上MA60"][ma60i][0]
                    combo_name = f"均{ma_name}/MACD{macd_name}/ATR{atr_name}/MA60{ma60_name}"
                    
                    print(f"  {combo_name:<36} 2025:出票{r25:>5.1f}%候选{c25:>4.0f}胜率{w25:>5.1f}% | 2026:出票{r26:>5.1f}%胜率{w26:>5.1f}%")
                    
                    if score_val > best["score"]:
                        best = {"name":combo_name,"score":score_val,"res":res,
                                "params":(mi,macdi,atri,ma60i,0)}

print(f"\n{'='*70}")
print(f"🏆🏆 最终最优: {best['name']}")
print(f"{'='*70}")
for yr in ["2025","2026"]:
    r = best["res"][yr]
    print(f"  {yr}: 出票率{r['pick_rate']:.1f}%, 均候选{r['avg_cand']:.0f}, 最低{r['min_cand']:.0f}, 胜率{r['win_rate']:.1f}%")
    status = "✅" if r["pick_rate"]>=95 else ("⚠️" if r["pick_rate"]>=80 else "❌")
    status2 = "✅" if r["win_rate"]>=60 else "❌"
    print(f"    出票达标: {status} 胜率达标: {status2}")

print(f"\n⏱ {(time.time()-t0)/60:.1f}分钟")
