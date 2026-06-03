#!/usr/bin/env python
"""
统一配置读取模块 — 所有脚本从这里读配置，不改代码
支持 production / dev 环境隔离

用法：
    from db_config import get_config, get_config_int, get_config_list

    smtp_host = get_config('email', 'smtp_host')
    recipients = get_config_list('email', 'recipients')
    token = get_config('api', 'tushare_token', env='dev')
"""
import sqlite3, os, sys

DB_PATH = os.path.expanduser('~/AppData/Local/hermes/scripts/v13_quant.db')

# 当前环境：优先从环境变量读，默认 production
CURRENT_ENV = os.environ.get('HERMES_ENV', 'production')

_cache = {}  # 内存缓存，避免每次查询都读数据库

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
        # 先查指定环境，没有再 fallback 到 production
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

def get_email_config(env=None, category='email'):
    """快捷获取邮件配置
    category: 'email'=A配置, 'email_b'=B配置
    """
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
            os.path.expanduser('~/AppData/Local/hermes/scripts'), env),
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

# 单元测试
if __name__ == '__main__':
    e = CURRENT_ENV
    print(f'=== db_config 自检 (env={e}) ===')
    print(f'smtp_host:    {get_config("email", "smtp_host")}')
    print(f'sender:       {get_config("email", "sender")}')
    print(f'recipients:   {get_config_list("email", "recipients")}')
    print(f'active_ver:   {get_config("strategy", "active_version")}')
    print(f'')
    print(f'=== 开发环境 (env=dev) ===')
    print(f'sender:       {get_config("email", "sender", env="dev")}')
    print(f'active_ver:   {get_config("strategy", "active_version", env="dev")}')
    print(f'backtest_days:{get_config_int("strategy", "backtest_dates", env="dev")}')
    print(f'✅ db_config 正常工作')
