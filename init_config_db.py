#!/usr/bin/env python
"""配置存入数据库 — 邮箱/token/路径/收件人全纳入 config 表"""
import sqlite3, os, json, hashlib

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
db_path = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

conn = sqlite3.connect(db_path)
c = conn.cursor()

# =============================================
#  创建 config 表
# =============================================
c.execute('''
    CREATE TABLE IF NOT EXISTS config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,       -- email / api / path / strategy / notification
        key TEXT NOT NULL,            -- 配置名
        value TEXT NOT NULL,          -- 配置值
        value_type TEXT DEFAULT 'text', -- text / password / json / int / path
        description TEXT,             -- 说明
        updated_at TEXT,              -- 最后修改时间
        UNIQUE(category, key)
    )
''')
print('✅ config 表已创建')

# =============================================
#  清空旧配置，填入现有的硬编码配置
# =============================================
c.execute('DELETE FROM config')

configs = [
    # ── 邮箱配置 ──
    ('email', 'smtp_host',      'smtp.163.com',        'text',     'SMTP服务器'),
    ('email', 'smtp_port',      '465',                  'int',      'SMTP端口'),
    ('email', 'sender',         'xiaozhufenfen88@163.com', 'text',  '发件人邮箱'),
    ('email', 'password',       'YZmfTbTsvXWbSnFy',    'password', '发件人密码'),
    ('email', 'recipients',     '1254628314@qq.com,314913203@qq.com', 'text', '收件人（逗号分隔）'),
    ('email', 'night_block_start', '0',                 'int',      '深夜禁发开始时间'),
    ('email', 'night_block_end',   '6',                 'int',      '深夜禁发结束时间'),

    # ── API配置 ──
    ('api', 'tushare_token',    '',                      'password', 'Tushare Pro Token'),
    ('api', 'sina_endpoint',    'hq.sinajs.cn',          'text',     '新浪实时行情API'),
    ('api', 'tencent_kline',    'web.ifzq.gtimg.cn',     'text',     '腾讯K线API'),
    ('api', 'tencent_realtime', 'qt.gtimg.cn',           'text',     '腾讯实时报价API'),
    ('api', 'eastmoney_kline',  'push2his.eastmoney.com','text',     '东方财富K线API'),
    ('api', 'eastmoney_kline_params', 'secid={mkt}.{code}&klt=101&fqt=1&lmt=365', 'text', '东方财富K线参数模板'),

    # ── 路径配置 ──
    ('path', 'scripts_dir',     os.path.expanduser('~/AppData/Local/hermes/scripts'), 'path', '脚本根目录'),
    ('path', 'cache_dir',       os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache'), 'path', '缓存目录'),
    ('path', 'database_path',   db_path,                'path',     '数据库路径'),
    ('path', 'v13_dir',         os.path.join(SCRIPTS_DIR, 'release', 'V13'), 'path', 'V13策略目录'),
    ('path', 'email_archive',   os.path.join(SCRIPTS_DIR, 'email_archive'), 'path', '邮件归档目录'),
    ('path', 'stock_pool',      os.path.join(SCRIPTS_DIR, '活跃股票池_3043.json'), 'path', '活跃股票池文件'),

    # ── 策略配置 ──
    ('strategy', 'active_version', 'V13',                'text',     '当前生产版本'),
    ('strategy', 'data_cache_version', 'big_cache_2026-05-29', 'text', '当前big_cache版本'),
    ('strategy', 'features_version', 'features_30d_2026-05-29', 'text', '当前特征版本'),
    ('strategy', 'backtest_dates', '30',                 'int',      '回测天数'),
    ('strategy', 'target_nh',     '2.5',                 'float',    '达标线（次日最高%）'),

    # ── 通知配置 ──
    ('notification', 'weixin_enabled',  '1',             'int',      '微信通知开关'),
    ('notification', 'email_enabled',   '1',             'int',      '邮件通知开关'),
    ('notification', 'daily_run_time',  '14:50',         'text',     '每日运行时间'),
]

now = '2026-06-01 00:00:00'
for cat, key, val, vtype, desc in configs:
    c.execute('''
        INSERT INTO config (category, key, value, value_type, description, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (cat, key, val, vtype, desc, now))

conn.commit()

# =============================================
#  展示
# =============================================
print(f'\n{"="*70}')
print(f'  📋 config 表 — 所有配置')
print(f'{"="*70}')

print(f'\n{"类别":>14} {"Key":>25} {"值":>30}')
print(f'{"-"*70}')
current_cat = ''
for r in c.execute('''
    SELECT category, key, value, value_type, description 
    FROM config ORDER BY category, key
'''):
    cat, key, val, vtype, desc = r
    if cat != current_cat:
        print(f'  {"─"*65}')
        current_cat = cat
    # 密码类脱敏显示
    display_val = val[:3]+'***'+val[-3:] if vtype == 'password' and len(val) > 6 else val
    print(f'  {cat:>14} {key:>25} {display_val:>30}  # {desc}')

# 测试：从数据库读取配置
print(f'\n{"="*70}')
print(f'  🔄 验证：修改配置不需要改代码')
print(f'{"="*70}')
print(f'  当前发件人: ', end='')
r = c.execute("SELECT value FROM config WHERE category='email' AND key='sender'").fetchone()
print(f'{r[0]}')
print(f'  当前收件人: ', end='')
r = c.execute("SELECT value FROM config WHERE category='email' AND key='recipients'").fetchone()
print(f'{r[0]}')
print(f'')
print(f'  ✅ 如果修改收件人：')
print(f'     UPDATE config SET value = "新邮箱@qq.com"')
print(f'     WHERE key = "recipients";')
print(f'  → 下次运行自动生效，代码不用改一个字')

# 统计
print(f'\n{"="*70}')
print(f'  📊 配置统计')
print(f'{"="*70}')
print(f'  总配置项: {c.execute("SELECT COUNT(*) FROM config").fetchone()[0]} 项')
for r in c.execute('SELECT category, COUNT(*) FROM config GROUP BY category'):
    print(f'    {r[0]:>15}: {r[1]} 项')

conn.close()
print(f'\n📁 {db_path}')
