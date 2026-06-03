#!/usr/bin/env python3
"""输出每日选股明细表 — M1+阳线+站MA5 + 4.0~5.5%涨幅范围内"""
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

# ── 加载全部主板股 ──
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files=[f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
print(f"📊 {len(main_files)}只主板股")

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
        pct=[0.0]
        for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr_l)/14
        all_codes[code]={"c":c,"o":o,"h":h,"l":l,"v":v,"mas":mas,"dif":dif,"dea":dea,"macd":macd,"pct":pct,"recs":recs,"atr":atr}
        loaded+=1
        if loaded%500==0: print(f"  {loaded}/{len(main_files)}")
    except: pass
print(f"✅ {loaded}只")

# ── 2026年交易日 ──
dates_2026=sorted(set(r["date"] for code,sd in all_codes.items() for r in sd["recs"] if r["date"].startswith("2026")))
print(f"📅 2026: {len(dates_2026)}交易日")

# ── 定义条件 ──
def cond_price(code,sd,di): return sd["c"][di]<80
def cond_ma_bullish(code,sd,di):
    mas=sd["mas"]
    return bool(mas[5][di] and mas[10][di] and mas[20][di] and mas[60][di] and mas[5][di]>mas[10][di]>mas[20][di]>mas[60][di])
def cond_macd_above(code,sd,di): return bool(sd["dif"][di] and sd["dea"][di] and sd["dif"][di]>0 and sd["dif"][di]>sd["dea"][di])
def cond_atr(code,sd,di):
    a=sd["atr"][di]; cl=sd["c"][di]
    return bool(a and cl>0 and a/cl*100>3)
def cond_ma60(code,sd,di): return bool(sd["mas"][60][di] and sd["c"][di]>sd["mas"][60][di])
def cond_yang(code,sd,di): return sd["c"][di]>sd["o"][di]
def cond_ma5_up(code,sd,di): return bool(sd["mas"][5][di] and sd["c"][di]>sd["mas"][5][di])
def cond_pct_4_5(code,sd,di):
    p=sd["pct"][di]
    return 4.0<=p<=5.5

M1=[cond_price,cond_ma_bullish,cond_macd_above,cond_atr,cond_ma60]
BEST = M1+[cond_yang,cond_ma5_up,cond_pct_4_5]

# ── 逐天统计 + 列出股票 ──
print(f"\n{'='*120}")
print(f"📋 M1+阳线+站MA5+涨4.0~5.5% — 每日选股明细表")
print(f"{'='*120}")
print(f"{'日期':<12} {'候选数':>6} {'涨跌%':>8} {'股票代码':>10} {'名称(代码)':<20} {'评分':>6} {'次日高%':>8} {'达标':>6}")
print(f"{'─'*70}")

total_pick_days=0
total_win=0
total_candidates=0

for dt in sorted(dates_2026):
    cand=[]
    for code,sd in all_codes.items():
        try:
            di=None
            for idx,r in enumerate(sd["recs"]):
                if r["date"]==dt: di=idx; break
            if di is None or di<80: continue
            ok=True
            for cond in BEST:
                if not cond(code,sd,di): ok=False; break
            if not ok: continue
            
            # 简单评分
            sc=0; cl=sd["c"][di]
            atr_v=sd["atr"][di]; sc+=(atr_v/cl*100)*2 if atr_v and cl>0 else 0
            if sd["pct"][di]>0: sc+=10
            v5=sd["mas"]["v5"][di] if sd["mas"]["v5"][di] else 0
            vr=sd["v"][di]/v5 if v5>0 else 0
            if 1<vr<2: sc+=15; sc+=10
            elif vr>2: sc+=8
            
            # 找次日高
            next_h=None
            for j,r2 in enumerate(sd["recs"]):
                if r2["date"]==dt and j+1<len(sd["recs"]):
                    next_h=round((sd["recs"][j+1]["high"]/cl-1)*100,2)
                    break
            
            cand.append((code,sd["pct"][di],sd["c"][di],next_h,sc))
        except: continue
    
    total_candidates+=len(cand)
    
    if len(cand)>=10:
        total_pick_days+=1
        cand.sort(key=lambda x:x[4],reverse=True)
        champ=cand[0]
        win_mark="🔥" if champ[3] and champ[3]>=2.5 else "  "
        if champ[3] and champ[3]>=2.5: total_win+=1
        
        # 代码映射：sh6xxx→6xxxx, sz0xxxx→0xxxx, sz2xxxx→2xxxx
        def fmt_code(c):
            if c.startswith('sh'): return '6'+c[2:]
            elif c.startswith('sz0'): return '0'+c[3:]
            elif c.startswith('sz2'): return '2'+c[3:]
            return c
        
        champ_code=fmt_code(champ[0])
        champ_name=f"{champ_code}"
        sc=champ[4]
        nh=champ[3] if champ[3] else 0
        win_flag="✅" if nh>=2.5 else "❌"
        
        print(f"{dt:<12} {len(cand):>6} {champ[1]:>+7.2f}% {champ_code:>10} {champ_name:<20} {sc:>6} {nh:>+7.2f}% {win_flag:>6}")
        
        # 显示当天所有候选票数（不一一列出名称，太长了）
        # 只列出前3名
        top3=cand[:3]
        top3_str=", ".join([f"{fmt_code(t[0])}(涨{t[1]:+.1f}%)" for t in top3])
        if len(cand)>3:
            top3_str+=f" ... 共{len(cand)}只"
        print(f"  {'TOP3':>6} {top3_str}")
    else:
        print(f"{dt:<12} {len(cand):>6} {'<10只':>15}")

print(f"{'─'*70}")
print(f"\n📊 统计总结")
print(f"{'─'*30}")
print(f"  交易日总数: {len(dates_2026)}天")
print(f"  出票天数: {total_pick_days}天 ({total_pick_days/len(dates_2026)*100:.1f}%)")
print(f"  冠军胜率: {total_win}/{total_pick_days} = {total_win/total_pick_days*100:.1f}%")
print(f"  日均候选: {total_candidates/len(dates_2026):.0f}只")
print(f"  出票日候选: {total_candidates/max(total_pick_days,1):.0f}只/天")
