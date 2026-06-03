
#!/usr/bin/env python3
"""小猪策略 — 底仓条件组合测试：找到每天10+候选的最优过滤"""
import json, os, time
from collections import defaultdict

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

print("📡 加载数据...")
all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files = [f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
print(f"📊 共{len(main_files)}只主板股")

# 加载部分（时间考虑，取全部）
import random; random.seed(42)
# 直接用全部
sample_files = main_files

all_codes = {}
loaded = 0
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
        
        # ATR
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14, len(c)):
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr_l)/14
        
        # 位置
        pos20=[None]*len(c)
        for i in range(19, len(c)):
            h20=max(h[i-19:i+1]); l20=min(l[i-19:i+1])
            pos20[i]=(c[i]-l20)/(h20-l20+0.001)*100
        pos60=[None]*len(c)
        for i in range(59, len(c)):
            h60=max(h[i-59:i+1]); l60=min(l[i-59:i+1])
            pos60[i]=(c[i]-l60)/(h60-l60+0.001)*100
        
        all_codes[code]={"c":c,"o":o,"h":h,"l":l,"v":v,"mas":mas,"dif":dif,"dea":dea,"macd":macd,"k":k,"d":d,"j":j,"pct":pct,"recs":recs,"atr":atr,"pos20":pos20,"pos60":pos60}
        loaded+=1
        if loaded%500==0: print(f"  {loaded}/{len(sample_files)}")
    except: pass

print(f"✅ 加载{loaded}只")

# 找出所有交易日
years = ["2026","2025","2024"]
all_test_dates = {}
for yr in years:
    dates = set()
    for code,sd in all_codes.items():
        for r in sd["recs"]:
            if r["date"].startswith(yr):
                dates.add(r["date"])
    all_test_dates[yr] = sorted(dates)
    print(f"📅 {yr}: {len(all_test_dates[yr])}交易日 ({all_test_dates[yr][0]}~{all_test_dates[yr][-1]})")

# ═══ 定义各种条件 ═══
# 每个条件是一个函数，返回True/False

def cond_ma_bullish(code, sd, di):
    """均线多头"""
    mas = sd["mas"]
    return (mas[5][di] and mas[10][di] and mas[20][di] and mas[60][di] and
            mas[5][di] > mas[10][di] > mas[20][di] > mas[60][di])

def cond_macd_above(code, sd, di):
    """MACD零轴上"""
    return (sd["dif"][di] and sd["dea"][di] and sd["dif"][di] > 0 and sd["dif"][di] > sd["dea"][di])

def cond_atr(code, sd, di, threshold=3.0):
    """ATR大于阈值"""
    atr = sd["atr"][di]; close = sd["c"][di]
    return atr and close > 0 and atr/close*100 > threshold

def cond_above_ma60(code, sd, di):
    """站上MA60"""
    return (sd["mas"][60][di] and sd["c"][di] > sd["mas"][60][di])

def cond_pos20(code, sd, di, lo=30, hi=85):
    """20日位置在范围内"""
    p = sd["pos20"][di]
    return p is not None and lo <= p <= hi

def cond_pct_range(code, sd, di, lo=-2, hi=6):
    """当日涨跌幅"""
    return lo <= sd["pct"][di] <= hi

def cond_ma5_slope(code, sd, di, min_slope=0):
    """MA5斜率"""
    if di < 4: return False
    mas = sd["mas"]
    return (mas[5][di] and mas[5][di-4] and mas[5][di-4] > 0 and
            (mas[5][di]-mas[5][di-4])/mas[5][di-4]*100 > min_slope)

def cond_vr_range(code, sd, di, lo=0.7, hi=5):
    """量比范围"""
    v5 = sd["mas"]["v5"][di] if sd["mas"]["v5"][di] else 0
    vr = sd["v"][di]/v5 if v5>0 else 0
    return lo <= vr <= hi

def cond_j_rising(code, sd, di):
    """J值上升"""
    j = sd["j"]
    return (j[di] and j[di-1] and j[di] > j[di-1])

def cond_yang(code, sd, di):
    """阳线"""
    return sd["c"][di] > sd["o"][di]

def cond_price(code, sd, di, max_price=80):
    """股价上限"""
    return sd["c"][di] < max_price

def cond_close_pos_above_ma5(code, sd, di):
    """收盘在MA5上方"""
    return (sd["mas"][5][di] and sd["c"][di] > sd["mas"][5][di])

def cond_macd_golden(code, sd, di):
    """MACD金叉"""
    dif,dea = sd["dif"],sd["dea"]
    return (di>=1 and dif[di] and dea[di] and dif[di-1] and dea[di-1] and
            dif[di-1] <= dea[di-1] and dif[di] > dea[di])

# ═══ 底仓组合测试 ═══
# 定义要测试的组合
COMBOS = [
    # (名称, 条件列表)
    ("M1: 均线多头+MACD+ATR>3%+站MA60+价<80+位20~85", 
     [cond_price, cond_ma_bullish, cond_macd_above, lambda c,s,d: cond_atr(c,s,d,3), cond_above_ma60, lambda c,s,d: cond_pos20(c,s,d,20,85)]),
    
    ("M2: M1+MA5斜率>0",
     [cond_price, cond_ma_bullish, cond_macd_above, lambda c,s,d: cond_atr(c,s,d,3), cond_above_ma60, lambda c,s,d: cond_pos20(c,s,d,20,85), lambda c,s,d: cond_ma5_slope(c,s,d,0)]),
    
    ("M3: M1+量比0.7~5+阳线",
     [cond_price, cond_ma_bullish, cond_macd_above, lambda c,s,d: cond_atr(c,s,d,3), cond_above_ma60, lambda c,s,d: cond_pos20(c,s,d,20,85), lambda c,s,d: cond_vr_range(c,s,d,0.7,5), cond_yang]),
    
    ("M4: M1+涨0~6%+阳线",
     [cond_price, cond_ma_bullish, cond_macd_above, lambda c,s,d: cond_atr(c,s,d,3), cond_above_ma60, lambda c,s,d: cond_pos20(c,s,d,20,85), cond_yang, lambda c,s,d: cond_pct_range(c,s,d,-2,6)]),
    
    ("M5: M1+涨0~6%+量比>0.7",
     [cond_price, cond_ma_bullish, cond_macd_above, lambda c,s,d: cond_atr(c,s,d,3), cond_above_ma60, lambda c,s,d: cond_pos20(c,s,d,20,85), lambda c,s,d: cond_pct_range(c,s,d,-2,6), lambda c,s,d: cond_vr_range(c,s,d,0.7,5)]),
    
    ("M6: M1+涨0~6%+量比0.7~5+阳线",
     [cond_price, cond_ma_bullish, cond_macd_above, lambda c,s,d: cond_atr(c,s,d,3), cond_above_ma60, lambda c,s,d: cond_pos20(c,s,d,20,85), lambda c,s,d: cond_pct_range(c,s,d,-2,6), lambda c,s,d: cond_vr_range(c,s,d,0.7,5), cond_yang]),
    
    # ATR放松版
    ("M7: M1-ATR>2.5%",
     [cond_price, cond_ma_bullish, cond_macd_above, lambda c,s,d: cond_atr(c,s,d,2.5), cond_above_ma60, lambda c,s,d: cond_pos20(c,s,d,20,85)]),
    
    ("M8: M1+MA5斜率>0+涨0~6%+量比0.7~5",
     [cond_price, cond_ma_bullish, cond_macd_above, lambda c,s,d: cond_atr(c,s,d,3), cond_above_ma60, lambda c,s,d: cond_pos20(c,s,d,20,85), lambda c,s,d: cond_ma5_slope(c,s,d,0), lambda c,s,d: cond_pct_range(c,s,d,-2,6), lambda c,s,d: cond_vr_range(c,s,d,0.7,5)]),
    
    # CG-05风格的严格版（但不卡涨幅）
    ("M9: CG-05底仓（涨4~5%放松到2~6%+MA5斜率≥8+位置≥40+量比≤2.5+J≥10）",
     [cond_price, lambda c,s,d: cond_pct_range(c,s,d,2,6), lambda c,s,d: cond_ma5_slope(c,s,d,8), cond_yang, lambda c,s,d: cond_vr_range(c,s,d,0,2.5)]),
    
    ("M10: M9+MACD零轴上+ATR>3%",
     [cond_price, cond_macd_above, lambda c,s,d: cond_atr(c,s,d,3), lambda c,s,d: cond_pct_range(c,s,d,2,6), lambda c,s,d: cond_ma5_slope(c,s,d,8), cond_yang, lambda c,s,d: cond_vr_range(c,s,d,0,2.5)]),
    
    # 尝试宽松版确保每天10+
    ("M11: 均线多头+MACD零轴上+价<80",
     [cond_price, cond_ma_bullish, cond_macd_above]),
    
    ("M12: 均线多头+MACD零轴上+ATR>2.5%+站MA60",
     [cond_price, cond_ma_bullish, cond_macd_above, lambda c,s,d: cond_atr(c,s,d,2.5), cond_above_ma60]),
    
    ("M13: 均线多头+MACD零轴上+ATR>3%+站MA60+涨0~6%+量比0.7~5",
     [cond_price, cond_ma_bullish, cond_macd_above, lambda c,s,d: cond_atr(c,s,d,3), cond_above_ma60, lambda c,s,d: cond_pct_range(c,s,d,-2,6), lambda c,s,d: cond_vr_range(c,s,d,0.7,5)]),
    
    # 更宽松确保10+
    ("M14: 均线多头+MACD零轴上+站MA60+MA5斜率>0+价<80",
     [cond_price, cond_ma_bullish, cond_macd_above, cond_above_ma60, lambda c,s,d: cond_ma5_slope(c,s,d,0)]),
    
    ("M15: 均线多头+MACD零轴上+ATR>3%+MA5斜率>0+价<80",
     [cond_price, cond_ma_bullish, cond_macd_above, lambda c,s,d: cond_atr(c,s,d,3), lambda c,s,d: cond_ma5_slope(c,s,d,0)]),
]

print(f"\n{'='*80}")
print("🧪 底仓条件组合测试 — 每种组合的每日候选数统计")
print(f"{'='*80}")

for yr in ["2026","2025","2024"]:
    dates = all_test_dates[yr]
    print(f"\n{'─'*80}")
    print(f"📅 {yr}年 ({len(dates)}个交易日)")
    print(f"{'─'*80}")
    print(f"{'组合名':<40} {'日均':>6} {'最少':>6} {'最多':>6} {'<10天':>8} {'<10%':>8} {'10+天':>8}")
    print("-"*80)
    
    results = []
    for name, conditions in COMBOS:
        daily_counts = []
        for td in dates:
            count = 0
            for code,sd in all_codes.items():
                try:
                    di = None
                    for idx, r in enumerate(sd["recs"]):
                        if r["date"] == td:
                            di = idx; break
                    if di is None or di < 80: continue
                    
                    ok = True
                    for cond in conditions:
                        if not cond(code, sd, di):
                            ok = False; break
                    if ok: count += 1
                except: pass
            daily_counts.append(count)
        
        avg = round(sum(daily_counts)/len(daily_counts), 0)
        mn = min(daily_counts)
        mx = max(daily_counts)
        lt10 = sum(1 for c in daily_counts if c < 10)
        lt10_pct = lt10/len(daily_counts)*100
        ge10 = sum(1 for c in daily_counts if c >= 10)
        
        results.append((lt10_pct, -ge10, avg, name, mn, mx, lt10, ge10))
    
    results.sort()
    for lt10_pct, neg_ge10, avg, name, mn, mx, lt10, ge10 in results:
        print(f"{name:<40} {avg:>5.0f} {mn:>5} {mx:>5} {lt10:>5}天 {lt10_pct:>6.1f}% {ge10:>5}天")
