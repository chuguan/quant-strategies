#!/usr/bin/env python3
"""一键缓存 — 单线程高效版本"""
import json, os, time, pickle

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
PICKLE_PATH = os.path.join(CACHE_DIR, "..", "all_stocks.pkl")

def calc_ma(s, p):
    n = len(s); r = {}
    for pd in p:
        ma = [None]*n
        for i in range(pd-1, n): ma[i] = sum(s[i-pd+1:i+1])/pd
        r[pd] = ma
    return r

def calc_macd(ps):
    n = len(ps); dif=[None]*n; dea=[None]*n
    if n<26: return dif,dea
    e12=[ps[0]]; e26=[ps[0]]
    for i in range(1,n):
        e12.append(e12[-1]*11/13+ps[i]*2/13); e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i]=e12[i]-e26[i]
    dea[0]=dif[0] if dif[0] else 0
    for i in range(1,n): dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    return dif,dea

def process_code(code, recs):
    if len(recs) < 80: return None
    if recs[-1]["date"] < "2020": return None
    c=[r['close'] for r in recs]; h=[r['high'] for r in recs]
    l=[r['low'] for r in recs]; o=[r['open'] for r in recs]
    v=[r['volume'] for r in recs]
    
    mas = calc_ma(c, [5,10,20,60])
    mas['v5'] = calc_ma(v, [5])[5]
    dif, dea = calc_macd(c)
    
    pct = [0.0]
    for idx in range(1, len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
    
    atr = [None]*len(c)
    if len(c) >= 15:
        for i in range(14, len(c)):
            tr_l = [max(h[t]-l[t], abs(h[t]-c[t-1]), abs(l[t]-c[t-1])) for t in range(i-13, i+1)]
            atr[i] = sum(tr_l)/14
    
    pos20 = [None]*len(c)
    for i in range(19, len(c)):
        h20 = max(h[i-19:i+1]); l20 = min(l[i-19:i+1])
        pos20[i] = (c[i]-l20)/(h20-l20+0.001)*100
    
    date_idx = {}
    for idx, r in enumerate(recs): date_idx[r["date"]] = idx
    
    return (code, {
        "c": c, "h": h, "l": l, "o": o, "v": v,
        "mas": mas, "dif": dif, "dea": dea,
        "pct": pct, "atr": atr, "pos20": pos20,
        "date_idx": date_idx, "recs": recs
    })

def main():
    t0 = time.time()
    print("📡 扫描文件...")
    all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and 
                 (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
    print(f"📦 {len(all_files)}个文件，单线程处理...")
    
    all_codes = {}
    for idx, fn in enumerate(all_files):
        try:
            fp = os.path.join(CACHE_DIR, fn)
            with open(fp, 'rb') as f:
                recs = json.loads(f.read().decode('utf-8'))
            code = fn.replace('.json', '')
            res = process_code(code, recs)
            if res:
                code, data = res
                all_codes[code] = data
        except:
            pass
        if (idx + 1) % 500 == 0:
            print(f"  {idx+1}/{len(all_files)} ({time.time()-t0:.0f}s) -> {len(all_codes)}只有效")
    
    print(f"✅ 加载{len(all_codes)}只有效股票, 用时{time.time()-t0:.0f}秒")
    
    # 只保留候选特征（节省体积）
    print("📝 构建候选特征...")
    
    # 收集所有日期
    all_dates = set()
    for sd in all_codes.values():
        for r in sd["recs"]:
            if r["date"] >= "2024-01-01":
                all_dates.add(r["date"])
    
    dates_2025 = sorted(d for d in all_dates if d.startswith("2025"))
    dates_2026 = sorted(d for d in all_dates if d.startswith("2026"))
    print(f"📅 2025:{len(dates_2025)}天 2026:{len(dates_2026)}天")
    
    # 按天收集候选特征
    data_by_year = {"2025": {}, "2026": {}}
    processed = 0
    
    for code, sd in all_codes.items():
        processed += 1
        if processed % 500 == 0:
            print(f"  特征收集: {processed}/{len(all_codes)}")
        date_idx = sd["date_idx"]
        for yr in ["2025", "2026"]:
            dates = dates_2025 if yr == "2025" else dates_2026
            for dt in dates:
                di = date_idx.get(dt)
                if di is None or di < 80: continue
                if sd["c"][di] >= 80: continue
                m = sd["mas"]
                if not (m[5][di] and m[10][di] and m[20][di] and m[60][di] and
                        m[5][di] > m[10][di] > m[20][di] > m[60][di]): continue
                if not (sd["dif"][di] and sd["dea"][di] and sd["dif"][di] > 0 and sd["dif"][di] > sd["dea"][di]): continue
                a = sd["atr"][di]; cl = sd["c"][di]
                if not (a and cl > 0 and a/cl*100 > 3): continue
                if not (m[60][di] and cl > m[60][di]): continue
                if sd["c"][di] <= sd["o"][di]: continue
                if not (m[5][di] and cl > m[5][di]): continue
                
                op = sd["o"][di]; hi = sd["h"][di]; lo = sd["l"][di]
                rng = hi - lo
                shadow = (hi - max(cl, op)) / (rng + 0.001) * 100 if rng > 0 else 0
                body = abs(cl - op) / op * 100
                atr_p = sd["atr"][di] / cl * 100 if sd["atr"][di] and cl > 0 else 0
                next_h = round((sd["recs"][di+1]["high"] / cl - 1) * 100, 2) if di + 1 < len(sd["recs"]) else None
                
                if dt not in data_by_year[yr]:
                    data_by_year[yr][dt] = []
                data_by_year[yr][dt].append((shadow, body, atr_p, next_h))
    
    # 只保留>=5候选的天
    for yr in ["2025", "2026"]:
        keep = {dt: cand for dt, cand in data_by_year[yr].items() if len(cand) >= 5}
        print(f"  {yr}: {len(keep)}天有≥5候选 (共{len(data_by_year[yr])}天)")
        data_by_year[yr] = keep
    
    # 只保存特征缓存（去掉庞大的all_codes，节省空间）
    cache_pkg = {
        "data_by_year": data_by_year,
        "build_time": time.time() - t0,
        "build_date": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open(PICKLE_PATH, 'wb') as f:
        pickle.dump(cache_pkg, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    mb = os.path.getsize(PICKLE_PATH)/1024/1024
    print(f"\n💾 缓存已保存: {PICKLE_PATH}")
    print(f"📦 大小: {mb:.0f}MB")
    print(f"⏱ 总用时: {time.time()-t0:.0f}秒")

if __name__ == "__main__":
    main()
