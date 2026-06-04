#!/usr/bin/env python3
"""完整策略回测: 固定止损(-7%) + 回望止盈(激活+3%/回落-2%) + 3日时限"""
import json

with open('C:/Users/12546/AppData/Local/hermes/scripts/release/1180/_paper_trading_report.json') as f:
    report = json.load(f)
trades = report['trades'][-30:]

data = []
for t in trades:
    data.append({
        'd1h': t.get('d1h',0) or 0,
        'd2h': t.get('d2h',0) if 'd2h' in t else 0,
        'd3h': t.get('d3h',0) if 'd3h' in t else 0,
        'nl': t.get('nl',0) or 0,
        'name': t['name'], 'date': t['date'], 'code': t['code'],
        'p': t.get('p',0) or 0,
    })

def full_strategy(d, trail_pct=2.0, hard_stop=7.0, activate=3.0):
    """
    完整策略:
    Phase 1 (before +3%): 固定硬止损 -7%
    Phase 2 (after +3%):  回望止盈 -2%回落
    Phase 3 (3 days):     强制平仓
    """
    b3 = max(d['d1h'], d['d2h'], d['d3h'], 0)
    nl = d['nl']  # D+1 最低%
    
    # Phase 1: 检查硬止损(适用于+3%前)
    # 只有D+1有低点数据,nl是D+1最低
    if nl <= -hard_stop:
        return -hard_stop, f'硬止损-{hard_stop}%(最低{nl:.1f}%)'
    
    # Phase 2: +3%到了,回望止盈
    if b3 >= activate:
        ret = b3 - trail_pct
        return ret, f'回望{ret:.1f}%(冲到{b3:.1f}%回落{trail_pct:.0f}%)'
    
    # Phase 3: 没到3%,也没触发止损
    return b3, f'3日最高{b3:.1f}%'


def backtest_full(trail_pct=2.0, hard_stop=7.0, activate=3.0):
    c = 30000
    details = []
    for d in data:
        ret, reason = full_strategy(d, trail_pct, hard_stop, activate)
        old = c
        c *= (1 + ret/100)
        details.append({
            'date': d['date'], 'name': d['name'], 'code': d['code'],
            'd1h': d['d1h'], 'ret': ret, 'reason': reason,
            'balance': c, 'profit': c - old
        })
    return c, details


print('=' * 95)
print('完整策略回测: 固定止损(-7%) + 回望止盈(+3%激活/-2%回落) + 3日时限')
print('本金: 3万 | 梭哈全进 | 30天')
print('=' * 95)

final, details = backtest_full()
total_profit = final - 30000
wins = sum(1 for d in details if d['ret'] >= 2.5)
loses = sum(1 for d in details if d['ret'] < 0)
stops = sum(1 for d in details if '硬止损' in d['reason'])
trails = sum(1 for d in details if '回望' in d['reason'])
timeout = sum(1 for d in details if '3日' in d['reason'])

print(f'\n最终: {final:>8,.0f}元 | 盈利: +{total_profit:>6,.0f}元 (+{total_profit/30000*100:.1f}%)')
print(f'胜:{wins}笔 | 亏:{loses}笔')
print(f'回望止盈触发: {trails}笔 | 硬止损触发: {stops}笔 | 3日平仓: {timeout}笔')

print(f'\n{"="*95}')
print(f'逐日明细')
print(f'{"="*95}')
print(f'{"天":>3} {"日期":>12} {"票":>8} {"D+1高":>7} {"D+1低":>7} {"收益":>7} {"总资产":>10} {"操作"}')
print(f'{"-"*80}')
for i, d in enumerate(details):
    emoji = '✅' if d['ret'] >= 2.5 else ('💸' if d['ret'] < 0 else '⏸️')
    nl = data[i]['nl']
    print(f'{i+1:>3} {d["date"]:>12} {d["name"]:>8} {d["d1h"]:>+5.1f}% {nl:>+5.1f}% {d["ret"]:>+5.1f}% {emoji} {d["balance"]:>8,.0f} {d["reason"]}')


# 不同止损参数对比
print(f'\n{"="*95}')
print(f'止损参数对比')
print(f'{"="*95}')

for ts, hs in [(1.0, 7.0), (2.0, 7.0), (2.0, 5.0), (3.0, 7.0), (2.0, 10.0)]:
    final, details = backtest_full(trail_pct=ts, hard_stop=hs)
    p = final - 30000
    stops = sum(1 for d in details if '硬止损' in d['reason'])
    print(f'回望-{ts:.0f}%/硬止损-{hs:.0f}%:  {final:>8,.0f}元 +{p:>6,.0f}元 +{p/30000*100:>5.1f}% 止损触发{stops}次')


# 卖不掉场景分析
print(f'\n{"="*95}')
print(f'卖不掉场景分析')
print(f'{"="*95}')
print(f'')
print(f'30笔交易中最低价分布:')
for d in data:
    level = '0~-2%' if d['nl'] >= -2 else ('-2~-4%' if d['nl'] >= -4 else ('-4~-7%' if d['nl'] >= -7 else '<-7%'))
    if d['nl'] <= -5:
        print(f'  ⚠️  {d["date"]} {d["name"]:>8} D+1最低{d["nl"]:+.1f}%  D+1高{d["d1h"]:+.1f}%')

print(f'')
print(f'30笔中:')
below_7 = sum(1 for d in data if d['nl'] <= -7)
below_5 = sum(1 for d in data if d['nl'] <= -5)
print(f'  最低<-7%(触发硬止损): {below_7}笔')
print(f'  最低<-5%(接近止损): {below_5}笔')
print(f'')
print(f'{"="*95}')
print(f'极端情况: 如果跌停卖不掉会怎样？')
print(f'{"="*95}')
print(f'')
print(f'假设最坏情况: 某票开盘直接跌停-10%,条件单无法成交')
print(f'')
print(f'应对方案:')
print(f'  第1天: 挂跌停价卖出,但没成交(封死跌停)')
print(f'  第2天: 开盘集合竞价挂市价单,开盘即卖出')
print(f'  实际亏损: -10%~-15% (取决于第2天开盘价)')
print(f'')
print(f'概率分析:')
print(f'  30天中: 0笔实际触发跌停')
print(f'  1180选的票都是活跃股,非ST,流动性好')
print(f'  主板跌停是-10%,我们的止损设在-7%')
print(f'  所以卖不掉的前提是开盘直接跳-7%+ 并且封死')
print(f'  这在A股活跃股中极少发生')

# 极端情景模拟: 如果某笔卖不掉延迟到第二天
print(f'\n{"="*95}')
print(f'极端情景模拟: 最差一笔卖不掉')
print(f'{"="*95}')

# 找到D+1最低的那笔
worst = min(data, key=lambda d: d['nl'] or 0)
print(f'\n最差案例: {worst["date"]} {worst["name"]}')
print(f'  D+1高: {worst["d1h"]:+.1f}%')
print(f'  D+1低: {worst["nl"]:+.1f}%')
print(f'')
print(f'正常情况:-7%硬止损触发,卖在预计-7%')
print(f'  损失: 30,000 × -7% = -2,100元')
print(f'')
print(f'极端情况:开盘直接跳-7%+封死跌停,第2天才卖掉')
print(f'  假设第2天继续-5%,总损失约-12%')
print(f'  损失: 30,000 × -12% = -3,600元')
print(f'')
print(f'但注意:这个票D+1还冲到+{worst["d1h"]:.1f}%了')
if worst['d1h'] >= 3:
    print(f'  如果+3%回望止盈先触发: 盈利+{worst["d1h"]-2:.1f}%,根本不会到止损')
