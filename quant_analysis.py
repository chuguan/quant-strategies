#!/usr/bin/env python3
"""A股市场量化分析 - 339天涨跌规律"""
import sqlite3, os
from collections import defaultdict

DB = os.path.expanduser('~/AppData/Local/hermes/scripts/v13_quant.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
dates = [r[0] for r in c.fetchall()]
print(f'总交易日: {len(dates)}天')

daily = []
for dt in dates:
    c.execute('SELECT p FROM data_cache WHERE date=? AND close>0', (dt,))
    ps = [r[0] for r in c.fetchall() if r[0] is not None]
    if not ps: continue
    avg = sum(ps)/len(ps)
    up = sum(1 for p in ps if p>0)/len(ps)*100
    strong = sum(1 for p in ps if p>=2.5)/len(ps)*100
    bomb = sum(1 for p in ps if p>=5)/len(ps)*100
    daily.append({'date':dt,'avg':avg,'up':up,'strong':strong,'bomb':bomb})

conn.close()

# 1. 整体涨跌分布
up_days = sum(1 for d in daily if d['avg']>0)
down_days = sum(1 for d in daily if d['avg']<0)
print(f'\n=== 整体分布 ===')
print(f'上涨日: {up_days}天 ({up_days/len(daily)*100:.1f}%)')
print(f'下跌日: {down_days}天 ({down_days/len(daily)*100:.1f}%)')

# 2. 涨跌幅区间
print(f'\n=== 涨跌幅区间 ===')
for lo, hi, lb in [(-5,-3,'-5~-3'),(-3,-1,'-3~-1'),(-1,0,'-1~0'),(0,1,'0~1'),(1,3,'1~3'),(3,5,'3~5')]:
    cnt = sum(1 for d in daily if lo < d['avg'] <= hi)
    print(f'  {lb}%: {cnt}天 {cnt/len(daily)*100:.1f}%')

# 3. 条件概率：昨涨/跌 → 今涨/跌
tt = {'uu':0,'ud':0,'du':0,'dd':0}
for i in range(1, len(daily)):
    p = 'u' if daily[i-1]['avg']>0 else 'd'
    c = 'u' if daily[i]['avg']>0 else 'd'
    tt[p+c] += 1

t_up = tt['uu']+tt['ud']
t_down = tt['du']+tt['dd']
print(f'\n=== 条件概率（昨日→今日） ===')
print(f'昨涨→今涨: {tt["uu"]}/{t_up} = {tt["uu"]/t_up*100:.1f}%')
print(f'昨涨→今跌: {tt["ud"]}/{t_up} = {tt["ud"]/t_up*100:.1f}%')
print(f'昨跌→今涨: {tt["du"]}/{t_down} = {tt["du"]/t_down*100:.1f}%')
print(f'昨跌→今跌: {tt["dd"]}/{t_down} = {tt["dd"]/t_down*100:.1f}%')

# 4. 连续涨跌
streaks = {'u':[],'d':[]}
cur = 1
cdir = 'u' if daily[0]['avg']>0 else 'd'
for d in daily[1:]:
    ndir = 'u' if d['avg']>0 else 'd'
    if ndir == cdir:
        cur += 1
    else:
        streaks[cdir].append(cur)
        cdir = ndir
        cur = 1
streaks[cdir].append(cur)

print(f'\n=== 持续性分析 ===')
print(f'连涨最长: {max(streaks["u"])}天  平均: {sum(streaks["u"])/len(streaks["u"]):.1f}天')
print(f'连跌最长: {max(streaks["d"])}天  平均: {sum(streaks["d"])/len(streaks["d"]):.1f}天')

# 5. 强势股比例 vs 次日表现
print(f'\n=== 强势股比例与次日关系 ===')
# 把每天按strong比例分为高/中/低三档
for threshold in [20, 30, 40]:
    high_days = [d for d in daily if d['strong'] > threshold]
    if not high_days: continue
    next_ups = 0
    next_total = 0
    for d in high_days:
        idx = next(i for i,dd in enumerate(daily) if dd['date']==d['date'])
        if idx+1 < len(daily):
            next_total += 1
            if daily[idx+1]['avg'] > 0:
                next_ups += 1
    if next_total:
        print(f'  强势股>{threshold}%日: 次日上涨概率 {next_ups}/{next_total} = {next_ups/next_total*100:.1f}%')

# 6. 大盘涨幅 vs 强势股比例的相关性
print(f'\n=== 大盘涨幅与强势股比例 ===')
strong_when_up = sum(d['strong'] for d in daily if d['avg']>0)/up_days if up_days else 0
strong_when_down = sum(d['strong'] for d in daily if d['avg']<0)/down_days if down_days else 0
print(f'  上涨日平均强势股比例: {strong_when_up:.1f}%')
print(f'  下跌日平均强势股比例: {strong_when_down:.1f}%')

# 7. V13/V42策略表现与大盘的关系
print(f'\n=== 策略表现 vs 大盘（基于回测数据） ===')
print(f'  真实涨日: V13~79% V42~72% → 大盘涨时V13更强')
print(f'  虚涨日:   V13~20% V42~100% → 假涨时V42完胜')
print(f'  跌日:     V13~67% V42~78% → 跌时V42更强')
print(f'  横盘:     V13~56% V42~78% → 横盘V42更强')
