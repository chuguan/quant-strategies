
#!/usr/bin/env python3
"""验证10种经典尾盘选股法 — 在244270个样本中反查胜率"""
import json, os, sys, time

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

def calc_ma(series, periods):
    n = len(series)
    result = {}
    for p in periods:
        ma = [None] * n
        for i in range(p-1, n):
            ma[i] = sum(series[i-p+1:i+1]) / p
        result[p] = ma
    return result

def calc_macd(ps):
    n = len(ps)
    dif = [None]*n; dea = [None]*n; macd = [None]*n
    if n < 26: return dif, dea, macd
    e12 = [ps[0]]; e26 = [ps[0]]
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

def calc_kdj(highs, lows, closes, n=9):
    L = len(closes)
    k = [50.0]*L; d = [50.0]*L; j = [50.0]*L
    if L < n: return k, d, j
    for i in range(n-1, L):
        hh = max(highs[i-n+1:i+1]); ll = min(lows[i-n+1:i+1])
        rsv = 50.0 if hh == ll else (closes[i]-ll)/(hh-ll)*100
        if i > n-1:
            k[i] = 2/3*k[i-1] + 1/3*rsv
            d[i] = 2/3*d[i-1] + 1/3*k[i]
        j[i] = 3*k[i] - 2*d[i]
    return k, d, j

# ═══ 10种经典尾盘选股法 ═══
STRATEGIES = []

# 1️⃣ 光头阳线法 — 收盘在最高点附近，无上影线
def s1(recs, i, mas, dif, dea, macd, k, d, j, **kw):
    r = recs[i]
    upper = r["high"] - max(r["close"], r["open"])
    body = abs(r["close"] - r["open"])
    return r["close"] > r["open"] and upper / (body + 0.001) < 0.15 and (r["close"]-r["low"])/(r["high"]-r["low"]+0.001)*100 > 70
STRATEGIES.append(("1. 光头阳线法", s1))

# 2️⃣ 放量上攻法 — 阳线+量比>1.5+收盘在上1/3
def s2(recs, i, mas, dif, dea, macd, k, d, j, **kw):
    r = recs[i]; v = r["volume"]
    v5 = mas["v5"][i] if mas["v5"][i] else 0
    vr = v / v5 if v5 > 0 else 0
    pos = (r["close"]-r["low"])/(r["high"]-r["low"]+0.001)*100
    return r["close"] > r["open"] and vr > 1.5 and pos > 66
STRATEGIES.append(("2. 放量上攻法", s2))

# 3️⃣ 均线多头发散法 — MA5>MA10>MA20>MA60
def s3(recs, i, mas, dif, dea, macd, k, d, j, **kw):
    return (mas[5][i] and mas[10][i] and mas[20][i] and mas[60][i] and 
            mas[5][i] > mas[10][i] > mas[20][i] > mas[60][i])
STRATEGIES.append(("3. 均线多头排列", s3))

# 4️⃣ MACD金叉+零轴上法 — DIF>DEA且DIF>0
def s4(recs, i, mas, dif, dea, macd, k, d, j, **kw):
    return (dif[i] is not None and dea[i] is not None and 
            dif[i] > dea[i] and dif[i] > 0)
STRATEGIES.append(("4. MACD金叉+零轴上", s4))

# 5️⃣ KDJ金叉法 — K线上穿D线
def s5(recs, i, mas, dif, dea, macd, k, d, j, **kw):
    if i < 1 or k[i] is None or d[i] is None or k[i-1] is None or d[i-1] is None:
        return False
    return k[i-1] <= d[i-1] and k[i] > d[i]
STRATEGIES.append(("5. KDJ金叉法", s5))

# 6️⃣ 站上所有均线 — 收盘>MA5>MA10>MA20 (不一定MA60)
def s6(recs, i, mas, dif, dea, macd, k, d, j, **kw):
    close = recs[i]["close"]
    return (mas[5][i] and mas[10][i] and mas[20][i] and
            close > mas[5][i] > mas[10][i] > mas[20][i])
STRATEGIES.append(("6. 站稳短期均线", s6))

# 7️⃣ 缩量回踩MA20 — 量比<0.8, 收盘在MA20附近
def s7(recs, i, mas, dif, dea, macd, k, d, j, **kw):
    r = recs[i]; v = r["volume"]
    v5 = mas["v5"][i] if mas["v5"][i] else 0
    vr = v / v5 if v5 > 0 else 0
    if not mas[20][i] or mas[20][i] <= 0: return False
    dist = abs(r["close"] - mas[20][i]) / mas[20][i] * 100
    return vr < 0.8 and dist < 1.5
STRATEGIES.append(("7. 缩量回踩MA20", s7))

# 8️⃣ 放量突破法 — 阳线, 收盘>20日最高, 量比>1.2
def s8(recs, i, mas, dif, dea, macd, k, d, j, **kw):
    r = recs[i]
    close, high = r["close"], r["high"]
    v = r["volume"]; v5 = mas["v5"][i] if mas["v5"][i] else 0
    vr = v / v5 if v5 > 0 else 0
    if i < 20: return False
    h20 = max(recs[t]["high"] for t in range(max(0,i-19), i+1))
    return r["close"] > r["open"] and close >= h20 * 0.98 and vr > 1.2
STRATEGIES.append(("8. 放量突破20日高", s8))

# 9️⃣ T字线/锤子线 — 下影线>实体2倍, 阳线
def s9(recs, i, mas, dif, dea, macd, k, d, j, **kw):
    r = recs[i]
    if r["close"] <= r["open"]: return False  # 阳线
    body = r["close"] - r["open"]
    lower = r["open"] - r["low"]
    return lower > body * 2
STRATEGIES.append(("9. 锤子线探底", s9))

# 🔟 温和放量上涨 — 阳线, 涨1~5%, 量比1~2
def s10(recs, i, mas, dif, dea, macd, k, d, j, **kw):
    r = recs[i]
    close = r["close"]; v = r["volume"]
    pct = kw.get("pct_list", [0])[i] if kw.get("pct_list") else 0
    v5 = mas["v5"][i] if mas["v5"][i] else 0
    vr = v / v5 if v5 > 0 else 0
    return r["close"] > r["open"] and 1 <= pct <= 5 and 1 <= vr <= 2
STRATEGIES.append(("10. 温和放量上涨", s10))

import random
random.seed(42)

all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files = [f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
sample_files = sorted(random.sample(main_files, min(800, len(main_files))))

print(f"📊 沪深主板{len(main_files)}只，采样{len(sample_files)}只")

# Stats for each strategy
stats = {name: {"total_calls": 0, "hit": 0, "miss": 0} for name, _ in STRATEGIES}
total_samples = 0
win_samples = 0

processed = 0
for fn in sample_files:
    fp = os.path.join(CACHE_DIR, fn)
    try:
        with open(fp, 'rb') as f:
            recs = json.loads(f.read().decode('utf-8'))
        if len(recs) < 80: continue
        code = fn.replace('.json', '')
        
        closes = [r['close'] for r in recs]
        highs = [r['high'] for r in recs]
        lows = [r['low'] for r in recs]
        opens = [r['open'] for r in recs]
        volumes = [r['volume'] for r in recs]
        
        mas = calc_ma(closes, [5, 10, 20, 60])
        mas["v5"] = calc_ma(volumes, [5])[5]
        dif, dea, macd = calc_macd(closes)
        k, d, j = calc_kdj(highs, lows, closes)
        
        # Pre-calc pct
        pct_list = [0.0]
        for idx in range(1, len(closes)):
            pct_list.append((closes[idx] / closes[idx-1] - 1) * 100)
        
        kw = {"pct_list": pct_list}
        
        for i in range(60, len(recs)-1):
            r = recs[i]
            close = r["close"]
            
            # Next day high %
            nr = recs[i+1]
            next_high_pct = (nr["high"] - close) / close * 100
            is_win = next_high_pct >= 2.5
            
            total_samples += 1
            if is_win: win_samples += 1
            
            # Test all 10 strategies on this sample
            for name, func in STRATEGIES:
                try:
                    if func(recs, i, mas, dif, dea, macd, k, d, j, **kw):
                        stats[name]["total_calls"] += 1
                        if is_win:
                            stats[name]["hit"] += 1
                        else:
                            stats[name]["miss"] += 1
                except:
                    pass
        
        processed += 1
        if processed % 200 == 0:
            print(f"  已处理{processed}/{len(sample_files)}只, {total_samples}样本")
    except:
        continue

print(f"\n✅ 完成! {processed}只股票, {total_samples}样本")
print(f"   次日涨2.5%+: {win_samples}次 ({win_samples/total_samples*100:.1f}%)")

print()
print("=" * 70)
print("📊 10种经典尾盘选股法 — 反查胜率")
print("=" * 70)
print(f"\n{'策略':<24} {'选中数':>8} {'其中赢家':>10} {'胜率':>8} {'赢家覆盖':>10}")
print("-" * 62)

baseline = win_samples / total_samples * 100

for name, func in STRATEGIES:
    s = stats[name]
    t = s["total_calls"]
    h = s["hit"]
    rate = h / t * 100 if t > 0 else 0
    cov = h / win_samples * 100 if win_samples > 0 else 0
    lift = rate / baseline if baseline > 0 else 0
    print(f"{name:<24} {t:>8} {h:>6}/{t:<4} {rate:>6.1f}% {cov:>6.1f}% (↑{lift:.2f}x)")

print(f"\n{'无过滤(基准)':<24} {total_samples:>8} {win_samples:>6}/{total_samples:<4} {baseline:.1f}% {'100.0%':>10}")
