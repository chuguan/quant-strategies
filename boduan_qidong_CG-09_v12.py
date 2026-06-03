#!/usr/bin/env python3
"""
🐷 CG-09 v12（综合版）
═══════════════════════════════
尾盘选股 → 次日冲2.5%+卖出

【底仓条件】同CG-07（M1+阳线+站MA5）
【评分】涨×3.5 + ATR×1.2 + VR1~1.5+18/1.5~2.5+8 + 上影<10+22/<18+10/<30+0/else-12 + MA5×1.2(≤18) + 实体×1.5(≤15)

【跨年表现】2025: 76.7%  2026: 83.3%  平均79.8%
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

# ═══ CG-09 v12（综合版）评分 ═══
def calc_score(close, pct, vol, v5, pos20, j_val, high, op, atr_pct, body_pct, shadow_pct, ma5_sl, vr):
    sc = max(0, pct) * 3.5
    sc += atr_pct * 1.2
    sc += (18 if 1 <= vr <= 1.5 else 8 if 1.5 < vr <= 2.5 else 0)
    if shadow_pct < 10: sc += 22
    elif shadow_pct < 18: sc += 10
    elif shadow_pct < 30: sc += 0
    else: sc -= 12
    sc += min(ma5_sl, 15) * 1.2
    sc += min(body_pct, 10) * 1.5
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
        pct = sd["pct"][di]
        v5 = m["v5"][di] if m["v5"][di] else 0
        pos20 = sd["pos20"][di]
        j_val = sd["j"][di]
        atr_pct = atr_val/cl*100 if atr_val and cl > 0 else 0
        body_pct = abs(cl - op)/op*100
        rng = hi - lo
        shadow_pct = (hi - max(cl, op))/(rng + 0.001)*100 if rng > 0 else 0
        ma5_sl = sd.get("ma5_sl", [None]*len(sd["recs"]))[di] or 0
        vr = vo/v5 if v5 > 0 else 0
        sc = calc_score(cl, pct, vo, v5, pos20, j_val, hi, op, atr_pct, body_pct, shadow_pct, ma5_sl, vr)
        candidates.append((code, sc, date))
    if not candidates: return None
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0], candidates[0][1], candidates

def load_data():
    all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
    main_files = [f for f in all_files
                  if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
    all_data = {}; loaded = 0
    for fn in main_files:
        fp = os.path.join(CACHE_DIR, fn)
        try:
            with open(fp, 'rb') as f: recs = json.loads(f.read().decode('utf-8'))
            if len(recs) < 80: continue
            code = fn.replace('.json', '')
            c=[r['close'] for r in recs]; h=[r['high'] for r in recs]
            l=[r['low'] for r in recs]; o=[r['open'] for r in recs]
            v=[r['volume'] for r in recs]
            mas = calc_ma(c, [5,10,20,60]); mas['v5'] = calc_ma(v, [5])[5]
            dif, dea, macd = calc_macd(c)
            k, d, j = calc_kdj(h, l, c)
            pct = [0.0]
            for idx in range(1, len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
            atr = [None]*len(c)
            if len(c) >= 15:
                for i in range(14, len(c)):
                    tr = [max(h[t]-l[t], abs(h[t]-c[t-1]), abs(l[t]-c[t-1])) for t in range(i-13, i+1)]
                    atr[i] = sum(tr)/14
            pos20 = [None]*len(c); ma5_sl = [None]*len(c)
            for i in range(19, len(c)):
                h20 = max(h[i-19:i+1]); l20 = min(l[i-19:i+1])
                pos20[i] = (c[i]-l20)/(h20-l20+0.001)*100
            for i in range(4, len(c)):
                if mas[5][i] and mas[5][i-4]:
                    ma5_sl[i] = (mas[5][i]-mas[5][i-4])/mas[5][i-4]*100
            all_data[code] = {"recs": recs, "mas": mas, "dif": dif, "dea": dea,
                "pct": pct, "atr": atr, "pos20": pos20, "j": j, "ma5_sl": ma5_sl,
                "date_idx": {r["date"]: idx for idx, r in enumerate(recs)}}
            loaded += 1
            if loaded % 500 == 0: print(f"  {loaded}/{len(main_files)}")
        except: continue
    print(f"✅ {loaded}只主板股")
    return all_data

if __name__ == "__main__":
    t0 = time.time()
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📅 CG-09 v12（综合版） 选股 — {today}")
    print("📡 加载数据...")
    all_data = load_data()
    print(f"🔍 扫描{today}...")
    result = pick_today(all_data, today)
    if result:
        champ, score, cands = result
        cands.sort(key=lambda x: x[1], reverse=True)
        print(f"\n🏆 冠军: {champ}  评分: {score:.1f}")
        print(f"📊 共{len(cands)}只候选")
        print(f"\nTOP10:")
        for code, sc, _ in cands[:10]:
            print(f"  {code:<10} {sc:.1f}分")
    else:
        print("❌ 今日无符合条件的股票")
    print(f"⏱ {time.time()-t0:.1f}秒")
