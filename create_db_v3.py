#!/usr/bin/env python
"""v13_quant.db V3 — 数据源精确到API端点"""
import sqlite3, os

db_path = os.path.expanduser('~/AppData/Local/hermes/scripts/v13_quant.db')
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
c = conn.cursor()

# ===== 样式 =====
def table(name):
    c.execute(f"SELECT COUNT(*) FROM {name}")
    return c.fetchone()[0]

# =============================================
#  1. 公共行情数据（按来源分表 + 精确到API端点）
# =============================================

# ① 新浪实时行情（2:50拉取）
c.execute('''
    CREATE TABLE data_sina (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        code TEXT NOT NULL,
        name TEXT,
        price REAL, pre_close REAL, pct REAL,
        high REAL, low REAL, volume REAL, amount REAL,
        api_endpoint TEXT DEFAULT 'hq.sinajs.cn',
        fetch_batch INTEGER,
        UNIQUE(date, code, time)
    )
''')
c.execute('CREATE INDEX idx_sina_date ON data_sina(date)')

# ② 腾讯K线
c.execute('''
    CREATE TABLE data_tencent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        code TEXT NOT NULL,
        name TEXT,
        kline_date TEXT,
        open REAL, close REAL, high REAL, low REAL,
        volume REAL, pct REAL,
        api_endpoint TEXT DEFAULT 'web.ifzq.gtimg.cn',
        UNIQUE(date, code, kline_date)
    )
''')
c.execute('CREATE INDEX idx_tencent_date ON data_tencent(date)')

# ③ big_cache历史收盘数据（原始数据源待填）
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
        original_source TEXT,   -- 这个数据最初是从哪来的（腾讯/东方财富/新浪）
        UNIQUE(date, code)
    )
''')
c.execute('CREATE INDEX idx_cache_date ON data_cache(date)')

# =============================================
#  2. 特征数据
# =============================================
c.execute('''
    CREATE TABLE features_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        code TEXT NOT NULL,
        d1 REAL, d2 REAL, d3 REAL, d4 REAL, d5 REAL,
        slope5 REAL, t4_shadow REAL, cons_up REAL, peak_decay REAL,
        computed_from TEXT,  -- 从哪个数据源计算来的（data_cache/data_sina）
        UNIQUE(date, code)
    )
''')

# =============================================
#  3. 选股池（所有候选股，精确数据源）
# =============================================
c.execute('''
    CREATE TABLE selection_pool (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        run_time TEXT,
        
        -- 🌐 数据源追踪（精确到API）
        data_provider TEXT,           -- sina / tencent / tushare / big_cache
        data_api TEXT,                -- hq.sinajs.cn / web.ifzq.gtimg.cn / pro
        data_type TEXT,               -- realtime / kline / daily_close
        data_fetch_time TEXT,         -- 实际拉取的时间
        
        -- 🧩 策略信息
        strategy_version TEXT NOT NULL,  -- V13 / V14 / V15
        scoring_method TEXT,             -- v10_score / data_driven / heuristic
        market_type TEXT,
        market_key TEXT,
        pool_size INTEGER,
        used_level TEXT,
        total_candidates INTEGER,
        
        -- 📈 股票信息
        code TEXT NOT NULL,
        name TEXT,
        p REAL, cl REAL, wrv REAL, vr REAL, price REAL,
        
        -- 📊 评分过程
        base_score REAL,            -- 策略评分函数算出
        momentum_penalty REAL,      -- 7天动量衰减扣分
        total_score REAL,           -- base + momentum
        
        UNIQUE(date, strategy_version, code, run_time, data_provider)
    )
''')
c.execute('CREATE INDEX idx_pool_date_ver ON selection_pool(date, strategy_version, total_score DESC)')

# =============================================
#  4. 冠军视图
# =============================================
c.execute('''
    CREATE VIEW champion_daily AS
    SELECT p1.*
    FROM selection_pool p1
    INNER JOIN (
        SELECT date, strategy_version, data_provider, MAX(total_score) as max_score
        FROM selection_pool
        GROUP BY date, strategy_version, data_provider
    ) p2 ON p1.date = p2.date 
        AND p1.strategy_version = p2.strategy_version 
        AND p1.data_provider = p2.data_provider
        AND p1.total_score = p2.max_score
''')

conn.commit()

# =============================================
#  插入演示数据：同一个股，不同数据源的差异
# =============================================

# 场景：2026-05-22，V13用新浪实时数据 vs 用腾讯K线数据
sina_candidates = [
    ('600260', '再升科技', 6.4, 78, 35, 1.8, 12.50, 88.5, 0, 88.5),
    ('600776', '东方通信', 4.5, 72, 25, 2.1, 18.20, 82.0, -5, 77.0),
    ('002111', '威海广泰', 5.2, 65, 42, 1.5, 15.30, 75.0, 0, 75.0),
]
tencent_candidates = [
    ('600260', '再升科技', 6.1, 75, 38, 1.7, 12.40, 85.0, 0, 85.0),  # 腾讯数据不同
    ('600776', '东方通信', 4.8, 70, 28, 2.0, 18.30, 80.0, -5, 75.0),  # 腾讯数据不同
    ('002111', '威海广泰', 5.5, 62, 45, 1.3, 15.20, 72.0, 0, 72.0),
]

for code, name, p, cl, wrv, vr, price, base, pen, total in sina_candidates:
    c.execute('''
        INSERT INTO selection_pool
        (date, run_time, data_provider, data_api, data_type, data_fetch_time,
         strategy_version, scoring_method, market_type, market_key,
         pool_size, used_level, total_candidates,
         code, name, p, cl, wrv, vr, price, base_score, momentum_penalty, total_score)
        VALUES ('2026-05-22', '14:50:00',
                'sina', 'hq.sinajs.cn', 'realtime', '2026-05-22 14:50:02',
                'V13', 'v10_score', '真实涨日', 'real_up',
                15, 'L0', 3043,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (code, name, p, cl, wrv, vr, price, base, pen, total))

for code, name, p, cl, wrv, vr, price, base, pen, total in tencent_candidates:
    c.execute('''
        INSERT INTO selection_pool
        (date, run_time, data_provider, data_api, data_type, data_fetch_time,
         strategy_version, scoring_method, market_type, market_key,
         pool_size, used_level, total_candidates,
         code, name, p, cl, wrv, vr, price, base_score, momentum_penalty, total_score)
        VALUES ('2026-05-22', '14:50:00',
                'tencent', 'web.ifzq.gtimg.cn', 'kline', '2026-05-22 14:50:05',
                'V13', 'v10_score', '真实涨日', 'real_up',
                12, 'L0', 3043,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (code, name, p, cl, wrv, vr, price, base, pen, total))

# 也插历史30天冠军数据
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
        (date, run_time, data_provider, data_api, data_type, data_fetch_time,
         strategy_version, scoring_method, market_type, market_key,
         pool_size, used_level, total_candidates,
         code, name, p, cl, wrv, vr, price, base_score, momentum_penalty, total_score)
        VALUES (?, '14:50:00',
                'sina', 'hq.sinajs.cn', 'realtime', '14:50:00',
                'V13', 'v10_score', '真实涨日', 'real_up',
                30, 'L1', 3043,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (dt, f'600{idx+100:03d}', name, p, cl, wrv, vr, price, base, penalty, total))

conn.commit()

# =============================================
#  展示
# =============================================
print(f'\n{"="*75}')
print(f'  📂 v13_quant.db V3 — 数据源精确到API端点')
print(f'{"="*75}')

print(f'\n📋 所有表：')
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    cnt = c.execute(f'SELECT COUNT(*) FROM {r[0]}').fetchone()[0]
    print(f'  {r[0]:>25}  → {cnt} 行')

print(f'\n📋 视图：')
for r in c.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"):
    print(f'  {r[0]}')

print(f'\n{"="*75}')
print(f'  🌐 同一日期+同一版本，不同数据源，冠军不同')
print(f'{"="*75}')

# 新浪数据冠军
r = c.execute('''
    SELECT name, data_provider, data_api, total_score
    FROM selection_pool
    WHERE date='2026-05-22' AND strategy_version='V13' AND data_provider='sina'
    ORDER BY total_score DESC LIMIT 1
''').fetchone()
print(f'  📡 sina | {r[2]:>20} | 冠军:{r[0]:>8} | 总分:{r[3]} ✅')

# 腾讯数据冠军
r = c.execute('''
    SELECT name, data_provider, data_api, total_score
    FROM selection_pool
    WHERE date='2026-05-22' AND strategy_version='V13' AND data_provider='tencent'
    ORDER BY total_score DESC LIMIT 1
''').fetchone()
print(f'  📡 tencent | {r[2]:>20} | 冠军:{r[0]:>8} | 总分:{r[3]} ✅')

print(f'\n  → 不同API拉的数据不一样，冠军也可能不一样，各存各的，清清楚楚')

print(f'\n{"="*75}')
print(f'  🔍 选股池一条完整记录长什么样')
print(f'{"="*75}')
r = c.execute('''
    SELECT * FROM selection_pool 
    WHERE data_provider='sina' 
    LIMIT 1
''').fetchone()
cols = [d[0] for d in c.description]
for name, val in zip(cols, r):
    if val is not None:
        print(f'  {name:>25} = {val}')

print(f'\n{"="*75}')
print(f'  🏆 历史冠军')
print(f'{"="*75}')
print(f'{"日期":>12} {"冠军":>10} {"涨幅":>6} {"总分":>6} {"数据源":>10}')
print(f'{"-"*60}')
for r in c.execute('''
    SELECT date, name, p, total_score, data_provider
    FROM selection_pool
    WHERE strategy_version='V13' AND data_provider='sina'
    ORDER BY date DESC LIMIT 10
'''):
    print(f'{r[0]:>12} {r[1]:>10} {r[2]:>+5.1f}% {r[3]:>6.0f} {r[4]:>10}')

print(f'\n📁 数据库: {db_path}')
print(f'📏 大小: {os.path.getsize(db_path)/1024:.1f} KB')

conn.close()
