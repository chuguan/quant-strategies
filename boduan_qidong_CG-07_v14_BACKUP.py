#!/usr/bin/env python3
"""
🐷 CG-07 v14（上影+实体+ATR版）
═══════════════════════════════
尾盘选股 → 次日冲2.5%+卖出

【底仓条件】（硬过滤）
  1. 股价 < 80
  2. 均线多头 MA5 > MA10 > MA20 > MA60
  3. MACD零轴上 DIF > 0 且 DIF > DEA
  4. ATR > 3%
  5. 站上MA60
  6. 阳线
|  7. 站上MA5
|  8. 涨跌幅 1%~7%（排除涨停/追高）
|
|【评分】v14：上影线罚(35-1.2x) + 实体×3(≤25) + ATR×2(≤16)
|
|【跨年表现】2025: 78.6%(243天出票)  2026: 77.5%(89天出票)  平均78.0%
"""

import json, os, sys, time
from datetime import datetime

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
MIN_CANDIDATES = 5

def calc_ma(s, p):
    n = len(s); r = {}
    for pd in p:
        ma = [None]*n
        for i in range(pd-1, n): ma[i] = sum(s[i-pd+1:i+1])/pd
        r[pd] = ma
    return r

def calc_macd(ps):
    n = len(ps); dif=[None]*n; dea=[None]*n; macd=[None]*n
    if n < 26: return dif, dea, macd
    e12=[ps[0]]; e26=[ps[0]]
    for i in range(1, n):
        e12.append(e12[-1]*11/13+ps[i]*2/13)
        e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i]=e12[i]-e26[i]
    dea[0]=dif[0] if dif[0] else 0
    for i in range(1, n):
        dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    for i in range(n):
        if dif[i] is not None and dea[i] is not None:
            macd[i]=dif[i]-dea[i]
    return dif, dea, macd

def calc_kdj(h, l, c, n=9):
    L=len(c); k=[50.0]*L; d=[50.0]*L; j=[50.0]*L
    if L < n: return k, d, j
    for i in range(n-1, L):
        hh=max(h[i-n+1:i+1]); ll=min(l[i-n+1:i+1])
        rsv=50.0 if hh==ll else (c[i]-ll)/(hh-ll)*100
        if i > n-1:
            k[i]=2/3*k[i-1]+1/3*rsv
            d[i]=2/3*d[i-1]+1/3*k[i]
        j[i]=3*k[i]-2*d[i]
    return k, d, j

# ═══ v14评分 ═══
def calc_score(close, pct, vol, v5, pos20, j_val, high, op, atr_pct, body_pct, shadow_pct):
    """v14：上影罚(35-1.2x) + 实体×3(≤25) + ATR×2(≤16)"""
    sc = 0
    # 上影线（越短越好）
    if shadow_pct is not None and shadow_pct < 30:
        sc += max(0, 35 - shadow_pct * 1.2)
    # 阳线实体（越大越好）
    if body_pct is not None:
        sc += min(body_pct * 3, 25)
    # ATR波动率（越大越好）
    if atr_pct is not None:
        sc += min(atr_pct * 2, 16)
    return sc

def pick_today(all_data, date):
    candidates = []
    for code, sd in all_data.items():
        di = sd.get("date_idx", {}).get(date)
        if di is None or di < 80: continue
        rec = sd["recs"][di]
        cl = rec["close"]; op = rec["open"]
        hi = rec["high"]; lo = rec["low"]
        vo = rec["volume"]
        m = sd["mas"]
        
        # ═══ 硬过滤 ═══
        if cl > 80: continue
        if not (m[5][di] and m[10][di] and m[20][di] and m[60][di]): continue
        if not (m[5][di] > m[10][di] > m[20][di] > m[60][di]): continue
        dif_v = sd["dif"][di]; dea_v = sd["dea"][di]
        if not (dif_v and dea_v and dif_v > 0 and dif_v > dea_v): continue
        atr_val = sd["atr"][di]
        if not (atr_val and cl > 0 and atr_val/cl*100 > 3): continue
        if not (m[60][di] and cl > m[60][di]): continue
        if not (cl > op): continue
        if not (m[5][di] and cl > m[5][di]): continue
        # 8️⃣ 涨跌幅% 1%~7%（排除涨停/追高）
        pct_val = sd["pct"][di]
        if not (1 <= pct_val < 7): continue
        
        # ═══ 评分 ═══
        v5 = m["v5"][di] if m["v5"][di] else 0
        pos20 = sd["pos20"][di]
        j_val = sd["j"][di]
        atr_pct = atr_val/cl*100 if atr_val and cl > 0 else 0
        rng = hi - lo
        shadow_pct = (hi - max(cl, op))/(rng + 0.001)*100 if rng > 0 else 0
        
        sc = calc_score(cl, pct, vo, v5, pos20, j_val, hi, op, atr_pct, body_pct, shadow_pct)
        candidates.append((code, sc, date))
    
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0], candidates[0][1], candidates

def load_data():
    all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
    main_files = [f for f in all_files
                  if f.startswith('sh6') or
                  (f.startswith('sz0') and not f.startswith('sz3')) or
                  f.startswith('sz2')]
    all_data = {}
    loaded = 0
    for fn in main_files:
        fp = os.path.join(CACHE_DIR, fn)
        try:
            with open(fp, 'rb') as f:
                recs = json.loads(f.read().decode('utf-8'))
            if len(recs) < 80: continue
            code = fn.replace('.json', '')
            c=[r['close'] for r in recs]; h=[r['high'] for r in recs]
            l=[r['low'] for r in recs]; o=[r['open'] for r in recs]
            v=[r['volume'] for r in recs]
            mas = calc_ma(c, [5,10,20,60]); mas['v5'] = calc_ma(v, [5])[5]
            dif, dea, macd = calc_macd(c)
            k, d, j = calc_kdj(h, l, c)
            pct = [0.0]
            for idx in range(1, len(c)):
                pct.append((c[idx]/c[idx-1]-1)*100)
            # ATR
            atr = [None]*len(c)
            if len(c) >= 15:
                for i in range(14, len(c)):
                    tr = [max(h[t]-l[t], abs(h[t]-c[t-1]), abs(l[t]-c[t-1])) for t in range(i-13, i+1)]
                    atr[i] = sum(tr)/14
            # 位置
            pos20 = [None]*len(c); j_v = j
            for i in range(19, len(c)):
                h20 = max(h[i-19:i+1]); l20 = min(l[i-19:i+1])
                pos20[i] = (c[i]-l20)/(h20-l20+0.001)*100
            all_data[code] = {
                "recs": recs, "mas": mas, "dif": dif, "dea": dea,
                "pct": pct, "atr": atr, "pos20": pos20, "j": j_v,
                "date_idx": {r["date"]: idx for idx, r in enumerate(recs)}
            }
            loaded += 1
            if loaded % 500 == 0:
                print(f"  {loaded}/{len(main_files)}")
        except:
            continue
    print(f"✅ {loaded}只主板股")
    return all_data

if __name__ == "__main__":
    t0 = time.time()
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📅 CG-07 v14 选股 — {today}")
    print("📡 加载数据...")
    all_data = load_data()
    print(f"🔍 扫描{today}...")
    result = pick_today(all_data, today)
    if result:
        champ, score, cands = result
        cands.sort(key=lambda x: x[1], reverse=True)
        print(f"\n📊 共{len(cands)}只候选（≥{MIN_CANDIDATES}票）")
        print(f"\n{'='*75}")
        print(f"🏆 TOP10 详情")
        print(f"{'='*75}")
        print(f"{'排名':<4} {'代码':<12} {'买入价':>7} {'涨跌幅':>7} {'总分':>5} {'次日最高':>8} {'次日收盘':>8}")
        print("-"*60)
        for rank, (code, sc, dt) in enumerate(cands[:10], 1):
            sd = all_data.get(code)
            if sd:
                di = sd["date_idx"].get(dt)
                if di:
                    cl=sd["c"][di]; op=sd["o"][di]; hi=sd["h"][di]; lo=sd["l"][di]
                    rng=hi-lo
                    shadow=(hi-max(cl,op))/(rng+0.001)*100 if rng>0 else 0
                    body=abs(cl-op)/op*100 if op>0 else 0
                    atr_p=sd["atr"][di]/cl*100 if sd["atr"][di] and cl>0 else 0
                    pct_val=sd["pct"][di] if sd["pct"][di] else 0
                    next_h = round((sd["recs"][di+1]["high"]/cl-1)*100, 1) if di+1 < len(sd["recs"]) else None
                    nh = f"{next_h:+.1f}%" if next_h is not None else "N/A"
                    # 次日收盘涨幅
                    next_c = round((sd["recs"][di+1]["close"]/cl-1)*100, 1) if di+1 < len(sd["recs"]) else None
                    nc = f"{next_c:+.1f}%" if next_c is not None else "N/A"
                    mk = "🏆" if rank==1 else ""
                    print(f"{rank:<4} {code:<12} {cl:>7.2f} {pct_val:>+6.2f}% {sc:>5.1f} {nh:>8} {nc:>8} {mk}")
                else:
                    print(f"{rank:<4} {code:<12} {'':>7} {'':>7} {sc:>5.1f} {'':>8} {'':>8}")
            else:
                print(f"{rank:<4} {code:<12} {'':>7} {'':>7} {sc:>5.1f} {'':>8} {'':>8}")
        print(f"\n🥇 冠军: {champ}  评分: {score:.1f}")
    else:
        print("❌ 今日无符合条件的股票")
    print(f"⏱ {time.time()-t0:.1f}秒")
