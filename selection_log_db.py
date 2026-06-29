#!/usr/bin/env python3
"""在V13_日报.py和V22_日报.py末尾添加数据库记录功能"""
import sqlite3
import os
from datetime import datetime, timedelta

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

def ensure_daily_log_table():
    """确保 daily_selection_log 表存在"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS daily_selection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,           -- 'V13' 或 'V22'
            date TEXT NOT NULL,              -- 选股日期 YYYY-MM-DD
            run_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            market_type TEXT,                -- 真实涨日/虚涨日/跌日/横盘
            used_level TEXT,                 -- 使用级别 L0~L4
            pool_size INTEGER,               -- 候选池大小
            
            -- 冠军详情
            c_code TEXT, c_name TEXT, c_price REAL, c_p REAL, c_score REAL,
            c_cl REAL, c_vr REAL, c_hsl REAL, c_wr REAL, c_dif REAL,
            
            -- 亚军详情
            s_code TEXT, s_name TEXT, s_price REAL, s_p REAL, s_score REAL,
            s_cl REAL, s_vr REAL, s_hsl REAL, s_wr REAL, s_dif REAL,
            
            -- 季军详情
            t_code TEXT, t_name TEXT, t_price REAL, t_p REAL, t_score REAL,
            t_cl REAL, t_vr REAL, t_hsl REAL, t_wr REAL, t_dif REAL,
            
            -- 完整TOP10 JSON（可选，用于深度回测）
            top10_json TEXT,
            
            notes TEXT
        )
    ''')
    # 索引
    conn.execute('CREATE INDEX IF NOT EXISTS idx_dsl_version_date ON daily_selection_log(version, date)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_dsl_date ON daily_selection_log(date)')
    conn.commit()
    conn.close()
    print('✅ daily_selection_log 表已就绪')

def log_selection_to_db(version, date, market_type, used_level, pool_size, top10):
    """记录选股结果到数据库，version = 'V13' 或 'V22'"""
    # 检查是否已存在（防重复写入，同版本同日期不再写）
    conn = sqlite3.connect(DB_PATH, timeout=10)
    existing = conn.execute(
        'SELECT id FROM daily_selection_log WHERE version=? AND date=?',
        (version, date)
    ).fetchone()
    if existing:
        print(f'⏭️  {version} {date} 已记录，跳过')
        conn.close()
        return
    
    champ = top10[0] if len(top10) > 0 else None
    second = top10[1] if len(top10) > 1 else None
    third = top10[2] if len(top10) > 2 else None
    
    def vals(s, code_str, ind=None):
        if not s:
            return (None,) * 10
        code = code_str or ''
        name = s.get('name','') if isinstance(s, dict) else ''
        price = s.get('price',0) if isinstance(s, dict) else 0
        pct = s.get('p',0) if isinstance(s, dict) else 0
        sc = s.get('score',0) if isinstance(s, dict) else 0
        cl = s.get('cl',50) if isinstance(s, dict) else 50
        vr = s.get('vol_ratio',1) if isinstance(s, dict) else 1
        hsl = s.get('hsl',0) if isinstance(s, dict) else 0
        wr = 50
        dif = 0
        if ind:
            wr = ind.get('wr',50)
            dif = ind.get('dif',0)
        return (code, name, price, pct, sc, cl, vr, hsl, wr, dif)
    
    # 处理 top10 的结构: [(sc, s, ind, code), ...] 格式
    c_code = champ[3] if champ and len(champ) >= 4 else ''
    s_code = second[3] if second and len(second) >= 4 else ''
    t_code = third[3] if third and len(third) >= 4 else ''
    c_vals = vals(champ[1], c_code, champ[2]) if champ and len(champ) >= 3 else (None,)*10
    s_vals = vals(second[1], s_code, second[2]) if second and len(second) >= 3 else (None,)*10
    t_vals = vals(third[1], t_code, third[2]) if third and len(third) >= 3 else (None,)*10
    
    import json
    top10_json = json.dumps([
        {'sc': it[0], 'name': (it[1].get('name','') if isinstance(it[1], dict) else ''),
         'code': it[3] if len(it) >= 4 else '',
         'price': (it[1].get('price',0) if isinstance(it[1], dict) else 0),
         'p': (it[1].get('p',0) if isinstance(it[1], dict) else 0)}
        for it in top10[:10] if len(it) >= 2
    ], ensure_ascii=False, default=str)
    
    conn.execute('''
        INSERT INTO daily_selection_log
        (version, date, market_type, used_level, pool_size,
         c_code, c_name, c_price, c_p, c_score, c_cl, c_vr, c_hsl, c_wr, c_dif,
         s_code, s_name, s_price, s_p, s_score, s_cl, s_vr, s_hsl, s_wr, s_dif,
         t_code, t_name, t_price, t_p, t_score, t_cl, t_vr, t_hsl, t_wr, t_dif,
         top10_json)
        VALUES (?,?,?,?,?,
                ?,?,?,?,?,?,?,?,?,?,
                ?,?,?,?,?,?,?,?,?,?,
                ?,?,?,?,?,?,?,?,?,?,
                ?)
    ''', (version, date, market_type, used_level, pool_size,
          *c_vals, *s_vals, *t_vals, top10_json))
    
    # 同时写入 selection_candidates（供择优读取）
    conn.execute('''CREATE TABLE IF NOT EXISTS selection_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, run_time TEXT, version TEXT, rank INTEGER,
        code TEXT, name TEXT, price REAL, pct REAL, score REAL,
        cl REAL, vr REAL, hsl REAL, dif REAL, wr REAL
    )''')
    run_t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for i, item in enumerate(top10[:10]):
        if len(item) >= 4:
            sc, s, ind, code = item[0], item[1], item[2], item[3]
        elif isinstance(item, dict):
            sc = item.get('sc', 0); s = item; code = item.get('code', ''); ind = {}
        else:
            continue
        nm = s.get('name','') if isinstance(s, dict) else ''
        pr = s.get('price',0) if isinstance(s, dict) else 0
        pc = s.get('p',0) if isinstance(s, dict) else 0
        cl_v = ind.get('cl',50) if ind else (s.get('cl',50) if isinstance(s, dict) else 50)
        vr_v = ind.get('vol_ratio',1) if ind else (s.get('vol_ratio',1) if isinstance(s, dict) else 1)
        hsl_v = s.get('hsl',0) if isinstance(s, dict) else 0
        dif_v = ind.get('dif',0) if ind else 0
        wr_v = ind.get('wr',50) if ind else 50
        conn.execute('''INSERT OR IGNORE INTO selection_candidates
            (date, run_time, version, rank, code, name, price, pct, score, cl, vr, hsl, dif, wr)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (date, run_t, version, i+1, code, nm, pr, pc, round(sc,1),
             cl_v, vr_v, hsl_v, dif_v, wr_v))
    
    conn.commit()
    conn.close()
    print(f'✅ {version} {date} 选股日志已写入 daily_selection_log')


def save_realtime_to_datacache(date, stocks, indicators, source_tag='tencent:1450'):
    """把当天14:50实时数据写入data_cache，统一数据源"""
    import sqlite3, os
    DB_PATH = os.path.join(os.path.expanduser('~/AppData/Local/hermes/scripts'), 'v13_quant.db')
    conn = sqlite3.connect(DB_PATH, timeout=30)
    
    rows = []
    # 预加载上交易日vr，代替API虚假量比
    prev_vr = {}
    try:
        prev_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        cur2 = conn.execute('SELECT code, vr FROM data_cache WHERE date=? AND vr>0', (prev_date,))
        # 如果没有前一天，从最新完整交易日取
        if not cur2.fetchone():
            cur2 = conn.execute('SELECT DISTINCT date FROM data_cache WHERE date<? AND vr>0 ORDER BY date DESC LIMIT 1', (date,))
            r2 = cur2.fetchone()
            if r2:
                cur3 = conn.execute('SELECT code, vr FROM data_cache WHERE date=? AND vr>0', (r2[0],))
                prev_vr = {r[0]: r[1] for r in cur3.fetchall()}
        else:
            prev_vr = {r[0]: r[1] for r in cur2.fetchall()}
    except:
        pass
    
    for code, s in stocks.items():
        ind = indicators.get(code)
        if not ind: continue
        # vr: 优先用上交易日data_cache的真实值，避免API的虚假量比（如28.9）
        real_vr = prev_vr.get(code, s.get('vol_ratio', 0))
        rows.append((
            date, code, s.get('name', ''),
            s.get('p', 0), ind.get('cl', 50), real_vr, 0,
            ind.get('dif', 0), 1 if ind.get('dif', 0) > 0 else 0,
            ind.get('wr', 50), ind.get('j_val', 50),
            ind.get('k_val', 50), ind.get('d_val', 50),
            50, 1, 1 if ind.get('k_val', 50) > ind.get('d_val', 50) else 0,
            s.get('price', 0), s.get('price', 0),
            source_tag, '1.0'
        ))
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS data_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL, code TEXT NOT NULL, name TEXT,
            p REAL, cl REAL, vr REAL, n REAL,
            dif_val REAL, macd_golden INTEGER,
            wr_val REAL, j_val REAL, k_val REAL, d_val REAL,
            pos_in_day REAL, above_ma5 INTEGER, kdj_golden INTEGER,
            close REAL, volume REAL,
            original_source TEXT,
            cache_version TEXT, high REAL DEFAULT 0, low REAL DEFAULT 0,
            UNIQUE(date, code)
        )
    ''')
    
    conn.executemany('''
        INSERT OR REPLACE INTO data_cache
        (date, code, name, p, cl, vr, n,
         dif_val, macd_golden, wr_val, j_val, k_val, d_val,
         pos_in_day, above_ma5, kdj_golden,
         close, volume, original_source, cache_version)
        VALUES (?,?,?,?,?,?,?,
                ?,?,?,?,?,?,
                ?,?,?,
                ?,?,?,?)
    ''', rows)
    
    conn.commit()
    conn.close()
    print(f'✅ {date} 实时数据已写入data_cache ({len(rows)}只/{len(stocks)}只)')


if __name__ == '__main__':
    ensure_daily_log_table()
    print('✅ 数据库初始化完成')
