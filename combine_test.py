
#!/usr/bin/env python3
"""组合最强条件 — 找出次日2.5%+的最优过滤"""
import json, os, random, time

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

def calc_ma(s, p):
    n = len(s); r = {}
    for pd in p:
        ma = [None]*n
        for i in range(pd-1,n): ma[i] = sum(s[i-pd+1:i+1])/pd
        r[pd] = ma
    return r

def calc_macd(ps):
    n = len(ps); dif=[None]*n; dea=[None]*n; macd=[None]*n
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

import random; random.seed(42)
all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files = [f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
sample_files = sorted(random.sample(main_files, min(600, len(main_files))))

print(f"📊 {len(main_files)}只→采样{len(sample_files)}只")

# Collect features + outcomes
all_data = []
processed = 0

for fn in sample_files:
    fp = os.path.join(CACHE_DIR, fn)
    try:
        with open(fp,'rb') as f: recs = json.loads(f.read().decode('utf-8'))
        if len(recs)<80: continue
        code = fn.replace('.json','')
        c=[r['close'] for r in recs]; h=[r['high'] for r in recs]; l=[r['low'] for r in recs]
        o=[r['open'] for r in recs]; v=[r['volume'] for r in recs]
        mas=calc_ma(c,[5,10,20,60]); mas['v5']=calc_ma(v,[5])[5]
        dif,dea,macd=calc_macd(c)
        k,d,j=calc_kdj(h,l,c)
        pct=[0.0]
        for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
        
        for i in range(60,len(recs)-1):
            rec=recs[i]; close=c[i]
            nr=recs[i+1]; nh=(nr['high']-close)/close*100
            win=nh>=2.5
            
            rng=rec['high']-rec['low']; rpos=(close-rec['low'])/(rng+0.001)*100
            body=abs(close-rec['open']); bp=body/rec['open']*100
            yang=close>rec['open']
            us=rec['high']-max(close,rec['open']); ls=min(close,rec['open'])-rec['low']
            sr=us/(us+ls+0.001)*100
            
            vr=v[i]/mas['v5'][i] if mas['v5'][i] else 0
            
            ma5_slope=(mas[5][i]-mas[5][i-4])/mas[5][i-4]*100 if i>=4 and mas[5][i] and mas[5][i-4] else None
            
            bm = (mas[5][i] and mas[10][i] and mas[20][i] and mas[60][i] and
                  mas[5][i] > mas[10][i] > mas[20][i] > mas[60][i]) if (mas[5][i] and mas[10][i] and mas[20][i] and mas[60][i]) else False
            
            am60 = close > mas[60][i] if mas[60][i] else False
            am20 = close > mas[20][i] if mas[20][i] else False
            
            macd_ok = dif[i] and dea[i] and dif[i] > dea[i] and dif[i] > 0
            macd_golden = (i>=1 and dif[i] and dea[i] and dif[i-1] and dea[i-1] and dif[i-1]<=dea[i-1] and dif[i]>dea[i])
            
            kdj_golden = (i>=1 and k[i] and d[i] and k[i-1] and d[i-1] and k[i-1]<=d[i-1] and k[i]>d[i])
            k_over_d = k[i] > d[i] if (k[i] and d[i]) else False
            j_gt_50 = j[i] > 50 if j[i] else False
            
            # 20日位置
            if i>=19: h20=max(h[i-19:i+1]); l20=min(l[i-19:i+1])
            else: h20=max(h[:i+1]); l20=min(l[:i+1])
            p20=(close-l20)/(h20-l20+0.001)*100
            
            # ATR
            atr_v=None
            if i>=14:
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr_v=sum(tr_l)/14
            atr_pct=(atr_v/close*100) if atr_v and close>0 else None
            
            all_data.append({
                "win": win, "pct": round(pct[i],2), "bp": round(bp,2),
                "yang": yang, "rpos": round(rpos,1), "sr": round(sr,1),
                "vr": round(vr,2), "bm": bm, "am60": am60, "am20": am20,
                "macd_ok": macd_ok, "macd_golden": macd_golden,
                "kdj_golden": kdj_golden, "k_over_d": k_over_d, "j_gt_50": j_gt_50,
                "ma5_slope": round(ma5_slope,2) if ma5_slope else None,
                "p20": round(p20,1), "atr_pct": round(atr_pct,2) if atr_pct else None,
            })
        
        processed += 1
        if processed%200==0: print(f"  {processed}/{len(sample_files)}")
    except: pass

print(f"\n✅ 共{len(all_data)}样本, 赢家{sum(1 for d in all_data if d['win'])}次({sum(1 for d in all_data if d['win'])/len(all_data)*100:.1f}%)")

# ═══ 测试各种条件组合 ═══
def test(cond, name):
    selected = [d for d in all_data if cond(d)]
    tot = len(selected)
    hit = sum(1 for d in selected if d["win"])
    rate = hit/tot*100 if tot>0 else 0
    cov = hit/sum(1 for d in all_data if d["win"])*100
    return tot, hit, rate, cov

combos = [
    ("放量上攻(量比>1.5+阳线+高位收盘)", lambda d: d["yang"] and d["vr"]>1.5 and d["rpos"]>66),
    ("光头阳线(上影<15%+高位收盘)", lambda d: d["yang"] and d["sr"]<15 and d["rpos"]>70),
    ("均线多头+量比>1", lambda d: d["bm"] and d["vr"]>1),
    ("均线多头+放量(量比>1.5)", lambda d: d["bm"] and d["vr"]>1.5),
    ("均线多头+阳线+量比>1", lambda d: d["bm"] and d["yang"] and d["vr"]>1),
    ("均线多头+站上MA60+量比>1", lambda d: d["bm"] and d["am60"] and d["vr"]>1),
    ("均线多头+MACD零轴上+K>D", lambda d: d["bm"] and d["macd_ok"] and d["k_over_d"]),
    ("均线多头+MACD零轴上+量比>1", lambda d: d["bm"] and d["macd_ok"] and d["vr"]>1),
    ("放量突破(量比>1.5+阳线+rpos>66+均线多头)", lambda d: d["yang"] and d["vr"]>1.5 and d["rpos"]>66 and d["bm"]),
    ("放量突破+均线多头+MACD", lambda d: d["yang"] and d["vr"]>1.5 and d["rpos"]>66 and d["bm"] and d["macd_ok"]),
    ("均线多头+MACD+阳线+量比1~3", lambda d: d["bm"] and d["macd_ok"] and d["yang"] and 1<=d["vr"]<=3),
    ("均线多头+位置40~80%+量比>1", lambda d: d["bm"] and 40<=d["p20"]<=80 and d["vr"]>1),
    ("均线多头+ATR>3%+MACD", lambda d: d["bm"] and (d["atr_pct"] or 0)>3 and d["macd_ok"]),
    ("均线多头+MACD+位置40~80%+量比>1", lambda d: d["bm"] and d["macd_ok"] and 40<=d["p20"]<=80 and d["vr"]>1),
    ("站上MA60+均线多头+MACD+量比>1", lambda d: d["am60"] and d["bm"] and d["macd_ok"] and d["vr"]>1),
    ("均线多头+MACD+阳线+量比>1+ATR>3%", lambda d: d["bm"] and d["macd_ok"] and d["yang"] and d["vr"]>1 and (d["atr_pct"] or 0)>3),
    ("均线多头+MACD+位置40~80%+量比>1+阳线", lambda d: d["bm"] and d["macd_ok"] and 40<=d["p20"]<=80 and d["vr"]>1 and d["yang"]),
    # 超严格组合
    ("放量上攻+均线多头+MACD+位置40~80%", lambda d: d["yang"] and d["vr"]>1.5 and d["rpos"]>66 and d["bm"] and d["macd_ok"] and 40<=d["p20"]<=80),
    ("放量上攻+均线多头+MACD+站MA60", lambda d: d["yang"] and d["vr"]>1.5 and d["rpos"]>66 and d["bm"] and d["macd_ok"] and d["am60"]),
    ("放量上攻+均线多头+MACD+量比>1.5+ATR>3%", lambda d: d["yang"] and d["vr"]>1.5 and d["rpos"]>66 and d["bm"] and d["macd_ok"] and (d["atr_pct"] or 0)>3),
]

baseline = sum(1 for d in all_data if d["win"])/len(all_data)*100

print(f"\n{'='*70}")
print(f"🧪 条件组合胜率测试（排序：胜率从高到低）")
print(f"基础概率: {baseline:.1f}%")
print(f"{'='*70}")
print(f"{'组合条件':<34} {'命中/总数':>12} {'胜率':>8} {'覆盖':>8}")
print("-"*64)

results = []
for name, cond in combos:
    tot, hit, rate, cov = test(cond, name)
    results.append((rate, tot, hit, cov, name))

results.sort(reverse=True)

for rate, tot, hit, cov, name in results:
    lift = rate/baseline if baseline>0 else 0
    print(f"{name:<34} {hit:>4}/{tot:<6} {rate:>5.1f}% {cov:>5.1f}% (↑{lift:.2f}x)")

# Also show best looser combinations (higher coverage)
print(f"\n{'='*70}")
print(f"📊 最佳平衡组合（胜率>30%+覆盖>10%）")
print(f"{'='*70}")
print(f"{'组合条件':<34} {'命中/总数':>12} {'胜率':>8} {'覆盖':>8}")
print("-"*64)
balanced = [(r,t,h,c,n) for r,t,h,c,n in results if r>30 and c>10]
for rate, tot, hit, cov, name in sorted(balanced, reverse=True):
    lift = rate/baseline if baseline>0 else 0
    print(f"{name:<34} {hit:>4}/{tot:<6} {rate:>5.1f}% {cov:>5.1f}% (↑{lift:.2f}x)")
