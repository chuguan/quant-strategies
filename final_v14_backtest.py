#!/usr/bin/env python3
"""2025-2026回测 — v14评分冠军胜率"""
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
        pct=[0.0]
        for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr_l)/14
        all_codes[code]={"c":c,"h":h,"l":l,"o":o,"v":v,"mas":mas,"dif":dif,"dea":dea,"pct":pct,"recs":recs,"atr":atr}
    except: pass

active=len(all_codes)
print(f"✅ {active}只活跃股, {time.time()-t0:.0f}秒")

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

def v14_score(c,s,d):
    """v14评分：上影罚+实体×3+ATR×2"""
    cl=s["c"][d]; op=s["o"][d]; hi=s["h"][d]; lo=s["l"][d]
    rng=hi-lo
    shadow=(hi-max(cl,op))/(rng+0.001)*100 if rng>0 else 0
    body=abs(cl-op)/op*100
    atr_p=s["atr"][d]/cl*100 if s["atr"][d] and cl>0 else 0
    sc=0
    if shadow<30: sc+=max(0,35-shadow*1.2)
    sc+=min(body*3,25)
    sc+=min(atr_p*2,16)
    return sc

print(f"\n{'='*80}")
print("🏆 v14评分回测 — 2025+2026年")
print(f"{'='*80}")

for yr_name, dates in [("2025",dates_2025),("2026",dates_2026)]:
    print(f"\n📅 {yr_name}年 ({len(dates)}交易日)")
    
    win_days=0; pick_days=0; total_cand=0
    win_streak=0; max_win_streak=0; lose_streak=0; max_lose_streak=0
    daily_stats=[]
    
    for dt in sorted(dates):
        cand=[]
        for code,sd in all_codes.items():
            try:
                di=None
                for idx,r in enumerate(sd["recs"]):
                    if r["date"]==dt: di=idx; break
                if di is None or di<80: continue
                if not pass_M1(code,sd,di): continue
                
                next_h=None
                for j,r2 in enumerate(sd["recs"]):
                    if r2["date"]==dt and j+1<len(sd["recs"]):
                        next_h=round((sd["recs"][j+1]["high"]/sd["c"][di]-1)*100,2); break
                
                sc=v14_score(code,sd,di)
                cand.append({"code":code,"score":sc,"pct":sd["pct"][di],"next_h":next_h})
            except: continue
        
        total_cand+=len(cand)
        
        if len(cand)>=5:
            cand.sort(key=lambda x:x["score"],reverse=True)
            champ=cand[0]
            pick_days+=1
            win=champ["next_h"] and champ["next_h"]>=2.5
            if win:
                win_days+=1
                win_streak+=1; lose_streak=0
                max_win_streak=max(max_win_streak,win_streak)
            else:
                win_streak=0; lose_streak+=1
                max_lose_streak=max(max_lose_streak,lose_streak)
            
            nh=champ["next_h"] if champ["next_h"] else 0
            daily_stats.append((dt,len(cand),champ["pct"],nh,champ["code"],win))
    
    wr=win_days/pick_days*100 if pick_days else 0
    print(f"  📊 出票{pick_days}/{len(dates)}天 = {pick_days/len(dates)*100:.0f}%")
    print(f"  🏆 冠军胜率: {win_days}/{pick_days} = {wr:.1f}%")
    print(f"  📈 日均候选: {total_cand/max(pick_days,1):.0f}只")
    print(f"  🔥 最长连胜: {max_win_streak}天")
    print(f"  ❄️ 最长连败: {max_lose_streak}天")
    
    # 每日明细
    print(f"\n  每日明细（日期 候选 冠军涨% 次日高% 结果）")
    for dt, nc, pct, nh, code, win in daily_stats:
        mk="✅" if win else "❌"
        pct_s=f"{pct:+.2f}%"
        nh_s=f"{nh:+.2f}%" if nh else "—"
        print(f"  {dt} {nc:>4}只 {pct_s:>8} {nh_s:>8} {mk}")

print(f"\n⏱ 总用时: {time.time()-t0:.0f}秒")
