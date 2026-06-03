#!/usr/bin/env python3
"""3个候选池 × 最优评分系统 = 找出最佳组合"""
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

print("📡 加载数据…")
t0=time.time()
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

# ── 定义3个候选池 ──
def collect_pool(dates, extra_checkers=None):
    """收集M1+阳线+站MA5候选，可选额外过滤"""
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
                pct_v=sd["pct"][di]; atr_v=sd["atr"][di]
                v5=sd["mas"]["v5"][di] if sd["mas"]["v5"][di] else 0
                vr=vo/v5 if v5>0 else 0
                atr_pct=atr_v/cl*100 if atr_v and cl>0 else 0
                body_pct=abs(cl-op)/op*100
                shadow_pct=(hi-max(cl,op))/(hi-lo+0.001)*100
                rpos=(cl-lo)/(hi-lo+0.001)*100
                ma5_sl_v=sd["ma5_sl"][di] if sd["ma5_sl"][di] else 0
                pos20_v=sd["pos20"][di] if sd["pos20"][di] else 0
                
                # 额外过滤
                if extra_checkers:
                    ok=True
                    for chk in extra_checkers:
                        if not chk(pct_v, vr, atr_pct, body_pct, shadow_pct, rpos, ma5_sl_v, pos20_v):
                            ok=False; break
                    if not ok: continue
                
                next_h=None
                for j,r2 in enumerate(sd["recs"]):
                    if r2["date"]==dt and j+1<len(sd["recs"]):
                        next_h=round((sd["recs"][j+1]["high"]/cl-1)*100,2); break
                
                cand.append({"code":code,"pct":pct_v,"atr_pct":atr_pct,"vr":vr,
                            "body_pct":body_pct,"shadow_pct":shadow_pct,"rpos":rpos,
                            "ma5_sl":ma5_sl_v,"pos20":pos20_v,"next_h":next_h})
            except: continue
        if len(cand)>=10: daily[dt]=cand
    return daily

dates_2025=sorted(set(r["date"] for c,s in all_codes.items() for r in s["recs"] if r["date"].startswith("2025")))
dates_2026=sorted(set(r["date"] for c,s in all_codes.items() for r in s["recs"] if r["date"].startswith("2026")))
print(f"📅 2025: {len(dates_2025)}天, 2026: {len(dates_2026)}天")

# ── 定义3个池 ──
print("📝 收集3个候选池…")
# 池1: M1全池
pool1_25=collect_pool(dates_2025); pool1_26=collect_pool(dates_2026)
print(f"  池1(全池): 2025={len(pool1_25)}天, 2026={len(pool1_26)}天")

# 池2: M1+涨4.0~5.5%
pool2_25=collect_pool(dates_2025, [lambda p,v,a,b,s,r,ms,pp: 4<=p<=5.5])
pool2_26=collect_pool(dates_2026, [lambda p,v,a,b,s,r,ms,pp: 4<=p<=5.5])
print(f"  池2(4~5.5%): 2025={len(pool2_25)}天, 2026={len(pool2_26)}天")

# 池3: M1+涨4.0~7.5%
pool3_25=collect_pool(dates_2025, [lambda p,v,a,b,s,r,ms,pp: 4<=p<=7.5])
pool3_26=collect_pool(dates_2026, [lambda p,v,a,b,s,r,ms,pp: 4<=p<=7.5])
print(f"  池3(4~7.5%): 2025={len(pool3_25)}天, 2026={len(pool3_26)}天")

# ── 评分方案 ──
scorers = [
    ("v14(上影+实体+ATR)", lambda d: (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0) + min(d["body_pct"]*3,25) + min(d["atr_pct"]*2,16)),
    ("v10(三因子·涨+上影+MA5)", lambda d: max(0,d["pct"])*3 + (25 if d["shadow_pct"]<12 else 5) + min(d["ma5_sl"]*2,20)),
    ("v14-3(涨+上影+实体+ATR)", lambda d: max(0,d["pct"])*1.5 + (max(0,35-d["shadow_pct"]*1.2) if d["shadow_pct"]<30 else 0) + min(d["body_pct"]*3,25) + min(d["atr_pct"]*2,16)),
    ("v15((涨-2%)×4+上影+MA5+ATR)", lambda d: max(0,d["pct"]-2)*4 + (20 if d["shadow_pct"]<12 else 10 if d["shadow_pct"]<20 else 0) + min(d["ma5_sl"]*0.8,16) + d["atr_pct"]*2.5 + (10 if 1<=d["vr"]<=2 else 0)),
    ("v2(涨×3+VR1~1.5+上影<10+MA5)", lambda d: max(0,d["pct"])*3 + (20 if 1<=d["vr"]<=1.5 else 10 if 1.5<d["vr"]<=2.5 else 0) + (20 if d["shadow_pct"]<10 else 10 if d["shadow_pct"]<20 else 0) + min(d["ma5_sl"]*1.5,25)),
    ("v5(上影主导)", lambda d: (35 if d["shadow_pct"]<8 else 20 if d["shadow_pct"]<15 else 5 if d["shadow_pct"]<25 else -15) + max(0,d["pct"])*2 + (15 if 1<=d["vr"]<=1.5 else 8 if 1.5<d["vr"]<=3 else 0) + d["atr_pct"]*1.5 + d["pos20"]*0.15),
    ("v12(综合)", lambda d: max(0,d["pct"])*3.5 + d["atr_pct"]*1.2 + (18 if 1<=d["vr"]<=1.5 else 8 if 1.5<d["vr"]<=2.5 else 0) + (22 if d["shadow_pct"]<10 else 10 if d["shadow_pct"]<18 else 0 if d["shadow_pct"]<30 else -12) + min(d["ma5_sl"],15)*1.2 + min(d["body_pct"],10)*1.5),
]

# ═══ 跑所有组合 ═══
print(f"\n{'='*100}")
print("3候选池 × 7评分方案 = 21种组合，2025+2026跨年验证")
print(f"{'='*100}")

results = []
for pool_name, pool_25, pool_26 in [("池1(M1全池)", pool1_25, pool1_26), 
                                      ("池2(涨4.0~5.5%)", pool2_25, pool2_26),
                                      ("池3(涨4.0~7.5%)", pool3_25, pool3_26)]:
    for scr_name, scorer in scorers:
        wins25=0; tot25=0; wins26=0; tot26=0
        for dt, cds in pool_25.items():
            if not cds: continue
            ranked=sorted(cds, key=scorer, reverse=True)
            champ=ranked[0]
            tot25+=1
            if champ["next_h"] and champ["next_h"]>=2.5: wins25+=1
        for dt, cds in pool_26.items():
            if not cds: continue
            ranked=sorted(cds, key=scorer, reverse=True)
            champ=ranked[0]
            tot26+=1
            if champ["next_h"] and champ["next_h"]>=2.5: wins26+=1
        
        wr25=wins25/tot25*100 if tot25 else 0
        wr26=wins26/tot26*100 if tot26 else 0
        avg=(wr25+wr26)/2
        diff=abs(wr25-wr26)
        
        results.append((avg, diff, wr25, tot25, wr26, tot26, pool_name, scr_name))

# 排序+输出
results.sort(reverse=True)
print(f"\n{'排名':>4} {'候选池':<18} {'评分方案':<32} {'2025':>8} {'2026':>8} {'平均':>8} {'稳定性':>8}")
print("-"*90)
for i,(avg,diff,wr25,t25,wr26,t26,pname,sname) in enumerate(results):
    stable="✅" if diff<=5 else ("⚠️" if diff<=10 else "❌")
    mk="🔥" if avg>=75 else ("✅" if avg>=70 else "")
    pname_short=pname[:16]
    sname_short=sname[:30]
    print(f"{i+1:>3}. {pname_short:<18} {sname_short:<32} {wr25:>5.1f}%({t25:>3}天) {wr26:>5.1f}%({t26:>3}天) {avg:>5.1f}% {stable:>8} {mk}")

# 展示各种池的最优方案
print(f"\n{'─'*90}")
print("各池最佳方案汇总:")
print(f"{'─'*90}")
for pname in ["池1(M1全池)", "池2(涨4.0~5.5%)", "池3(涨4.0~7.5%)"]:
    pool_best=[r for r in results if r[6]==pname]
    if pool_best:
        avg,diff,wr25,t25,wr26,t26,pname,sname=pool_best[0]
        print(f"  🏆 {pname} + {sname}: 平均{avg:.1f}% (2025:{wr25:.1f}%/{t25}天 2026:{wr26:.1f}%/{t26}天)")

print(f"\n⏱ 总用时: {time.time()-t0:.0f}秒")
