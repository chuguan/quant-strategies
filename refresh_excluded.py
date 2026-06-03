#!/usr/bin/env python
"""每日刷新剔除清单 — 自动检测新增ST/新股/停牌等"""
import sqlite3, os, sys

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

def refresh_st_excluded():
    """刷新剔除清单：检测新ST、新股、停牌"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    
    # 获取最新交易日
    c.execute('SELECT MAX(date) FROM data_cache WHERE close > 0')
    latest = c.fetchone()[0]
    if not latest:
        conn.close()
        return 0
    
    today = latest
    added = 0
    
    # ① ST/*ST/退
    c.execute("SELECT DISTINCT code, name FROM data_cache WHERE date=? AND (name LIKE '%ST%' OR name LIKE '%*ST%' OR name LIKE '%退%')", (today,))
    for code, name in c.fetchall():
        existing = c.execute('SELECT code FROM excluded_stocks WHERE code=?', (code,)).fetchone()
        if not existing:
            c.execute('INSERT OR REPLACE INTO excluded_stocks VALUES(?,?,?,?,?,1)',
                      (code, name or '', '%s ST/*ST/退市' % today, 'ST_退市', today))
            added += 1

    # ② 新股<14天
    c.execute('''SELECT d.code, d.name FROM data_cache d WHERE d.date=?
        AND (d.wr_val IS NULL OR d.wr_val=50)
        AND (SELECT COUNT(*) FROM data_cache WHERE code=d.code AND close>0) < 14''', (today,))
    for code, name in c.fetchall():
        existing = c.execute('SELECT code FROM excluded_stocks WHERE code=?', (code,)).fetchone()
        if not existing:
            days = c.execute('SELECT COUNT(*) FROM data_cache WHERE code=? AND close>0', (code,)).fetchone()[0]
            c.execute('INSERT OR REPLACE INTO excluded_stocks VALUES(?,?,?,?,?,1)',
                      (code, name or '', '新股数据不足14天(%d天)' % days, '新股_数据不足', today))
            added += 1

    # ③ 数据不足20天
    c.execute('''SELECT code, COUNT(*) as days FROM data_cache WHERE close>0
        GROUP BY code HAVING days>=14 AND days<20''')
    for code, days in c.fetchall():
        existing = c.execute('SELECT code FROM excluded_stocks WHERE code=?', (code,)).fetchone()
        if not existing:
            n = c.execute('SELECT name FROM data_cache WHERE code=? AND name!="" LIMIT 1', (code,)).fetchone()
            c.execute('INSERT OR REPLACE INTO excluded_stocks VALUES(?,?,?,?,?,1)',
                      (code, n[0] if n else '', '总数据仅%d天' % days, '数据不足20天', today))
            added += 1

    # ④ 当日无数据(停牌)
    c.execute('SELECT d.code, d.name FROM data_cache d WHERE d.date=? AND (d.volume=0 OR d.volume IS NULL) AND (d.p=0 OR d.p IS NULL) AND d.close>0', (today,))
    for code, name in c.fetchall():
        existing = c.execute('SELECT code FROM excluded_stocks WHERE code=?', (code,)).fetchone()
        if not existing:
            c.execute('INSERT OR REPLACE INTO excluded_stocks VALUES(?,?,?,?,?,1)',
                      (code, name or '', '%s停牌' % today, '停牌', today))
            added += 1

    # ⑤ 已退市/摘牌(连续>30天无数据)
    c.execute('SELECT DISTINCT date FROM data_cache ORDER BY date DESC LIMIT 30')
    recent = set(r[0] for r in c.fetchall())
    c.execute('SELECT code, MAX(date) FROM data_cache WHERE close>0 GROUP BY code')
    for code, last_dt in c.fetchall():
        if last_dt not in recent:
            existing = c.execute('SELECT code FROM excluded_stocks WHERE code=?', (code,)).fetchone()
            if not existing:
                n = c.execute('SELECT name FROM data_cache WHERE code=? AND name!="" LIMIT 1', (code,)).fetchone()
                c.execute('INSERT OR REPLACE INTO excluded_stocks VALUES(?,?,?,?,?,1)',
                          (code, n[0] if n else '', '最后数据%s已退市/停牌' % last_dt, '已退市_停牌', today))
                added += 1

    conn.commit()
    conn.close()
    return added

if __name__ == '__main__':
    n = refresh_st_excluded()
    print('刷新剔除清单: 新增%d只' % n)
