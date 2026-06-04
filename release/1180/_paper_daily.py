#!/usr/bin/env python3
"""
1180 模拟盘日结 — 15:05运行，输出当日交易总结
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paper_core import load_positions, load_log, generate_html
from datetime import datetime, timedelta

today = datetime.now().strftime('%Y-%m-%d')
weekday = datetime.now().weekday()

if weekday >= 5:
    sys.exit(0)

log = load_log()
positions = load_positions()

# 当日交易
today_trades = [t for t in log if t['sell_date'] == today]
today_buys = [p for p in positions if p['buy_date'] == today and p['status'] == '持有']
today_sold = [p for p in positions if p['sell_date'] == today]

# 更新看板
path = generate_html()

print(f'📊 1180 模拟盘日结 {today}')
print(f'{"="*40}')

if today_buys:
    for p in today_buys:
        print(f'')
        print(f'💰 今日买入: {p["name"]}({p["code"]})')
        print(f'  买入价: {p["buy_price"]:.2f}元')
        print(f'  回望: +3%激活 回落{p.get("trailing_drop",0.3)}%卖')
        print(f'  收盘未触发: 清仓')
        print(f'  持仓: 3万股 市值{p["buy_price"]*30000/10000:.1f}万')

if today_sold:
    for p in today_sold:
        emoji = '✅' if p['return_pct'] >= 2.5 else ('🛑' if p['return_pct'] < -2 else '⏸️')
        print(f'')
        print(f'{emoji} 今日卖出: {p["name"]}({p["code"]})')
        print(f'  买入: {p["buy_price"]:.2f} → 卖出: {p["sell_price"]:.2f}')
        print(f'  收益: {p["return_pct"]:+.1f}%')
        print(f'  总盈亏: {p["return_pct"]/100*30000:+,.0f}元')

# 汇总
active = [p for p in positions if p['status'] == '持有']
buy_today = [p for p in active if p['buy_date'] == today]
holding = [p for p in active if p['buy_date'] != today]

print(f'')
print(f'{"="*40}')
print(f'📊 当前持仓: {len(active)}只')

if buy_today:
    total_cost = sum(p['buy_price'] * 30000 / p['buy_price'] for p in buy_today)
    print(f'  今日买入: {len(buy_today)}只')
    for p in buy_today:
        days = (datetime.now() - datetime.strptime(p['buy_date'], '%Y-%m-%d')).days
        print(f'    {p["name"]}({p["code"]}) 买入{p["buy_price"]:.2f} 目标{p["target_price"]:.2f} 止损{p["stop_price"]:.2f} D{days}')

if holding:
    print(f'  持有中(过夜): {len(holding)}只')
    for p in holding:
        days = (datetime.now() - datetime.strptime(p['buy_date'], '%Y-%m-%d')).days
        print(f'    {p["name"]}({p["code"]}) 买入{p["buy_price"]:.2f} 目标{p["target_price"]:.2f} D{days}')

# 累计统计
total_trades = len(log)
wins = len([t for t in log if t['return_pct'] >= 2.5])
total_pnl = sum(t['return_pct']/100 * 30000 for t in log)

print(f'')
print(f'{"="*40}')
print(f'📈 累计统计')
print(f'  总交易: {total_trades}笔')
print(f'  +5%止盈: {wins}笔')
print(f'  总盈亏: {total_pnl:+,.0f}元')
print(f'  看板: {path}')
