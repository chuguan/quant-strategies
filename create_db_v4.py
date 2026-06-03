#!/usr/bin/env python
"""v13_quant.db V4 — 完全隔离：时间+数据源+版本+参数+代码+缓存版本"""
import sqlite3, os, hashlib, json

db_path = os.path.expanduser('~/AppData/Local/hermes/scripts/v13_quant.db')
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
c = conn.cursor()

# =============================================
#  0. 策略快照（每一次跑的参数和代码都锁死）
# =============================================
c.execute('''
    CREATE TABLE strategy_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_version TEXT NOT NULL,       -- V13 / V14 / V15
        run_date TEXT NOT NULL,               -- 哪天跑的
        run_time TEXT NOT NULL,               -- 几点跑的
        
        -- 📋 参数快照
        params_json TEXT,                      -- PARAMS完整字典（JSON）
        levels_json TEXT,                     -- LEVELS完整列表（JSON）
        
        -- 🔐 评分函数代码指纹
        scoring_code_hash TEXT,               -- score()函数源码的SHA256
        scoring_code TEXT,                    -- score()函数源码（全文存档）
        
        -- 🏷 行情分类规则
        classification_method TEXT,           -- v1_mkt_class / v2_mkt_class
        classification_params TEXT,           -- 分类用的参数（阈值等）
        
        -- 💾 数据缓存版本
        data_cache_version TEXT,              -- big_cache的生成日期
        
        UNIQUE(strategy_version, run_date, run_time)
    )
''')
c.execute('CREATE INDEX idx_snap_ver_date ON strategy_snapshot(strategy_version, run_date)')

# =============================================
#  1. 公共行情数据
# =============================================
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
        original_source TEXT,
        cache_version TEXT,        -- 这个数据属于哪个big_cache版本
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
        computed_from TEXT,           -- 从data_cache还是data_sina算的
        cache_version TEXT,           -- 特征属于哪个版本
        UNIQUE(date, code)
    )
''')

# =============================================
#  3. 选股池（引用策略快照ID）
# =============================================
c.execute('''
    CREATE TABLE selection_pool (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        run_time TEXT,
        
        -- 🔗 关联到策略快照（锁死参数+代码）
        snapshot_id INTEGER REFERENCES strategy_snapshot(id),
        
        -- 🌐 数据源追踪
        data_provider TEXT,           -- sina / tencent / tushare / big_cache
        data_api TEXT,                -- hq.sinajs.cn / web.ifzq.gtimg.cn / pro
        data_type TEXT,               -- realtime / kline / daily_close
        
        -- 🧩 策略信息
        strategy_version TEXT NOT NULL,
        market_type TEXT,
        market_key TEXT,
        pool_size INTEGER,
        used_level TEXT,
        total_candidates INTEGER,
        
        -- 📈 股票信息
        code TEXT NOT NULL,
        name TEXT,
        p REAL, cl REAL, wrv REAL, vr REAL, price REAL,
        
        -- 📊 评分
        base_score REAL,
        momentum_penalty REAL,
        total_score REAL,
        
        UNIQUE(date, strategy_version, code, run_time, data_provider)
    )
''')
c.execute('CREATE INDEX idx_pool_snap ON selection_pool(snapshot_id)')
c.execute('CREATE INDEX idx_pool_date_ver ON selection_pool(date, strategy_version, total_score DESC)')

# =============================================
#  4. 冠军视图
# =============================================
c.execute('''
    CREATE VIEW champion_daily AS
    SELECT p1.*
    FROM selection_pool p1
    INNER JOIN (
        SELECT date, strategy_version, data_provider, run_time, 
               MAX(total_score) as max_score
        FROM selection_pool
        GROUP BY date, strategy_version, data_provider, run_time
    ) p2 ON p1.date = p2.date 
        AND p1.strategy_version = p2.strategy_version 
        AND p1.data_provider = p2.data_provider
        AND p1.run_time = p2.run_time
        AND p1.total_score = p2.max_score
''')

conn.commit()

# =============================================
#  插入演示数据
# =============================================

# 模拟V13跌日评分函数的源码
v13_down_scoring_code = '''
def score(stock):
    s=stock; p=PARAMS
    score=0
    score+=s.get('p',0)*p.get('p_w',1)
    cl=s.get('cl',50)
    score+=cl*p.get('cl_w',0.05)
    ...
    if mg and dif>0.5: 
        score+=10*p.get('macd_w',0.3)
    return round(score,1)
'''

# 模拟V13A跌日评分函数的源码（不同）
v13a_down_scoring_code = '''
def score(stock):
    s=stock; p=PARAMS
    sc=0
    sc+=s.get('p',0)*p.get('p_w',1)  # p_w=2.5(更激进)
    cl=s.get('cl',50)
    sc+=cl*p.get('cl_w',0.05)
    ...
    return round(sc,1)
'''

# 创建策略快照 - V13
v13_params = {
    "跌日": {"p_w": 1.8, "cl_w": 0.2, "macd_w": 1.5, "wr_lo_b": -15, "dif_bonus": 3, "use_wr": 1},
    "横盘": {"p_w": 0.5, "cl_w": 0.1, "macd_w": 1, "use_wr": 0, "bonus_dif_03": 10},
    "真实涨日": {"p_w": 0.5, "cl_w": 0.05},
    "虚涨日": {"p_w": 0.5, "cl_w": 0.05},
}
v13_levels = {
    "跌日": [
        {"name":"L0","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":1.5,"hs_min":5,"hs_max":20,"cl_min":40},
        {"name":"L1","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":1.5,"hs_min":5,"hs_max":20,"cl_min":40},
        {"name":"L2","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":2.0,"hs_min":3,"hs_max":25,"cl_min":30},
        {"name":"L3","p_min":0,"p_max":7,"vr_min":0.5,"vr_max":2.5,"hs_min":2,"hs_max":30,"cl_min":20},
        {"name":"L4","p_min":-10,"p_max":7,"vr_min":0.1,"vr_max":10,"hs_min":0.1,"hs_max":100,"cl_min":0},
    ],
    "横盘": [{"name":"L0","p_min":0,"p_max":7,"vr_min":0.6,"vr_max":2.5,"cl_min":40}],
    "真实涨日": [{"name":"L1","p_min":3,"p_max":7,"vr_min":0.6,"vr_max":2.0,"cl_min":30}],
    "虚涨日": [{"name":"L1","p_min":4,"p_max":7,"vr_min":0.6,"vr_max":2.0,"cl_min":30}],
}
v13_code_hash = hashlib.sha256(v13_down_scoring_code.encode()).hexdigest()[:16]
c.execute('''
    INSERT INTO strategy_snapshot
    (strategy_version, run_date, run_time, 
     params_json, levels_json, 
     scoring_code_hash, scoring_code,
     classification_method,
     data_cache_version)
    VALUES (?, ?, ?,
            ?, ?,
            ?, ?,
            ?,
            ?)
''', ('V13', '2026-05-22', '14:50:00',
      json.dumps(v13_params, ensure_ascii=False),
      json.dumps(v13_levels, ensure_ascii=False),
      v13_code_hash, v13_down_scoring_code.strip(),
      'v1_mkt_class(avg_p>0.5→real_up,<-0.5→down)',
      'big_cache_2026-05-29'))
v13_snap_id = c.lastrowid

# 创建策略快照 - V13A
v13a_params = {
    "跌日": {"p_w": 2.5, "cl_w": 0.1, "macd_w": 2.0, "wr_lo_b": -20, "dif_bonus": 5, "use_wr": 1},
    "横盘": {"p_w": 0.5, "cl_w": 0.08, "macd_w": 1.5, "use_wr": 1, "wr_lo_b": -15, "dif_bonus": 25},
    "真实涨日": {"p_w": 0.6, "cl_w": 0.05},
    "虚涨日": {"p_w": 0.5, "cl_w": 0.03, "macd_w": 1.5, "use_wr": 1, "wr_lo_b": -10},
}
v13a_levels_v2 = {
    "跌日": [
        {"name":"L0","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":1.5,"hs_min":5,"hs_max":20,"cl_min":40},
        {"name":"L1","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":1.5,"hs_min":5,"hs_max":20,"cl_min":40},
        {"name":"L2","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":2.0,"hs_min":3,"hs_max":25,"cl_min":30},
        {"name":"L3","p_min":0,"p_max":7,"vr_min":0.5,"vr_max":2.5,"hs_min":2,"hs_max":30,"cl_min":20},
        {"name":"L4","p_min":-10,"p_max":7,"vr_min":0.1,"vr_max":10,"hs_min":0.1,"hs_max":100,"cl_min":0},
    ],
    "横盘": [
        {"name":"L0","p_min":2,"p_max":8,"vr_min":0.6,"vr_max":2.0,"cl_min":30, "a5_req":1},
    ],
    "真实涨日": [],
    "虚涨日": [
        {"name":"L0","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":2.0,"cl_min":30},
    ],
}
v13a_code_hash = hashlib.sha256(v13a_down_scoring_code.encode()).hexdigest()[:16]
c.execute('''
    INSERT INTO strategy_snapshot
    (strategy_version, run_date, run_time,
     params_json, levels_json,
     scoring_code_hash, scoring_code,
     classification_method,
     data_cache_version)
    VALUES (?, ?, ?,
            ?, ?,
            ?, ?,
            ?,
            ?)
''', ('V13A', '2026-05-22', '14:50:00',
      json.dumps(v13a_params, ensure_ascii=False),
      json.dumps(v13a_levels_v2, ensure_ascii=False),
      v13a_code_hash, v13a_down_scoring_code.strip(),
      'v1_mkt_class(avg_p>0.5→real_up)',
      'big_cache_2026-05-29'))
v13a_snap_id = c.lastrowid

# 插入选股结果（引用snapshot_id）
pools = {
    'V13': [
        ('600260', '再升科技', 6.4, 78, 35, 1.8, 12.50, 88.5, 0, 88.5),
        ('600776', '东方通信', 4.5, 72, 25, 2.1, 18.20, 82.0, -5, 77.0),
        ('002111', '威海广泰', 5.2, 65, 42, 1.5, 15.30, 75.0, 0, 75.0),
        ('300502', '新易盛', 3.8, 80, 18, 1.2, 22.10, 70.0, -10, 60.0),
        ('002463', '沪电股份', 4.1, 55, 55, 1.0, 18.90, 58.0, 0, 58.0),
    ],
    'V13A': [
        ('600776', '东方通信', 4.5, 72, 25, 2.1, 18.20, 92.0, -5, 87.0),
        ('600260', '再升科技', 6.4, 78, 35, 1.8, 12.50, 82.0, 0, 82.0),
        ('002111', '威海广泰', 5.2, 65, 42, 1.5, 15.30, 78.0, 0, 78.0),
        ('300502', '新易盛', 3.8, 80, 18, 1.2, 22.10, 72.0, -10, 62.0),
        ('002463', '沪电股份', 4.1, 55, 55, 1.0, 18.90, 60.0, 0, 60.0),
    ],
}

for ver, candidates in pools.items():
    snap_id = v13_snap_id if ver == 'V13' else v13a_snap_id
    for code, name, p, cl, wrv, vr, price, base, pen, total in candidates:
        c.execute('''
            INSERT INTO selection_pool
            (date, run_time, snapshot_id,
             data_provider, data_api, data_type,
             strategy_version, market_type, market_key,
             pool_size, used_level, total_candidates,
             code, name, p, cl, wrv, vr, price,
             base_score, momentum_penalty, total_score)
            VALUES ('2026-05-22', '14:50:00', ?,
                    'sina', 'hq.sinajs.cn', 'realtime',
                    ?, '真实涨日', 'real_up',
                    15, 'L0', 3043,
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?)
        ''', (snap_id, ver, code, name, p, cl, wrv, vr, price, base, pen, total))

conn.commit()

# =============================================
#  展示
# =============================================
print(f'\n{"="*75}')
print(f'  📂 v13_quant.db V4 — 完全隔离版')
print(f'{"="*75}')

print(f'\n📋 表结构：')
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    cnt = c.execute(f'SELECT COUNT(*) FROM {r[0]}').fetchone()[0]
    desc = {
        'data_cache':'big_cache历史收p',
        'data_sina':'新浪实时行情',
        'data_tencent':'腾讯K线',
        'features_cache':'预计算特征',
        'selection_pool':'选股池（所有候选股）',
        'strategy_snapshot':'策略快照（参数+代码锁死）'
    }
    print(f'  {r[0]:>25}  {cnt:>3}行  {desc.get(r[0],"")}')

print(f'\n📋 视图：champion_daily')

print(f'\n{"="*75}')
print(f'  🔍 策略快照 — 每一条都锁死了当时的参数和评分代码')
print(f'{"="*75}')
for r in c.execute('''
    SELECT strategy_version, run_date, run_time, 
           scoring_code_hash, data_cache_version
    FROM strategy_snapshot
    ORDER BY strategy_version
'''):
    print(f'  {r[0]:>8} | {r[1]} {r[2]} | 代码指纹:{r[3]} | 缓存版本:{r[4]}')

print(f'\n{"="*75}')
print(f'  🔍 选股池 — 每一条都关联到策略快照')
print(f'{"="*75}')
print(f'{"版本":>6} {"代码":>7} {"名称":>10} {"评分":>5} {"动量扣":>5} {"总分":>6} {"关联快照ID":>12}')
print(f'{"-"*65}')
for r in c.execute('''
    SELECT strategy_version, code, name, base_score, momentum_penalty, total_score, snapshot_id
    FROM selection_pool WHERE date='2026-05-22'
    ORDER BY strategy_version, total_score DESC
'''):
    print(f'{r[0]:>6} {r[1]:>7} {r[2]:>10} {r[3]:>5.0f} {r[4]:>5.0f} {r[5]:>6.0f} snap_id={r[6]:>3}')

print(f'\n{"="*75}')
print(f'  ✅ 完全隔离维度总结')
print(f'{"="*75}')
dims = [
    ('时间隔离',     'run_time',           '14:50 ≠ 14:30，不混淆'),
    ('数据源隔离',   'data_provider/data_api', 'sina ≠ tencent ≠ tushare'),
    ('版本隔离',     'strategy_version',   'V13 ≠ V13A ≠ V14 ≠ V15'),
    ('参数隔离',     'params_json',        'strategy_snapshot中存了当时所有的PARAMS'),
    ('分级隔离',     'levels_json',        'LEVELS快照，L0 p_min=2还是=0有记录'),
    ('代码隔离',     'scoring_code_hash',  'score()函数SHA256指纹，改过代码能发现'),
    ('分类隔离',     'classification_method', '市场分类规则也锁死'),
    ('缓存隔离',     'data_cache_version', '用的哪个big_cache版本'),
]
print(f'{"隔离维度":>16} {"字段":>22} {"说明":>30}')
print(f'{"-"*75}')
for dim, field, desc in dims:
    print(f'{dim:>16} {field:>22} {desc:>30}')

print(f'\n📁 {db_path}')
print(f'📏 {os.path.getsize(db_path)/1024:.1f} KB')

conn.close()
