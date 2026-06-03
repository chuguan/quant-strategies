
#!/usr/bin/env python3
"""高效版 — 预计算所有条件标志位，快速搜索最优组合"""
import json, os, sys, time, random
from itertools import product
import collections

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
print("📡 加载数据...")
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files=[f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
random.seed(42); sample_files=sorted(random.sample(main_files,800))

all_codes={}
stock_days=[]  # [(date, code, features_dict), ...]

loaded=0
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
                tr=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr)/14
        pos20=[None]*len(c)
        for i in range(19,len(c)):
            h20=max(h[i-19:i+1]); l20=min(l[i-19:i+1])
            pos20[i]=(c[i]-l20)/(h20-l20+0.001)*100
        ma5_slope=[None]*len(c)
        for i in range(4,len(c)):
            if mas[5][i] and mas[5][i-4]: ma5_slope[i]=(mas[5][i]-mas[5][i-4])/mas[5][i-4]*100
        
        for i in range(80, len(c)-1):
            dt=dts[i]
            if not (dt.startswith("2025") or dt.startswith("2026")): continue
            
            # Pre-compute ALL condition flags here
            flags = {}
            cl=c[i]; op=o[i]; hi=h[i]; lo=l[i]; vo=v[i]
            
            flags["price"] = cl < 80
            
            # 均线条件
            flags["ma_bullish_full"] = bool(mas[5][i] and mas[10][i] and mas[20][i] and mas[60][i] and mas[5][i]>mas[10][i]>mas[20][i]>mas[60][i])
            flags["ma_bullish_med"] = bool(mas[5][i] and mas[10][i] and mas[20][i] and mas[5][i]>mas[10][i]>mas[20][i])
            flags["ma_bullish_simple"] = bool(mas[5][i] and mas[10][i] and mas[5][i]>mas[10][i])
            
            # MACD条件
            flags["macd_strict"] = bool(dif[i] and dea[i] and dif[i]>0 and dif[i]>dea[i])
            flags["macd_loose"] = bool(dif[i] and dea[i] and dif[i]>dea[i])
            
            # ATR条件
            atr_pct = atr[i]/cl*100 if atr[i] and cl>0 else 0
            flags["atr3"] = atr_pct > 3
            flags["atr2"] = atr_pct > 2
            flags["atr1"] = atr_pct > 1
            
            # MA60
            flags["ma60"] = bool(mas[60][i] and cl > mas[60][i])
            
            # 其他常用条件
            flags["yang"] = cl > op
            flags["no_shadow"] = (hi-max(cl,op))/(hi-lo+0.001)*100 < 30
            flags["vol_active"] = bool(mas["v5"][i] and vo/mas["v5"][i] >= 0.7)
            vr = vo/mas["v5"][i] if mas["v5"][i] else 0
            flags["vr_good"] = 1 <= vr <= 3
            flags["pct_neg"] = pct[i] <= -2
            flags["pct_ok"] = -2 <= pct[i] <= 6
            flags["pos20_ok"] = pos20[i] is not None and 20 <= pos20[i] <= 85
            
            # KDJ
            flags["j_good"] = bool(j[i] and 50 < j[i] < 90)
            flags["k_over_d"] = bool(k[i] and d[i] and k[i] > d[i])
            
            # MA5斜率
            flags["ma5pos"] = bool(mas[5][i] and cl > mas[5][i])
            flags["ma5_slope_pos"] = ma5_slope[i] is not None and ma5_slope[i] > 0
            
            # 次日表现
            next_h = (recs[i+1]["high"]/cl-1)*100
            flags["next_win"] = next_h >= 2.5
            
            # 评分因子
            macd_r = dif[i]/cl*100 if dif[i] and cl>0 else 0
            score = 0
            score += atr_pct * 2
            if pct[i] > 0: score += 10
            if 1 < vr < 2: score += 15
            elif vr > 2: score += 8
            score += (pos20[i] or 50) * 0.2
            if flags["j_good"]: score += 10
            
            stock_days.append({
                "date": dt, "code": code,
                "score": score, **flags
            })
        
        loaded+=1
        if loaded%200==0: print(f"  {loaded}/{len(sample_files)} ({len(stock_days)} rows)")
    except: pass

print(f"✅ {loaded}只, {len(stock_days)}条记录")
print(f"   其中2025: {sum(1 for x in stock_days if x['date'].startswith('2025'))}条")
print(f"   其中2026: {sum(1 for x in stock_days if x['date'].startswith('2026'))}条")

# 按日期分组
from collections import defaultdict
by_date = defaultdict(list)
for sd in stock_days:
    by_date[sd["date"]].append(sd)

# ═══ 高效搜索 ═══
def evaluate_combo(cond_flags, min_candidates=10, year="2026"):
    """
    cond_flags: list of flag names that must ALL be True
    Returns: (pick_rate, avg_candidates, min_candidates_actual, win_rate)
    """
    # Get relevant dates
    all_dates = sorted(set(sd["date"] for sd in stock_days if sd["date"].startswith(year)))
    
    total_days = len(all_dates)
    pick_days = 0
    all_candidate_counts = []
    win_count = 0
    
    for dt in all_dates:
        cand = [sd for sd in by_date[dt] if all(sd[f] for f in cond_flags)]
        n = len(cand)
        all_candidate_counts.append(n)
        
        if n >= min_candidates:
            pick_days += 1
            # Pick champion (highest score)
            cand.sort(key=lambda x: x["score"], reverse=True)
            if cand[0]["next_win"]:
                win_count += 1
    
    pick_rate = pick_days / total_days * 100 if total_days else 0
    avg_cand = sum(all_candidate_counts) / total_days if total_days else 0
    min_cand = min(all_candidate_counts) if all_candidate_counts else 0
    win_rate = win_count / pick_days * 100 if pick_days else 0
    
    return pick_rate, avg_cand, min_cand, win_rate

# ═══ 搜索 ═══
# 定义条件组
all_flags = [
    "price","ma_bullish_full","ma_bullish_med","ma_bullish_simple",
    "macd_strict","macd_loose",
    "atr3","atr2","atr1",
    "ma60","yang","vol_active","vr_good","pct_ok","pos20_ok",
    "j_good","k_over_d","no_shadow","ma5pos","ma5_slope_pos"
]

# 起始基础（最严格）
BASE = ["price"]

# 从最严格开始，逐步添加条件
print(f"\n{'='*80}")
print(f"🔍 自动搜索最优底仓条件")
print(f"{'='*80}")

# 先测试一系列预定义组合
test_sets = [
    # (名称, 条件列表)
    ("M1:多头全+MACD严+ATR3+MA60", BASE+["ma_bullish_full","macd_strict","atr3","ma60"]),
    ("M11:多头全+MACD严+MA60", BASE+["ma_bullish_full","macd_strict","ma60"]),
    ("多头全+MACD严+ATR2+MA60", BASE+["ma_bullish_full","macd_strict","atr2","ma60"]),
    ("多头全+MACD严+ATR1+MA60", BASE+["ma_bullish_full","macd_strict","atr1","ma60"]),
    ("多头中+MACD严+ATR3+MA60", BASE+["ma_bullish_med","macd_strict","atr3","ma60"]),
    ("多头中+MACD严+MA60", BASE+["ma_bullish_med","macd_strict","ma60"]),
    ("多头中+MACD松+MA60", BASE+["ma_bullish_med","macd_loose","ma60"]),
    ("多头全+MACD严+ATR3", BASE+["ma_bullish_full","macd_strict","atr3"]),
    ("多头全+MACD严", BASE+["ma_bullish_full","macd_strict"]),
    ("多头中+MACD严", BASE+["ma_bullish_med","macd_strict"]),
    ("多头中+MA60", BASE+["ma_bullish_med","ma60"]),
    ("多头中+MACD松", BASE+["ma_bullish_med","macd_loose"]),
    ("多头简+MACD松", BASE+["ma_bullish_simple","macd_loose"]),
    ("多头简+MACD松+vol", BASE+["ma_bullish_simple","macd_loose","vol_active"]),
]

print(f"\n{'组合':<28} {'2025出票':>10} {'2025候选':>8} {'2025最低':>8} {'2025胜率':>8} {'2026出票':>10} {'2026候选':>8} {'2026胜率':>8}")
print("-"*84)

results_list = []

for name, flags in test_sets:
    r25, c25, m25, w25 = evaluate_combo(flags, 10, "2025")
    r26, c26, m26, w26 = evaluate_combo(flags, 10, "2026")
    
    print(f"{name:<28} {r25:>6.1f}% {c25:>5.0f} {m25:>4} {w25:>6.1f}% {r26:>6.1f}% {c26:>5.0f} {w26:>6.1f}%")
    
    results_list.append({
        "name": name, "flags": flags,
        "2025": {"rate":r25,"avg":c25,"min":m25,"win":w25},
        "2026": {"rate":r26,"avg":c26,"min":m26,"win":w26}
    })

# 找出同时满足条件的
print(f"\n{'='*80}")
print(f"🏆 搜索结果：同时满足2025+2026出票>95%且胜率>60%的组合")
print(f"{'='*80}")

found = False
for r in results_list:
    if r["2025"]["rate"] >= 95 and r["2026"]["rate"] >= 95 and r["2025"]["win"] >= 60 and r["2026"]["win"] >= 60:
        if not found:
            print(f"\n{'名称':<28} {'2025胜率':>10} {'2025候选':>10} {'2026胜率':>10} {'2026候选':>10}")
            print("-"*72)
            found = True
        print(f"{r['name']:<28} {r['2025']['win']:>7.1f}% {r['2025']['avg']:>7.0f} {r['2026']['win']:>7.1f}% {r['2026']['avg']:>7.0f}")

if not found:
    print("没有同时满足出票>95%+胜率>60%的组合，放宽到出票>90%+胜率>55%:")
    
    print(f"\n{'名称':<28} {'2025出票':>10} {'2025胜率':>10} {'2026出票':>10} {'2026胜率':>10}")
    print("-"*72)
    
    # Score by combined metric
    scored = []
    for r in results_list:
        s25 = r["2025"]["win"] if r["2025"]["rate"] >= 90 else r["2025"]["win"] * r["2025"]["rate"]/100
        s26 = r["2026"]["win"] if r["2026"]["rate"] >= 90 else r["2026"]["win"] * r["2026"]["rate"]/100
        total_score = s25 + s26
        scored.append((total_score, r))
    
    scored.sort(reverse=True)
    for score, r in scored[:10]:
        print(f"{r['name']:<28} {r['2025']['rate']:>7.1f}% {r['2025']['win']:>7.1f}% {r['2026']['rate']:>7.1f}% {r['2026']['win']:>7.1f}%")

print(f"\n⏱ {(time.time()-t0)/60:.1f}分钟")
