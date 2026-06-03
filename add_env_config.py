#!/usr/bin/env python
"""config表增加环境字段：production / dev 配置可不同"""
import sqlite3, os

db = os.path.expanduser('~/AppData/Local/hermes/scripts/v13_quant.db')
conn = sqlite3.connect(db)
c = conn.cursor()

# 1. 加环境字段
try:
    c.execute("ALTER TABLE config ADD COLUMN env TEXT DEFAULT 'production'")
    print('✅ 已添加 env 字段')
except sqlite3.OperationalError as e:
    if 'duplicate column' in str(e):
        print('ℹ️  env 字段已存在')
    else:
        raise

# 2. 原有配置全标 production
c.execute("UPDATE config SET env='production' WHERE env IS NULL")
print('✅ 现有配置全部标记为 production')

# 3. 备份原有UNIQUE约束重建
# SQLite不能直接改约束，转表
c.execute('''
    CREATE TABLE config_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        key TEXT NOT NULL,
        env TEXT DEFAULT 'production',
        value TEXT NOT NULL,
        value_type TEXT DEFAULT 'text',
        description TEXT,
        updated_at TEXT,
        UNIQUE(category, key, env)
    )
''')

# 复制数据
c.execute('''
    INSERT INTO config_new (id, category, key, env, value, value_type, description, updated_at)
    SELECT id, category, key, env, value, value_type, description, updated_at FROM config
''')

# 删旧表重建
c.execute('DROP TABLE config')
c.execute('ALTER TABLE config_new RENAME TO config')

# 4. 插入开发环境配置（与生产不同的值）
dev_configs = [
    # 开发用不同的邮箱
    ('email', 'sender',        'dev_test@163.com',       'production', 'text', '开发发件人'),
    ('email', 'password',      'dev_password_123',        'production', 'password', '开发密码'),
    ('email', 'recipients',    'dev@test.com',            'production', 'text', '开发收件人'),
    # 开发用不同路径
    ('path',  'v13_dir',       os.path.expanduser('~/AppData/Local/hermes/scripts/dev/current'), 'production', 'path', '开发V13目录'),
    ('path',  'email_archive', os.path.expanduser('~/AppData/Local/hermes/scripts/dev/email_archive'), 'production', 'path', '开发存档目录'),
    # 开发策略
    ('strategy', 'active_version', 'V13_dev',             'production', 'text', '开发版本'),
    ('strategy', 'backtest_dates', '5',                   'production', 'int', '开发回测天数（短）'),
]

# ⚠️ 上面误标成 production 了，修正为 dev
for cat, key, val, _, vtype, desc in dev_configs:
    # 先删可能的旧记录
    c.execute("DELETE FROM config WHERE category=? AND key=? AND env='dev'", (cat, key))
    c.execute('''
        INSERT OR REPLACE INTO config (category, key, env, value, value_type, description, updated_at)
        VALUES (?, ?, 'dev', ?, ?, ?, ?)
    ''', (cat, key, val, vtype, desc, '2026-06-01'))

conn.commit()

# 展示
print(f'\n{"="*70}')
print(f'  📋 config 表 — 生产 vs 开发环境')
print(f'{"="*70}')

for env in ['production', 'dev']:
    cnt = c.execute("SELECT COUNT(*) FROM config WHERE env=?", (env,)).fetchone()[0]
    print(f'\n  🌐 {env.upper()} 环境（{cnt}项）')
    print(f'  {"类别":>12} {"Key":>20} {"值":>30}')
    print(f'  {"-"*65}')
    for r in c.execute('''
        SELECT category, key, value, value_type
        FROM config WHERE env=? ORDER BY category, key
    ''', (env,)):
        cat, key, val, vtype = r
        display_val = val[:3]+'***'+val[-3:] if vtype == 'password' and len(val) > 6 else val
        print(f'  {cat:>12} {key:>20} {display_val:>30}')

# 对比：同一key在不同环境的值
print(f'\n{"="*70}')
print(f'  🔄 生产 vs 开发 — 同一配置项不同值')
print(f'{"="*70}')
compare_keys = ['sender', 'password', 'active_version', 'backtest_dates']
for key in compare_keys:
    p = c.execute("SELECT value FROM config WHERE key=? AND env='production'", (key,)).fetchone()
    d = c.execute("SELECT value FROM config WHERE key=? AND env='dev'", (key,)).fetchone()
    pv = p[0][:3]+'***' if p and key == 'password' else (p[0] if p else '-')
    dv = d[0][:3]+'***' if d and key == 'password' else (d[0] if d else '-')
    print(f'  {key:>20}: 生产={pv:>30}  开发={dv:>30}')

conn.close()
print(f'\n✅ 环境隔离完成。config表现在有 env 字段区分 production/dev')
