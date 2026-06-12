#!/usr/bin/env python3
"""利润最大化策略对比"""
import sqlite3, os

DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(DIR, '..', '东风5A', 'df04_prices.db')
conn = sqlite3.connect(DB)
cur = conn.cursor()

signals = [
    ('国城矿业','000688','2026-03-25',37.70),
    ('鹭燕医药','002788','2026-04-01',16.70),
    ('三孚股份','603938','2026-04-02',25.15),
    ('三孚股份','603938','2026-04-03',25.89),
    ('利通电子','603629','2026-04-09',74.62),
    ('云中马','603130','2026-04-21',45.40),
    ('万通发展','600246','2026-05-07',12.26),
    ('南兴股份','002757','2026-05-08',29.02),
    ('风华高科','000636','2026-05-20',34.00),
    ('雄韬股份','002733','2026-05-25',29.32),
    ('华控赛格','000068','2026-06-02',3.25),
    ('横店东磁','002056','2026-06-03',27.50),
    ('立昂微','605358','2026-06-05',66.77),
    ('远东股份','600869','2026-06-09',29.62),
]

def get_days(code, buy_date):
    cur.execute('SELECT date FROM daily_prices WHERE date>=? GROUP BY date ORDER BY date', (buy_date,))
    all_d = [r[0] for r in cur.fetchall()]
    if buy_date not in all_d: return []
    di = all_d.index(buy_date)
    days = []
    for j in range(1, min(4, len(all_d)-di)):
        d = all_d[di+j]
        cur.execute('SELECT open,close,high,low FROM daily_prices WHERE code=? AND date=?', (code, d))
        r = cur.fetchone()
        if r: days.append({'day':j,'o':r[0],'c':r[1],'h':r[2],'l':r[3]})
    return days

def run(name, fn):
    total = 0.0
    for n, code, buy_date, entry in signals:
        days = get_days(code, buy_date)
        if not days: continue
        total += fn(entry, days)
    return round(total, 1)

# 策略定义
r_current = lambda e, d: (
    -7.0 if any((x['l']/e-1)*100<=-7 for x in d) else
    5.0 if any((x['h']/e-1)*100>=5 for x in d) else
    round(([x for x in d if (x['h']/e-1)*100>=3 and x['c']/x['h']-1<=-0.003] or [d[-1]])[-1]['c']/e*100-100, 1) if any((x['h']/e-1)*100>=3 and x['c']/x['h']-1<=-0.003 for x in d) else
    round((d[-1]['c']/e-1)*100, 1)
)

r_d3close = lambda e, d: round((d[min(2,len(d)-1)]['c']/e-1)*100, 1)
r_d1close = lambda e, d: round((d[0]['c']/e-1)*100, 1)
r_half = lambda e, d: (
    -7.0 if any((x['l']/e-1)*100<=-7 for x in d) else
    2.5 + min(max((d[-1]['c']/e-1)*100, -7), 10)/2 if any((x['h']/e-1)*100>=5 for x in d) else
    round((d[-1]['c']/e-1)*100, 1)
)
r_half_follow = lambda e, d: (
    -7.0 if any((x['l']/e-1)*100<=-7 for x in d) else
    (lambda sold, pnl: pnl + (
        min(max(round((max(xx['c'] for xx in d)/e-1)*100, 1), -0.5), 5)
    ) if sold else round((d[-1]['c']/e-1)*100, 1)
    )(
        any((x['h']/e-1)*100>=5 for x in d),
        2.5 if any((x['h']/e-1)*100>=5 for x in d) else 0
    )
)

# 简单写更清晰的版本
def half5_follow(entry, days):
    half_sold = False
    for day in days:
        hp = (day['h']/entry-1)*100
        lp = (day['l']/entry-1)*100
        if lp <= -7: return -7.0
        if not half_sold and hp >= 5:
            half_sold = True
    if half_sold:
        last_hp = max(d['h'] for d in days)
        last = (last_hp/entry-1)*100
        return 2.5 + min(max(last-2.5, -0.5), 10)
    return round((days[-1]['c']/entry-1)*100, 1)

def max3(entry, days):
    mx = entry
    for d in days:
        mx = max(mx, d['h'])
    return round((mx/entry-1)*100, 1)

strategies = {
    '① 当前规则 +5%止盈': r_current,
    '② 次日收盘卖': r_d1close,
    '③ 持有3天收盘卖': r_d3close,
    '④ +5%半仓+另一半收盘': r_half,
    '⑤ +5%半仓+另一半跟高': half5_follow,
}

print(f'\n{"策略":<30} {"50天总收益":>10} {"均/笔":>8}')
print('-'*50)
for name, fn in strategies.items():
    r = run(name, fn)
    avg = round(r/len(signals), 2)
    print(f'{name:<30} {r:>+8.1f}% {avg:>+7.2f}%')

# 3日最高理论
r_max = run('3日最高(理论)', max3)
print(f'⑥ 3日最高(理论天花板)   {r_max:>+8.1f}% {round(r_max/len(signals),2):>+7.2f}%')

conn.close()
