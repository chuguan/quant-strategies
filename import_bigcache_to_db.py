#!/usr/bin/env python
"""导入 big_cache 数据到 SQLite"""
import sqlite3, os, sys, time

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

# ═══ 1. 先导入 scripts/big_cache_full.pkl (11MB) ═══
small_cache = os.path.join(SCRIPTS_DIR, 'big_cache_full.pkl')
if os.path.exists(small_cache):
    print(f'📦 发现小缓存: {small_cache} ({os.path.getsize(small_cache)/1024/1024:.0f}MB)')
    
    import pickle
    print('加载中...')
    t0 = time.time()
    with open(small_cache, 'rb') as f:
        d = pickle.load(f)
    print(f'  加载完成: {time.time()-t0:.1f}s')
    print(f'  keys: {list(d.keys())}')
    
    data = d.get('data', {})
    real = d.get('real', {})
    names = d.get('names', {})
    
    print(f'  天数: {len(data)}')
    sample_dates = sorted(data.keys())
    print(f'  日期范围: {sample_dates[0]} ~ {sample_dates[-1]}')
    
    # 看一条数据是什么结构
    first_date = sample_dates[0]
    first_stock = data[first_date][0]
    print(f'  单条数据字段: {list(first_stock.keys())[:20]}')
    
    # 连接到DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    total_rows = 0
    t1 = time.time()
    
    for dt in sorted(data.keys()):
        stocks = data[dt]
        batch = []
        for s in stocks:
            code = s.get('code', '')
            if not code:
                continue
            row = (
                dt, code,
                names.get(code, ''),
                s.get('p', 0) or 0,
                s.get('cl', 50) or 50,
                s.get('vr', 1) or 1,
                s.get('n', 0) or 0,
                s.get('vol_ratio', 1) or 1,
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
                'big_cache'
            )
            batch.append(row)
            total_rows += 1
        
        c.executemany('''
            INSERT OR IGNORE INTO data_cache
            (date, code, name, p, cl, vr, n, vol_ratio,
             dif_val, macd_golden, wr_val, j_val, k_val, d_val,
             pos_in_day, above_ma5, kdj_golden,
             close, volume, original_source)
            VALUES (?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,
                    ?,?,?,
                    ?,?,?)
        ''', batch)
    
    conn.commit()
    conn.close()
    print(f'  导入完成: {total_rows} 行, 耗时 {time.time()-t1:.1f}s')

# ═══ 2. 导入 V13/release/big_cache_full.pkl (269MB) ═══
# 这个文件太大，分批处理
big_cache = os.path.join(SCRIPTS_DIR, 'release', 'V13', 'big_cache_full.pkl')
if os.path.exists(big_cache):
    print(f'\n📦 发现大缓存: {big_cache} ({os.path.getsize(big_cache)/1024/1024:.0f}MB)')
    print(f'  尝试加载...')
    t0 = time.time()
    try:
        import pickle
        with open(big_cache, 'rb') as f:
            d = pickle.load(f)
        
        data = d.get('data', {})
        real = d.get('real', {})
        names = d.get('names', {})
        
        print(f'  加载完成: {time.time()-t0:.1f}s')
        print(f'  天数: {len(data)}')
        dates = sorted(data.keys())
        print(f'  日期范围: {dates[0]} ~ {dates[-1]}')
        print(f'  股票数: {len(names)}')
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 分批写入（每次100天）
        BATCH_DAYS = 50
        total = 0
        t1 = time.time()
        deleted = 0
        
        for batch_start in range(0, len(dates), BATCH_DAYS):
            batch_dates = dates[batch_start:batch_start + BATCH_DAYS]
            rows = []
            for dt in batch_dates:
                stocks = data.get(dt, [])
                for s in stocks:
                    code = s.get('code', '')
                    if not code:
                        continue
                    rows.append((
                        dt, code, names.get(code, ''),
                        s.get('p', 0) or 0,
                        s.get('cl', 50) or 50,
                        s.get('vr', 1) or 1,
                        s.get('n', 0) or 0,
                        s.get('vol_ratio', 1) or 1,
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
                        'big_cache',
                        'big_cache_2026-05-29'
                    ))
                    total += 1
            
            c.executemany('''
                INSERT OR IGNORE INTO data_cache
                (date, code, name, p, cl, vr, n, vol_ratio,
                 dif_val, macd_golden, wr_val, j_val, k_val, d_val,
                 pos_in_day, above_ma5, kdj_golden,
                 close, volume, original_source, cache_version)
                VALUES (?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,
                        ?,?,?,
                        ?,?,?,?)
            ''', rows)
            
            conn.commit()
            # 显示进度
            pct = min(100, (batch_start + BATCH_DAYS) * 100 // len(dates))
            elapsed = time.time() - t1
            rate = total / elapsed if elapsed > 0 else 0
            print(f'  进度: {pct}% | {total}行 | {elapsed:.0f}s | {rate:.0f}行/秒')
        
        # 释放内存
        del d, data, rows
        
        conn.close()
        print(f'\n  ✅ 大缓存导入完成: {total} 行, 总计 {time.time()-t1:.0f}s')
        
    except MemoryError:
        print(f'  ❌ 内存不足，无法加载269MB pickle')
        print(f'  💡 建议：用 akshare 或新浪API重新拉取数据，分批写入')
    except Exception as e:
        print(f'  ❌ 导入失败: {e}')

print(f'\n📊 入库完成')
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
cnt = c.execute('SELECT COUNT(*) FROM data_cache').fetchone()[0]
c.execute('SELECT MIN(date), MAX(date) FROM data_cache')
dr = c.fetchone()
conn.close()
print(f'  data_cache 表现有: {cnt} 行')
print(f'  日期范围: {dr[0]} ~ {dr[1]}')
print(f'  📁 {DB_PATH}')
