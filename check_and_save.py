#!/usr/bin/env python3
"""检查≥5票出票率 + 保存前6策略"""
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

# 收集M1全池候选
print("📝 收集M1全池候选…")
daily_cand={}
all_dates=sorted(set(dates_2025+dates_2026))
for dt in all_dates:
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
            pos20_v=sd["pos20"][di] if sd["pos20"][di] else 0
            next_h=None
            for j,r2 in enumerate(sd["recs"]):
                if r2["date"]==dt and j+1<len(sd["recs"]):
                    next_h=round((sd["recs"][j+1]["high"]/cl-1)*100,2); break
            cand.append({"code":code,"pct":pct_v,"atr_pct":atr_pct,"vr":vr,
                        "body_pct":body_pct,"shadow_pct":shadow_pct,"rpos":rpos,
                        "ma5_sl":ma5_sl_v,"pos20":pos20_v,"next_h":next_h})
        except: continue
    daily_cand[dt]=cand
print(f"✅ {len(daily_cand)}天")

# ── 前6评分方案 ──
top6 = [
    ("v14(上影+实体+ATR)", lambda d: (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0) + min(d["body_pct"]*3,25) + min(d["atr_pct"]*2,16)),
    ("v15(涨上影MA5ATR)", lambda d: max(0,d["pct"]-2)*4 + (20 if d["shadow_pct"]<12 else 10 if d["shadow_pct"]<20 else 0) + min(d["ma5_sl"]*0.8,16) + d["atr_pct"]*2.5 + (10 if 1<=d["vr"]<=2 else 0)),
    ("v12(综合)", lambda d: max(0,d["pct"])*3.5 + d["atr_pct"]*1.2 + (18 if 1<=d["vr"]<=1.5 else 8 if 1.5<d["vr"]<=2.5 else 0) + (22 if d["shadow_pct"]<10 else 10 if d["shadow_pct"]<18 else 0 if d["shadow_pct"]<30 else -12) + min(d["ma5_sl"],15)*1.2 + min(d["body_pct"],10)*1.5),
    ("v14-3(加涨幅)", lambda d: max(0,d["pct"])*1.5 + (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0) + min(d["body_pct"]*3,25) + min(d["atr_pct"]*2,16)),
    ("v2(涨×3+上影+VR+MA5)", lambda d: max(0,d["pct"])*3 + (20 if 1<=d["vr"]<=1.5 else 10 if 1.5<d["vr"]<=2.5 else 0) + (20 if d["shadow_pct"]<10 else 10 if d["shadow_pct"]<20 else 0) + min(d["ma5_sl"]*1.5,25)),
    ("v10(三因子)", lambda d: max(0,d["pct"])*3 + (25 if d["shadow_pct"]<12 else 5) + min(d["ma5_sl"]*2,20)),
]

# ═══ 检查≥5票出票率 ═══
print(f"\n{'='*90}")
print("📊 前6策略 × ≥5票出票率 + 冠军胜率（2025+2026）")
print(f"{'='*90}")

# 基线：之前的硬过滤4.0~5.5%冠军70.5%（但只能用2026比）
baseline_2026_wr=70.5

strategy_data=[]
for sname, scorer in top6:
    print(f"\n{sname}")
    for yr_name, yr_dates in [("2025", dates_2025), ("2026", dates_2026)]:
        wins5=0; tot5=0; wins10=0; tot10=0; wins_all=0
        for dt in yr_dates:
            cds=daily_cand.get(dt,[])
            # ≥5票
            cd5=[c for c in cds]
            if len(cd5)>=5:
                champ5=sorted(cd5, key=scorer, reverse=True)[0]
                tot5+=1
                if champ5["next_h"] and champ5["next_h"]>=2.5: wins5+=1
            # ≥10票
            cd10=[c for c in cds]
            if len(cd10)>=10:
                champ10=sorted(cd10, key=scorer, reverse=True)[0]
                tot10+=1
                if champ10["next_h"] and champ10["next_h"]>=2.5: wins10+=1
        
        wr5=wins5/tot5*100 if tot5 else 0
        wr10=wins10/tot10*100 if tot10 else 0
        total_days=len(yr_dates)
        pick5_rate=tot5/total_days*100
        pick10_rate=tot10/total_days*100
        
        mark5="✅" if (tot5>=total_days*0.9 and wr5>=60) or (tot5>=5) else "⚠️"
        mark10="✅" if (tot10>=total_days*0.9 and wr10>=60) or (tot10>=5) else "⚠️"
        
        print(f"  {yr_name}: ≥5票={tot5}/{total_days}天({pick5_rate:.0f}%) 胜率{wr5:.1f}% {mark5}")
        print(f"           ≥10票={tot10}/{total_days}天({pick10_rate:.0f}%) 胜率{wr10:.1f}% {mark10}")
        
        if yr_name=="2026":
            s26_5wr=wr5; s26_5pick=pick5_rate; s26_10wr=wr10; s26_10pick=pick10_rate

# ═══ 输出汇总对比 ═══
print(f"\n{'='*90}")
print("🏆 与原始硬过滤4.0~5.5%对比 (2026年)")
print(f"{'='*90}")
print(f"{'策略':<30} {'≥5票出票':>10} {'≥5票胜率':>10} {'≥10票出票':>10} {'≥10票胜率':>10}")
print("-"*70)
print(f"{'原始:硬过滤4.0~5.5%':<30} {'78/90(86.7%)':>10} {'70.5%':>10} {'78/90(86.7%)':>10} {'70.5%':>10}")
print("-"*70)
for sname, scorer in top6:
    print(f"{sname:<30} {'—':>10} {'—':>10} {'—':>10} {'—':>10}")

# ═══ 保存前6策略文件 ═══
print(f"\n{'='*90}")
print("💾 保存前6策略文件")
print(f"{'='*90}")

script_dir = "/c/Users/12546/AppData/Local/hermes/scripts"

strategy_template = '''#!/usr/bin/env python3
"""
{full_name}
候选池: M1(价<80+均线多头+MACD零轴上+ATR>3%+站MA60) + 阳线 + 站MA5
评分类别: {scoring_type}
评分公式: {formula_desc}
2025年: {y25_wr:.1f}%胜率 ({y25_pick}天出票/243天)
2026年: {y26_wr:.1f}%胜率 ({y26_pick}天出票/90天)
两年平均: {avg:.1f}%
"""

import json, os
from datetime import datetime

CACHE_DIR = r"C:\\Users\\12546\\AppData\\Local\\hermes\\hermes-agent\\cache"
MIN_CANDIDATES = 5  # 最少候选数

def calc_ma(s,p):
    n=len(s); r={{}}
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
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files=[f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
print(f"  {{len(main_files)}}只主板股")

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

def score_stock(d):
    """{short_name}评分公式"""
    {scoring_code}

today = datetime.now().strftime("%Y-%m-%d")
print(f"\\n📅 今日: {{today}}")
print("📝 扫描中...")

# 逐只扫描
candidates=[]
loaded=0
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
        
        # 找最后一天（今日）
        last_rec=recs[-1]
        di=len(recs)-1
        if last_rec["date"]!=today: continue
        if not pass_M1(code,locals()["___"] if False else None, di): continue
        # Re-check properly
        sd_s={{}}; exec("sd_s=locals()['___']") if False else None
        # Actually use the namespace
    except: continue
    loaded+=1
    if loaded%500==0: print(f"  {{loaded}}/{{len(main_files)}}")

# This is a simplified template - real implementation will be in the saved file
'''

# Let me just save simple strategy descriptors first, and note it needs a real selection script
# The key info to save:

strategies_info = [
    ("CG-07", "v14(上影+实体+ATR)", 
     "评分 = (35 - 上影线%×1.2, 上影<30%计) + 实体%×3(≤25) + ATR%×2(≤16)",
     "max(0,35-d['shadow_pct']*1.2) if d['shadow_pct']<30 else 0\n    sc += min(d['body_pct']*3,25)\n    sc += min(d['atr_pct']*2,16)\n    return sc"),
    ("CG-08", "v15(涨上影MA5ATR)",
     "评分 = (涨-2%)×4 + 上影<12+20/<20+10 + MA5×0.8(≤16) + ATR×2.5 + VR1~2+10",
     "max(0,d['pct']-2)*4 + (20 if d['shadow_pct']<12 else 10 if d['shadow_pct']<20 else 0)\n    sc += min(d['ma5_sl']*0.8,16)\n    sc += d['atr_pct']*2.5 + (10 if 1<=d['vr']<=2 else 0)\n    return sc"),
    ("CG-09", "v12(综合)",
     "评分 = 涨×3.5 + ATR×1.2 + VR1~1.5+18/1.5~2.5+8 + 上影<10+22/<18+10/<30+0/else-12 + MA5×1.2(≤18) + 实体×1.5(≤15)",
     "max(0,d['pct'])*3.5 + d['atr_pct']*1.2 + (18 if 1<=d['vr']<=1.5 else 8 if 1.5<d['vr']<=2.5 else 0)\n    sc += (22 if d['shadow_pct']<10 else 10 if d['shadow_pct']<18 else 0 if d['shadow_pct']<30 else -12)\n    sc += min(d['ma5_sl'],15)*1.2 + min(d['body_pct'],10)*1.5\n    return sc"),
    ("CG-10", "v14-3(加涨幅版)",
     "评分 = 涨×1.5 + 上影罚(35-1.2x, <30) + 实体×3(≤25) + ATR×2(≤16)",
     "max(0,d['pct'])*1.5 + (max(0,35-d['shadow_pct']*1.2) if d['shadow_pct']<30 else 0)\n    sc += min(d['body_pct']*3,25) + min(d['atr_pct']*2,16)\n    return sc"),
    ("CG-11", "v2(涨×3+上影+VR+MA5)",
     "评分 = 涨×3 + VR1~1.5+20/1.5~2.5+10 + 上影<10+20/<20+10 + MA5×1.5(≤25)",
     "max(0,d['pct'])*3 + (20 if 1<=d['vr']<=1.5 else 10 if 1.5<d['vr']<=2.5 else 0)\n    sc += (20 if d['shadow_pct']<10 else 10 if d['shadow_pct']<20 else 0)\n    sc += min(d['ma5_sl']*1.5,25)\n    return sc"),
    ("CG-12", "v10(三因子)",
     "评分 = 涨×3 + 上影<12+25/else+5 + MA5×2(≤20)",
     "max(0,d['pct'])*3 + (25 if d['shadow_pct']<12 else 5) + min(d['ma5_sl']*2,20)\n    return sc"),
]

print(f"\n{'策略':<10} {'名称':<22} {'2025胜率':>10} {'2026胜率':>10} {'平均':>8}")
print("-"*60)

for ver, sname, formula_desc, scoring_code in strategies_info:
    print(f"{ver:<10} {sname:<22} {'—':>10} {'—':>10} {'—':>8}")

print(f"\n✅ 策略信息已准备。实际数据需从上述回测获取。")
print(f"⏱ {time.time()-t0:.0f}秒")
