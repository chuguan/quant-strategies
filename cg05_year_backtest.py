#!/usr/bin/env python3
"""
Top3参数 vs CG-01原版 — 全90个交易日回测对比
"""
import json, os, time
from datetime import datetime

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
OUT_DIR = r"C:\Users\12546\AppData\Local\hermes\scripts"

# ═══ 技术指标 ═══
def ma(d, pd):
    res = []
    for i in range(len(d)):
        if i < pd-1: res.append(None)
        else: res.append(sum(d[i-pd+1:i+1])/pd)
    return res

def macd_full(ps):
    n = len(ps)
    if n < 26: return None, None, None
    e12 = [ps[0]]; e26 = [ps[0]]
    dif = [None]*n; dea = [None]*n; macd = [None]*n
    for i in range(1, n):
        e12.append(e12[-1]*11/13+ps[i]*2/13)
        e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i] = e12[i] - e26[i]
    dea[0] = dif[0] if dif[0] else 0
    for i in range(1, n):
        dea[i] = dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    for i in range(n):
        if dif[i] is not None and dea[i] is not None:
            macd[i] = dif[i] - dea[i]
    return dif, dea, macd

def kdj_calc(highs, lows, closes, n=9):
    length = len(closes)
    if length < n: return None, None, None
    k = [50.0]*length; d = [50.0]*length; j = [50.0]*length
    for i in range(n-1, length):
        hh = max(highs[i-n+1:i+1]); ll = min(lows[i-n+1:i+1])
        rsv = 50.0 if hh == ll else (closes[i]-ll)/(hh-ll)*100
        if i == n-1: k[i] = 50.0
        else: k[i] = 2/3*k[i-1] + 1/3*rsv
        d[i] = 2/3*d[i-1] + 1/3*k[i]
        j[i] = 3*k[i] - 2*d[i]
    return k, d, j

# ═══ 4组参数 ═══
CONFIGS = [
    {
        "name": "CG-01 原版",
        "pct_lower": 3, "pct_upper": 5,
        "ma5_slope_min": 8,
        "close_pos_min": 40,
        "vr_max": 3.0,
        "j_ratio_min": 10
    },
    {
        "name": "Top1 🥇",
        "pct_lower": 4, "pct_upper": 5,
        "ma5_slope_min": 10,
        "close_pos_min": 50,
        "vr_max": 2.5,
        "j_ratio_min": 15
    },
    {
        "name": "Top2 🥈",
        "pct_lower": 4, "pct_upper": 5,
        "ma5_slope_min": 10,
        "close_pos_min": 50,
        "vr_max": 3.0,
        "j_ratio_min": 15
    },
    {
        "name": "Top3 🥉",
        "pct_lower": 4, "pct_upper": 5,
        "ma5_slope_min": 10,
        "close_pos_min": 50,
        "vr_max": 4.0,
        "j_ratio_min": 15
    }
]

# ═══ 加载数据 ═══
print("📡 加载K线数据...")
all_data = {}
loaded_cnt = 0
err_cnt = 0
for fn in os.listdir(CACHE_DIR):
    if not fn.endswith('.json'): continue
    if not (fn.startswith('sh6') or fn.startswith('sz0')): continue
    fp = os.path.join(CACHE_DIR, fn)
    try:
        with open(fp, 'rb') as fh:
            raw = fh.read()
        recs = json.loads(raw.decode('utf-8'))
        if not isinstance(recs, list) or len(recs) < 80: continue
    except:
        err_cnt += 1
        if err_cnt <= 3: print(f"  ⚠️ {fn}: 加载失败")
        continue
    
    market = "sh" if fn.startswith("sh") else "sz"
    code = fn.replace('.json','').replace('sh','').replace('sz','')
    
    close_p = [r["close"] for r in recs]
    high_p = [r["high"] for r in recs]
    low_p = [r["low"] for r in recs]
    vol = [r["volume"] for r in recs]
    open_p = [r.get("open", r["close"]) for r in recs]
    dates = [r["date"] for r in recs]
    
    pct_list = [0.0]
    for i in range(1, len(close_p)):
        pct_list.append((close_p[i]/close_p[i-1]-1)*100)
    
    ma5 = ma(close_p, 5)
    ma10 = ma(close_p, 10)
    ma20 = ma(close_p, 20)
    ma60 = ma(close_p, 60)
    v5 = ma(vol, 5)
    dif, dea, macd = macd_full(close_p)
    k, d, j = kdj_calc(high_p, low_p, close_p)
    
    date_idx = {}
    for i, dt in enumerate(dates):
        date_idx[dt] = i
    
    all_data[code] = {
        "p": close_p, "h": high_p, "l": low_p, "v": vol, "o": open_p,
        "pct": pct_list, "dates": dates, "date_idx": date_idx,
        "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
        "v5": v5, "dif": dif, "dea": dea, "macd": macd,
        "k": k, "d": d, "j": j, "recs": recs, "market": market
    }
    loaded_cnt += 1

print(f"  ✅ {loaded_cnt} 只股票 ({err_cnt}错误)")
if loaded_cnt == 0:
    print(f"  ⚠️ 检查缓存路径: {CACHE_DIR}")
    print(f"  ⚠️ 目录存在: {os.path.exists(CACHE_DIR)}")
    sample = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')][:3]
    print(f"  ⚠️ 示例文件: {sample}")
    exit(1)

# ═══ 找出2026年所有交易日 ═══
all_dates = set()
for code, sd in all_data.items():
    for dt in sd["dates"]:
        if dt.startswith("2026-"):
            all_dates.add(dt)
test_dates = sorted(all_dates)
print(f"  2026年共 {len(test_dates)} 个交易日 ({test_dates[0]} ~ {test_dates[-1]})")

# ═══ 预计算未来表现 ═══
print("📡 预计算未来5日表现...")
future_lookup = {}
for code, sd in all_data.items():
    recs = sd["recs"]
    for i in range(len(recs) - 5):
        dt = recs[i]["date"]
        buy = recs[i]["close"]
        if buy <= 0: continue
        after = recs[i+1:i+6]
        if not after: continue
        m5 = round((max(x["high"] for x in after) / buy - 1) * 100, 1)
        future_lookup[(code, dt)] = m5
print(f"  ✅ {len(future_lookup)} 条记录")

# ═══ 单次回测 ═══
def backtest(cfg):
    """用指定参数回测所有交易日，返回每日冠军结果"""
    days_result = []
    
    for td in test_dates:
        best_score = -999
        best_code = None
        best_max5 = None
        
        for code, sd in all_data.items():
            di = sd["date_idx"].get(td)
            if di is None or di < 80: continue
            
            p = sd["p"]; h = sd["h"]; l = sd["l"]; v = sd["v"]; o = sd["o"]
            pct = sd["pct"]; di_ok = True
            
            cur = p[di]
            # 过滤条件
            if cur > 80: continue
            if cur <= o[di] or (cur-o[di])/o[di]*100 < 1: continue
            if sd["v5"][di] and v[di]/sd["v5"][di] > cfg["vr_max"]: continue
            if (h[di]-l[di]) > 0 and (cur-l[di])/(h[di]-l[di])*100 < cfg["close_pos_min"]: continue
            
            if not (sd["ma60"][di] and sd["ma60"][di] > 0): continue
            
            dif, dea, macd = sd["dif"], sd["dea"], sd["macd"]
            k, d, j = sd["k"], sd["d"], sd["j"]
            ma5, ma10, ma20 = sd["ma5"], sd["ma10"], sd["ma20"]
            
            if not (dif[di] and dea[di] and dif[di] > dea[di]): continue
            if not (macd[di] and macd[di] > 0): continue
            if dif[di] - dea[di] < 0.1: continue
            if macd[di-1] is not None and macd[di] <= macd[di-1]: continue
            if macd[di-1] is not None and macd[di-2] is not None:
                if macd[di] - macd[di-1] < macd[di-1] - macd[di-2]: continue
            if dif[di-3] is not None and dif[di] <= dif[di-3]: continue
            
            j_slope = j[di] - j[di-1] if (j[di-1] is not None and j[di] is not None) else 0
            d_prev = d[di-1] if d[di-1] is not None and d[di-1] != 0 else 1
            j_ratio = j_slope / d_prev * 100
            kdj_g = (j[di] > k[di] > d[di]) or (j[di] > k[di] and k[di] <= d[di])
            if j[di-1] is not None and k[di-1] is not None and j[di-1] <= k[di-1] and j[di] > k[di]:
                kdj_g = True
            if not (j_ratio > cfg["j_ratio_min"] or kdj_g): continue
            
            if k[di] > 80 and j[di] > 90: continue
            if k[di] < 20: continue
            
            if not (ma5[di] and ma5[di-3] and ma5[di] > ma5[di-3]): continue
            if not (ma20[di] and ma20[di-5] and ma20[di] > ma20[di-5]): continue
            if not (ma5[di] and ma10[di] and ma20[di] and ma5[di] > ma10[di] > ma20[di]): continue
            if not (ma5[di] and cur > ma5[di]): continue
            
            if ma5[di] and ma5[di-5] and ma5[di-5] > 0:
                slope = (ma5[di] - ma5[di-5]) / ma5[di-5] * 100
                if slope <= cfg["ma5_slope_min"]: continue
            else: continue
            
            gap = ma10[di] - ma20[di] if (ma10[di] and ma20[di]) else 0
            gap_before = ma10[di-4] - ma20[di-4] if (ma10[di-4] and ma20[di-4]) else 0
            if gap <= gap_before * 0.8: continue
            
            if not (cfg["pct_lower"] < pct[di] < cfg["pct_upper"]): continue
            
            # 评分
            score = 0
            macd_r = dif[di]/cur*100 if cur > 0 else 0
            if macd_r > 5: score += 25
            elif macd_r > 2: score += 20
            elif macd_r > 1: score += 12
            elif macd_r > 0: score += 5
            
            vr_cur = v[di] / sd["v5"][di] if sd["v5"][di] else 0
            if pct[di] > 7: score += 30
            elif pct[di] > 5: score += 25
            elif pct[di] > 3: score += 15
            elif pct[di] > 0: score += 8
            if vr_cur > 2: score += 15
            elif vr_cur > 1.2: score += 10
            elif vr_cur > 0.7: score += 5
            if ma5[di] and cur > ma5[di]: score += 12
            
            if len(p) >= 120 and di >= 120:
                bh = max(h[di-60:di-1]); bl = min(l[di-60:di-1])
                rl = min(p[di-120:di]); rh = max(p[di-120:di])
                pos = ((bh+bl)/2 - rl) / (rh - rl) * 100 if (rh-rl) > 0 else 50
            else: pos = 50
            if pos < 30: score += 15
            elif pos < 50: score += 8
            elif pos > 60: score -= 5
            
            sum5 = sum(pct[di-4:di+1]) if di >= 5 else 0
            if sum5 > 5: score += 8
            if 5 < cur < 35: score += 5
            
            gc = sum(1 for i in range(max(0,di-5), di-1) if pct[i] > 0)
            if gc >= 3: score += 5
            
            if pct[di] > 4.5: score -= 8
            if di >= 1 and pct[di-1] > 3: score -= 5
            if di >= 2 and pct[di-2] > 3: score -= 5
            shadow = h[di] - max(o[di], cur)
            tr = h[di] - l[di]
            if tr > 0 and shadow > 0:
                sr = shadow/tr*100
                if sr > 50: score -= 5
                elif sr > 30: score -= 3
                elif sr > 15: score -= 1
            
            if score > best_score:
                best_score = score
                best_code = code
                best_max5 = future_lookup.get((code, td))
        
        if best_code is not None and best_max5 is not None:
            days_result.append({
                "date": td,
                "code": best_code,
                "score": best_score,
                "max5": best_max5
            })
    
    return days_result

# ═══ 跑4组 ═══
print("\n🚀 开始回测4组参数 (90个交易日)...")
t0 = time.time()

all_results = []
for cfg in CONFIGS:
    t1 = time.time()
    print(f"\n📊 测试: {cfg['name']}...", end=" ", flush=True)
    days = backtest(cfg)
    elapsed = time.time() - t1
    
    total = len(days)
    hit10 = sum(1 for d in days if d["max5"] >= 10)
    hit5 = sum(1 for d in days if d["max5"] >= 5)
    avg = round(sum(d["max5"] for d in days) / total, 1) if total else 0
    rate10 = round(hit10 / total * 100, 1) if total else 0
    rate5 = round(hit5 / total * 100, 1) if total else 0
    
    print(f"出票{total}天 | 10%+ {hit10}天({rate10}%) | 5%+ {hit5}天({rate5}%) | 均+{avg}% | {elapsed:.0f}s")
    
    all_results.append({
        "name": cfg["name"],
        "params": {k: cfg[k] for k in ["pct_lower","pct_upper","ma5_slope_min","close_pos_min","vr_max","j_ratio_min"]},
        "total_days": total,
        "hit10": hit10, "rate10": rate10,
        "hit5": hit5, "rate5": rate5,
        "avg_max5": avg,
        "days": days
    })

t1 = time.time()
print(f"\n{'='*80}")
print(f"✅ 全部完成! 耗时 {(t1-t0)/60:.1f} 分钟")
print(f"{'='*80}")

# ═══ 对比输出 ═══
print(f"\n{'='*80}")
print(f"📊 CG-01 参数对比 — 2026年全年回测 ({len(test_dates)}个交易日)")
print(f"{'='*80}")
print(f"  {'策略':<16} {'出票':>4} {'10%+':>6} {'胜率10%':>8} {'5%+':>5} {'胜率5%':>7} {'平均最高':>8}")
print(f"  {'─'*56}")
for r in all_results:
    print(f"  {r['name']:<16} {r['total_days']:>4}天 {r['hit10']:>4}天 {r['rate10']:>7.1f}% {r['hit5']:>4}天 {r['rate5']:>6.1f}% {r['avg_max5']:>+7.1f}%")

# ═══ 按月对比 ═══
print(f"\n\n📊 按月胜率对比:")
print(f"{'='*80}")
months = ["2026-01","2026-02","2026-03","2026-04","2026-05"]
header = f"  {'月份':<10}"
for r in all_results:
    header += f" {r['name'][:8]:>10}"
print(header)
print(f"  {'─'*55}")
for m in months:
    line = f"  {m:<10}"
    for r in all_results:
        m_days = [d for d in r["days"] if d["date"].startswith(m)]
        m_total = len(m_days)
        m_hit10 = sum(1 for d in m_days if d["max5"] >= 10)
        m_rate = round(m_hit10/m_total*100,1) if m_total else 0
        line += f" {m_rate:>9.1f}%"
    print(line)

# ═══ 保存结果 ═══
out_path = os.path.join(OUT_DIR, "cg05_year_backtest_result.json")
# 保存摘要（不含完整days列表太大）
summary = []
for r in all_results:
    summary.append({k: r[k] for k in ["name","params","total_days","hit10","rate10","hit5","rate5","avg_max5"]})
with open(out_path, "w") as f:
    json.dump({"summary": summary, "all_results": all_results, "total_trading_days": len(test_dates)}, f, ensure_ascii=False, indent=2)
print(f"\n💾 结果已保存: {out_path}")
