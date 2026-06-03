"""
全量扫描五连板 — 3年主板数据
用法: python download_5board_scan.py
"""
import os, pickle, time, json, sys
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
PREFIX = lambda c: 'sh' if c.startswith('6') else 'sz'

# 获取代码列表
pool = json.load(open(os.path.join(SCRIPTS_DIR, '活跃股票池_3043.json'), encoding='utf-8'))
codes = pool['codes']
main_codes = sorted(set(c for c in codes if IS_MAIN(c)))
print(f'主板: {len(main_codes)}只')

# 名称
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    names = pickle.load(f)['names']

import akshare as ak
all_5b = []
done = 0
total = len(main_codes)

for i, code in enumerate(main_codes):
    sym = f"{PREFIX(code)}{code}"
    try:
        df = ak.stock_zh_a_daily(symbol=sym, adjust='qfq')
    except:
        done += 1; continue
    if df is None or len(df) < 60:
        done += 1; continue
    
    records = []
    prev_c = None
    for _, row in df.iterrows():
        dt = str(row['date'])[:10]
        if dt < '2023-06-01' or dt > '2026-05-29': continue
        c = float(row['close'])
        p = round((c - prev_c) / prev_c * 100, 2) if prev_c and prev_c > 0 else 0
        records.append({'date': dt, 'close': c, 'open': float(row['open']),
                       'high': float(row['high']), 'low': float(row['low']),
                       'volume': float(row['volume']), 'p': p})
        prev_c = c
    
    if len(records) < 60: done += 1; continue
    
    for j in range(len(records) - 5):
        if all(records[j+k]['p'] >= 9.5 for k in range(5)):
            if j >= 7:
                nm = names.get(code, sym)
                all_5b.append((code, nm, records[j]['date'], records[j+4]['date'],
                              [records[j+k]['p'] for k in range(5)]))
    
    done += 1
    if done % 50 == 0:
        print(f'[{done}/{total}] 五连板:{len(all_5b)}个')
    time.sleep(0.08)

# 去重
seen = set()
unique = []
for c, n, s, e, ps in all_5b:
    key = f"{c}_{s}"
    if key not in seen:
        seen.add(key)
        unique.append((c, n, s, e, ps))

unique.sort(key=lambda x: x[2])

years = {}
for _, _, s, _, _ in unique:
    years[s[:4]] = years.get(s[:4], 0) + 1

print(f'\n✅ 完成! 扫描{done}只, 发现{len(unique)}个五连板')
print(f'按年份: {years}')
for c, n, s, e, ps in unique[:10]:
    print(f'  {c}({n}): {s}~{e} {"→".join(f"{x:.0f}%" for x in ps)}')

# 保存
with open(os.path.join(SCRIPTS_DIR, 'five_board_3year.pkl'), 'wb') as f:
    pickle.dump({'boards': unique, 'names': names}, f)
print(f'已保存')
