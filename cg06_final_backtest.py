
#!/usr/bin/env python3
"""🐷 小猪策略 CG-06 最终版 — 尾盘选股，次日冲2.5%+卖出"""
import json, os, sys, time
from datetime import datetime

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
        dif[i]=e12[i]-e26[i]; dea[0]=dif[0] if dif[0] else 0
    for i in range(1,n):
        dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
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

def calc_score(code, sd, di):
    sc = 0; cl = sd["c"][di]; rec = sd["recs"][di]
    atr_p = sd["atr"][di]/cl*100 if sd["atr"][di] and cl>0 else 0
    sc += atr_p * 2
    if sd["pct"][di] > 0: sc += 10
    v5 = sd["mas"]["v5"][di] if sd["mas"]["v5"][di] else 0
    vr = sd["v"][di]/v5 if v5>0 else 0
    if 1 < vr < 2: sc += 15
    elif vr > 2: sc += 8
    sc += (sd["pos20"][di] or 50) * 0.2
    if sd["j"][di] and 50 < sd["j"][di] < 90: sc += 10
    # 扣分: 上影线太长
    up = rec["high"] - max(rec["close"], rec["open"])
    rng = rec["high"] - rec["low"]
    sr = up/(rng+0.001)*100
    if sr > 50: sc -= 10
    elif sr > 30: sc -= 3
    return sc

def filter_and_pick(stock_data, test_dates, min_candidates=10):
    """
    过滤+评分+选冠军
    底仓: 价<80 + 均线多头 + MACD零轴上 + ATR>3% + 站MA60 + 阳线 + 量比1~3 + J>50
    """
    results = []
    for td in test_dates:
        candidates = []
        for code, sd in stock_data.items():
            di = sd["date_idx"].get(td)
            if di is None or di < 80: continue
            cl = sd["c"][di]
            
            # ═══ 底仓硬过滤 ═══
            if cl > 80: continue
            m = sd["mas"]
            if not (m[5][di] and m[10][di] and m[20][di] and m[60][di]): continue
            if not (m[5][di] > m[10][di] > m[20][di] > m[60][di]): continue  # 均线多头
            if not (sd["dif"][di] and sd["dea"][di] and sd["dif"][di] > 0 and sd["dif"][di] > sd["dea"][di]): continue  # MACD零轴上
            if not (sd["atr"][di] and cl > 0 and sd["atr"][di]/cl*100 > 3): continue  # ATR>3%
            if not (m[60][di] and cl > m[60][di]): continue  # 站上MA60
            if not (sd["recs"][di]["close"] > sd["recs"][di]["open"]): continue  # 阳线
            v5 = m["v5"][di] if m["v5"][di] else 0
            vr = sd["v"][di]/v5 if v5>0 else 0
            if not (1 <= vr <= 3): continue  # 量比1~3
            if not (sd["j"][di] and sd["j"][di] > 50): continue  # J>50
            
            sc = calc_score(code, sd, di)
            fwd = sd["future"].get(td, (None, None, None))
            candidates.append((code, sc, fwd[0], fwd[1], fwd[2]))
        
        if len(candidates) >= min_candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            results.append({
                "date": td,
                "code": candidates[0][0],
                "score": candidates[0][1],
                "n_candidates": len(candidates),
                "d1_high": candidates[0][2],
                "d1_close": candidates[0][3],
                "max5": candidates[0][4],
            })
    
    return results

t0 = time.time()
print("=" * 70)
print("🐷 小猪策略 CG-06 最终版 — 全量回测")
print("=" * 70)

# 加载数据
print("\n📡 加载全量数据...")
all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files = [f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
print(f"📊 主板共 {len(main_files)} 只")

all_data = {}; loaded = 0
for fn in main_files:
    fp = os.path.join(CACHE_DIR, fn)
    try:
        with open(fp, 'rb') as f: recs = json.loads(f.read().decode('utf-8'))
        if len(recs) < 80: continue
        code = fn.replace('.json','')
        c=[r['close'] for r in recs]; h=[r['high'] for r in recs]; l=[r['low'] for r in recs]
        o=[r['open'] for r in recs]; v=[r['volume'] for r in recs]
        mas=calc_ma(c,[5,10,20,60]); mas['v5']=calc_ma(v,[5])[5]
        dif,dea,macd=calc_macd(c)
        k,d,j=calc_kdj(h,l,c)
        pct=[0.0]
        for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for n in range(14,len(c)):
                tr=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(n-13,n+1)]
                atr[n]=sum(tr)/14
        pos20=[None]*len(c)
        for n in range(19,len(c)):
            h20=max(h[n-19:n+1]); l20=min(l[n-19:n+1])
            pos20[n]=(c[n]-l20)/(h20-l20+0.001)*100
        
        date_idx = {}
        for i, rr in enumerate(recs):
            date_idx[rr["date"]] = i
        
        # 预计算未来表现
        future = {}
        for i in range(len(c)-5):
            dt = recs[i]["date"]
            buy = c[i]
            if buy <= 0: continue
            d1h = round((h[i+1]/buy-1)*100,2)
            d1c = round((c[i+1]/buy-1)*100,2)
            after = c[i+1:i+6]
            m5 = round(max(after)/buy*100-100,2) if len(after)==5 else None
            future[dt] = (d1h, d1c, m5)
        
        all_data[code] = {
            "c":c,"h":h,"l":l,"o":o,"v":v,
            "mas":mas,"dif":dif,"dea":dea,"macd":macd,
            "k":k,"d":d,"j":j,"pct":pct,"atr":atr,"pos20":pos20,
            "recs":recs,"date_idx":date_idx,"future":future
        }
        loaded+=1
        if loaded%500==0: print(f"  {loaded}/{len(main_files)}")
    except: pass

print(f"✅ 加载 {loaded} 只")

# 跑回测
for yr in ["2026","2025"]:
    test_dates = sorted(set(
        dt for code,sd in all_data.items() for dt in sd["date_idx"].keys() if dt.startswith(yr)
    ))
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"📅 {yr}年 {len(test_dates)}个交易日")
    print(f"{sep}")
    
    res = filter_and_pick(all_data, test_dates)
    print(f"\n🎯 底仓：均线多头+MACD零轴上+ATR>3%+站MA60+阳线+量比1~3+J>50")
    print(f"   出票: {len(res)}/{len(test_dates)}天 ({len(res)/len(test_dates)*100:.1f}%)")
    
    if not res: continue
    
    n = len(res)
    d1h = [d["d1_high"] for d in res if d["d1_high"] is not None]
    d1c = [d["d1_close"] for d in res if d["d1_close"] is not None]
    m5 = [d["max5"] for d in res if d["max5"] is not None]
    nc = [d["n_candidates"] for d in res]
    
    h25 = sum(1 for v in d1h if v >= 2.5)
    h5 = sum(1 for v in m5 if v >= 5)
    h10 = sum(1 for v in m5 if v >= 10)
    
    print(f"\n📊 每日候选数:")
    print(f"   平均: {sum(nc)/n:.0f}只 | 最少: {min(nc)}只 | 最多: {max(nc)}只")
    print(f"   <10只的天数: {sum(1 for v in nc if v<10)}/{n}天")
    
    print(f"\n🎯 次日表现（核心指标）:")
    print(f"   冲2.5%+: {h25}/{n}天 = {h25/n*100:.1f}% ✅")
    print(f"   平均最高: {sum(d1h)/len(d1h):.2f}%")
    print(f"   平均收盘: {sum(d1c)/len(d1c):.2f}%")
    
    print(f"\n📈 5日表现:")
    print(f"   5日10%+: {h10}/{n}天 ({h10/n*100:.1f}%)")
    print(f"   5日5%+: {h5}/{n}天 ({h5/n*100:.1f}%)")
    print(f"   平均最高: {sum(m5)/len(m5):.1f}%")
    
    # 按月统计
    months = {}
    for d in res:
        m = d["date"][:7]
        if m not in months: months[m] = {"total":0,"hit25":0,"hit10":0}
        months[m]["total"]+=1
        if d["d1_high"] and d["d1_high"]>=2.5: months[m]["hit25"]+=1
        if d["max5"] and d["max5"]>=10: months[m]["hit10"]+=1
    
    print(f"\n📆 按月:")
    for m in sorted(months.keys()):
        ms = months[m]
        print(f"   {m}: {ms['total']}天出票 | 次日2.5%+: {ms['hit25']}/{ms['total']}({ms['hit25']/ms['total']*100:.0f}%) | 5日10%+: {ms['hit10']}/{ms['total']}({ms['hit10']/ms['total']*100:.0f}%)")

print(f"\n{'='*70}")
print(f"⏱ 总耗时: {(time.time()-t0)/60:.1f}分钟")
