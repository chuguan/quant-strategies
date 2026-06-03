#!/usr/bin/env python
"""导入269MB big_cache全量数据到SQLite"""
import pickle, sqlite3, os, time, sys

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
BIG_FILE = os.path.join(SCRIPTS_DIR, 'release', 'V13', 'big_cache_full.pkl')

print('加载269MB big_cache...')
sys.stdout.flush()
t0 = time.time()
with open(BIG_FILE, 'rb') as f:
    d = pickle.load(f)
print(f'加载完成: {time.time()-t0:.1f}s')
sys.stdout.flush()

data = d['data']
names = d.get('names', {})
dates = sorted(data.keys())
print(f'总天数: {len(dates)}, 日期: {dates[0]}~{dates[-1]}')
print(f'股票数: {len(names)}')
sys.stdout.flush()

conn = sqlite3.connect(DB_PATH)
conn.execute('PRAGMA synchronous=OFF')
conn.execute('PRAGMA cache_size=-800000')
c = conn.cursor()

# 清空旧的big_cache数据
del_sql = "DELETE FROM data_cache WHERE original_source='big_cache'"
c.execute(del_sql)
conn.commit()
print('已清空旧数据')

total = 0
t1 = time.time()
BATCH = 50

for batch_start in range(0, len(dates), BATCH):
    batch_dates = dates[batch_start:batch_start + BATCH]
    rows = []
    for dt in batch_dates:
        stocks = data.get(dt, [])
        for s in stocks:
            code = s.get('code', '')
            if not code:
                continue
            nm = names.get(code, '')
            if not nm:
                continue
            
            rows.append((
                dt, code, nm,
                s.get('p', 0) or 0,
                s.get('cl', 50) or 50,
                s.get('vr', 1) or s.get('vol_ratio', 1) or 1,
                s.get('n', 0) or 0,
                s.get('dif_val', 0) or s.get('dif', 0) or 0,
                1 if (s.get('macd_golden', 0) or s.get('mg', 0)) else 0,
                s.get('wr_val', 0) or s.get('wrv', 50) or 50,
                s.get('j_val', 0) or s.get('jv', 50) or 50,
                s.get('k_val', 0) or s.get('kv', 50) or 50,
                s.get('d_val', 0) or s.get('dv', 50) or 50,
                s.get('pos_in_day', 50) or 50,
                1 if s.get('above_ma5', 0) else 0,
                1 if (s.get('kdj_golden', 0) or s.get('kdj_g', 0)) else 0,
                s.get('close', 0) or 0,
                s.get('volume', 0) or 0,
                'big_cache', 'big_cache_full'
            ))
    
    insert_sql = '''
        INSERT OR IGNORE INTO data_cache
        (date,code,name,p,cl,vr,n,
         dif_val,macd_golden,wr_val,j_val,k_val,d_val,
         pos_in_day,above_ma5,kdj_golden,
         close,volume,original_source,cache_version)
        VALUES(?,?,?,?,?,?,?,
               ?,?,?,?,?,?,
               ?,?,?,
               ?,?,?,?)
    '''
    c.executemany(insert_sql, rows)
    conn.commit()
    total += len(rows)
    pct = min(100, (batch_start + BATCH) * 100 // len(dates))
    elapsed = time.time() - t1
    rate = total / elapsed if elapsed > 0 else 0
    print(f'{pct:>3}% | {batch_start+BATCH}/{len(dates)}天 | {total}行 | {elapsed:.0f}s | {rate:.0f}行/秒')
    sys.stdout.flush()

del d  # 释放内存

c.execute("SELECT COUNT(*),MIN(date),MAX(date) FROM data_cache WHERE original_source='big_cache'")
cnt, dmin, dmax = c.fetchone()
print(f'\n✅ 导入完成: {cnt}行, {dmin}~{dmax}, 耗时{time.time()-t1:.0f}s')
conn.close()
