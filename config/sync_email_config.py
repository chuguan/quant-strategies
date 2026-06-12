#!/usr/bin/env python3
"""
邮件配置同步工具 — 将 email_config.yaml 写入数据库
用法:
    python config/sync_email_config.py          # 同步生产配置到DB
    python config/sync_email_config.py --dry    # 预览，不实际写入

所有邮件配置修改请编辑 config/email_config.yaml，然后运行此脚本同步到数据库。
不要直接修改数据库。
"""
import os, sys, yaml, json

# 路径
PROD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YAML_PATH = os.path.join(PROD_DIR, 'config', 'email_config.yaml')
DB_PATH = os.path.join(PROD_DIR, 'data', 'v13_quant.db')


def load_yaml():
    with open(YAML_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def update_db(cfg, dry_run=False):
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 确保 config 表存在
    c.execute('''
        CREATE TABLE IF NOT EXISTS config (
            category TEXT,
            key TEXT,
            value TEXT,
            env TEXT DEFAULT 'production',
            PRIMARY KEY (category, key, env)
        )
    ''')

    changes = []

    # 处理 A 组配置
    email_a = cfg.get('email_a', {})
    env = cfg.get('env', 'production')
    for key, val in email_a.items():
        if key == 'night_block':
            c2 = 'email'
            c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                      (c2, 'night_block_start', str(val['start_hour']), env))
            c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                      (c2, 'night_block_end', str(val['end_hour']), env))
            changes.append(f'email.night_block: {val["start_hour"]}~{val["end_hour"]}')
        elif key == 'recipients':
            c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                      ('email', key, ','.join(val), env))
            changes.append(f'email.recipients: {", ".join(val)}')
        else:
            c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                      ('email', key, str(val), env))
            changes.append(f'email.{key}: {"****" if "password" in key else val}')

    # 处理 B 组配置
    email_b = cfg.get('email_b', {})
    for key, val in email_b.items():
        if key == 'night_block':
            c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                      ('email_b', 'night_block_start', str(val['start_hour']), env))
            c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                      ('email_b', 'night_block_end', str(val['end_hour']), env))
            changes.append(f'email_b.night_block: {val["start_hour"]}~{val["end_hour"]}')
        elif key == 'recipients':
            c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                      ('email_b', key, ','.join(val), env))
            changes.append(f'email_b.recipients: {", ".join(val)}')
        else:
            c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                      ('email_b', key, str(val), env))
            changes.append(f'email_b.{key}: {"****" if "password" in key else val}')

    # 处理开发环境配置
    dev = cfg.get('dev', {})
    for key, val in dev.items():
        if key == 'recipients':
            c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                      ('email', key, ','.join(val), 'dev'))
            changes.append(f'[dev] email.recipients: {", ".join(val)}')
        elif key != 'night_block':
            c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                      ('email', key, str(val), 'dev'))
            changes.append(f'[dev] email.{key}: {"****" if "password" in key else val}')

    if dry_run:
        conn.close()
        return changes

    conn.commit()
    conn.close()

    # 清空 db_config 缓存
    try:
        sys.path.insert(0, os.path.join(PROD_DIR, 'lib'))
        from db_config import reload_cache
        reload_cache()
    except ImportError:
        pass

    return changes


def main():
    dry_run = '--dry' in sys.argv

    if not os.path.exists(YAML_PATH):
        print(f'❌ 配置文件不存在: {YAML_PATH}')
        sys.exit(1)
    if not os.path.exists(DB_PATH):
        print(f'❌ 数据库不存在: {DB_PATH}')
        sys.exit(1)

    cfg = load_yaml()
    changes = update_db(cfg, dry_run)

    print(f'{"="*50}')
    print(f'{" [预览] " if dry_run else " [同步] "} 邮件配置 → 数据库')
    print(f'{"="*50}')
    print(f'配置文件: {YAML_PATH}')
    print(f'数据库:   {DB_PATH}')
    print(f'环境:     {cfg.get("env", "production")}')
    print()
    print('变更内容:')
    for c in changes:
        print(f'  ✓ {c}')
    print()
    if dry_run:
        print('这是预览模式，加 --dry 取消。真正执行: python sync_email_config.py')
    else:
        print('✅ 配置已同步到数据库')
        print('📝 下次修改请编辑 config/email_config.yaml 后重新运行')


if __name__ == '__main__':
    main()
