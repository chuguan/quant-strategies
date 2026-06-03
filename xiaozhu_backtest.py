
#!/usr/bin/env python3
"""小猪策略 — 每日选票数统计 + 冠军回测"""
import json, os, sys
from datetime import datetime

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

print("📡 加载全部股票数据...")
all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
# 全量沪深主板
main_files = [f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
print(f"📊 沪深主板共 {len(main_files)} 只")

all_codes = {}
loaded = 0
for fn in main_files:
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
        
        # 预计算ATR
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14, len(c)):
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr_l)/14
        
        all_codes[code]={"c":c,"h":h,"l":l,"o":o,"v":v,"mas":mas,"dif":dif,"dea":dea,"macd":macd,"k":k,"d":d,"j":j,"pct":pct,"recs":recs,"atr":atr}
        loaded+=1
        if loaded%500==0: print(f"  已加载 {loaded}/{len(main_files)}")
    except: pass

print(f"✅ 加载 {loaded} 只")

# 找所有交易日
year = "2026"
all_dates = set()
for code,sd in all_codes.items():
    for r in sd["recs"]:
        if r["date"].startswith(year):
            all_dates.add(r["date"])
test_dates = sorted(all_dates)
print(f"📅 {year}年共 {len(test_dates)} 个交易日")

# 预计算未来5日表现
print("📡 预计算未来5日高涨幅...")
future_lookup = {}
for code,sd in all_codes.items():
    recs = sd["recs"]
    for i in range(len(recs)-5):
        dt = recs[i]["date"]
        buy = recs[i]["close"]
        if buy<=0: continue
        after = recs[i+1:i+6]
        m5 = round(max(x["high"] for x in after)/buy*100-100,1) if after else None
        d1 = round(recs[i+1]["high"]/buy*100-100,1) if i+1<len(recs) else None
        future_lookup[(code,dt)] = (m5, d1)

# ═══ 核心过滤条件 ═══
# 均线多头 + MACD零轴上 + ATR>3% + (可选)
# 加上简单评分

import time
t0 = time.time()

def filter_stock(code, sd, di, td):
    """检查当日是否符合条件，返回(通过, 评分)"""
    rec = sd["recs"][di]
    close = sd["c"][di]; open_p = sd["o"][di]; vol = sd["v"][di]
    pct = sd["pct"][di]; high = sd["h"][di]; low = sd["l"][di]
    mas = sd["mas"]; dif = sd["dif"]; dea = sd["dea"]; macd = sd["macd"]
    k = sd["k"]; d = sd["d"]; j = sd["j"]; atr = sd["atr"]
    
    # ---- 硬过滤 ----
    # 1. 股价<80
    if close > 80: return False, 0
    
    # 2. 非ST/退市（通过文件名已筛）
    
    # 3. 均线多头 MA5>MA10>MA20>MA60
    if not (mas[5][di] and mas[10][di] and mas[20][di] and mas[60][di]): return False, 0
    if not (mas[5][di] > mas[10][di] > mas[20][di] > mas[60][di]): return False, 0
    
    # 4. MACD零轴上 DIF>0且DIF>DEA
    if not (dif[di] and dea[di] and dif[di] > 0 and dif[di] > dea[di]): return False, 0
    
    # 5. ATR% > 3%
    if not (atr[di] and close > 0): return False, 0
    atr_pct = atr[di] / close * 100
    if atr_pct <= 3: return False, 0
    
    # 6. 当日不能涨太多（尾盘选股不追涨停）
    if pct > 6: return False, 0
    
    # 7. 站上MA60（作为额外保障）
    if not (mas[60][di] and close > mas[60][di]): return False, 0
    
    # 8. 20日位置不要太高
    if di >= 19:
        h20 = max(sd["h"][di-19:di+1])
        l20 = min(sd["l"][di-19:di+1])
    else:
        h20 = max(sd["h"][:di+1]); l20 = min(sd["l"][:di+1])
    pos20 = (close - l20) / (h20 - l20 + 0.001) * 100
    if pos20 > 85: return False, 0  # 不要追高
    
    # ---- 评分 ----
    score = 0
    
    # MACD强度
    macd_r = dif[di]/close*100
    if macd_r > 5: score += 25
    elif macd_r > 2: score += 20
    elif macd_r > 1: score += 15
    elif macd_r > 0: score += 8
    
    # 当日涨幅评分（不要太弱的也不要太强的）
    if pct > 0: score += 10
    elif pct > -1: score += 5
    
    # 量比
    v5 = mas["v5"][di] if mas["v5"][di] else 0
    vr = vol / v5 if v5 > 0 else 0
    if 1 <= vr <= 3: score += 15
    elif vr > 3: score += 8
    elif vr > 0.7: score += 5
    
    # 位置评分（中位最好）
    if 40 <= pos20 <= 70: score += 15
    elif 30 <= pos20 <= 80: score += 8
    
    # ATR评分（波动越大越好）
    if atr_pct > 5: score += 10
    elif atr_pct > 4: score += 5
    
    # J值
    if j[di] and 50 < j[di] < 90: score += 8
    elif j[di] and j[di] > 90: score -= 5  # 超买
    
    # 实体
    body_pct = abs(close - open_p) / open_p * 100
    if body_pct > 1.5: score += 5
    
    # 扣分：高上影线
    upper = high - max(close, open_p)
    rng = high - low
    sr = upper / (rng + 0.001) * 100
    if sr > 50: score -= 8
    elif sr > 30: score -= 3
    
    # 前日涨太多的降分
    if di >= 1 and sd["pct"][di-1] > 3: score -= 5
    
    return True, score

print(f"🚀 开始回测 {year}年 ({len(test_dates)}天)")
print(f"   过滤条件：均线多头+MACD零轴上+ATR>3%+站MA60+位置<85%")

daily_stats = []
champion_days = []

for td_idx, td in enumerate(test_dates):
    candidates = []
    passing_count = 0
    
    for code,sd in all_codes.items():
        di = sd["recs"][0]["date"]
        # Find index for this date
        date_idx = None
        for idx, r in enumerate(sd["recs"]):
            if r["date"] == td:
                date_idx = idx
                break
        if date_idx is None or date_idx < 80: continue
        
        ok, score = filter_stock(code, sd, date_idx, td)
        if ok:
            passing_count += 1
            # Get future performance
            fwd = future_lookup.get((code, td), (None, None))
            candidates.append((code, score, fwd[0], fwd[1]))
    
    # Pick champion (highest score)
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        champ = candidates[0]
        daily_stats.append({
            "date": td,
            "passing": passing_count,
            "candidates": len(candidates),
            "champ_code": champ[0], "champ_score": champ[1],
            "max5": champ[2], "d1_high": champ[3]
        })
        champion_days.append(champ)
    
    if (td_idx+1) % 20 == 0:
        dt = time.time()-t0
        print(f"  {td} / {td_idx+1}/{len(test_dates)}天 | 当日通过{passing_count}只选{len(candidates)}只 | 冠军{champ[0] if candidates else '-'} | {dt:.0f}s")

print(f"\n{'='*70}")
print(f"📊 小猪策略 — {year}年回测结果")
print(f"{'='*70}")

total_days = len(test_dates)
pick_days = len(champion_days)
avg_passing = sum(d["passing"] for d in daily_stats) / len(daily_stats) if daily_stats else 0
avg_candidates = sum(d["candidates"] for d in daily_stats) / len(daily_stats) if daily_stats else 0

print(f"\n📅 交易日: {total_days}天")
print(f"🎯 出票: {pick_days}天 ({pick_days/total_days*100:.1f}%)")
print(f"📊 日均通过过滤: {avg_passing:.0f}只 (全部股票)")
print(f"📊 日均候选(量比>0.7有成交量): {avg_candidates:.0f}只")

# 冠军表现统计
if champion_days:
    all_max5 = [d[2] for d in champion_days if d[2] is not None]
    all_d1 = [d[3] for d in champion_days if d[3] is not None]
    
    hit10 = sum(1 for v in all_max5 if v >= 10) if all_max5 else 0
    hit5 = sum(1 for v in all_max5 if v >= 5) if all_max5 else 0
    hit25_d1 = sum(1 for v in all_d1 if v >= 2.5) if all_d1 else 0
    
    avg_max5 = round(sum(all_max5)/len(all_max5),1) if all_max5 else 0
    avg_d1 = round(sum(all_d1)/len(all_d1),1) if all_d1 else 0
    
    print(f"\n🏆 冠军5日表现:")
    print(f"   5日最高10%+: {hit10}/{len(all_max5)}天 ({hit10/len(all_max5)*100:.1f}%)")
    print(f"   5日最高5%+: {hit5}/{len(all_max5)}天 ({hit5/len(all_max5)*100:.1f}%)")
    print(f"   平均5日最高: {avg_max5}%")
    print(f"\n🎯 次日表现:")
    print(f"   次日冲2.5%+: {hit25_d1}/{len(all_d1)}天 ({hit25_d1/len(all_d1)*100:.1f}%)")
    print(f"   次日平均最高: {avg_d1}%")
    
    # 按月统计
    months = {}
    for d in daily_stats:
        if d["candidates"] > 0:
            m = d["date"][:7]
            if m not in months: months[m] = {"days":0,"passing":[],"candidates":[]}
            months[m]["days"]+=1
            months[m]["passing"].append(d["passing"])
            months[m]["candidates"].append(d["candidates"])
    
    print(f"\n📆 按月统计:")
    for m in ["2026-01","2026-02","2026-03","2026-04","2026-05"]:
        if m in months:
            ms = months[m]
            avg_p = round(sum(ms["passing"])/len(ms["passing"]),0)
            avg_c = round(sum(ms["candidates"])/len(ms["candidates"]),0)
            champ_m = [d for d in champion_days if d.date.startswith(m)]
            mh = sum(1 for d in champ_m if d[2] and d[2]>=10)
            print(f"   {m}: {ms['days']}天出票 | 日均通过{avg_p:.0f}只 | 候选{avg_c:.0f}只 | 10%+ {mh}/{len(champ_m)}天")

# 每日通过数分布
if daily_stats:
    passing_counts = [d["passing"] for d in daily_stats if d["candidates"]>0]
    if passing_counts:
        print(f"\n📊 出票日通过数分布:")
        print(f"   最少: {min(passing_counts)}只 | 最多: {max(passing_counts)}只 | 中位: {sorted(passing_counts)[len(passing_counts)//2]}只")

print(f"\n⏱ 总耗时: {(time.time()-t0)/60:.1f}分钟")
