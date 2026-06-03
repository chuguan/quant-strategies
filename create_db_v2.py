#!/usr/bin/env python
"""v13_quant.db — V2版：所有候选股保存，冠军SQL查询得出"""
import sqlite3, os, json
from datetime import datetime

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
        p REAL, cl REAL, vr REAL, n REAL,
        dif_val REAL, macd_golden INTEGER,
        wr_val REAL, j_val REAL, k_val REAL, d_val REAL,
        pos_in_day REAL, above_ma5 INTEGER, kdj_golden INTEGER,
        close REAL, volume REAL,
        source TEXT DEFAULT 'big_cache',
        UNIQUE(date, code)
    )
''')
c.execute('CREATE INDEX idx_cache_date ON data_cache(date)')
c.execute('CREATE INDEX idx_cache_code ON data_cache(code)')

c.execute('''
    CREATE TABLE data_sina (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        code TEXT NOT NULL,
        name TEXT,
        price REAL, pre_close REAL, pct REAL,
        high REAL, low REAL, volume REAL, amount REAL,
        source TEXT DEFAULT 'sina',
        UNIQUE(date, code, time)
    )
''')
c.execute('CREATE INDEX idx_sina_date ON data_sina(date)')

# ===== 2. 特征数据 =====
c.execute('''
    CREATE TABLE features_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        code TEXT NOT NULL,
        d1 REAL, d2 REAL, d3 REAL, d4 REAL, d5 REAL,
        slope5 REAL, t4_shadow REAL, cons_up REAL, peak_decay REAL,
        source TEXT DEFAULT 'features_30d',
        UNIQUE(date, code)
    )
''')
c.execute('CREATE INDEX idx_feat_date_code ON features_cache(date, code)')

# ===== 3. 选股池（所有候选股，所有版本）=====
c.execute('''
    CREATE TABLE selection_pool (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        run_time TEXT,
        data_source TEXT DEFAULT 'sina_1450',
        strategy_version TEXT NOT NULL,
        market_type TEXT,
        market_key TEXT,
        pool_size INTEGER,
        used_level TEXT,
        total_candidates INTEGER,
        
        code TEXT NOT NULL,
        name TEXT,
        
        -- 原始数据
        p REAL, cl REAL, wrv REAL, vr REAL, price REAL,
        
        -- 评分过程
        base_score REAL,          -- 评分函数算出的基础分
        momentum_penalty REAL,    -- 7天动量衰减扣分
        total_score REAL,         -- base_score + momentum_penalty = 最终分
        
        UNIQUE(date, strategy_version, code, run_time)
    )
''')
# 关键索引：按日期+版本+总分排序（查冠军/TOP10就靠它）
c.execute('CREATE INDEX idx_pool_date_ver_score ON selection_pool(date, strategy_version, total_score DESC)')
c.execute('CREATE INDEX idx_pool_ver_date ON selection_pool(strategy_version, date)')

# ===== 4. 视图：冠军视图（方便查询每天每个版本的冠军）=====
c.execute('''
    CREATE VIEW champion_daily AS
    SELECT p1.*
    FROM selection_pool p1
    INNER JOIN (
        SELECT date, strategy_version, MAX(total_score) as max_score
        FROM selection_pool
        GROUP BY date, strategy_version
    ) p2 ON p1.date = p2.date 
        AND p1.strategy_version = p2.strategy_version 
        AND p1.total_score = p2.max_score
''')

conn.commit()

# ===== 插入演示数据：V13和V13A同一天不同冠军 =====

# 模拟：2026-05-22 V13的候选池候选股（TOP5展示）
v13_pool_0522 = [
    # (代码, 名称, p, cl, wrv, vr, 价格, base_score, momentum, total)
    ('600260', '再升科技', 6.4, 78, 35, 1.8, 12.50, 88.5, 0, 88.5),
    ('600776', '东方通信', 4.5, 72, 25, 2.1, 18.20, 82.0, -5, 77.0),
    ('002111', '威海广泰', 5.2, 65, 42, 1.5, 15.30, 75.0, 0, 75.0),
    ('300502', '新易盛', 3.8, 80, 18, 1.2, 22.10, 70.0, -10, 60.0),
    ('002463', '沪电股份', 4.1, 55, 55, 1.0, 18.90, 58.0, 0, 58.0),
]

# V13A同一天候选池（参数不同，评分不同，冠军不同）
v13a_pool_0522 = [
    ('600776', '东方通信', 4.5, 72, 25, 2.1, 18.20, 92.0, -5, 87.0),  # V13A给更高分
    ('600260', '再升科技', 6.4, 78, 35, 1.8, 12.50, 82.0, 0, 82.0),
    ('002111', '威海广泰', 5.2, 65, 42, 1.5, 15.30, 78.0, 0, 78.0),
    ('300502', '新易盛', 3.8, 80, 18, 1.2, 22.10, 72.0, -10, 62.0),
    ('002463', '沪电股份', 4.1, 55, 55, 1.0, 18.90, 60.0, 0, 60.0),
]

for pdata in [('V13', v13_pool_0522), ('V13A', v13a_pool_0522)]:
    ver, pool = pdata
    for code, name, p, cl, wrv, vr, price, base, penalty, total in pool:
        c.execute('''
            INSERT INTO selection_pool
            (date, run_time, data_source, strategy_version, market_type, market_key,
             pool_size, used_level, total_candidates,
             code, name, p, cl, wrv, vr, price, base_score, momentum_penalty, total_score)
            VALUES (?, '14:50:00', 'sina_1450', ?, '真实涨日', 'real_up',
                    10, 'L0', 3043,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('2026-05-22', ver, code, name, p, cl, wrv, vr, price, base, penalty, total))

# 也插入之前30天V13冠军数据（简化，每个日期只插冠军作为演示）
champions = [
    '2026-04-08', '兴瑞科技', 5.7, 72, 45, 1.5, 22.80, 75.0, 0, 75.0,
    '2026-04-09', '奥海科技', 4.2, 68, 55, 1.2, 18.50, 68.0, 0, 68.0,
    '2026-04-10', '海思科', 5.1, 75, 30, 1.8, 15.20, 82.0, 0, 82.0,
    '2026-04-13', '航天电器', 1.5, 60, 50, 0.8, 25.10, 52.0, 0, 52.0,
    '2026-04-14', '通宇通讯', 6.2, 82, 28, 2.2, 11.30, 90.0, 0, 90.0,
    '2026-04-15', '华懋科技', 3.0, 55, 60, 1.0, 16.80, 55.0, 0, 55.0,
    '2026-04-16', '通宇通讯', 4.8, 70, 35, 1.5, 11.80, 78.0, 0, 78.0,
    '2026-04-17', '华正新材', 4.7, 65, 42, 1.3, 14.50, 72.0, 0, 72.0,
    '2026-04-20', '泰晶科技', 4.5, 78, 22, 1.9, 13.20, 85.0, 0, 85.0,
    '2026-04-21', '水晶光电', 3.9, 62, 48, 1.1, 17.60, 65.0, 0, 65.0,
    '2026-04-22', '博云新材', 6.8, 85, 15, 2.5, 9.80, 95.0, 0, 95.0,
    '2026-04-23', '博杰股份', 6.7, 80, 20, 2.3, 10.50, 92.0, 0, 92.0,
    '2026-04-24', '株冶集团', 3.6, 58, 52, 0.9, 14.20, 58.0, 0, 58.0,
    '2026-04-27', '禾望电气', 4.1, 72, 38, 1.6, 12.80, 76.0, 0, 76.0,
    '2026-04-28', '中旗新材', 3.9, 66, 48, 1.2, 15.50, 68.0, 0, 68.0,
    '2026-04-29', '安孚科技', 4.0, 70, 42, 1.4, 13.00, 70.0, 0, 70.0,
    '2026-04-30', '四方股份', 3.9, 63, 50, 1.1, 16.40, 64.0, 0, 64.0,
    '2026-05-06', '迎丰股份', 6.2, 82, 25, 2.0, 11.00, 90.0, 0, 90.0,
    '2026-05-07', '华升股份', 5.0, 75, 32, 1.7, 12.20, 80.0, 0, 80.0,
    '2026-05-08', '东方通信', 4.5, 68, 28, 1.8, 17.50, 76.0, 0, 76.0,
    '2026-05-11', '平安电工', 5.3, 78, 22, 2.1, 11.80, 88.0, 0, 88.0,
    '2026-05-12', '宇环数控', 6.7, 85, 18, 2.4, 10.20, 94.0, 0, 94.0,
    '2026-05-13', '东方钽业', 4.1, 65, 40, 1.5, 14.00, 72.0, 0, 72.0,
    '2026-05-14', '巨轮智能', 4.8, 72, 35, 1.6, 13.50, 78.0, 0, 78.0,
    '2026-05-15', '新泉股份', 5.0, 70, 38, 1.4, 15.20, 80.0, 0, 80.0,
    '2026-05-18', '兆易创新', 6.6, 82, 20, 2.2, 12.00, 92.0, 0, 92.0,
    '2026-05-19', '法狮龙', 6.6, 80, 25, 2.0, 11.50, 90.0, -8, 82.0,
    '2026-05-20', '锦和商管', 3.0, 55, 55, 0.8, 15.80, 55.0, 0, 55.0,
    '2026-05-21', '新坐标', 6.3, 78, 30, 1.9, 11.50, 88.0, 0, 88.0,
]
for idx, i in enumerate(range(0, len(champions), 10)):
    dt, name, p, cl, wrv, vr, price, base, penalty, total = champions[i:i+10]
    c.execute('''
        INSERT INTO selection_pool
        (date, run_time, data_source, strategy_version, market_type, market_key,
         pool_size, used_level, total_candidates,
         code, name, p, cl, wrv, vr, price, base_score, momentum_penalty, total_score)
        VALUES (?, '14:50:00', 'sina_1450', 'V13', '真实涨日', 'real_up',
                30, 'L1', 3043,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (dt, f'600{idx+100:03d}', name, p, cl, wrv, vr, price, base, penalty, total))

conn.commit()

# ===== 展示 =====
print(f'\n{"="*70}')
print(f'  📂 v13_quant.db V2 — 完整设计')
print(f'{"="*70}')

print(f'\n📋 所有表：')
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    cnt = c.execute(f'SELECT COUNT(*) FROM {r[0]}').fetchone()[0]
    print(f'  {r[0]:>25}  → {cnt} 行')

print(f'\n📋 视图：')
for r in c.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"):
    print(f'  {r[0]}')

print(f'\n{"="*70}')
print(f'  🏆 冠军是怎么算出来的？')
print(f'{"="*70}')
print(f'  SQL查询：')
print(f'    SELECT code, name, total_score FROM selection_pool')
print(f'    WHERE date="2026-05-22" AND strategy_version="V13"')
print(f'    ORDER BY total_score DESC LIMIT 1')
print()

# 演示冠军查询
r = c.execute('''
    SELECT date, strategy_version, name, code, base_score, momentum_penalty, total_score
    FROM selection_pool
    WHERE date='2026-05-22' AND strategy_version='V13'
    ORDER BY total_score DESC LIMIT 1
''').fetchone()
print(f'  V13的2026-05-22冠军：{r[2]}({r[3]})  base={r[4]}  penalty={r[5]}  total={r[6]} ✅')

r = c.execute('''
    SELECT date, strategy_version, name, code, base_score, momentum_penalty, total_score
    FROM selection_pool
    WHERE date='2026-05-22' AND strategy_version='V13A'
    ORDER BY total_score DESC LIMIT 1
''').fetchone()
print(f'  V13A的2026-05-22冠军：{r[2]}({r[3]})  base={r[4]}  penalty={r[5]}  total={r[6]} ✅')

print(f'\n  → 同一日期，不同版本，冠军不同，各存各的，不混淆')

print(f'\n{"="*70}')
print(f'  📊 V13每天冠军一览（从champion_daily视图取）')
print(f'{"="*70}')
print(f'{"日期":>12} {"冠军":>10} {"涨幅":>6} {"基础分":>6} {"动量扣":>6} {"总分":>6}')
print(f'{"-"*55}')
for r in c.execute('''
    SELECT date, name, p, base_score, momentum_penalty, total_score
    FROM champion_daily
    WHERE strategy_version='V13'
    ORDER BY date DESC LIMIT 10
'''):
    print(f'{r[0]:>12} {r[1]:>10} {r[2]:>+5.1f}% {r[3]:>6.0f} {r[4]:>6.0f} {r[5]:>6.0f}')

print(f'\n{"="*70}')
print(f'  🎯 关键设计原则')
print(f'{"="*70}')
print(f'  1. 所有候选股都存 → 冠军是SQL查出来的，不是硬编码的')
print(f'  2. 版本隔离 → strategy_version字段区分')
print(f'  3. 数据源隔离 → data_source字段区分(sina/big_cache)')
print(f'  4. 时间溯源 → date + run_time')
print(f'  5. 评分透明 → base_score + momentum_penalty 分开存')
print(f'  6. 高速查询 → date+version+score索引')

conn.close()

print(f'\n📁 数据库位置: {db_path}')
print(f'📏 文件大小: {os.path.getsize(db_path)/1024:.1f} KB')
