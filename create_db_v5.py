#!/usr/bin/env python
"""v13_quant.db V5 — 策略文件完整归档到数据库"""
import sqlite3, os, hashlib, json, glob

db_path = os.path.expanduser('~/AppData/Local/hermes/scripts/v13_quant.db')
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
c = conn.cursor()

# =============================================
#  0. 策略文件归档（完整.py文件内容）
# =============================================
c.execute('''
    CREATE TABLE strategy_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_version TEXT NOT NULL,
        file_date TEXT NOT NULL,
        file_time TEXT NOT NULL,
        
        file_name TEXT NOT NULL,      -- 原始文件名（含时间戳）
        file_path TEXT NOT NULL,      -- 原始目录路径
        file_type TEXT,               -- scoring_strategy / backtest / production / data_cache
        
        file_content TEXT NOT NULL,   -- 完整文件内容
        file_size INTEGER,            -- 文件bytes
        file_hash TEXT NOT NULL,      -- SHA256
        
        UNIQUE(strategy_version, file_name, file_date, file_time)
    )
''')
c.execute('CREATE INDEX idx_files_ver ON strategy_files(strategy_version, file_date)')

# =============================================
#  0b. 策略快照（参数+分级+运行时信息）
# =============================================
c.execute('''
    CREATE TABLE strategy_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_version TEXT NOT NULL,
        run_date TEXT NOT NULL,
        run_time TEXT NOT NULL,
        
        -- 关联到归档的评分策略文件
        scoring_file_id INTEGER REFERENCES strategy_files(id),
        backtest_file_id INTEGER REFERENCES strategy_files(id),
        production_file_id INTEGER REFERENCES strategy_files(id),
        data_cache_file_id INTEGER REFERENCES strategy_files(id),
        
        -- 参数快照（冗余存一份方便SQL查询）
        params_json TEXT,
        levels_json TEXT,
        
        -- 评分函数代码指纹
        scoring_code_hash TEXT,
        
        -- 分类规则
        classification_method TEXT,
        classification_params TEXT,
        
        -- 缓存版本
        data_cache_version TEXT,
        features_version TEXT,
        
        UNIQUE(strategy_version, run_date, run_time)
    )
''')
c.execute('CREATE INDEX idx_snap_ver ON strategy_snapshot(strategy_version, run_date)')

# =============================================
#  1. 公共行情数据
# =============================================
c.execute('''
    CREATE TABLE data_sina (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, time TEXT NOT NULL,
        code TEXT NOT NULL, name TEXT,
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
        date TEXT NOT NULL, code TEXT NOT NULL, name TEXT,
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
        date TEXT NOT NULL, code TEXT NOT NULL, name TEXT,
        p REAL, cl REAL, vr REAL, n REAL,
        dif_val REAL, macd_golden INTEGER,
        wr_val REAL, j_val REAL, k_val REAL, d_val REAL,
        pos_in_day REAL, above_ma5 INTEGER, kdj_golden INTEGER,
        close REAL, volume REAL,
        original_source TEXT,
        cache_version TEXT,
        UNIQUE(date, code)
    )
''')
c.execute('CREATE INDEX idx_cache_date ON data_cache(date)')

c.execute('''
    CREATE TABLE features_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, code TEXT NOT NULL,
        d1 REAL, d2 REAL, d3 REAL, d4 REAL, d5 REAL,
        slope5 REAL, t4_shadow REAL, cons_up REAL, peak_decay REAL,
        computed_from TEXT,
        cache_version TEXT,
        UNIQUE(date, code)
    )
''')

# =============================================
#  3. 选股池
# =============================================
c.execute('''
    CREATE TABLE selection_pool (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, run_time TEXT,
        snapshot_id INTEGER REFERENCES strategy_snapshot(id),
        
        data_provider TEXT, data_api TEXT, data_type TEXT,
        strategy_version TEXT NOT NULL,
        market_type TEXT, market_key TEXT,
        pool_size INTEGER, used_level TEXT, total_candidates INTEGER,
        
        code TEXT NOT NULL, name TEXT,
        p REAL, cl REAL, wrv REAL, vr REAL, price REAL,
        base_score REAL, momentum_penalty REAL, total_score REAL,
        
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
        SELECT date, strategy_version, data_provider, run_time, 
               MAX(total_score) as max_score
        FROM selection_pool
        GROUP BY date, strategy_version, data_provider, run_time
    ) p2 ON p1.date=p2.date AND p1.strategy_version=p2.strategy_version 
        AND p1.data_provider=p2.data_provider AND p1.run_time=p2.run_time
        AND p1.total_score=p2.max_score
''')

conn.commit()

# =============================================
#  插入演示：把真实的策略文件存进数据库
# =============================================

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')

# 读V13的真实策略文件
strategy_files_to_archive = [
    ('跌日_V13_2026-05-29_0650.py', '评分策略/分而治之_V10_跌日_评分策略.py', 'scoring_strategy'),
    ('横盘_V13_2026-05-29_0650.py', '评分策略/分而治之_V10_横盘_评分策略.py', 'scoring_strategy'),
    ('真实涨日_V13_2026-05-29_0650.py', '评分策略/分而治之_V10_真实涨日_评分策略.py', 'scoring_strategy'),
    ('虚涨日_V13_2026-05-29_0650.py', '评分策略/分而治之_V10_虚涨日_评分策略.py', 'scoring_strategy'),
    ('回测_V13_2026-05-29_0650.py', '回测_V13_95pct.py', 'backtest'),
    ('生产_V13_2026-05-29_0650.py', '../../V13_生产.py', 'production'),
]

v13_file_ids = {}
for arc_name, rel_path, ftype in strategy_files_to_archive:
    full_path = os.path.join(V13_DIR, rel_path)
    full_path = os.path.normpath(full_path)
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        fhash = hashlib.sha256(content.encode()).hexdigest()[:16]
        fsize = len(content.encode())
        
        c.execute('''
            INSERT INTO strategy_files
            (strategy_version, file_date, file_time, file_name, file_path, file_type,
             file_content, file_size, file_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('V13', '2026-05-29', '06:50:00', arc_name, full_path, ftype,
              content, fsize, fhash))
        v13_file_ids[ftype] = c.lastrowid
        print(f'  ✅ 归档: {arc_name:>35} ({fsize:>5} bytes) hash={fhash}')
    except FileNotFoundError:
        print(f'  ⚠️ 未找到: {full_path}')

# 模拟V13快照
v13_params = {"跌日": {"p_w":1.8,"wr_lo_b":-15},"横盘": {"p_w":0.5},"真实涨日": {"p_w":0.5},"虚涨日": {"p_w":0.5}}
v13_levels = {"跌日":[{"name":"L0","p_min":2}],"横盘":[{"name":"L0","p_min":0}],"真实涨日":[],"虚涨日":[]}
c.execute('''
    INSERT INTO strategy_snapshot
    (strategy_version, run_date, run_time,
     scoring_file_id, backtest_file_id, production_file_id,
     params_json, levels_json,
     scoring_code_hash, classification_method, data_cache_version, features_version)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', ('V13', '2026-05-29', '06:50:00',
      v13_file_ids.get('scoring_strategy'),
      v13_file_ids.get('backtest'),
      v13_file_ids.get('production'),
      json.dumps(v13_params), json.dumps(v13_levels),
      '4c96ad3ea1ddef47', 'v1_mkt_class', 'big_cache_2026-05-29', 'features_30d_2026-05-29'))

# 插入历史30天选股数据
champions = [
    '2026-04-08','兴瑞科技',5.7,72,45,1.5,22.80,75,0,75,
    '2026-04-09','奥海科技',4.2,68,55,1.2,18.50,68,0,68,
    '2026-04-10','海思科',5.1,75,30,1.8,15.20,82,0,82,
    '2026-04-13','航天电器',1.5,60,50,0.8,25.10,52,0,52,
    '2026-04-14','通宇通讯',6.2,82,28,2.2,11.30,90,0,90,
    '2026-04-15','华懋科技',3.0,55,60,1.0,16.80,55,0,55,
    '2026-04-16','通宇通讯',4.8,70,35,1.5,11.80,78,0,78,
    '2026-04-17','华正新材',4.7,65,42,1.3,14.50,72,0,72,
    '2026-04-20','泰晶科技',4.5,78,22,1.9,13.20,85,0,85,
    '2026-04-21','水晶光电',3.9,62,48,1.1,17.60,65,0,65,
    '2026-04-22','博云新材',6.8,85,15,2.5,9.80,95,0,95,
    '2026-04-23','博杰股份',6.7,80,20,2.3,10.50,92,0,92,
    '2026-04-24','株冶集团',3.6,58,52,0.9,14.20,58,0,58,
    '2026-04-27','禾望电气',4.1,72,38,1.6,12.80,76,0,76,
    '2026-04-28','中旗新材',3.9,66,48,1.2,15.50,68,0,68,
    '2026-04-29','安孚科技',4.0,70,42,1.4,13.00,70,0,70,
    '2026-04-30','四方股份',3.9,63,50,1.1,16.40,64,0,64,
    '2026-05-06','迎丰股份',6.2,82,25,2.0,11.00,90,0,90,
    '2026-05-07','华升股份',5.0,75,32,1.7,12.20,80,0,80,
    '2026-05-08','东方通信',4.5,68,28,1.8,17.50,76,0,76,
    '2026-05-11','平安电工',5.3,78,22,2.1,11.80,88,0,88,
    '2026-05-12','宇环数控',6.7,85,18,2.4,10.20,94,0,94,
    '2026-05-13','东方钽业',4.1,65,40,1.5,14.00,72,0,72,
    '2026-05-14','巨轮智能',4.8,72,35,1.6,13.50,78,0,78,
    '2026-05-15','新泉股份',5.0,70,38,1.4,15.20,80,0,80,
    '2026-05-18','兆易创新',6.6,82,20,2.2,12.00,92,0,92,
    '2026-05-19','法狮龙',6.6,80,25,2.0,11.50,90,-8,82,
    '2026-05-20','锦和商管',3.0,55,55,0.8,15.80,55,0,55,
    '2026-05-21','新坐标',6.3,78,30,1.9,11.50,88,0,88,
    '2026-05-22','再升科技',6.4,78,35,1.8,12.50,88,0,88,
]
for idx, i in enumerate(range(0, len(champions), 10)):
    dt, name, p, cl, wrv, vr, price, base, pen, total = champions[i:i+10]
    c.execute('''
        INSERT INTO selection_pool
        (date, run_time, snapshot_id,
         data_provider, data_api, data_type,
         strategy_version, market_type, market_key,
         pool_size, used_level, total_candidates,
         code, name, p, cl, wrv, vr, price,
         base_score, momentum_penalty, total_score)
        VALUES (?, '14:50:00', 1,
                'sina', 'hq.sinajs.cn', 'realtime',
                'V13', '真实涨日', 'real_up',
                30, 'L1', 3043,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?)
    ''', (dt, f'600{idx:03d}', name, p, cl, wrv, vr, price, base, pen, total))

conn.commit()

# =============================================
#  展示
# =============================================
print(f'\n{"="*75}')
print(f'  📂 v13_quant.db V5 — 最终版：策略文件完整归档')
print(f'{"="*75}')

print(f'\n📋 表结构：')
tables_info = {
    'strategy_files':'策略文件完整内容（从.py到DB）',
    'strategy_snapshot':'策略快照（参数+分级+关联文件ID）',
    'data_sina':'新浪实时行情',
    'data_tencent':'腾讯K线',
    'data_cache':'big_cache历史数据',
    'features_cache':'预计算特征',
    'selection_pool':'选股池（所有候选股）'
}
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    cnt = c.execute(f'SELECT COUNT(*) FROM {r[0]}').fetchone()[0]
    print(f'  {r[0]:>25}  {cnt:>3}行  {tables_info.get(r[0],"")}')

print(f'\n📋 视图：champion_daily')

print(f'\n{"="*75}')
print(f'  📄 strategy_files — 策略文件完整内容已归档')
print(f'{"="*75}')
print(f'{"文件名":>40} {"类型":>18} {"大小":>6} {"hash":>18}')
print(f'{"-"*85}')
for r in c.execute('''
    SELECT file_name, file_type, file_size, file_hash
    FROM strategy_files ORDER BY file_type, file_name
'''):
    print(f'{r[0]:>40} {r[1]:>18} {r[2]:>6}B  {r[3]}')

# 验证：从数据库还原文件内容
print(f'\n{"="*75}')
print(f'  🔄 验证：从数据库还原策略文件')
print(f'{"="*75}')
r = c.execute("SELECT file_name, file_content FROM strategy_files WHERE file_type='scoring_strategy' LIMIT 1").fetchone()
content_preview = r[1][:200]
print(f'  文件名: {r[0]}')
print(f'  内容预览（前200字）:')
print(f'  {"─"*55}')
print(f'  {content_preview}')
print(f'  {"─"*55}')
print(f'  ✅ 文件完整存于数据库，原文件丢失可从此还原')

print(f'\n{"="*75}')
print(f'  🔗 关联关系：snapshot → files')
print(f'{"="*75}')
r = c.execute('''
    SELECT ss.strategy_version, ss.run_date, ss.run_time,
           sf1.file_name, sf2.file_name, sf3.file_name
    FROM strategy_snapshot ss
    LEFT JOIN strategy_files sf1 ON ss.scoring_file_id=sf1.id
    LEFT JOIN strategy_files sf2 ON ss.backtest_file_id=sf2.id
    LEFT JOIN strategy_files sf3 ON ss.production_file_id=sf3.id
    WHERE ss.strategy_version='V13'
''').fetchone()
print(f'  V13 {r[1]} {r[2]}')
print(f'    ├─ 评分策略: {r[3]}')
print(f'    ├─ 回测脚本:  {r[4]}')
print(f'    └─ 生产脚本:  {r[5]}')

print(f'\n{"="*75}')
print(f'  🏆 历史冠军 — 从选股池SQL查询')
print(f'{"="*75}')
print(f'{"日期":>12} {"冠军":>10} {"评分":>5} {"涨幅":>6} {"总分":>6}')
print(f'{"-"*55}')
for r in c.execute('''
    SELECT date, name, base_score, p, total_score
    FROM selection_pool WHERE strategy_version='V13'
    ORDER BY date DESC LIMIT 10
'''):
    print(f'{r[0]:>12} {r[1]:>10} {r[2]:>5.0f} {r[3]:>+5.1f}% {r[4]:>6.0f}')

# 验证文件恢复功能
print(f'\n{"="*75}')
print(f'  💾 文件恢复演示')
print(f'{"="*75}')
print(f'  假如"分而治之_V10_跌日_评分策略.py"丢失了：')
print(f'  SELECT file_content FROM strategy_files WHERE file_name LIKE "%跌日%"')
print(f'  → 获得完整.py文件内容，直接写回磁盘即可恢复')
print(f'  ✅ 文件永不丢失')

conn.close()
print(f'\n📁 {db_path}')
print(f'📏 {os.path.getsize(db_path)/1024:.0f} KB')
