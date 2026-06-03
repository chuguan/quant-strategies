#!/usr/bin/env python3
"""重建 big_cache_full.pkl — 从所有K线JSON文件 + 腾讯API
- 不走M1/涨幅过滤，所有股票全部入库
- 只取今年数据 (2025-01-01 起)
"""
import json, os, time, sys, pickle, subprocess
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)
CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
SCRIPTS_DIR = r"C:\Users\12546\AppData\Local\hermes\scripts"
OUTPUT = os.path.join(SCRIPTS_DIR, "big_cache_full.pkl")
T0 = time.time()

# ====== 工具函数 ======
def calc_ma(closes, pds):
    n = len(closes)
    r = {}
    for pd in pds:
        ma = [None]*n
        for i in range(pd-1, n):
            ma[i] = sum(closes[i-pd+1:i+1]) / pd
        r[pd] = ma
    return r

def calc_macd(closes):
    n = len(closes)
    dif, dea, mcd = [None]*n, [None]*n, [None]*n
    if n < 26: return dif, dea, mcd
    e12, e26 = [closes[0]], [closes[0]]
    for i in range(1, n):
        e12.append(e12[-1]*11/13 + closes[i]*2/13)
        e26.append(e26[-1]*25/27 + closes[i]*2/27)
        dif[i] = e12[i] - e26[i]
    dea[0] = dif[0] if dif[0] else 0
    for i in range(1, n):
        dea[i] = dea[i-1]*8/10 + (dif[i] if dif[i] else 0)*2/10
    for i in range(n):
        if dif[i] and dea[i]:
            mcd[i] = dif[i] - dea[i]
    return dif, dea, mcd

def calc_kdj(highs, lows, closes, n=9):
    L = len(closes)
    k, d, j = [50.0]*L, [50.0]*L, [50.0]*L
    if L < n: return k, d, j
    for i in range(n-1, L):
        hh = max(highs[i-n+1:i+1])
        ll = min(lows[i-n+1:i+1])
        rsv = 50.0 if hh == ll else (closes[i]-ll)/(hh-ll)*100
        if i > n-1:
            k[i] = 2/3*k[i-1] + 1/3*rsv
            d[i] = 2/3*d[i-1] + 1/3*k[i]
            j[i] = 3*k[i] - 2*d[i]
    return k, d, j

def curl_get(url, timeout=10):
    try:
        r = subprocess.run(["curl", "-s", "--max-time", str(timeout), url],
                          capture_output=True, timeout=timeout+5)
        return r.stdout.decode("gbk", errors="replace")
    except: return ""

# ====== 1. 扫描所有K线JSON ======
print("📡 扫描K线JSON文件...")
all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".json")
             and (f.startswith("sh6") or f.startswith("sz0")
                  or f.startswith("sz2") or f.startswith("sh0"))]
# 去重（可能有 sh600000.json 和 600000.json 并存）
seen_codes = set()
unique_files = []
for fn in all_files:
    code = fn.replace(".json", "").lstrip("sh").lstrip("sz")
    if code in seen_codes: continue
    # 过滤创业板300和688
    if code.startswith("300") or code.startswith("688"): continue
    seen_codes.add(code)
    unique_files.append((fn, code))

print(f"📦 {len(unique_files)}只A股主板股票")

# ====== 2. 逐股票处理K线 ======
all_data = defaultdict(list)  # {date: [record, ...]}
processed = 0

for idx, (fn, code) in enumerate(unique_files):
    fp = os.path.join(CACHE_DIR, fn)
    try:
        with open(fp, "rb") as f:
            kdata = json.loads(f.read().decode("utf-8", errors="replace"))
    except: continue
    if not kdata or len(kdata) < 80: continue
    
    closes = [r["close"] for r in kdata]
    highs = [r["high"] for r in kdata]
    lows = [r["low"] for r in kdata]
    opens = [r["open"] for r in kdata]
    volumes = [r["volume"] for r in kdata]
    
    # 计算指标
    mas = calc_ma(closes, [5, 10, 20, 60])
    dif, dea, mcd = calc_macd(closes)
    k, d, j = calc_kdj(highs, lows, closes)
    
    # WR
    wr_vals = [50.0]*len(closes)
    for i in range(20, len(closes)):
        h21 = max(highs[i-20:i+1])
        l21 = min(lows[i-20:i+1])
        wr_vals[i] = 100 * (h21 - closes[i]) / (h21 - l21 + 1e-10)
    
    # CL (收盘价在20日区间位置)
    cl_vals = [50.0]*len(closes)
    for i in range(19, len(closes)):
        h20 = max(highs[i-19:i+1])
        l20 = min(lows[i-19:i+1])
        cl_vals[i] = (closes[i] - l20) / (h20 - l20 + 1e-10) * 100
    
    # 5日均量
    ma5_v = [None]*len(closes)
    for i in range(4, len(closes)):
        ma5_v[i] = sum(volumes[i-4:i+1]) / 5
    
    # 逐日处理
    for di in range(60, len(kdata)):
        dt = kdata[di]["date"]
        if dt < "2025-01-01" or dt > "2026-12-31": continue
        
        cl = closes[di]
        op = opens[di]
        hi = highs[di]
        lo = lows[di]
        
        # p = 当日涨跌幅
        pct = round((cl / closes[di-1] - 1) * 100, 2) if di > 0 else 0
        
        # 振幅
        amp = round((hi - lo) / cl * 100, 2) if cl > 0 else 0
        
        # 实体百分比
        body_pct = round(abs(cl - op) / op * 100, 2) if op > 0 else 0
        
        # 量比 = 当日量 / 5日均量
        vr = round(volumes[di] / ma5_v[di], 2) if ma5_v[di] and ma5_v[di] > 0 else 1.0
        
        # n = 次日最高涨幅
        nh = round((kdata[di+1]["high"] / cl - 1) * 100, 1) if di + 1 < len(kdata) else 0
        next_close_pct = round((kdata[di+1]["close"] / cl - 1) * 100, 2) if di + 1 < len(kdata) else 0
        
        # 次日~后5日最高价
        d1h = round((kdata[di+1]["high"] / cl - 1) * 100, 1) if di+1 < len(kdata) else None
        d2h = round((kdata[di+2]["high"] / cl - 1) * 100, 1) if di+2 < len(kdata) else None
        d3h = round((kdata[di+3]["high"] / cl - 1) * 100, 1) if di+3 < len(kdata) else None
        d4h = round((kdata[di+4]["high"] / cl - 1) * 100, 1) if di+4 < len(kdata) else None
        d5h = round((kdata[di+5]["high"] / cl - 1) * 100, 1) if di+5 < len(kdata) else None
        
        # 均线多头排列
        ma5 = mas[5][di]; ma10 = mas[10][di]; ma20 = mas[20][di]; ma60 = mas[60][di]
        above_ma5 = 1 if cl > ma5 else 0
        above_ma10 = 1 if cl > ma10 else 0
        above_ma20 = 1 if cl > ma20 else 0
        
        # MACD金叉
        macd_golden = 1 if dif[di] is not None and dea[di] is not None and dif[di] > dea[di] else 0
        # KDJ金叉
        kdj_golden = 1 if k[di] > d[di] else 0
        
        # 强势信号
        is_yang = 1 if cl > op else 0
        pos_in_day = round((cl - lo) / (hi - lo + 0.001) * 100, 1) if hi > lo else 50
        
        # 量比修正：跳过异常值
        if vr > 10 or vr < 0.05: vr = 1.0
        
        record = {
            "code": code,
            "p": pct,
            "b": body_pct,
            "s": 0,  # 上影线占比
            "a": amp,
            "cl": round(cl_vals[di], 1) if di >= 19 else 50,
            "vol_ratio": vr,
            "j_val": round(j[di], 1),
            "ma5_slope": round((ma5 / mas[5][di-4] - 1) * 100, 2) if di >= 4 and mas[5][di-4] else 0,
            "dif_val": round(dif[di], 3) if dif[di] else 0,
            "amplitude": amp,
            "vol": volumes[di],
            "close": round(cl, 2),
            "body_pct": body_pct,
            "is_yang": is_yang,
            "above_ma5": above_ma5,
            "above_ma10": above_ma10,
            "above_ma20": above_ma20,
            "n": nh,
            "next_close": next_close_pct,
            "next_high": nh,
            "mg": macd_golden,
            "macd_golden": macd_golden,
            "kv": round(k[di], 1),
            "k_val": round(k[di], 1),
            "dv": round(d[di], 1),
            "d_val": round(d[di], 1),
            "wrv": round(wr_vals[di], 1) if di >= 20 else 50,
            "wr_val": round(wr_vals[di], 1) if di >= 20 else 50,
            "kdj_g": 1 if k[di] > d[di] else 0,
            "kdj_golden": kdj_golden,
            "pos_in_day": pos_in_day,
            # D+1 ~ D+5 后加字段
            "d1h": d1h, "d2h": d2h, "d3h": d3h, "d4h": d4h, "d5h": d5h,
        }
        all_data[dt].append(record)
    
    processed += 1
    if processed % 500 == 0:
        print(f"  {processed}/{len(unique_files)} 股票, {sum(len(v) for v in all_data.values())}条记录", flush=True)

print(f"\n✅ 股票处理: {processed}/{len(unique_files)}")
print(f"📅 {len(all_data)}个交易日, {sum(len(v) for v in all_data.values())}条记录")
print(f"⏱ {time.time()-T0:.0f}秒")

# ====== 3. 获取实时行情数据（换手率/PE/市值）====== 
all_codes = sorted(set(r["code"] for v in all_data.values() for r in v))
print(f"\n📡 获取{len(all_codes)}只股票实时数据...")

real_data = {}
names = {}

for i in range(0, len(all_codes), 80):
    chunk = all_codes[i:i+80]
    symbols = [f"sh{c}" if c.startswith(("6","9")) else f"sz{c}" for c in chunk]
    url = f"https://qt.gtimg.cn/q={','.join(symbols)}"
    text = curl_get(url, timeout=10)
    for line in text.split("\n"):
        if "~" not in line: continue
        parts = line.split("~")
        if len(parts) < 46: continue
        try:
            ck = parts[2]
            nm = parts[1]
            if "ST" in nm or "*ST" in nm or "退" in nm: continue
            if ck not in all_codes: continue
            hsl = 0
            try: hsl = float(parts[46]) if parts[46] and float(parts[46]) < 100 else 0
            except: pass
            pe = 0
            try: pe = float(parts[39]) if parts[39] else 0
            except: pass
            sz = 0
            try: sz = float(parts[44]) / 1e8 if parts[44] else 0
            except: pass
            real_data[ck] = {"hsl": hsl, "pe": pe, "shizhi": sz, "liangbi": 0}
            names[ck] = nm
        except: pass

print(f"✅ 实时数据: {len(real_data)}只")

# ====== 4. 保存 ======
cache = {
    "data": dict(all_data),
    "names": names,
    "real": real_data,
    "build_time": time.time() - T0,
    "date": time.strftime("%Y-%m-%d %H:%M:%S"),
}

with open(OUTPUT, "wb") as f:
    pickle.dump(cache, f)

# ====== 5. 统计 ======
dates = sorted(all_data.keys())
print(f"\n{'='*50}")
print(f"✅ 缓存已保存: {OUTPUT}")
print(f"📅 {len(dates)}天 ({dates[0]} ~ {dates[-1]})")
print(f"📊 {sum(len(v) for v in all_data.values())}条记录")
print(f"💾 {len(real_data)}只实时数据")
print(f"⏱ {time.time()-T0:.0f}秒")
print(f"\n最新5天:")
for dt in dates[-5:]:
    ss = all_data[dt]
    ps = [s["p"] for s in ss if abs(s["p"]) < 15]
    neg = sum(1 for p in ps if p < 0)
    pos = sum(1 for p in ps if p > 0)
    ap = sum(ps)/len(ps) if ps else 0
    print(f"  {dt}: {len(ss)}只, 正{pos}负{neg}, 均{ap:.2f}%")
