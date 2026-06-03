"""
全量缓存重建 v2 - 高效版
3427只沪深主板，用增量算法算MACD/KDJ
"""
import os, json, time, pickle

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
t0 = time.time()

# 1. 获取股票代码
main_codes = []
for fname in os.listdir(CACHE_DIR):
    if not fname.endswith('.json'):
        continue
    code = fname.replace('.json', '')
    if code.startswith('sh60') or code.startswith('sz000') or code.startswith('sz001') or code.startswith('sz002') or code.startswith('sz003'):
        main_codes.append(code)
print(f'沪深主板股票: {len(main_codes)}只', flush=True)

# 2. 加载旧缓存
with open('big_cache.pkl', 'rb') as f:
    old = pickle.load(f)
names = old.get('names', {})
real = old.get('real', {})

# 3. 逐股票计算
all_dates = set()
stock_data = {}
processed = 0

for code in main_codes:
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    try:
        with open(fp, 'r') as f:
            klines = json.load(f)
    except:
        continue
    if len(klines) < 60:
        continue

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

    # 增量EMA计算
    ema12 = closes[0]
    ema26 = closes[0]

    for i in range(n):
        if i == 0:
            continue
        dt = dates[i]
        c, h, l, o, v = closes[i], highs[i], lows[i], opens[i], volumes[i]
        pc = closes[i - 1]

        p = (c / pc - 1) * 100 if pc > 0 else 0
        if abs(p) > 20:
            # 即使跳过，也要更新EMA
            ema12 = ema12 * 11/13 + c * 2/13
            ema26 = ema26 * 25/27 + c * 2/27
            continue

        cl = (c - l) / (h - l) * 100 if h != l else 50
        is_yang = 1 if c > o else 0

        # MA
        ma5 = sum(closes[max(0,i-4):i+1]) / min(5,i+1)
        above_ma5 = 1 if c > ma5 else 0
        ma10 = sum(closes[max(0,i-9):i+1]) / min(10,i+1)
        ma20 = sum(closes[max(0,i-19):i+1]) / min(20,i+1)
        ma60 = sum(closes[max(0,i-59):i+1]) / min(60,i+1)

        # 量比
        vol_5 = sum(volumes[max(0,i-4):i+1]) / min(5,i+1)
        vol_ratio = v / vol_5 if vol_5 > 0 else 1

        # ATR(14)
        close_atr = 0
        if i >= 14:
            tr = max(h-l, abs(h-pc), abs(l-pc))
            trs = [max(highs[j]-lows[j], abs(highs[j]-closes[j-1]), abs(lows[j]-closes[j-1])) for j in range(i-13, i+1)]
            atr = sum(trs) / 14
            close_atr = atr / c * 100 if c > 0 else 0

        # MACD - 增量EMA
        ema12 = ema12 * 11/13 + c * 2/13
        ema26 = ema26 * 25/27 + c * 2/27
        dif = ema12 - ema26
        # DEA用简化的同步计算
        if i == 1:
            dea = dif
        else:
            dea = dea * 8/10 + dif * 2/10
        macd_gap = dif - dea

        # MACD金叉：DIF上穿DEA（前一天DIF<DEA，今天DIF>=DEA）
        macd_golden = 0
        if i >= 2:
            # 用前一天的dif_prev和dea_prev
            if dif_prev is not None and dea_prev is not None:
                if dif_prev < dea_prev and dif >= dea:
                    macd_golden = 1

        dif_prev = dif
        dea_prev = dea

        # KDJ (9,3,3) - 增量
        k_val = 50; d_val = 50; j_val = 50; kdj_golden = 0
        if i >= 8:
            h9 = max(highs[i-8:i+1])
            l9 = min(lows[i-8:i+1])
            rsv = (c - l9) / (h9 - l9) * 100 if h9 != l9 else 50
            if i == 8:
                k9 = d9 = 50
            k9 = k9 * 2/3 + rsv * 1/3
            d9 = d9 * 2/3 + k9 * 1/3
            j9 = 3 * k9 - 2 * d9
            k_val = k9; d_val = d9; j_val = j9
            # KDJ金叉：K上穿D
            if i >= 9:
                if k_prev < d_prev and k9 >= d9:
                    kdj_golden = 1

        # 保存当前KDJ值供下一轮使用
        if i >= 8:
            k_prev = k9; d_prev = d9
        else:
            k_prev = 50; d_prev = 50

        # 次日最高/收盘
        n_val = 0; nc_val = 0
        if i < n - 1:
            n_val = (highs[i+1] / c - 1) * 100
            nc_val = (closes[i+1] / c - 1) * 100

        records[dt] = {
            'code': code, 'p': round(p,2), 'a': round(close_atr,2), 'cl': round(cl,1),
            'close': c, 'is_yang': is_yang, 'above_ma5': above_ma5,
            'vol_ratio': round(vol_ratio,2), 'dif_val': round(dif,3),
            'dea_val': round(dea,3), 'macd_gap': round(macd_gap,3),
            'macd_golden': macd_golden, 'k_val': round(k_val,1),
            'd_val': round(d_val,1), 'j_val': round(j_val,1),
            'kdj_golden': kdj_golden, 'n': round(n_val,2),
            'next_close': round(nc_val,2),
            'ma5': round(ma5,3), 'ma10': round(ma10,3), 'ma20': round(ma20,3), 'ma60': round(ma60,3),
        }

        # KDJ金叉需要前一天的K/D值，用first_day_idx方案
        # 简化：在回测前初始化kdj_prev

    stock_data[code] = records
    processed += 1
    if processed % 500 == 0:
        print(f'进度: {processed}/{len(main_codes)} ({time.time()-t0:.0f}s)', flush=True)

print(f'计算完成: {processed}只, {time.time()-t0:.0f}s', flush=True)

# 4. 按日期整理
all_dates_sorted = sorted(d for d in all_dates if d >= '2024-01-01')

new_data = {}
for dt in all_dates_sorted:
    day_stocks = []
    for code in main_codes:
        rec = stock_data.get(code, {}).get(dt)
        if rec:
            day_stocks.append(rec)
    if day_stocks:
        new_data[dt] = day_stocks

print(f'日期: {all_dates_sorted[0]}~{all_dates_sorted[-1]}, 有数据{len(new_data)}天', flush=True)
last_dt = all_dates_sorted[-1]
print(f'最新一天({last_dt}): {len(new_data.get(last_dt,[]))}只', flush=True)

# 5. 保存
new_cache = {'data': new_data, 'names': names, 'real': real, 'build_time': time.time()}
with open('big_cache_full.pkl', 'wb') as f:
    pickle.dump(new_cache, f)

elapsed = time.time() - t0
fsize = os.path.getsize('big_cache_full.pkl')
print(f'保存完成! {fsize/1024/1024:.0f}MB, 用时{elapsed:.0f}s', flush=True)
