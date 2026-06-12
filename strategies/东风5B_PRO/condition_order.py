#!/usr/bin/env python3
"""条件单策略 — 50天收益对比 & 不败方案"""
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
        if r: days.append({'day':j, 'o':r[0], 'c':r[1], 'h':r[2], 'l':r[3]})
    return days

def run(name, fn):
    total = 0.0; min_pnl = 0.0
    for n, code, buy, entry in signals:
        days = get_days(code, buy)
        if not days: continue
        r = fn(entry, days)
        total += r
        min_pnl = min(min_pnl, r)
    return round(total, 1), round(min_pnl, 1)

# ===== 各条件单策略 =====

def cur_rules(e, days):
    """当前规则: +3%回落0.3%卖 / +5%止盈 / -7%止损"""
    peak = e
    for d in days:
        peak = max(peak, d['h'])
        if d['l']/e-1 <= -0.07: return -7.0
        if d['h']/e-1 >= 0.05: return 5.0
        if peak/e-1 >= 0.03 and d['c']/peak-1 <= -0.003:
            return round((d['c']/e-1)*100, 1)
    return round((days[-1]['c']/e-1)*100, 1)

def half5_breakeven(e, days):
    """方案A:+5%卖一半,另一半成本价保本出"""
    half = False
    for d in days:
        if d['l']/e-1 <= -0.07: return -7.0
        if not half and d['h']/e-1 >= 0.05:
            half = True
    if half:
        # 另一半保本出
        last = (days[-1]['c']/e-1)*100
        return 2.5 + min(max(last, 0), 5)
    return round((days[-1]['c']/e-1)*100, 1)

def half5_follow_retrace(e, days):
    """方案B:+5%卖一半,另一半回落0.5%卖(从最高)"""
    half = False; peak = e
    for d in days:
        peak = max(peak, d['h'])
        if d['l']/e-1 <= -0.07: return -7.0
        if not half and d['h']/e-1 >= 0.05:
            half = True
        if half and peak/e-1 >= 0.03 and d['c']/peak-1 <= -0.005:
            return 2.5 + round((d['c']/e-1)*100, 1)
    if half:
        last = (days[-1]['c']/e-1)*100
        return 2.5 + min(max(last, 0), 5)
    return round((days[-1]['c']/e-1)*100, 1)

def pure_retrace_05(e, days):
    """纯回落0.5%:从最高回落0.5%全仓卖"""
    peak = e
    for d in days:
        peak = max(peak, d['h'])
        if d['l']/e-1 <= -0.07: return -7.0
        if peak/e-1 >= 0.03 and d['c']/peak-1 <= -0.005:
            return round((d['c']/e-1)*100, 1)
    return round((days[-1]['c']/e-1)*100, 1)

def step3_5(e, days):
    """+3%卖1/3, +5%卖1/3, 剩1/3收盘卖"""
    s1=False; s2=False
    for d in days:
        if d['l']/e-1 <= -0.07: return -7.0
        hp = (d['h']/e-1)*100
        if not s1 and hp >= 3: s1=True
        if not s2 and hp >= 5: s2=True
    last = (days[-1]['c']/e-1)*100
    r = 0
    if s1: r += 1.0
    if s2: r += 1.67
    remaining = 3 - (1 if s1 else 0) - (1 if s2 else 0)
    if remaining > 0:
        r += last * remaining / 3
    return round(r, 1)

def hold3_close(e, days):
    """持有3天收盘卖"""
    if len(days) >= 3:
        return round((days[2]['c']/e-1)*100, 1)
    return round((days[-1]['c']/e-1)*100, 1)

strategies = [
    ('当前规则(+3%回落)', cur_rules),
    ('方案A:+5%半仓+保本', half5_breakeven),
    ('方案B:+5%半仓+回落跟高', half5_follow_retrace),
    ('方案C:纯回落0.5%卖', pure_retrace_05),
    ('方案D:阶梯+3%/+5%分仓', step3_5),
    ('方案E:持有3天收盘卖', hold3_close),
]

print(f'\n{"条件单策略(不用盯盘)":<30} {"50天收益":>8} {"均/笔":>8} {"最差单笔":>8}')
print('-'*60)
for name, fn in strategies:
    total, worst = run(name, fn)
    avg = round(total/len(signals), 2)
    print(f'{name:<30} {total:>+7.1f}% {avg:>+7.2f}% {worst:>+7.1f}%')

print()
print('='*60)
print('推荐实操：方案A — +5%卖一半 + 另一半成本价保本')
print('='*60)
print()
print('条件单设置（买入后一次性设好，不需要盯盘）：')
print()
print('条件单① 止盈单:')
print('  触发: 股价 ≥ 买入价 × 1.05')
print('  动作: 卖出50%仓位')
print('  (到+5%自动卖一半，锁定+2.5%利润)')
print()
print('条件单② 保本单:')
print('  触发: 股价 ≤ 买入价 × 0.995')
print('  动作: 卖出剩余仓位')
print('  (另一半不亏钱出，已赚的2.5%不吐回去)')
print()
print('条件单③ 止损单:')
print('  触发: 股价 ≤ 买入价 × 0.93')  
print('  动作: 卖出全部仓位')
print('  (-7%硬止损，防极端情况)')
print()
print('时间条件单④ 收盘清:')
print('  触发: 14:55')
print('  动作: 卖出全部剩余仓位')
print('  (收盘前必清，不过夜)')

# 明细
print()
print('方案A逐笔明细:')
print(f'{"日期":>12} {"名称":>10} {"入场":>7} {"D+1高":>7} {"D+2高":>7} {"D+3高":>7} {"结果":>8}')
print('-'*60)
for n,code,buy,entry in signals:
    days=get_days(code,buy)
    if not days: continue
    r=half5_breakeven(entry,days)
    d1h=round((days[0]['h']/entry-1)*100,1) if len(days)>=1 else 0
    d2h=round((days[1]['h']/entry-1)*100,1) if len(days)>=2 else 0
    d3h=round((days[2]['h']/entry-1)*100,1) if len(days)>=3 else 0
    m='✅' if r>0 else '❌'
    print(f'{buy:>12} {n:>10} {entry:>7.2f} {d1h:>+6.1f}% {d2h:>+6.1f}% {d3h:>+6.1f}% {r:>+6.1f}% {m}')

conn.close()
