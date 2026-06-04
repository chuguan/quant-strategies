#!/usr/bin/env python3
"""回望卖出 -1% vs -2% vs -3% 完整对比"""
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
        'name': t['name'], 'date': t['date']
    })

def run_trail(trail_pct, activate=3.0):
    c = 30000
    details = []
    for d in data:
        b3 = max(d['d1h'], d['d2h'], d['d3h'], 0)
        sl = d['nl'] <= -7.0
        
        if b3 >= activate:
            ret = b3 - trail_pct
        elif sl:
            ret = max(-7.0, d['nl'])
        else:
            ret = b3
        
        old = c
        c *= (1 + ret/100)
        details.append({'ret': ret, 'balance': c, 'profit': c-old,
                       'name': d['name'], 'date': d['date'], 'd1h': d['d1h'],
                       'd2h': d['d2h'], 'd3h': d['d3h'], 'b3': b3})
    return c, details

print('=' * 90)
print('回望卖出对比: -1% vs -2% vs -3% (均激活+3%)')
print('本金: 3万 | 梭哈 | 30天')
print('=' * 90)

results = {}
for trail in [1, 2, 3]:
    final, details = run_trail(float(trail))
    total_profit = final - 30000
    wins = sum(1 for d in details if d['ret'] >= 2.5)
    loses = sum(1 for d in details if d['ret'] < 0)
    zero = sum(1 for d in details if 0 <= d['ret'] < 2.5)
    avg_ret = sum(d['ret'] for d in details) / len(details)
    results[trail] = {
        'final': final, 'profit': total_profit, 'pct': (final/30000-1)*100,
        'wins': wins, 'loses': loses, 'zero': zero, 'avg': avg_ret,
        'details': details
    }
    print(f'\n== 回望-{trail}% ==')
    print(f'  最终: {final:>8,.0f}元 | 盈利: +{total_profit:>6,.0f}元 (+{(final/30000-1)*100:>5.1f}%)')
    print(f'  胜:{wins}笔 | 亏:{loses}笔 | 保本:{zero}笔 | 均:+{avg_ret:.1f}%')

# 逐日对比
print(f'\n{"="*90}')
print(f'逐日对比')
print(f'{"="*90}')
print(f'{"天":>3} {"日期":>12} {"票":>8} {"D+1高":>7} {"-1%":>8} {"-2%":>8} {"-3%":>8}  {"最高":>6}')
print(f'{"-"*65}')
for i in range(30):
    d1 = results[1]['details'][i]
    d2 = results[2]['details'][i]
    d3 = results[3]['details'][i]
    print(f'{i+1:>3} {d1["date"]:>12} {d1["name"]:>8} {d1["d1h"]:>+5.1f}% {d1["ret"]:>+5.1f}% {d2["ret"]:>+5.1f}% {d3["ret"]:>+5.1f}%  {d1["b3"]:>+4.1f}%')

# 利润差异
print(f'\n{"="*90}')
print(f'总利润对比')
print(f'{"="*90}')
for trail in [1, 2, 3]:
    r = results[trail]
    diff1 = r['profit'] - results[1]['profit']
    print(f'回望-{trail}%: 总利润+{r["profit"]:>6,.0f}元'
          + (f'  ← 最多赚' if trail == 1 else f'  (比-1%少赚{abs(diff1):>6,.0f}元, 少{abs(diff1)/results[1]["profit"]*100:.1f}%)'))

# 利润分布
print(f'\n{"="*90}')
print(f'每笔利润分布')
print(f'{"="*90}')
for trail in [1, 2, 3]:
    d = results[trail]['details']
    gt5 = sum(1 for x in d if x['ret'] >= 5)
    b3_5 = sum(1 for x in d if 3 <= x['ret'] < 5)
    b2_3 = sum(1 for x in d if 2 <= x['ret'] < 3)
    b0_2 = sum(1 for x in d if 0 < x['ret'] < 2)
    zero_loss = sum(1 for x in d if x['ret'] <= 0)
    print(f'回望-{trail}%: +5%>{gt5:>2d} | +3~5%>{b3_5:>2d} | +2~3%>{b2_3:>2d} | 0~2%>{b0_2:>2d} | 亏{zero_loss:>2d}')

# 差异最大的日子
print(f'\n{"="*90}')
print(f'-1% vs -2%差异最大的日子')
print(f'{"="*90}')
diffs = []
for i in range(30):
    d1 = results[1]['details'][i]
    d2 = results[2]['details'][i]
    diff = d1['ret'] - d2['ret']
    diffs.append((abs(diff), i, d1, d2, '-2%'))
diffs.sort(key=lambda x: -x[0])
for _, i, d1, d2, label in diffs[:5]:
    diff = d1['ret'] - d2['ret']
    print(f'{d1["date"]} {d1["name"]:>8} D+1高{d1["d1h"]:+.1f}% 3日最高{d1["b3"]:+.1f}%')
    print(f'  -1%: +{d1["ret"]:.1f}% | -2%: +{d2["ret"]:.1f}% | 差异:{diff:+.1f}% (={abs(diff)/100*30000:,.0f}元)')

print(f'\n{"="*90}')
print(f'-1% vs -3%差异最大的日子')
print(f'{"="*90}')
diffs2 = []
for i in range(30):
    d1 = results[1]['details'][i]
    d3 = results[3]['details'][i]
    diff = d1['ret'] - d3['ret']
    diffs2.append((abs(diff), i, d1, d3))
diffs2.sort(key=lambda x: -x[0])
for _, i, d1, d3 in diffs2[:5]:
    diff = d1['ret'] - d3['ret']
    print(f'{d1["date"]} {d1["name"]:>8} D+1高{d1["d1h"]:+.1f}% 3日最高{d1["b3"]:+.1f}%')
    print(f'  -1%: +{d1["ret"]:.1f}% | -3%: +{d3["ret"]:.1f}% | 差异:{diff:+.1f}% (={abs(diff)/100*30000:,.0f}元)')

# 总结
print(f'\n{"="*90}')
print(f'最终结论')
print(f'{"="*90}')
print(f'')
print(f'回望-1%: 3万->{results[1]["final"]:>8,.0f} (+{results[1]["pct"]:.1f}%)  吃最满,但盘中震荡可能误触发')
print(f'回望-2%: 3万->{results[2]["final"]:>8,.0f} (+{results[2]["pct"]:.1f}%)  少赚{results[1]["profit"]-results[2]["profit"]:,}元,但更抗震荡')
print(f'回望-3%: 3万->{results[3]["final"]:>8,.0f} (+{results[3]["pct"]:.1f}%)  少赚{results[1]["profit"]-results[3]["profit"]:,}元,最稳妥')
print(f'')
print(f'-1%只比-2%多赚{results[1]["profit"]-results[2]["profit"]:,}元 ({(results[1]["profit"]-results[2]["profit"])/results[2]["profit"]*100:.1f}%)')
print(f'-2%比-3%多赚{results[2]["profit"]-results[3]["profit"]:,}元 ({(results[2]["profit"]-results[3]["profit"])/results[3]["profit"]*100:.1f}%)')
print(f'')
print(f'推荐: -2%回落, 平衡收益与抗震荡')
