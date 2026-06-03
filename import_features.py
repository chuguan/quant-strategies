#!/usr/bin/env python
"""导入 features_30d.pkl 到 features_cache 表"""
import pickle, sqlite3, os, time, sys

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
FEATURES_FILE = os.path.join(SCRIPTS_DIR, 'release', 'V13', 'features_30d.pkl')

print('加载 features_30d.pkl...')
sys.stdout.flush()
t0 = time.time()
with open(FEATURES_FILE, 'rb') as f:
    precomputed = pickle.load(f)
print(f'加载完成: {time.time()-t0:.1f}s')
print(f'数据类型: {type(precomputed).__name__}')
sys.stdout.flush()

# 看看数据结构
sample_key = None
for k in precomputed:
    sample_key = k
    break
print(f'键格式: {sample_key}')
print(f'值字段: {list(precomputed[sample_key].keys()) if isinstance(precomputed.get(sample_key), dict) else type(precomputed[sample_key])}')
sys.stdout.flush()

conn = sqlite3.connect(DB_PATH)
conn.execute('PRAGMA synchronous=OFF')
c = conn.cursor()

# 确保 features_cache 表存在
c.execute('''
    CREATE TABLE IF NOT EXISTS features_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        code TEXT NOT NULL,
        d1 REAL DEFAULT 0, d2 REAL DEFAULT 0, d3 REAL DEFAULT 0,
        d4 REAL DEFAULT 0, d5 REAL DEFAULT 0,
        slope5 REAL DEFAULT 0,
        t4_shadow REAL DEFAULT 0,
        cons_up REAL DEFAULT 0,
        peak_decay REAL DEFAULT 0,
        computed_from TEXT DEFAULT 'features_30d_pkl',
        UNIQUE(date, code)
    )
''')
c.execute('CREATE INDEX IF NOT EXISTS idx_feat_date_code ON features_cache(date, code)')

# 清空旧数据
c.execute("DELETE FROM features_cache WHERE computed_from='features_30d_pkl'")
conn.commit()

total = 0
t1 = time.time()
rows = []

for (code, dt), feats in precomputed.items():
    if not isinstance(feats, dict):
        continue
    rows.append((
        dt, code,
        feats.get('d1', 0), feats.get('d2', 0), feats.get('d3', 0),
        feats.get('d4', 0), feats.get('d5', 0),
        feats.get('slope5', 0),
        feats.get('t4_shadow', 0),
        feats.get('cons_up', 0),
        feats.get('peak_decay', 0),
        'features_30d_pkl'
    ))
    total += 1
    
    # 每5万条写入一次
    if len(rows) >= 50000:
        c.executemany('''
            INSERT OR IGNORE INTO features_cache
            (date, code, d1, d2, d3, d4, d5,
             slope5, t4_shadow, cons_up, peak_decay, computed_from)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ''', rows)
        conn.commit()
        print(f'  已写入 {total} 条...')
        sys.stdout.flush()
        rows = []

# 写入剩余
if rows:
    c.executemany('''
        INSERT OR IGNORE INTO features_cache
        (date, code, d1, d2, d3, d4, d5,
         slope5, t4_shadow, cons_up, peak_decay, computed_from)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    ''', rows)
    conn.commit()

del precomputed

c.execute('SELECT COUNT(*), MIN(date), MAX(date) FROM features_cache')
cnt, dmin, dmax = c.fetchone()
print(f'\n✅ features_cache: {cnt}行, {dmin}~{dmax}, 耗时{time.time()-t1:.0f}s')
conn.close()
