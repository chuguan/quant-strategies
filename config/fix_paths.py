#!/usr/bin/env python3
"""修复DB中过时的路径配置（scripts → prod）"""
import sqlite3, os

prod = r'C:\Users\12546\AppData\Local\hermes\prod'
db = os.path.join(prod, 'data', 'v13_quant.db')

conn = sqlite3.connect(db)
c = conn.cursor()

updates = {
    ('path', 'scripts_dir', 'production'): prod,
    ('path', 'database_path', 'production'): os.path.join(prod, 'data', 'v13_quant.db'),
    ('path', 'email_archive', 'production'): os.path.join(prod, 'backup'),
    ('path', 'stock_pool', 'production'): os.path.join(prod, 'data', '活跃股票池_3043.json'),
    ('path', 'v13_dir', 'production'): os.path.join(prod, 'strategies', 'V13'),
}

count = 0
for (cat, key, env), new_val in updates.items():
    c.execute('UPDATE config SET value=? WHERE category=? AND key=? AND env=?',
              (new_val, cat, key, env))
    if c.rowcount:
        count += 1
        print(f'  [{env}] {cat}.{key} → {new_val}')
    else:
        print(f'  [{env}] {cat}.{key} 未找到（可能已更新）')

conn.commit()
conn.close()
print(f'\n已更新 {count} 条路径配置')
