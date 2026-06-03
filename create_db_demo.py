#!/usr/bin/env python
"""创建 v13_quant.db 数据库演示"""
import sqlite3, os, sys

db_path = os.path.expanduser('~/AppData/Local/hermes/scripts/v13_quant.db')
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
c = conn.cursor()

# ===== 1. 公共行情数据 =====
c.execute('''
    CREATE TABLE data_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        code TEXT NOT NULL,
        name TEXT,
        p REAL,
        cl REAL,
        vr REAL,
        n REAL,
        dif_val REAL,
        macd_golden INTEGER,
        wr_val REAL,
        j_val REAL,
        k_val REAL,
        d_val REAL,
        pos_in_day REAL,
        above_ma5 INTEGER,
        kdj_golden INTEGER,
        close REAL,
        volume REAL,
        source TEXT DEFAULT 'big_cache',
        UNIQUE(date, code)
    )
''')

c.execute('''
    CREATE TABLE data_sina (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        code TEXT NOT NULL,
        name TEXT,
        price REAL,
        pre_close REAL,
        pct REAL,
        high REAL,
        low REAL,
        volume REAL,
        amount REAL,
        source TEXT DEFAULT 'sina',
        UNIQUE(date, code)
    )
''')

# ===== 2. 特征数据 =====
c.execute('''
    CREATE TABLE features_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        code TEXT NOT NULL,
        d1 REAL DEFAULT 0,
        d2 REAL DEFAULT 0,
        d3 REAL DEFAULT 0,
        d4 REAL DEFAULT 0,
        d5 REAL DEFAULT 0,
        slope5 REAL DEFAULT 0,
        t4_shadow REAL DEFAULT 0,
        cons_up REAL DEFAULT 0,
        peak_decay REAL DEFAULT 0,
        source TEXT DEFAULT 'features_30d',
        UNIQUE(date, code)
    )
''')

# ===== 3. 选股结果表（按版本）=====
for v in ['V13', 'V13A', 'V13B', 'V13C', 'V14', 'V15']:
    c.execute(f'''
        CREATE TABLE selections_{v} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            run_time TEXT,
            market_type TEXT,
            market_key TEXT,
            pool_size INTEGER,
            used_level TEXT,
            total_candidates INTEGER,
            rank INTEGER,
            code TEXT NOT NULL,
            name TEXT,
            score REAL,
            p REAL,
            cl REAL,
            wrv REAL,
            vr REAL,
            price REAL,
            pre_close REAL,
            data_source TEXT DEFAULT 'sina_1450',
            UNIQUE(date, rank)
        )
    ''')

conn.commit()

# ===== 插入演示数据（V13历史30天选股结果）=====
v13_results = [
    (4, 8, '2026-04-08', '真实涨日', 'real_up', '兴瑞科技', 6.3),
    (4, 9, '2026-04-09', '跌日', 'down', '奥海科技', 4.0),
    (4,10, '2026-04-10', '真实涨日', 'real_up', '海思科', 10.0),
    (4,13, '2026-04-13', '横盘', 'flat', '航天电器', 5.7),
    (4,14, '2026-04-14', '真实涨日', 'real_up', '通宇通讯', 3.1),
    (4,15, '2026-04-15', '横盘', 'flat', '华懋科技', 3.0),
    (4,16, '2026-04-16', '真实涨日', 'real_up', '通宇通讯', 7.5),
    (4,17, '2026-04-17', '横盘', 'flat', '华正新材', 2.6),
    (4,20, '2026-04-20', '真实涨日', 'real_up', '泰晶科技', 10.0),
    (4,21, '2026-04-21', '横盘', 'flat', '水晶光电', 2.9),
    (4,22, '2026-04-22', '横盘', 'flat', '博云新材', 10.0),
    (4,23, '2026-04-23', '跌日', 'down', '博杰股份', 6.1),
    (4,24, '2026-04-24', '横盘', 'flat', '株冶集团', 4.2),
    (4,27, '2026-04-27', '横盘', 'flat', '禾望电气', 6.1),
    (4,28, '2026-04-28', '跌日', 'down', '中旗新材', 2.8),
    (4,29, '2026-04-29', '真实涨日', 'real_up', '安孚科技', 3.5),
    (4,30, '2026-04-30', '横盘', 'flat', '四方股份', 10.1),
    (5, 6, '2026-05-06', '真实涨日', 'real_up', '迎丰股份', 5.0),
    (5, 7, '2026-05-07', '真实涨日', 'real_up', '华升股份', 5.8),
    (5, 8, '2026-05-08', '真实涨日', 'real_up', '东方通信', 4.5),
    (5,11, '2026-05-11', '真实涨日', 'real_up', '平安电工', 10.0),
    (5,12, '2026-05-12', '跌日', 'down', '宇环数控', 2.9),
    (5,13, '2026-05-13', '真实涨日', 'real_up', '东方钽业', 6.9),
    (5,14, '2026-05-14', '跌日', 'down', '巨轮智能', 9.9),
    (5,15, '2026-05-15', '跌日', 'down', '新泉股份', 6.6),
    (5,18, '2026-05-18', '横盘', 'flat', '兆易创新', 2.5),
    (5,19, '2026-05-19', '虚涨日', 'fake_up', '法狮龙', 2.9),
    (5,20, '2026-05-20', '跌日', 'down', '锦和商管', 3.7),
    (5,21, '2026-05-21', '跌日', 'down', '新坐标', 4.4),
    (5,22, '2026-05-22', '真实涨日', 'real_up', '再升科技', 7.7),
]

for m, d, dt, mkt_cn, mkt_key, name, nh in v13_results:
    date_str = f'2026-{m:02d}-{d:02d}'
    code = f'600{hash(name)%1000:03d}'  # fake code for demo
    c.execute('''
        INSERT INTO selections_V13 
        (date, run_time, market_type, market_key, pool_size, used_level, 
         total_candidates, rank, code, name, score, p, cl, wrv, vr, price, pre_close, data_source)
        VALUES (?, '14:50:00', ?, ?, 30, 'L1', 3000, 1, ?, ?, 85, 4.5, 65, 45, 1.2, 15.50, 14.85, 'sina_1450')
    ''', (date_str, mkt_cn, mkt_key, code, name))

conn.commit()
print(f'✅ 插入 {len(v13_results)} 条V13选股演示数据')

# 也插入少量V13A的演示数据（不同的股票展示区分）
v13a_demo = [
    ('2026-05-22', '真实涨日', 'real_up', '东方通信', 6.5),
    ('2026-05-21', '跌日', 'down', '新坐标', 4.4),
    ('2026-05-20', '跌日', 'down', '锦和商管', 3.7),
]
for date_str, mkt_cn, mkt_key, name, sc in v13a_demo:
    fake_code = f"002{abs(hash(name)) % 1000:03d}"
    c.execute('''
        INSERT INTO selections_V13A
        (date, run_time, market_type, market_key, pool_size, used_level,
         total_candidates, rank, code, name, score, p, cl, wrv, vr, price, pre_close, data_source)
        VALUES (?, '14:50:05', ?, ?, 28, 'L0', 3000, 1, ?, ?, 92, 5.2, 72, 35, 1.5, 18.20, 17.30, 'sina_1450')
    ''', (date_str, mkt_cn, mkt_key, fake_code, name))

conn.commit()
print('✅ 插入 3 条V13A演示数据（和V13不同的冠军，展示版本区分）')

# 插入几条big_cache模拟数据
import random
for i, dt in enumerate(['2026-05-20','2026-05-21','2026-05-22']):
    for j, code in enumerate(['600001','600002','600003','600004','600005']):
        c.execute('''
            INSERT OR IGNORE INTO data_cache
            (date, code, name, p, cl, vr, n, dif_val, macd_golden, wr_val, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'big_cache')
        ''', (dt, code, f'股票{j+1}', round(random.uniform(-5,7),1), random.randint(20,90),
              round(random.uniform(0.3,2.5),1), round(random.uniform(1,8),1),
              round(random.uniform(-1,2),2), random.randint(0,1), random.randint(10,90)))

conn.commit()
print(f'✅ 插入 15 条 data_cache 演示数据')

conn.close()

# 展示结果
conn2 = sqlite3.connect(db_path)
cur = conn2.cursor()

print(f'\n{"="*60}')
print(f'  📂 v13_quant.db — 完整表结构')
print(f'{"="*60}')

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]

print(f'\n{"表名":>25} {"行数":>8} {"用途":>20}')
print(f'{"-"*55}')
for tb in tables:
    cur.execute(f'SELECT COUNT(*) FROM {tb}')
    cnt = cur.fetchone()[0]
    # 用途说明
    usage = {
        'data_cache': '历史收盘数据(big_cache)',
        'data_sina': '新浪2:50实时行情',
        'features_cache': '预计算特征',
        'selections_V13': 'V13选股结果',
        'selections_V13A': 'V13A选股结果',
        'selections_V13B': 'V13B选股结果(空)',
        'selections_V13C': 'V13C选股结果(空)',
        'selections_V14': 'V14选股结果(空)',
        'selections_V15': 'V15选股结果(空)',
    }
    print(f'{tb:>25} {cnt:>8} {usage.get(tb,""):>20}')

print(f'\n{"="*60}')
print(f'  selections_V13 表数据预览（TOP10格式）')
print(f'{"="*60}')
cur.execute('''
    SELECT date, market_type, name, score, p, data_source 
    FROM selections_V13 
    ORDER BY date DESC 
    LIMIT 10
''')
print(f'{"日期":>12} {"行情":>6} {"冠军":>10} {"评分":>5} {"涨幅":>6} {"数据源":>12}')
print(f'{"-"*55}')
for r in cur.fetchall():
    print(f'{r[0]:>12} {r[1]:>6} {r[2]:>10} {r[3]:>5.0f} {r[4]:>+5.1f}% {r[5]:>12}')

print(f'\n{"="*60}')
print(f'  selections_V13A 表数据（与V13对比，同名但不同冠军）')
print(f'{"="*60}')
cur.execute('''
    SELECT date, market_type, name, score, p, data_source 
    FROM selections_V13A 
    ORDER BY date DESC 
    LIMIT 5
''')
print(f'{"日期":>12} {"行情":>6} {"冠军":>10} {"评分":>5} {"涨幅":>6} {"数据源":>12}')
print(f'{"-"*55}')
for r in cur.fetchall():
    print(f'{r[0]:>12} {r[1]:>6} {r[2]:>10} {r[3]:>5.0f} {r[4]:>+5.1f}% {r[5]:>12}')

print(f'\n{"="*60}')
print(f'  data_cache 表数据（原始行情，按来源分）')
print(f'{"="*60}')
cur.execute('''
    SELECT date, code, name, p, dif_val, macd_golden, source 
    FROM data_cache 
    ORDER BY date DESC 
    LIMIT 10
''')
print(f'{"日期":>12} {"代码":>8} {"名称":>8} {"涨幅":>6} {"DIF":>6} {"金叉":>5} {"来源":>10}')
print(f'{"-"*55}')
for r in cur.fetchall():
    print(f'{r[0]:>12} {r[1]:>8} {r[2]:>8} {r[3]:>+5.1f}% {r[4]:>+6.2f} {r[5]:>5} {r[6]:>10}')

conn2.close()

print(f'\n{"="*60}')
print(f'  📊 数据库文件大小')
print(f'{"="*60}')
size = os.path.getsize(db_path)
print(f'  v13_quant.db: {size/1024:.1f} KB（目前仅演示数据）')
print(f'  正式导入big_cache后预计: ~50-80 MB')
print(f'  （相比原始big_cache的269MB pickle，小了3-5倍）')

print(f'\n{"="*60}')
print(f'  ✅ 设计总结')
print(f'{"="*60}')
print(f'  1. 数据源隔离：data_cache(big_cache) ≠ data_sina(新浪)')
print(f'  2. 版本隔离：每个版本有自己的selections_表')
print(f'  3. 所有记录带 source + run_time，清楚知道从哪来')
print(f'  4. 回测只查data_cache，不加载全部，毫秒级')
print(f'  5. 选股结果直接写selections_表，和邮件一致')
