"""
Step 1: 下载所有五连板股票的日K线
"""
import os, pickle, json, time, sys
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

with open(os.path.join(SCRIPTS_DIR, 'five_board_3year.pkl'), 'rb') as f:
    d = pickle.load(f)
raw = d['boards']

# 去重获取唯一股票
codes = set()
for c, n, s, e, ps in raw:
    codes.add(c)
codes = sorted(codes)
print(f'唯一股票: {len(codes)}只')

import akshare as ak
PREFIX = lambda c: 'sh' if c.startswith('6') else 'sz'

stock_data = {}
for i, code in enumerate(codes):
    sym = f'{PREFIX(code)}{code}'
    try:
        df = ak.stock_zh_a_daily(symbol=sym, adjust='qfq')
        records = []; prev = None
        for _, row in df.iterrows():
            dt = str(row['date'])[:10]
            c = float(row['close'])
            p = round((c - prev) / prev * 100, 2) if prev and prev > 0 else 0
            records.append({'date': dt, 'close': c, 'p': p,
                          'open': float(row['open']), 'high': float(row['high']),
                          'low': float(row['low']), 'volume': float(row['volume'])})
            prev = c
        stock_data[code] = records
    except:
        pass
    
    if (i+1) % 50 == 0:
        print(f'[{i+1}/{len(codes)}] 已缓存{len(stock_data)}只')
    time.sleep(0.05)

print(f'\n✅ 下载完成: {len(stock_data)}只')
# 保存
with open(os.path.join(SCRIPTS_DIR, 'five_board_stock_cache.pkl'), 'wb') as f:
    pickle.dump(stock_data, f)
print(f'已保存: five_board_stock_cache.pkl')
