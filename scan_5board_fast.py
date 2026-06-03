"""
快速扫描五连板 v2 — 兼容稳定版本
"""
import os, pickle, time, json, sys
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
LOG = '/tmp/scan5b.log'

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')
    print(msg)

pool = json.load(open(os.path.join(SCRIPTS_DIR, '活跃股票池_3043.json'), encoding='utf-8'))
codes = pool['codes']
main_codes = sorted(set(c for c in codes if IS_MAIN(c)))
log(f'主板: {len(main_codes)}只')

V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    names = pickle.load(f)['names']

import akshare as ak
all_5b = []
done = 0
total = len(main_codes)

for i, code in enumerate(main_codes):
    try:
        df = ak.stock_zh_a_hist(symbol=code, period='daily',
                               start_date='20230601', end_date='20260529',
                               adjust='qfq')
    except:
        done += 1
        continue
    
    if df is None or len(df) < 30:
        done += 1
        continue
    
    records = []
    for _, row in df.iterrows():
        dt = str(row.iloc[0])[:10]  # 日期
        close = float(row.iloc[3])  # 收盘
        pct = float(row.iloc[9]) if row.iloc[9] != '' else 0  # 涨跌幅
        records.append({'date': dt, 'p': pct, 'close': close})
    
    if len(records) < 60:
        done += 1
        continue
    
    for j in range(len(records) - 5):
        ok = True
        for k in range(5):
            if records[j+k]['p'] < 9.5:
                ok = False
                break
        if ok and j >= 7:
            nm = names.get(code, '?')
            all_5b.append((code, nm, records[j]['date'], records[j+4]['date'],
                          [records[j+k]['p'] for k in range(5)]))
    
    done += 1
    if done % 100 == 0:
        log(f'[{done}/{total}] 五连板:{len(all_5b)}个')

# 去重
seen = set()
unique = []
for c, n, s, e, ps in all_5b:
    if (c, s) not in seen:
        seen.add((c, s))
        unique.append((c, n, s, e, ps))

unique.sort(key=lambda x: x[2])

years = {}
for _, _, s, _, _ in unique:
    years[s[:4]] = years.get(s[:4], 0) + 1

log(f'\n✅ 完成! {done}/{total}, 五连板:{len(unique)}个')
log(f'按年份: {years}')
for c, n, s, e, ps in unique[:20]:
    log(f'  {c}({n}): {s}~{e} {"→".join(f"{x:.0f}%" for x in ps)}')

# 保存
with open(os.path.join(SCRIPTS_DIR, 'five_board_3year.pkl'), 'wb') as f:
    pickle.dump({'boards': unique, 'names': names}, f)
log(f'✅ 已保存')
