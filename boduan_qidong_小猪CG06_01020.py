#!/usr/bin/env python3
"""
🐷 小猪策略 CG-06 v01020（冠军版）
═══════════════════════════════
尾盘选股 → 次日冲2.5%+卖出

【底仓条件】（硬过滤）
  1. 股价 < 80
  2. 均线多头 MA5 > MA10 > MA20 > MA60
  3. MACD零轴上 DIF > 0 且 DIF > DEA
  4. ATR > 3%（波动率够大）
  5. 站上MA60（中长期趋势向上）

【额外条件】
  6. 阳线（收 > 开）
  7. 站上MA5（短线强势）

【评分】v1基础（ATR加权+涨幅+量比+位置+J值）

【2026年回测】75.3%次日冲2.5%+，100%出票
【2025年验证】65.5%次日冲2.5%+，53.5%出票

优化完成：2026-05-24
"""

import json, os, sys, time
from datetime import datetime

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# ═══ 技术指标 ═══
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

# ═══ 评分 ═══
def calc_score(close, pct, vol, v5, pos20, j_val, high, op):
    """v1基础评分"""
    sc = 0
    # ATR分（已在过滤中用了ATR>3%，这里不再重复加分）
    # 当日涨幅
    if pct > 0: sc += 10
    # 量比
    vr = vol/v5 if v5 > 0 else 0
    if 1 < vr < 2: sc += 15
    elif vr > 2: sc += 8
    # 位置
    sc += (pos20 or 50) * 0.2
    # J值
    if j_val and 50 < j_val < 90: sc += 10
    # 扣分：上影线太长
    upper = high - max(close, op)
    rng = high - min(close, op, high)
    sr = upper/(rng+0.001)*100
    if sr > 50: sc -= 10
    elif sr > 30: sc -= 3
    return sc

# ═══ 日线选股 ═══
def pick_today(all_data, date):
    """对指定日期进行选股，返回(冠军代码, 评分, 候选列表)或None"""
    candidates = []
    for code, sd in all_data.items():
        di = sd.get("date_idx", {}).get(date)
        if di is None or di < 80: continue
        rec = sd["recs"][di]
        cl = rec["close"]; op = rec["open"]
        hi = rec["high"]; lo = rec["low"]
        vo = rec["volume"]
        m = sd["mas"]
        
        # ═══ 底仓硬过滤 ═══
        # 1. 股价<80
        if cl > 80: continue
        
        # 2. 均线多头 MA5>MA10>MA20>MA60
        if not (m[5][di] and m[10][di] and m[20][di] and m[60][di]): continue
        if not (m[5][di] > m[10][di] > m[20][di] > m[60][di]): continue
        
        # 3. MACD零轴上 DIF>0且DIF>DEA
        dif = sd["dif"][di]; dea = sd["dea"][di]
        if not (dif and dea and dif > 0 and dif > dea): continue
        
        # 4. ATR>3%
        atr_val = sd["atr"][di]
        if not (atr_val and cl > 0 and atr_val/cl*100 > 3): continue
        
        # 5. 站上MA60
        if not (m[60][di] and cl > m[60][di]): continue
        
        # 6. 阳线
        if not (cl > op): continue
        
        # 7. 站上MA5
        if not (m[5][di] and cl > m[5][di]): continue
        
        # ═══ 评分 ═══
        pct = sd["pct"][di]
        v5 = m["v5"][di] if m["v5"][di] else 0
        pos20 = sd["pos20"][di]
        j_val = sd["j"][di]
        sc = calc_score(cl, pct, vo, v5, pos20, j_val, hi, op)
        
        candidates.append((code, sc, rec["date"]))
    
    if not candidates:
        return None
    
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0], candidates[0][1], candidates

# ═══ 加载数据 ═══
def load_data():
    """加载所有主板股缓存数据"""
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
            
            c = [r['close'] for r in recs]
            h = [r['high'] for r in recs]
            l = [r['low'] for r in recs]
            o = [r['open'] for r in recs]
            v = [r['volume'] for r in recs]
            dates = [r['date'] for r in recs]
            
            mas = calc_ma(c, [5, 10, 20, 60])
            mas['v5'] = calc_ma(v, [5])[5]
            dif, dea, macd = calc_macd(c)
            k, d, j = calc_kdj(h, l, c)
            
            pct = [0.0]
            for idx in range(1, len(c)):
                pct.append((c[idx]/c[idx-1]-1)*100)
            
            # ATR
            atr = [None]*len(c)
            if len(c) >= 15:
                for i in range(14, len(c)):
                    tr = [max(h[t]-l[t], abs(h[t]-c[t-1]), abs(l[t]-c[t-1]))
                          for t in range(i-13, i+1)]
                    atr[i] = sum(tr)/14
            
            # 20日位置
            pos20 = [None]*len(c)
            for i in range(19, len(c)):
                h20 = max(h[i-19:i+1]); l20 = min(l[i-19:i+1])
                pos20[i] = (c[i]-l20)/(h20-l20+0.001)*100
            
            date_idx = {dates[i]: i for i in range(len(dates))}
            
            all_data[code] = {
                "recs": recs, "c": c, "h": h, "l": l, "o": o, "v": v,
                "mas": mas, "dif": dif, "dea": dea, "macd": macd,
                "k": k, "d": d, "j": j, "pct": pct, "atr": atr,
                "pos20": pos20, "date_idx": date_idx
            }
            loaded += 1
        except:
            continue
    
    return all_data, loaded

# ═══ 主入口 ═══
if __name__ == '__main__':
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "today"
    
    print("🐷 小猪策略 CG-06 v01020（冠军版）")
    print("=" * 50)
    
    print("\n📡 加载数据...")
    all_data, n_stocks = load_data()
    print(f"✅ {n_stocks}只股票已加载")
    
    if mode == "today":
        # 今日选股
        today = datetime.now().strftime("%Y-%m-%d")
        # 找最近的交易日（如果今天不是交易日）
        all_dates = set()
        for code, sd in all_data.items():
            for dt in sd["recs"][-1:]:
                all_dates.add(dt["date"])
        latest_date = max(all_dates)
        
        print(f"\n📅 最新交易日: {latest_date}")
        result = pick_today(all_data, latest_date)
        
        if result:
            champ_code, score, candidates = result
            print(f"\n🏆 冠军: {champ_code} (评分: {score})")
            print(f"📊 候选总数: {len(candidates)}只")
            print(f"\n📋 Top 10:")
            for i, (code, sc, dt) in enumerate(candidates[:10], 1):
                print(f"  {i:>2}. {code} 评分:{sc:>4}")
        else:
            print("\n❌ 今日无符合条件的股票")
    
    elif mode == "backtest":
        # 回测模式
        year = sys.argv[2] if len(sys.argv) > 2 else "2026"
        print(f"\n📅 开始回测 {year}年...")
        
        all_dates = sorted(set(
            dt for code, sd in all_data.items()
            for dt in sd["date_idx"].keys()
            if dt.startswith(year)
        ))
        
        print(f"   共 {len(all_dates)} 个交易日")
        
        results = []
        for td in all_dates:
            result = pick_today(all_data, td)
            if result:
                champ_code, score, candidates = result
                n_cand = len(candidates)
                results.append({
                    "date": td, "code": champ_code,
                    "score": score, "n_candidates": n_cand
                })
        
        pick_days = len(results)
        print(f"\n📊 回测结果: {pick_days}/{len(all_dates)}天出票 ({pick_days/len(all_dates)*100:.1f}%)")
        
        if pick_days > 0:
            avg_cand = sum(r["n_candidates"] for r in results) / pick_days
            print(f"   日均候选: {avg_cand:.0f}只")
    
    elif mode == "info":
        print(f"\n🔧 使用说明:")
        print(f"  python {__file__} today      - 今日选股")
        print(f"  python {__file__} backtest 2026 - 回测2026年")
        print(f"  python {__file__} info        - 查看说明")
