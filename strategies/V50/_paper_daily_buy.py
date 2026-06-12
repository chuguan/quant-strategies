#!/usr/bin/env python3
"""V50 模拟盘每日买入 — 13:10执行，从DB读取最新冠军买入"""
import sys, os, sqlite3
from datetime import datetime
DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)
from _paper_core import add_position, get_account_summary

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/prod')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

today = datetime.now().strftime('%Y-%m-%d')
weekday = datetime.now().weekday()
if weekday >= 5:
    print(f'📅 {today} 周末，跳过买入')
    sys.exit(0)

try:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.execute(
        "SELECT code, name, price, market_type FROM selection_candidates "
        "WHERE version='V50' AND rank=1 ORDER BY run_time DESC LIMIT 1",
    )
    row = cur.fetchone()
    conn.close()
except Exception as e:
    print(f'❌ DB读取失败: {e}')
    sys.exit(1)

if not row:
    print(f'⚠️ V50 {today} 无选股记录，跳过买入')
    sys.exit(0)

code, name, price, market_type = row
if not price or price <= 0:
    print(f'⚠️ V50 冠军{name}({code}) 价格无效: {price}')
    sys.exit(0)

ret = add_position(code, name, price, market_type=market_type or '')
if ret:
    acct, mv, ta = get_account_summary()
    print(f'✅ V50 模拟买入成功: {name}({code}) {ret["shares"]}股@{price:.2f}')
    print(f'💰 账户: 总资产{ta:.0f} 现金{acct["available_cash"]:.0f} 市值{mv:.0f}')
else:
    print(f'❌ V50 买入失败')
