#!/usr/bin/env python3
"""
1180 盘中监控 — cron每5分钟执行一次
读取持仓 → 拉实时价 → 检查止盈/止损 → 输出信号
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paper_core import check_positions, generate_html, get_summary, load_positions
from datetime import datetime

now = datetime.now()
today = now.strftime('%Y-%m-%d')
weekday = now.weekday()

# 非交易日跳过
if weekday >= 5:
    print('非交易日，跳过')
    sys.exit(0)

# 非交易时间跳过
hour, minute = now.hour, now.minute
trading_min = hour * 60 + minute
# 9:30~11:30, 13:00~15:00
if not ((9*60+30 <= trading_min <= 11*60+30) or (13*60+0 <= trading_min <= 15*60+0)):
    sys.exit(0)

# 检查持仓
signals = check_positions()

# 输出信号（cron会把这些输出作为通知发出去）
if signals:
    print(f'⏰ {today} {now.strftime("%H:%M")}')
    for sig_type, pos in signals:
        if sig_type == '止盈':
            profit = round(pos['sell_price'] - pos['buy_price'], 2)
            ret = pos['return_pct']
            print(f'')
            print(f'💰 回望止盈触发！')
            print(f'  {pos["name"]}({pos["code"]})')
            print(f'  买入: {pos["buy_price"]:.2f} → 卖出: {pos["sell_price"]:.2f}')
            print(f'  收益: +{ret:.1f}% (+{profit:.2f}元/股)')
            print(f'  操作: 从最高点回落{pos.get("trailing_drop",0.3)}%触发')
        elif sig_type == '止损':
            loss = round(pos['buy_price'] - pos['sell_price'], 2)
            print(f'')
            print(f'🛑 -3%止损触发！')
            print(f'  {pos["name"]}({pos["code"]})')
            print(f'  买入: {pos["buy_price"]:.2f} → 卖出: {pos["sell_price"]:.2f}')
            print(f'  亏损: {pos["return_pct"]:.1f}% (-{loss:.2f}元/股)')
        elif sig_type == '回望激活':
            print(f'')
            print(f'📈 回望已激活！(+3%到达)')
            print(f'  {pos["name"]}({pos["code"]}) 当前价: {pos["price"]:.2f}' 
                  if 'price' in pos else f'  {pos["name"]}({pos["code"]})')
            print(f'  从当前价回落0.3%即卖出')
        elif sig_type == '收盘清仓':
            ret = pos['return_pct']
            emoji = '✅' if ret >= 0 else '💸'
            print(f'')
            print(f'{emoji} 收盘清仓')
            print(f'  {pos["name"]}({pos["code"]})')
            print(f'  买入: {pos["buy_price"]:.2f} → 卖出: {pos["sell_price"]:.2f}')
            print(f'  收益: {ret:+.1f}%')
        elif sig_type == '3天平仓':
            print(f'')
            print(f'⏰ 3天平仓（未达目标）')
            print(f'  {pos["name"]}({pos["code"]})')
            print(f'  买入: {pos["buy_price"]:.2f} → 卖出: {pos["sell_price"]:.2f}')
            print(f'  收益: {pos["return_pct"]:+.1f}%')

# 输出当前持仓状态
positions = load_positions()
active = [p for p in positions if p['status'] == '持有']
if active:
    today_active = [p for p in active if p['buy_date'] == today]
    old_active = [p for p in active if p['buy_date'] != today]
    
    if old_active:
        print(f'\n📡 持仓监控中:')
        for p in old_active:
            hold_days = (now - datetime.strptime(p['buy_date'], '%Y-%m-%d')).days
            print(f'  {p["name"]}({p["code"]}) 买入{p["buy_price"]:.2f} 目标{p["target_price"]:.2f} 止损{p["stop_price"]:.2f} 持有{hold_days}天')

# 生成看板
path = generate_html()
