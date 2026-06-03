"""
全量缓存重建 - 3427只沪深主板股票
从K线文件计算所有技术指标
"""
import os, json, time, pickle
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
t0 = time.time()

# 1. 获取所有沪深主板股票代码
main_codes = []
for fname in os.listdir(CACHE_DIR):
    if not fname.endswith('.json'):
        continue
    code = fname.replace('.json', '')
    if code.startswith('sh60') or code.startswith('sz000') or code.startswith('sz001') or code.startswith('sz002') or code.startswith('sz003'):
        main_codes.append(code)

print(f'沪深主板股票: {len(main_codes)}只', flush=True)

# 2. 加载旧缓存获取real和names
with open('big_cache.pkl', 'rb') as f:
    old = pickle.load(f)
names = old.get('names', {})
real = old.get('real', {})

# 3. 逐只股票计算
all_dates = set()
stock_data = {}
processed = 0
code_count = len(main_codes)

for code in main_codes:
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    try:
        with open(fp, 'r') as f:
            klines = json.load(f)
    except Exception:
        continue

    if len(klines) < 60:
        continue  # 少于60天数据，跳过

    dates = [d['date'] for d in klines]
    opens = [d['open'] for d in klines]
    highs = [d['high'] for d in klines]
    lows = [d['low'] for d in klines]
    closes = [d['close'] for d in klines]
    volumes = [d['volume'] for d in klines]
    n = len(klines)

    for dt in dates:
        all_dates.add(dt)

    records = {}

    for i in range(n):
        if i == 0:
            continue

        dt = dates[i]
        c, h, l, o, v = closes[i], highs[i], lows[i], opens[i], volumes[i]
        pc = closes[i - 1]

        # 涨跌幅
        p = (c / pc - 1) * 100 if pc > 0 else 0
        if abs(p) > 20:
            continue

        # 收盘位
        cl = (c - l) / (h - l) * 100 if h != l else 50

        # 阳线
        is_yang = 1 if c > o else 0

        # MA5
        if i >= 4:
            ma5 = sum(closes[i - 4:i + 1]) / 5
            above_ma5 = 1 if c > ma5 else 0
        else:
            ma5 = c
            above_ma5 = 0

        # MA10, MA20, MA60
        if i >= 9:
            ma10 = sum(closes[i - 9:i + 1]) / 10
        else:
            ma10 = 0
        if i >= 19:
            ma20 = sum(closes[i - 19:i + 1]) / 20
        else:
            ma20 = 0
        if i >= 59:
            ma60 = sum(closes[i - 59:i + 1]) / 60
        else:
            ma60 = 0

        # 量比
        vol_5 = sum(volumes[max(0, i - 4):i + 1]) / min(5, i + 1)
        vol_ratio = v / vol_5 if vol_5 > 0 else 1

        # ATR(14)
        close_atr = 0
        if i >= 14:
            tr_list = []
            for j in range(i - 13, i + 1):
                tr = max(highs[j] - lows[j], abs(highs[j] - closes[j - 1]), abs(lows[j] - closes[j - 1]))
                tr_list.append(tr)
            atr = sum(tr_list) / 14
            close_atr = atr / c * 100 if c > 0 else 0

        # MACD (12, 26, 9)
        dif = 0
        dea = 0
        macd_gap = 0
        macd_golden = 0
        if i >= 26:
            # EMA12
            ema12 = closes[0]
            for j in range(1, i + 1):
                ema12 = ema12 * 11 / 13 + closes[j] * 2 / 13
            # EMA26
            ema26 = closes[0]
            for j in range(1, i + 1):
                ema26 = ema26 * 25 / 27 + closes[j] * 2 / 27
            dif = ema12 - ema26
            dea = dif * 2 / 10  # 简化
            macd_gap = dif - dea
            # 前一天DIF(近似)
            if i >= 27:
                ema12_prev = closes[0]
                for j in range(1, i):
                    ema12_prev = ema12_prev * 11 / 13 + closes[j] * 2 / 13
                ema26_prev = closes[0]
                for j in range(1, i):
                    ema26_prev = ema26_prev * 25 / 27 + closes[j] * 2 / 27
                dif_prev = ema12_prev - ema26_prev
                if dif_prev < 0 and dif >= 0:
                    macd_golden = 1

        # KDJ (9, 3, 3)
        k_val = 50
        d_val = 50
        j_val = 50
        kdj_golden = 0
        if i >= 8:
            h9 = max(highs[i - 8:i + 1])
            l9 = min(lows[i - 8:i + 1])
            rsv = (c - l9) / (h9 - l9) * 100 if h9 != l9 else 50
            # 计算K值（递归）
            prev_k = 50
            prev_d = 50
            for j in range(i - 8, i + 1):
                r = (closes[j] - min(lows[j - 8:j + 1])) / (max(highs[j - 8:j + 1]) - min(lows[j - 8:j + 1])) * 100 if max(highs[j - 8:j + 1]) != min(lows[j - 8:j + 1]) else 50
                prev_k = 2 / 3 * prev_k + 1 / 3 * r
                prev_d = 2 / 3 * prev_d + 1 / 3 * prev_k
            k_val = prev_k
            d_val = prev_d
            j_val = 3 * k_val - 2 * d_val
            # KDJ金叉：K从下往上穿D
            if i >= 9:
                h9_prev = max(highs[i - 9:i])
                l9_prev = min(lows[i - 9:i])
                rsv_prev = (closes[i-1] - l9_prev) / (h9_prev - l9_prev) * 100 if h9_prev != l9_prev else 50
                pk = 50
                pd = 50
                for j in range(i - 9, i):
                    r = (closes[j] - min(lows[j - 8:j + 1])) / (max(highs[j - 8:j + 1]) - min(lows[j - 8:j + 1])) * 100 if max(highs[j - 8:j + 1]) != min(lows[j - 8:j + 1]) else 50
                    pk = 2 / 3 * pk + 1 / 3 * r
                    pd = 2 / 3 * pd + 1 / 3 * pk
                if pk < pd and k_val >= d_val:
                    kdj_golden = 1

        # 次日最高/收盘
        n_val = 0
        nc_val = 0
        if i < n - 1:
            n_val = (highs[i + 1] / c - 1) * 100
            nc_val = (closes[i + 1] / c - 1) * 100

        records[dt] = {
            'code': code,
            'p': round(p, 2),
            'a': round(close_atr, 2),
            'cl': round(cl, 1),
            'close': c,
            'is_yang': is_yang,
            'above_ma5': above_ma5,
            'vol_ratio': round(vol_ratio, 2),
            'dif_val': round(dif, 3),
            'dea_val': round(dea, 3),
            'macd_gap': round(macd_gap, 3),
            'macd_golden': macd_golden,
            'k_val': round(k_val, 1),
            'd_val': round(d_val, 1),
            'j_val': round(j_val, 1),
            'kdj_golden': kdj_golden,
            'n': round(n_val, 2),
            'next_close': round(nc_val, 2),
            'ma5': round(ma5, 3),
            'ma10': round(ma10, 3) if ma10 else 0,
            'ma20': round(ma20, 3) if ma20 else 0,
            'ma60': round(ma60, 3) if ma60 else 0,
        }

    stock_data[code] = records

    processed += 1
    if processed % 300 == 0:
        print(f'进度: {processed}/{code_count} ({time.time()-t0:.0f}s)', flush=True)

print(f'计算完成: {processed}只, {time.time()-t0:.0f}s', flush=True)

# 4. 按日期整理
all_dates_sorted = sorted(d for d in all_dates if d >= '2024-01-01')
print(f'日期范围: {all_dates_sorted[0]} ~ {all_dates_sorted[-1]}, {len(all_dates_sorted)}天', flush=True)

# 只保留有数据的日期
new_data = {}
for dt in all_dates_sorted:
    day_stocks = [rec for code in main_codes if (rec := stock_data.get(code, {}).get(dt))]
    if day_stocks:
        new_data[dt] = day_stocks
        if len(new_data) <= 3 or dt in ['2026-05-21', '2026-05-22']:
            print(f'  {dt}: {len(day_stocks)}只', flush=True)

print(f'实际有数据天数: {len(new_data)}天', flush=True)

# 5. 保存
new_cache = {
    'data': new_data,
    'names': names,
    'real': real,
    'build_time': time.time(),
}

with open('big_cache_full.pkl', 'wb') as f:
    pickle.dump(new_cache, f)

print(f'保存完成! big_cache_full.pkl', flush=True)
elapsed = time.time() - t0
print(f'总计用时{elapsed:.0f}s', flush=True)
fsize = os.path.getsize('big_cache_full.pkl')
print(f'文件大小: {fsize/1024/1024:.0f}MB', flush=True)
