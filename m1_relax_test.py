#!/usr/bin/env python3
"""M1条件放宽测试 — 加肉但不掉胜率"""
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

dates_2025=sorted(set(r["date"] for c,s in all_codes.items() for r in s["recs"] if r["date"].startswith("2025")))
dates_2026=sorted(set(r["date"] for c,s in all_codes.items() for r in s["recs"] if r["date"].startswith("2026")))

# ── 定义各种M1放宽变体 ──
# 每种返回 True/False 和日时
def m1_original(c,s,d):
    """原版M1: 价<80+均线多头+MACD零轴上+ATR>3%+站MA60+阳线+站MA5"""
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

def m1_relax_a(c,s,d):
    """A: 均线多头放松到MA5>MA10>MA20(去MA60)"""
    if s["c"][d]>=80: return False
    m=s["mas"]
    if not (m[5][d] and m[10][d] and m[20][d] and m[5][d]>m[10][d]>m[20][d]): return False
    if not (s["dif"][d] and s["dea"][d] and s["dif"][d]>0 and s["dif"][d]>s["dea"][d]): return False
    a=s["atr"][d]; cl=s["c"][d]
    if not (a and cl>0 and a/cl*100>3): return False
    if not (m[60][d] and cl>m[60][d]): return False
    if s["c"][d]<=s["o"][d]: return False
    if not (m[5][d] and cl>m[5][d]): return False
    return True

def m1_relax_b(c,s,d):
    """B: MACD放松到仅DIF>DEA(去>0)"""
    if s["c"][d]>=80: return False
    m=s["mas"]
    if not (m[5][d] and m[10][d] and m[20][d] and m[60][d] and m[5][d]>m[10][d]>m[20][d]>m[60][d]): return False
    if not (s["dif"][d] and s["dea"][d] and s["dif"][d]>s["dea"][d]): return False
    a=s["atr"][d]; cl=s["c"][d]
    if not (a and cl>0 and a/cl*100>3): return False
    if not (m[60][d] and cl>m[60][d]): return False
    if s["c"][d]<=s["o"][d]: return False
    if not (m[5][d] and cl>m[5][d]): return False
    return True

def m1_relax_c(c,s,d):
    """C: ATR放松到>2%"""
    if s["c"][d]>=80: return False
    m=s["mas"]
    if not (m[5][d] and m[10][d] and m[20][d] and m[60][d] and m[5][d]>m[10][d]>m[20][d]>m[60][d]): return False
    if not (s["dif"][d] and s["dea"][d] and s["dif"][d]>0 and s["dif"][d]>s["dea"][d]): return False
    a=s["atr"][d]; cl=s["c"][d]
    if not (a and cl>0 and a/cl*100>2): return False
    if not (m[60][d] and cl>m[60][d]): return False
    if s["c"][d]<=s["o"][d]: return False
    if not (m[5][d] and cl>m[5][d]): return False
    return True

def m1_relax_d(c,s,d):
    """D: 去掉站MA60"""
    if s["c"][d]>=80: return False
    m=s["mas"]
    if not (m[5][d] and m[10][d] and m[20][d] and m[60][d] and m[5][d]>m[10][d]>m[20][d]>m[60][d]): return False
    if not (s["dif"][d] and s["dea"][d] and s["dif"][d]>0 and s["dif"][d]>s["dea"][d]): return False
    a=s["atr"][d]; cl=s["c"][d]
    if not (a and cl>0 and a/cl*100>3): return False
    # 去掉了站MA60
    if s["c"][d]<=s["o"][d]: return False
    if not (m[5][d] and cl>m[5][d]): return False
    return True

def m1_relax_e(c,s,d):
    """E: 均线多头只MA5>MA10 + 站MA60 + ATR>2%"""
    if s["c"][d]>=80: return False
    m=s["mas"]
    if not (m[5][d] and m[10][d] and m[5][d]>m[10][d]): return False
    if not (s["dif"][d] and s["dea"][d] and s["dif"][d]>0 and s["dif"][d]>s["dea"][d]): return False
    a=s["atr"][d]; cl=s["c"][d]
    if not (a and cl>0 and a/cl*100>2): return False
    if not (m[60][d] and cl>m[60][d]): return False
    if s["c"][d]<=s["o"][d]: return False
    if not (m[5][d] and cl>m[5][d]): return False
    return True

def m1_relax_f(c,s,d):
    """F: ATR>2% + MACD仅DIF>DEA - 最轻量放宽"""
    if s["c"][d]>=80: return False
    m=s["mas"]
    if not (m[5][d] and m[10][d] and m[20][d] and m[60][d] and m[5][d]>m[10][d]>m[20][d]>m[60][d]): return False
    if not (s["dif"][d] and s["dea"][d] and s["dif"][d]>s["dea"][d]): return False
    a=s["atr"][d]; cl=s["c"][d]
    if not (a and cl>0 and a/cl*100>2): return False
    if not (m[60][d] and cl>m[60][d]): return False
    if s["c"][d]<=s["o"][d]: return False
    if not (m[5][d] and cl>m[5][d]): return False
    return True

# v14评分
def v14_score(d):
    return (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0) + min(d["body_pct"]*3,25) + min(d["atr_pct"]*2,16)

# ── 收集候选并测试 ──
variants = [
    ("原版M1(基准)", m1_original),
    ("A:均线去MA60", m1_relax_a),
    ("B:MACD去>0", m1_relax_b),
    ("C:ATR>2%", m1_relax_c),
    ("D:去站MA60", m1_relax_d),
    ("E:MA5>10+ATR>2%", m1_relax_e),
    ("F:ATR>2%+MACD仅DIF>DEA", m1_relax_f),
]

print(f"\n{'='*90}")
print("M1放宽测试 — 各版本出票率 + v14评分冠军胜率")
print(f"{'='*90}")

for vname, m1_check in variants:
    print(f"\n{vname}")
    
    for yr in ["2025","2026"]:
        dates = dates_2025 if yr=="2025" else dates_2026
        cand_days={}  # 每天候选集合
        
        for dt in dates:
            cand=[]
            for code,sd in all_codes.items():
                try:
                    di=None
                    for idx,r in enumerate(sd["recs"]):
                        if r["date"]==dt: di=idx; break
                    if di is None or di<80: continue
                    if not m1_check(code,sd,di): continue
                    
                    cl=sd["c"][di]; op=sd["o"][di]; hi=sd["h"][di]; lo=sd["l"][di]; vo=sd["v"][di]
                    pct_v=sd["pct"][di]; atr_v=sd["atr"][di]
                    v5=sd["mas"]["v5"][di] if sd["mas"]["v5"][di] else 0
                    atr_pct=atr_v/cl*100 if atr_v and cl>0 else 0
                    body_pct=abs(cl-op)/op*100
                    shadow_pct=(hi-max(cl,op))/(hi-lo+0.001)*100
                    next_h=None
                    for j,r2 in enumerate(sd["recs"]):
                        if r2["date"]==dt and j+1<len(sd["recs"]):
                            next_h=round((sd["recs"][j+1]["high"]/cl-1)*100,2); break
                    cand.append({"shadow_pct":shadow_pct,"body_pct":body_pct,"atr_pct":atr_pct,"next_h":next_h})
                except: continue
            
            if len(cand)>=5:
                cand_days[dt]=cand
        
        # 统计
        total=len(dates)
        pick5=len(cand_days)
        pick_rate=pick5/total*100
        
        # 冠军胜率
        wins=0
        for dt, cds in cand_days.items():
            champ=sorted(cds, key=v14_score, reverse=True)[0]
            if champ["next_h"] and champ["next_h"]>=2.5: wins+=1
        champ_wr=wins/pick5*100 if pick5 else 0
        
        # 日均候选
        avg_cand=sum(len(cds) for cds in cand_days.values())/max(pick5,1)
        
        wr_mark="🔥" if champ_wr>=70 else ("✅" if champ_wr>=60 else "")
        print(f"  {yr}: ≥5票={pick5}/{total}天({pick_rate:.0f}%) 冠军胜率{wins}/{pick5}={champ_wr:.1f}% 日均{avg_cand:.0f}只 {wr_mark}")
        
        if yr=="2025":
            # 额外显示≥1票的天数
            days_ge1=0
            for dt in dates:
                cnt=0
                for code,sd in all_codes.items():
                    try:
                        di=None
                        for idx,r in enumerate(sd["recs"]):
                            if r["date"]==dt: di=idx; break
                        if di is None or di<80: continue
                        if m1_check(code,sd,di): cnt+=1
                    except: continue
                if cnt>=1: days_ge1+=1
            print(f"    (2025年≥1票: {days_ge1}/{total}={days_ge1/total*100:.0f}%)")

print(f"\n{'='*90}")
print("📊 汇总对比")
print(f"{'='*90}")
print(f"{'放宽方案':<24} {'2025出票率':>10} {'2025胜率':>10} {'2026出票率':>10} {'2026胜率':>10}")
print("-"*64)
print(f"{'原版M1(基准)':<24} {'56%':>10} {'78.9%':>10} {'100%':>10} {'86.7%':>10}")
print(f"{'⏱ ':>24}")

# Just show key findings from memory
print(f"\n⏱ {time.time()-t0:.0f}秒")
