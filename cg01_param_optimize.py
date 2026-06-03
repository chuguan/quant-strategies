#!/usr/bin/env python3
"""
CG-01 参数寻优回测引擎 v1.1
6个关键条件 × 3档 = 729种组合 → 按#1冠军10%+胜率排序取Top3
数据源：3月~5月共37个交易日
"""
import json, os, sys, time
from itertools import product
from datetime import datetime

# 硬编码绝对路径，不依赖__file__
CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
BASE_DIR = r"C:\Users\12546\AppData\Local\hermes\scripts"

# ═══ 技术指标函数 ═══
def ma(d, pd):
    res = []
    for i in range(len(d)):
        if i < pd-1:
            res.append(None)
        else:
            res.append(sum(d[i-pd+1:i+1])/pd)
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
        if hh == ll:
            rsv = 50.0
        else:
            rsv = (closes[i]-ll)/(hh-ll)*100
        if i == n-1:
            k[i] = 50.0
        else:
            k[i] = 2/3*k[i-1] + 1/3*rsv
        d[i] = 2/3*d[i-1] + 1/3*k[i]
        j[i] = 3*k[i] - 2*d[i]
    return k, d, j

# ═══ 参数空间 ═══
PARAMS = {
    "pct_lower":      [2,   3,   4],    # 涨幅下限%
    "pct_upper":      [4,   5,   7],    # 涨幅上限%
    "ma5_slope_min":  [6,   8,   10],   # MA5斜率最小%
    "close_pos_min":  [30,  40,  50],   # 收盘位置下限%
    "vr_max":         [2.5, 3.0, 4.0],  # 量比上限
    "j_ratio_min":    [5,   10,  15],   # J线上涨比率%
}
PARAM_NAMES = list(PARAMS.keys())
COMBOS = list(product(*[PARAMS[k] for k in PARAM_NAMES]))
print(f"🔢 共 {len(COMBOS)} 种参数组合")

# ═══ 入选日期（从冠军缓存提取） ═══
TEST_DATES = [
    "2026-03-02","2026-03-04","2026-03-05","2026-03-06","2026-03-11",
    "2026-03-12","2026-03-16","2026-03-17","2026-03-19","2026-03-26",
    "2026-04-03","2026-04-07","2026-04-08","2026-04-09","2026-04-10",
    "2026-04-13","2026-04-14","2026-04-15","2026-04-16","2026-04-17",
    "2026-04-21","2026-04-22","2026-04-24","2026-04-29","2026-04-30",
    "2026-05-06","2026-05-07","2026-05-11","2026-05-12","2026-05-13",
    "2026-05-14","2026-05-15","2026-05-18","2026-05-19","2026-05-20",
    "2026-05-22"
]
DATE_SET = set(TEST_DATES)

# ═══ 加载K线数据并预计算指标 ═══
print("📡 加载K线缓存...")
all_data = {}  # {code: {indicators}}

all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
loaded = 0
skipped_short = 0
skipped_error = 0

for fn in all_files:
    fp = os.path.join(CACHE_DIR, fn)
    try:
        with open(fp, 'r') as fh:
            recs = json.load(fh)
        if not isinstance(recs, list) or len(recs) < 80:
            skipped_short += 1
            continue
        
        market = "sh" if fn.startswith("sh") else "sz"
        code = fn.replace('.json','').replace('sh','').replace('sz','')
        
        # 提取数据到列表
        close_prices = []
        high_prices = []
        low_prices = []
        volumes = []
        open_prices = []
        dates_list = []
        
        for rec in recs:
            close_prices.append(rec["close"])
            high_prices.append(rec["high"])
            low_prices.append(rec["low"])
            volumes.append(rec["volume"])
            open_prices.append(rec.get("open", rec["close"]))
            dates_list.append(rec["date"])
        
        n = len(close_prices)
        
        # 预计算指标
        pct_list = [0.0]
        for i in range(1, n):
            pct_list.append((close_prices[i]/close_prices[i-1]-1)*100)
        
        ma5 = ma(close_prices, 5)
        ma10 = ma(close_prices, 10)
        ma20 = ma(close_prices, 20)
        ma60 = ma(close_prices, 60)
        v5 = ma(volumes, 5)
        dif, dea, macd = macd_full(close_prices)
        k, d, j = kdj_calc(high_prices, low_prices, close_prices)
        
        # 建日期索引
        date_idx = {}
        for i, dt in enumerate(dates_list):
            date_idx[dt] = i
        
        all_data[code] = {
            "p": close_prices,
            "h": high_prices,
            "l": low_prices,
            "v": volumes,
            "o": open_prices,
            "pct": pct_list,
            "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
            "v5": v5,
            "dif": dif, "dea": dea, "macd": macd,
            "k": k, "d": d, "j": j,
            "date_idx": date_idx,
            "market": market,
            "dates": dates_list,
            "recs": recs
        }
        loaded += 1
        if loaded % 1000 == 0:
            print(f"  已加载 {loaded} 只...")
    except Exception as e:
        skipped_error += 1
        if skipped_error <= 3:
            print(f"  ⚠️ {fn}: {e}")

print(f"  ✅ 加载 {loaded} 只股票 (短数据{skipped_short}只跳过, {skipped_error}只错误)")

# ═══ 预计算每只股票每个日期的未来表现 ═══
print("📡 预计算未来5日表现...")
future_lookup = {}
for code, sd in all_data.items():
    recs = sd["recs"]
    for i in range(len(recs) - 5):
        dt = recs[i]["date"]
        buy_price = recs[i]["close"]
        if buy_price <= 0:
            continue
        after = recs[i+1:i+6]
        if not after:
            continue
        max_high = max(x["high"] for x in after)
        m5 = round((max_high / buy_price - 1) * 100, 1)
        future_lookup[(code, dt)] = m5
print(f"  ✅ {len(future_lookup)} 条记录")

# ═══ 单组合评分测试 ═══
def test_combo(param_vals):
    """测试一组参数：遍历每个交易日，取评分#1，算10%+概率"""
    params = dict(zip(PARAM_NAMES, param_vals))
    pct_l = params["pct_lower"]
    pct_u = params["pct_upper"]
    ma5_sm = params["ma5_slope_min"]
    cpm = params["close_pos_min"]
    vrm = params["vr_max"]
    jrm = params["j_ratio_min"]
    
    champ_max5_list = []
    
    for td in TEST_DATES:
        best_score = -999
        best_max5 = None
        
        for code, sd in all_data.items():
            di = sd["date_idx"].get(td)
            if di is None or di < 80:
                continue
            
            p = sd["p"]; h = sd["h"]; l = sd["l"]; v = sd["v"]; o = sd["o"]
            pct = sd["pct"]
            ma5 = sd["ma5"]; ma10 = sd["ma10"]; ma20 = sd["ma20"]; ma60 = sd["ma60"]
            v5 = sd["v5"]
            dif = sd["dif"]; dea = sd["dea"]; macd = sd["macd"]
            k = sd["k"]; d = sd["d"]; j = sd["j"]
            
            cur = p[di]
            if cur > 80: continue
            if cur <= o[di] or (cur-o[di])/o[di]*100 < 1: continue
            if v5[di] and v[di]/v5[di] > vrm: continue
            if (h[di]-l[di]) > 0 and (cur-l[di])/(h[di]-l[di])*100 < cpm: continue
            
            if not (ma60[di] and ma60[di] > 0): continue
            if not (dif[di] and dea[di] and dif[di] > dea[di]): continue
            if not (macd[di] and macd[di] > 0): continue
            if dif[di] - dea[di] < 0.1: continue
            if macd[di-1] is not None and macd[di] <= macd[di-1]: continue
            
            if macd[di-1] is not None and macd[di-2] is not None:
                if macd[di] - macd[di-1] < macd[di-1] - macd[di-2]: continue
            
            if dif[di-3] is not None and dif[di] <= dif[di-3]: continue
            
            # KDJ
            j_slope = j[di] - j[di-1] if (j[di-1] is not None and j[di] is not None) else 0
            d_prev = d[di-1] if d[di-1] is not None and d[di-1] != 0 else 1
            j_ratio = j_slope / d_prev * 100
            kdj_g = (j[di] > k[di] > d[di]) or (j[di] > k[di] and k[di] <= d[di])
            if j[di-1] is not None and k[di-1] is not None and j[di-1] <= k[di-1] and j[di] > k[di]:
                kdj_g = True
            if not (j_ratio > jrm or kdj_g): continue
            
            if k[di] > 80 and j[di] > 90: continue
            if k[di] < 20: continue
            
            if not (ma5[di] and ma5[di-3] and ma5[di] > ma5[di-3]): continue
            if not (ma20[di] and ma20[di-5] and ma20[di] > ma20[di-5]): continue
            if not (ma5[di] and ma10[di] and ma20[di] and ma5[di] > ma10[di] > ma20[di]): continue
            if not (ma5[di] and cur > ma5[di]): continue
            
            if ma5[di] and ma5[di-5] and ma5[di-5] > 0:
                slope = (ma5[di] - ma5[di-5]) / ma5[di-5] * 100
                if slope <= ma5_sm: continue
            else: continue
            
            gap = ma10[di] - ma20[di] if (ma10[di] and ma20[di]) else 0
            gap_before = ma10[di-4] - ma20[di-4] if (ma10[di-4] and ma20[di-4]) else 0
            if gap <= gap_before * 0.8: continue
            
            if not (pct_l < pct[di] < pct_u): continue
            
            # 评分
            score = 0
            macd_r = dif[di]/cur*100 if cur > 0 else 0
            if macd_r > 5: score += 25
            elif macd_r > 2: score += 20
            elif macd_r > 1: score += 12
            elif macd_r > 0: score += 5
            
            vr_cur = v[di] / v5[di] if v5[di] else 0
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
            
            green5 = 0
            for i in range(di-5, di-1):
                if i >= 0 and pct[i] > 0: green5 += 1
            if green5 >= 3: score += 5
            
            if pct[di] > 4.5: score -= 8
            if di >= 1 and pct[di-1] > 3: score -= 5
            if di >= 2 and pct[di-2] > 3: score -= 5
            shadow = h[di] - max(o[di], cur)
            total_range = h[di] - l[di]
            if total_range > 0 and shadow > 0:
                sr = shadow/total_range*100
                if sr > 50: score -= 5
                elif sr > 30: score -= 3
                elif sr > 15: score -= 1
            
            if score > best_score:
                best_score = score
                best_max5 = future_lookup.get((code, td))
        
        if best_max5 is not None:
            champ_max5_list.append(best_max5)
    
    if not champ_max5_list:
        return {"params": params, "total": 0, "hit10": 0, "rate": 0.0, "avg": 0.0}
    total = len(champ_max5_list)
    hit10 = sum(1 for v in champ_max5_list if v >= 10)
    hit5 = sum(1 for v in champ_max5_list if v >= 5)
    rate = round(hit10 / total * 100, 1)
    avg = round(sum(champ_max5_list) / total, 1)
    return {"params": params, "total": total, "hit10": hit10, "hit5": hit5, "rate": rate, "avg": avg}

# ═══ 批量跑组合 ═══
print(f"🚀 开始跑 {len(COMBOS)} 组参数 (每次测试 {len(TEST_DATES)} 天 × {len(all_data)} 只)...")
t0 = time.time()
results = []

for idx, combo in enumerate(COMBOS):
    r = test_combo(combo)
    results.append(r)
    
    if (idx + 1) % 10 == 0:
        elapsed = time.time() - t0
        done = idx + 1
        remaining = len(COMBOS) - done
        est_per = elapsed / done
        eta = est_per * remaining
        pct = done / len(COMBOS) * 100
        print(f"  [{done}/{len(COMBOS)}] {pct:.0f}%  耗时{elapsed:.0f}s  预计剩余{eta:.0f}s", flush=True)
        
        # 中间保存
        results.sort(key=lambda x: -x["rate"])
        tmp = results[:10]
        with open(os.path.join(BASE_DIR, "cg05_progress.json"), "w") as f:
            json.dump(tmp, f, ensure_ascii=False, indent=2)

t1 = time.time()
print(f"\n{'='*80}")
print(f"✅ 全部完成! 耗时 {(t1-t0)/60:.1f} 分钟")

# ═══ 排序输出Top3 ═══
results.sort(key=lambda x: -x["rate"])

print(f"\n🏆 CG-01 参数寻优 总排名:")
print(f"{'='*80}")

for i, r in enumerate(results):
    p = r["params"]
    medal = "🥇" if i == 0 else ("🥈" if i == 1 else ("🥉" if i == 2 else ""))
    tag = f"  #{i+1} {medal}" if medal else f"  #{i+1}"
    print(f"{tag} 胜率{r['rate']:>5.1f}% | 均{r['avg']:>+6.1f}% | {r['hit10']}/{r['total']:>2}天10%+ | 涨{p['pct_lower']}~{p['pct_upper']}% MA5>{p['ma5_slope_min']}% 位>{p['close_pos_min']}% 量<{p['vr_max']} J>{p['j_ratio_min']}%")

# ═══ 保存结果 ═══
output = {
    "top3": results[:3],
    "top10": results[:10],
    "all": results,
    "total_combos": len(results),
    "time_min": round((t1-t0)/60, 1),
    "test_dates": TEST_DATES,
    "test_date_count": len(TEST_DATES),
    "params_definition": {k: PARAMS[k] for k in PARAM_NAMES},
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
}

out_path = os.path.join(BASE_DIR, "cg05_optimize_full_result.json")
with open(out_path, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n💾 完整结果已保存: {out_path}")
print(f"📊 共测试 {len(results)} 组参数, 耗时 {output['time_min']} 分钟")

# ═══ 输出简洁版Top3 ═══
print(f"\n{'='*80}")
print(f"🏆 CG-05 建议参数 (Top3):")
print(f"{'='*80}")
for i, r in enumerate(results[:3], 1):
    p = r["params"]
    print(f"\n  #{i}  胜率 {r['rate']}% | {r['hit10']}/{r['total']}天达标10%+ | 平均{r['avg']:+.1f}% | 5%+达标{r['hit5']}/{r['total']}")
    print(f"  ─────────────────────────────────────────")
    print(f"  涨幅范围:   {p['pct_lower']}% ~ {p['pct_upper']}%")
    print(f"  MA5斜率:    ≥{p['ma5_slope_min']}%")
    print(f"  收盘位置:   ≥{p['close_pos_min']}%")
    print(f"  量比上限:   ≤{p['vr_max']}x")
    print(f"  J线比率:    ≥{p['j_ratio_min']}%")
