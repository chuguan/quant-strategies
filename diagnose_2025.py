#!/usr/bin/env python3
"""排查2025年出票率低的原因 - 逐条件检查"""
import json, os, time
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

t0=time.time()
print("📡 加载数据…")
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files=[f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
print(f"📊 {len(main_files)}只主板股文件")

# 只加载样本数据（选前500只快速排查）
sample_files = main_files[:500]

all_codes={}
for fn in sample_files:
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
        all_codes[code]={"c":c,"h":h,"l":l,"o":o,"v":v,"mas":mas,"dif":dif,"dea":dea,"macd":macd,"pct":pct,"recs":recs,"atr":atr,"k":k,"d":d,"j":j}
    except: pass
print(f"✅ {len(all_codes)}只 (样本)")

# 选出2025年所有交易日
dates_2025=sorted(set(r["date"] for c,s in all_codes.items() for r in s["recs"] if r["date"].startswith("2025")))
dates_2026=sorted(set(r["date"] for c,s in all_codes.items() for r in s["recs"] if r["date"].startswith("2026")))
print(f"📅 2025: {len(dates_2025)}天, 2026: {len(dates_2026)}天")

# ── 逐条件统计 ──
# 对每一天、每只票，检查每个条件是否通过
# 统计每天通过每个条件的票数

def check_price(c,s,d): return s["c"][d]<80
def check_ma_bullish(c,s,d): return bool(s["mas"][5][d] and s["mas"][10][d] and s["mas"][20][d] and s["mas"][60][d] and s["mas"][5][d]>s["mas"][10][d]>s["mas"][20][d]>s["mas"][60][d])
def check_macd(c,s,d): return bool(s["dif"][d] and s["dea"][d] and s["dif"][d]>0 and s["dif"][d]>s["dea"][d])
def check_atr(c,s,d): return bool(s["atr"][d] and s["c"][d]>0 and s["atr"][d]/s["c"][d]*100>3)
def check_ma60(c,s,d): return bool(s["mas"][60][d] and s["c"][d]>s["mas"][60][d])
def check_yang(c,s,d): return s["c"][d]>s["o"][d]
def check_ma5_up(c,s,d): return bool(s["mas"][5][d] and s["c"][d]>s["mas"][5][d])

conditions = [
    ("① 价<80", check_price),
    ("② 均线多头MA5>10>20>60", check_ma_bullish),
    ("③ MACD零轴上", check_macd),
    ("④ ATR>3%", check_atr),
    ("⑤ 站MA60", check_ma60),
    ("⑥ 阳线", check_yang),
    ("⑦ 站MA5", check_ma5_up),
]

print(f"\n{'='*80}")
print("📊 逐条件排查 — 每天通过该条件的平均股票数 (500只样本)")
print(f"{'='*80}")
print(f"{'条件':<28} {'2025日均':>10} {'2026日均':>10} {'变化':>10}")
print("-"*58)

for cname, cfn in conditions:
    totals_25=defaultdict(int)
    totals_26=defaultdict(int)
    
    for dt in dates_2025:
        for code,sd in all_codes.items():
            try:
                di=None
                for idx,r in enumerate(sd["recs"]):
                    if r["date"]==dt: di=idx; break
                if di is None or di<80: continue
                if cfn(code,sd,di): totals_25[dt]+=1
            except: continue
    
    for dt in dates_2026:
        for code,sd in all_codes.items():
            try:
                di=None
                for idx,r in enumerate(sd["recs"]):
                    if r["date"]==dt: di=idx; break
                if di is None or di<80: continue
                if cfn(code,sd,di): totals_26[dt]+=1
            except: continue
    
    avg25=sum(totals_25.values())/len(totals_25) if totals_25 else 0
    avg26=sum(totals_26.values())/len(totals_26) if totals_26 else 0
    chg=avg26-avg25
    chg_pct=chg/avg25*100 if avg25 else 0
    print(f"{cname:<28} {avg25:>7.1f}只 {avg26:>7.1f}只 {chg_pct:>+6.1f}%")

# ── 逐条件累积过滤 ──
print(f"\n{'='*80}")
print("🔍 条件累积过滤 — 一步步加条件，看哪里卡死")
print(f"{'='*80}")

for yr, dates in [("2025", dates_2025), ("2026", dates_2026)]:
    print(f"\n📅 {yr}年 ({len(dates)}天)")
    
    # 每天逐条件累积
    daily_by_cond = []
    
    for cname, cfn in conditions:
        daily_counts=[]
        for dt in dates:
            cnt=0
            for code,sd in all_codes.items():
                try:
                    di=None
                    for idx,r in enumerate(sd["recs"]):
                        if r["date"]==dt: di=idx; break
                    if di is None or di<80: continue
                    if not cfn(code,sd,di): continue
                    cnt+=1
                except: continue
            daily_counts.append(cnt)
        
        avg=sum(daily_counts)/len(daily_counts)
        ge5=sum(1 for c in daily_counts if c>=5)
        ge10=sum(1 for c in daily_counts if c>=10)
        print(f"  {cname:<22} 日均{avg:>5.1f}只  ≥5: {ge5:>3}/{len(dates)}天({ge5/len(dates)*100:.0f}%)  ≥10: {ge10:>3}/{len(dates)}天({ge10/len(dates)*100:.0f}%)")

# 看看2025年5月数据（最靠前的5月）
print(f"\n{'='*80}")
print("📅 2025年各月检查（看看是不是数据缺失）")
print(f"{'='*80}")
for yr, dates in [("2025", dates_2025), ("2026", dates_2026)]:
    months = defaultdict(list)
    for dt in dates:
        months[dt[:7]].append(dt)
    print(f"\n{yr}:")
    for m in sorted(months.keys()):
        print(f"  {m}: {len(months[m])}天")

print(f"\n⏱ {time.time()-t0:.0f}秒")
