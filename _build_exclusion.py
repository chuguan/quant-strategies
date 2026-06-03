#!/usr/bin/env python
"""建剔除清单表 excluded_stocks"""
import sqlite3, json
DB = r'C:\Users\12546\AppData\Local\hermes\scripts\v13_quant.db'
conn = sqlite3.connect(DB, timeout=60)
c = conn.cursor()

# 建表
c.execute('''CREATE TABLE IF NOT EXISTS excluded_stocks (
    code TEXT PRIMARY KEY, name TEXT DEFAULT '', reason TEXT NOT NULL,
    category TEXT NOT NULL, added_date TEXT NOT NULL, active INTEGER DEFAULT 1
)''')
c.execute('DELETE FROM excluded_stocks')
today = '2026-05-29'

# ① 新股<14天
c.execute('''SELECT d.code,d.name FROM data_cache d WHERE d.date=?
    AND (d.wr_val IS NULL OR d.wr_val=50)
    AND (SELECT COUNT(*) FROM data_cache WHERE code=d.code AND close>0)<14''', (today,))
for code, name in c.fetchall():
    days = c.execute('SELECT COUNT(*) FROM data_cache WHERE code=? AND close>0',(code,)).fetchone()[0]
    c.execute('INSERT OR REPLACE INTO excluded_stocks VALUES(?,?,?,?,?,1)',
              (code,name or '','新股数据不足14天(%d天)'%days,'新股_数据不足',today))

# ② 代码废弃
pool_file = r'C:\Users\12546\AppData\Local\hermes\scripts\活跃股票池_3043.json'
with open(pool_file) as f: pool = json.load(f)
pool_codes = set(pool if isinstance(pool,list) else pool.get('codes',[]))
c.execute('SELECT DISTINCT code FROM data_cache')
db_codes = set(r[0] for r in c.fetchall())
for code in sorted(pool_codes - db_codes):
    c.execute('INSERT OR REPLACE INTO excluded_stocks VALUES(?,?,?,?,?,1)',
              (code,'','代码废弃(3043池中无任何历史数据)','代码废弃_无历史',today))

# ③ 已退市/摘牌(最后数据不在最近30天)
c.execute('SELECT DISTINCT date FROM data_cache ORDER BY date DESC LIMIT 30')
recent = set(r[0] for r in c.fetchall())
c.execute('SELECT code, MAX(date) FROM data_cache WHERE close>0 GROUP BY code')
for code, last_dt in c.fetchall():
    if last_dt not in recent:
        n = c.execute('SELECT name FROM data_cache WHERE code=? AND name!="" LIMIT 1',(code,)).fetchone()
        c.execute('INSERT OR REPLACE INTO excluded_stocks VALUES(?,?,?,?,?,1)',
                  (code,n[0] if n else '','最后数据%s已退市/停牌'%last_dt,'已退市_停牌',today))

# ④ ST/*ST/退
c.execute("SELECT DISTINCT code,name FROM data_cache WHERE name LIKE '%ST%' OR name LIKE '%*ST%' OR name LIKE '%退%'")
for code,name in c.fetchall():
    if not c.execute('SELECT code FROM excluded_stocks WHERE code=?',(code,)).fetchone():
        c.execute('INSERT OR REPLACE INTO excluded_stocks VALUES(?,?,?,?,?,1)',
                  (code,name or '','ST/*ST/退市','ST_退市',today))

# ⑤ 停牌(volume=0且p=0)
c.execute('SELECT d.code,d.name FROM data_cache d WHERE d.date=? AND (d.volume=0 OR d.volume IS NULL) AND (d.p=0 OR d.p IS NULL) AND d.close>0',(today,))
for code,name in c.fetchall():
    if not c.execute('SELECT code FROM excluded_stocks WHERE code=?',(code,)).fetchone():
        c.execute('INSERT OR REPLACE INTO excluded_stocks VALUES(?,?,?,?,?,1)',
                  (code,name or '','%s停牌(volume=0,p=0)'%today,'停牌',today))

# ⑥ 数据不足20天
c.execute('SELECT code,COUNT(*) as days FROM data_cache WHERE close>0 GROUP BY code HAVING days<20')
for code,days in c.fetchall():
    if not c.execute('SELECT code FROM excluded_stocks WHERE code=?',(code,)).fetchone():
        n = c.execute('SELECT name FROM data_cache WHERE code=? AND name!="" LIMIT 1',(code,)).fetchone()
        c.execute('INSERT OR REPLACE INTO excluded_stocks VALUES(?,?,?,?,?,1)',
                  (code,n[0] if n else '','总数据仅%d天'%days,'数据不足20天',today))

# ⑦ 当日无数据
have = set(r[0] for r in c.execute('SELECT code FROM data_cache WHERE date=? AND close>0',(today,)).fetchall())
for code in sorted(pool_codes - have):
    if code in db_codes and not c.execute('SELECT code FROM excluded_stocks WHERE code=?',(code,)).fetchone():
        n = c.execute('SELECT name FROM data_cache WHERE code=? AND name!="" LIMIT 1',(code,)).fetchone()
        c.execute('INSERT OR REPLACE INTO excluded_stocks VALUES(?,?,?,?,?,1)',
                  (code,n[0] if n else '','%s无当日数据'%today,'当日无数据',today))

conn.commit()

# 统计
c.execute('SELECT category,COUNT(*) FROM excluded_stocks GROUP BY category ORDER BY COUNT(*) DESC')
print('≡≡≡ 剔除清单(excluded_stocks) ≡≡≡')
t=0
for cat,cnt in c.fetchall():
    print(f'  {cat}: {cnt}只'); t+=cnt
print(f'  合计: {t}只')

# 各类样例
print()
for cat in ['新股_数据不足','代码废弃_无历史','已退市_停牌','ST_退市','停牌','数据不足20天','当日无数据']:
    c.execute('SELECT code,name,reason FROM excluded_stocks WHERE category=? LIMIT 3',(cat,))
    rows=c.fetchall()
    if rows:
        c2=c.execute('SELECT COUNT(*) FROM excluded_stocks WHERE category=?',(cat,)).fetchone()[0]
        for code,name,reason in rows:
            print(f'  {cat}({c2}只): {code} {name or "?":>8} | {reason}')

conn.close()
print('\n✅ 剔除清单已入库')
