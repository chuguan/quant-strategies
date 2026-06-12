#!/usr/bin/env python

"""
统一配置读取模块 — 所有脚本从这里读配置，不改代码
支持 production / dev 环境隔离
邮件配置优先从 email_config.yaml 读取，实现统一控制

用法：
    from db_config import get_config, get_config_int, get_config_list

    smtp_host = get_config('email', 'smtp_host')
    recipients = get_config_list('email', 'recipients')
    token = get_config('api', 'tushare_token', env='dev')
"""
import sqlite3, os, sys

PROD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROD_DIR, 'data', 'v13_quant.db')
YAML_PATH = os.path.join(PROD_DIR, 'config', 'email_config.yaml')

# 当前环境：优先从环境变量读，默认 production
CURRENT_ENV = os.environ.get('HERMES_ENV', 'production')

_cache = {}
_yaml_cache = None


def _load_yaml():
    """加载 email_config.yaml（带缓存）"""
    global _yaml_cache
    if _yaml_cache is not None:
        return _yaml_cache
    if not os.path.exists(YAML_PATH):
        _yaml_cache = {}
        return _yaml_cache
    try:
        import yaml
        with open(YAML_PATH, 'r', encoding='utf-8') as f:
            _yaml_cache = yaml.safe_load(f) or {}
    except Exception:
        _yaml_cache = {}
    return _yaml_cache


def _query(category, key, env=None):
    """读数据库，带内存缓存"""
    env = env or CURRENT_ENV
    cache_key = (category, key, env)
    if cache_key in _cache:
        return _cache[cache_key]

    if not os.path.exists(DB_PATH):
        return None

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT value FROM config WHERE category=? AND key=? AND env=?',
                  (category, key, env))
        r = c.fetchone()
        if r is None and env != 'production':
            c.execute('SELECT value FROM config WHERE category=? AND key=? AND env=?',
                      (category, key, 'production'))
            r = c.fetchone()
        conn.close()
        val = r[0] if r else None
        _cache[cache_key] = val
        return val
    except Exception:
        return None


def get_config(category, key, default=None, env=None):
    """读取文本配置"""
    val = _query(category, key, env)
    return val if val is not None else default


def get_config_int(category, key, default=0, env=None):
    """读取整数配置"""
    val = _query(category, key, env)
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def get_config_float(category, key, default=0.0, env=None):
    """读取浮点配置"""
    val = _query(category, key, env)
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def get_config_list(category, key, separator=',', default=None, env=None):
    """读取列表配置（逗号分隔）"""
    val = _query(category, key, env)
    if val is None:
        return default or []
    return [v.strip() for v in val.split(separator) if v.strip()]


def get_config_bool(category, key, default=False, env=None):
    """读取布尔配置"""
    val = _query(category, key, env)
    if val is None:
        return default
    return val.lower() in ('1', 'true', 'yes', 'on')


def reload_cache():
    """清空缓存，强制重新读取（配置修改后调用）"""
    _cache.clear()
    global _yaml_cache
    _yaml_cache = None


def get_email_config(env=None, category='email'):
    """获取邮件配置
    优先从 email_config.yaml 读取（统一控制），fallback 到数据库
    category: 'email'=A配置, 'email_b'=B配置
    """
    env = env or CURRENT_ENV
    cfg = _load_yaml()

    # 尝试从 YAML 读取（仅 production 环境）
    if env == 'production' and cfg:
        yaml_key = 'email_a' if category == 'email' else 'email_b'
        yaml_cfg = cfg.get(yaml_key, {})
        yaml_cfg2 = cfg if yaml_key not in cfg else {}  # 如果yaml结构不对，忽略

        if 'sender' in yaml_cfg or 'smtp_host' in yaml_cfg:
            # YAML 配置完整，从 YAML 读取
            recipients = yaml_cfg.get('recipients', [])
            nb = yaml_cfg.get('night_block', {})

            return {
                'smtp_host': yaml_cfg.get('smtp_host', 'smtp.163.com'),
                'smtp_port': yaml_cfg.get('smtp_port', 465),
                'sender': yaml_cfg.get('sender', ''),
                'password': yaml_cfg.get('password', ''),
                'recipients': recipients if isinstance(recipients, list) else [recipients],
                'night_block_start': nb.get('start_hour', 0),
                'night_block_end': nb.get('end_hour', 6),
            }

    # 开发环境或YAML不可用，回退到数据库
    return {
        'smtp_host': get_config(category, 'smtp_host', 'smtp.163.com', env),
        'smtp_port': get_config_int(category, 'smtp_port', 465, env),
        'sender': get_config(category, 'sender', '', env),
        'password': get_config(category, 'password', '', env),
        'recipients': get_config_list(category, 'recipients', env=env),
        'night_block_start': get_config_int(category, 'night_block_start', 0, env),
        'night_block_end': get_config_int(category, 'night_block_end', 6, env),
    }


def get_path_config(env=None):
    """快捷获取路径配置"""
    return {
        'scripts_dir': get_config('path', 'scripts_dir',
            os.path.join(PROD_DIR), env),
        'cache_dir': get_config('path', 'cache_dir',
            os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache'), env),
        'database_path': DB_PATH,
        'v13_dir': get_config('path', 'v13_dir', '', env),
        'stock_pool': get_config('path', 'stock_pool', '', env),
    }


def get_strategy_config(env=None):
    """快捷获取策略配置"""
    return {
        'active_version': get_config('strategy', 'active_version', 'V13', env),
        'backtest_dates': get_config_int('strategy', 'backtest_dates', 30, env),
        'target_nh': get_config_float('strategy', 'target_nh', 2.5, env),
    }


def get_current_env():
    """获取当前环境"""
    return CURRENT_ENV


# ============================================================
# 同步函数：将 YAML 配置同步到数据库
# ============================================================
def sync_email_config_to_db():
    """将 email_config.yaml 的配置同步回数据库，保持一致性"""
    cfg = _load_yaml()
    if not cfg:
        return 0

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        count = 0
        env = cfg.get('env', 'production')

        # A组
        for section, cat in [('email_a', 'email'), ('email_b', 'email_b')]:
            scfg = cfg.get(section, {})
            for key, val in scfg.items():
                if key == 'night_block':
                    c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                              (cat, 'night_block_start', str(val.get('start_hour', 0)), env))
                    c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                              (cat, 'night_block_end', str(val.get('end_hour', 6)), env))
                    count += 2
                elif key == 'recipients':
                    c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                              (cat, key, ','.join(val) if isinstance(val, list) else str(val), env))
                    count += 1
                else:
                    c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                              (cat, key, str(val), env))
                    count += 1

        # dev环境
        dev = cfg.get('dev', {})
        for key, val in dev.items():
            if key == 'recipients':
                c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                          ('email', key, ','.join(val) if isinstance(val, list) else str(val), 'dev'))
            elif key != 'night_block':
                c.execute("INSERT OR REPLACE INTO config (category, key, value, env) VALUES (?,?,?,?)",
                          ('email', key, str(val), 'dev'))

        conn.commit()
        conn.close()
        _cache.clear()
        return count
    except Exception:
        return 0


# 单元测试
if __name__ == '__main__':
    e = CURRENT_ENV
    print(f'=== db_config 自检 (env={e}) ===')
    ecfg = get_email_config()
    print(f'smtp_host:    {ecfg["smtp_host"]}')
    print(f'sender:       {ecfg["sender"]}')
    print(f'recipients:   {", ".join(ecfg["recipients"])}')

    ecfg_b = get_email_config(category='email_b')
    print(f'B组 sender:   {ecfg_b["sender"]}')
    print(f'B组 收件人:   {", ".join(ecfg_b["recipients"])}')

    print(f'active_ver:   {get_config("strategy", "active_version")}')
    print(f'')
    print(f'=== 开发环境 (env=dev) ===')
    ecfg_dev = get_email_config(env='dev')
    print(f'sender:       {ecfg_dev["sender"]}')
    print(f'recipients:   {", ".join(ecfg_dev["recipients"])}')
    print()
    print(f'✅ db_config 正常工作')
    print(f'📝 邮件配置来源: {"YAML" if os.path.exists(YAML_PATH) else "数据库"}')
