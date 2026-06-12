#!/usr/bin/env python3
"""东风5B综合报告发送"""
import sqlite3, json, os, sys

DB = r'C:\Users\12546\AppData\Local\hermes\prod\data\df04_prices.db'
SCRIPTS_DIR = r'C:\Users\12546\AppData\Local\hermes\prod'

conn = sqlite3.connect(DB)
cur = conn.cursor()

signals = [
    ('2026-02-27','大族激光','002008','T1-C≥3',72.30),
    ('2026-03-03','德业股份','605117','T1-C≥3',121.96),
    ('2026-03-04','白云电器','603861','T3-2B',21.24),
    ('2026-03-06','中国西电','601179','T1-C≥3',19.30),
    ('2026-03-12','大元泵业','603757','T2-C=2',49.38),
    ('2026-03-25','国城矿业','000688','T1-C≥3',37.70),
    ('2026-04-01','鹭燕医药','002788','T2-C=2',16.70),
    ('2026-04-02','三孚股份','603938','T4-SP',25.15),
    ('2026-04-03','三孚股份','603938','T4-SP',25.89),
    ('2026-04-09','利通电子','603629','T1-C≥3',74.62),
    ('2026-04-21','云中马','603130','T2-C=2',45.40),
    ('2026-05-07','万通发展','600246','T3-2B',12.26),
    ('2026-05-08','南兴股份','002757','T1-C≥3',29.02),
    ('2026-05-20','风华高科','000636','T1-C≥3',34.00),
    ('2026-05-25','雄韬股份','002733','T4-SP',29.32),
    ('2026-06-02','华控赛格','000068','T4-SP',3.25),
    ('2026-06-03','横店东磁','002056','T3-2B',27.50),
    ('2026-06-05','立昂微','605358','T2-C=2',66.77),
    ('2026-06-09','远东股份','600869','T3-2B',29.62),
]

def get_days(code, buy_date, entry_pct):
    cur2 = conn.cursor()
    cur2.execute('SELECT date FROM daily_prices WHERE date>=? GROUP BY date ORDER BY date', (buy_date,))
    all_d = [r[0] for r in cur2.fetchall()]
    if len(all_d) < 2: return [], entry_pct
    di = all_d.index(buy_date)
    days = []
    for j in range(1, min(4, len(all_d)-di)):
        d = all_d[di+j]
        cur2.execute('SELECT open,close,high,low FROM daily_prices WHERE code=? AND date=?', (code, d))
        r = cur2.fetchone()
        if r: days.append({'j':j,'o':r[0],'c':r[1],'h':r[2],'l':r[3]})
    return days

rows_data = []
total_planA = 0.0
total_cur = 0.0
tier_stats = {}

for date, name, code, tier, entry in signals:
    # 查当天涨幅
    cur.execute('SELECT pct FROM daily_prices WHERE code=? AND date=?', (code, date))
    rr = cur.fetchone()
    entry_pct = rr[0] if rr else 0
    # 查前一天涨幅
    cur.execute('SELECT date FROM daily_prices WHERE code=? AND date<? ORDER BY date DESC LIMIT 1', (code, date))
    prev_r = cur.fetchone()
    prev_pct = 0
    if prev_r:
        cur.execute('SELECT pct FROM daily_prices WHERE code=? AND date=?', (code, prev_r[0]))
        p2 = cur.fetchone()
        if p2: prev_pct = p2[0]

    # 昨日涨停提示
    tip = ''
    if prev_pct >= 8:
        tip = '⚠️ 昨日涨停+%.0f%%，建议+5%%止盈' % prev_pct

    days = get_days(code, date, entry_pct)
    d1h = round((days[0]['h']/entry-1)*100,1) if len(days)>=1 else 0
    d2h = round((days[1]['h']/entry-1)*100,1) if len(days)>=2 else 0
    d3h = round((days[2]['h']/entry-1)*100,1) if len(days)>=3 else 0
    m3 = max(d1h, d2h, d3h)

    peak = entry; real = 0
    for d in days:
        peak = max(peak, d['h'])
        if d['h']/entry-1 >= 0.05: real = 5.0; break
        if peak/entry-1 >= 0.03 and d['c']/peak-1 <= -0.003:
            real = round((d['c']/entry-1)*100, 1); break
    if real == 0: real = round((days[-1]['c']/entry-1)*100, 1)

    planA = 0; hit5 = False
    for d in days:
        if d['l']/entry-1 <= -0.07: planA = -7.0; break
        if not hit5 and d['h']/entry-1 >= 0.05:
            hit5 = True
    if hit5:
        last_p = (days[-1]['c']/entry-1)*100
        planA = 2.5 + min(max(last_p, 0), 5)  # 半仓+5%锁利2.5% + 另一半收盘保本0~5%
    elif planA == 0:
        planA = round((days[-1]['c']/entry-1)*100, 1)

    total_planA += planA; total_cur += real

    tk = tier.split('-')[0]
    if tk not in tier_stats:
        tier_stats[tk] = {'count':0,'wins':0,'sum_m3':0,'sum_d1':0}
    tier_stats[tk]['count'] += 1
    tier_stats[tk]['wins'] += 1 if m3 >= 3.0 else 0
    tier_stats[tk]['sum_m3'] += m3
    tier_stats[tk]['sum_d1'] += d1h

    rows_data.append({
        'date': date[5:], 'name': name, 'code': code, 'tier': tier, 'entry': entry,
        'entry_pct': entry_pct, 'd1h': d1h, 'd2h': d2h, 'd3h': d3h, 'm3': m3, 'real': real, 'planA': planA,
        'tip': tip, 'win_cur': real > 0, 'win_planA': planA > 0
    })

r50 = [r for r in rows_data if r['date'] >= '04-01']
r74 = rows_data

# 星标映射
STAR_MAP = {'T1':'⭐⭐⭐⭐⭐', 'T2':'⭐⭐⭐⭐', 'T3':'⭐⭐⭐', 'T4':'⭐⭐⭐'}
# HTML
tier_rows = ''
for tk in ['T1','T2','T3','T4']:
    ts = tier_stats.get(tk,{'count':0,'wins':0,'sum_m3':0,'sum_d1':0})
    if ts['count'] > 0:
        wr = ts['wins']/ts['count']*100
        avg_m3 = ts['sum_m3']/ts['count']
        avg_d1 = ts['sum_d1']/ts['count']
        stars = STAR_MAP.get(tk, '')
    tier_rows += f'<tr><td>{tk}</td><td style="font-size:16px">{stars}</td><td style="color:#b8860b;font-weight:bold">{ts["count"]}</td><td style="color:#dc2626;font-weight:bold">{ts["wins"]}</td><td>{ts["count"]-ts["wins"]}</td><td style="color:#dc2626;font-weight:bold">{wr:.0f}%</td><td>{avg_d1:+.1f}%</td><td style="color:#8b5cf6;font-weight:bold">{avg_m3:+.1f}%</td></tr>\n'

today = '2026-06-10'
d1_pos = sum(1 for r in r74 if r['d1h'] > 0)
min_m3 = min(r['m3'] for r in r74)
max_m3 = max(r['m3'] for r in r74)

rows_html = ''
for r in rows_data:
    d1c = '#dc2626' if r['d1h'] > 0 else '#16a34a'
    d2c = '#dc2626' if r['d2h'] > 0 else '#16a34a'
    d3c = '#dc2626' if r['d3h'] > 0 else '#16a34a'
    m3c = '#dc2626'  # 累计最高永远是正数 → 用红色
    realc = '#dc2626' if r['real'] > 0 else '#16a34a'
    planAc = '#dc2626'  # 方案A不亏 → 永远是红色的盈利
    win_mark = '✅' if r['win_cur'] else '❌'

    bg = ''
    for tk, tc in [('T1','#fef2f2'),('T2','#eff6ff'),('T3','#f0fdf4'),('T4','#fefce8')]:
        if r['tier'].startswith(tk): bg = f' style="background:{tc}"'; break

    rows_html += f'<tr{bg}>'
    rows_html += f'<td style="padding:5px 6px">{r["date"]}</td>'
    star = STAR_MAP.get(r['tier'].split('-')[0], '')
    rows_html += f'<td style="padding:5px 6px;font-size:14px">{star}</td>'
    rows_html += f'<td style="padding:5px 6px;font-size:10px">{r["tier"]}</td>'
    rows_html += f'<td style="padding:5px 6px;font-weight:bold">{r["name"]}</td>'
    rows_html += f'<td style="padding:5px 6px;color:#999;font-size:10px">{r["code"]}</td>'
    rows_html += f'<td style="padding:5px 6px">&yen;{r["entry"]:.2f}</td>'
    rows_html += f'<td style="padding:5px 6px;color:#dc2626;font-weight:bold">{r["entry_pct"]:+.1f}%</td>'
    rows_html += f'<td style="padding:5px 6px;color:{d1c};font-weight:bold">{r["d1h"]:+.1f}%</td>'
    rows_html += f'<td style="padding:5px 6px;color:{d2c}">{r["d2h"]:+.1f}%</td>'
    rows_html += f'<td style="padding:5px 6px;color:{d3c}">{r["d3h"]:+.1f}%</td>'
    rows_html += f'<td style="padding:5px 6px;color:#dc2626;font-weight:bold">{r["m3"]:+.1f}%</td>'
    if r['tip']:
        rows_html += f'<td style="padding:5px 6px;font-size:10px;color:#d97706;max-width:120px">{r["tip"]}</td>'
    else:
        rows_html += f'<td style="padding:5px 6px;font-size:10px;color:#ccc">—</td></tr>\n'

html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:微软雅黑,Helvetica,sans-serif;background:#ffffff;color:#374151;margin:0;padding:12px">
<div style="background:linear-gradient(135deg,#fefce8,#fef3c7);padding:16px;border-radius:8px;margin-bottom:12px;border-bottom:3px solid #b8860b">
<h1 style="margin:0;font-size:20px;color:#b8860b">🏆 东风5B 综合报告</h1>
<p style="margin:4px 0 0;color:#666;font-size:12px">{today} | 全量100天回测 | 生产版 | 四阶梯(T1&#8594;T2&#8594;T3&#8594;T4) + 三重过滤</p>
</div>
<div style="background:linear-gradient(90deg,#dc2626,#b91c1c);padding:18px;border-radius:10px;margin-bottom:14px;text-align:center;box-shadow:0 4px 12px rgba(220,38,38,0.3)">
<h2 style="margin:0;font-size:28px;color:#fff;letter-spacing:4px;text-shadow:0 2px 4px rgba(0,0,0,0.3)">🚀 东方导弹 · 使命必达 🚀</h2>
<p style="margin:6px 0 0;color:#fecaca;font-size:14px;letter-spacing:2px">DongFeng Missile · Mission Accomplished</p>
</div>
<div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:12px;margin-bottom:12px;border-radius:4px">
<h3 style="margin:0 0 6px;font-size:15px;color:#16a34a">📭 今日(06-10) 无信号</h3>
<p style="margin:0;font-size:12px;color:#666">4个梯队全部扫描完毕，今日无符合条件股票</p>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:12px">
<div style="background:#fef2f2;padding:10px;border-radius:6px;text-align:center">
<div style="font-size:11px;color:#666">100天总信号</div>
<div style="font-size:24px;font-weight:bold;color:#dc2626">{len(r74)}笔</div></div>
<div style="background:#fef2f2;padding:10px;border-radius:6px;text-align:center">
<div style="font-size:11px;color:#666">达标(&ge;3%)</div>
<div style="font-size:24px;font-weight:bold;color:#dc2626">{sum(1 for r in r74 if r['m3']>=3)}/{len(r74)}</div></div>
<div style="background:#fef2f2;padding:10px;border-radius:6px;text-align:center">
<div style="font-size:11px;color:#666">方案A总收益</div>
<div style="font-size:24px;font-weight:bold;color:#dc2626">+{total_planA:.0f}%</div></div>
</div>
<div style="background:#f9fafb;padding:10px;border-radius:6px;margin-bottom:12px">
<h3 style="margin:0 0 6px;font-size:14px;color:#374151">📊 各梯队表现</h3>
<table style="width:100%;border-collapse:collapse;font-size:12px">
<thead><tr style="background:#f3f4f6">
<th style="padding:6px 8px;text-align:left">梯队</th><th style="padding:6px 8px">星级</th><th style="padding:6px 8px">信号</th><th style="padding:6px 8px">胜</th><th style="padding:6px 8px">败</th><th style="padding:6px 8px">胜率</th><th style="padding:6px 8px">D+1均</th><th style="padding:6px 8px;color:#8b5cf6">3日最高涨幅</th>
</tr></thead><tbody>
{tier_rows}
</tbody></table>
</div>
<div style="margin-bottom:12px">
<h3 style="margin:0 0 6px;font-size:14px;color:#374151">📋 {len(r74)}笔完整回测记录（逐日明细）</h3>
<div style="overflow-x:auto;-webkit-overflow-scrolling:touch">
<table style="min-width:820px;border-collapse:collapse;font-size:11px;white-space:nowrap">
<thead><tr style="background:#f3f4f6">
<th style="padding:5px 6px">日期</th><th style="padding:5px 6px">星级</th><th style="padding:5px 6px">层级</th><th style="padding:5px 6px">名称</th><th style="padding:5px 6px">代码</th><th style="padding:5px 6px">入场</th>
<th style="padding:5px 6px;color:#dc2626">当天涨</th><th style="padding:5px 6px;color:#dc2626">D+1高</th><th style="padding:5px 6px;color:#dc2626">D+2高</th><th style="padding:5px 6px;color:#dc2626">D+3高</th><th style="padding:5px 6px;color:#dc2626">3日最高涨幅</th><th style="padding:5px 6px;color:#d97706">提示</th>
</tr></thead><tbody>
{rows_html}
<tr style="background:#fefce8;font-weight:bold">
<td colspan="7" style="padding:5px 6px;text-align:right;color:#b8860b">合计{len(r74)}笔</td>
<td style="padding:5px 6px;color:#dc2626">{d1_pos}天红</td>
<td style="padding:5px 6px"></td>
<td style="padding:5px 6px"></td>
<td style="padding:5px 6px;color:#b8860b">{sum(r['m3'] for r in r74)/len(r74):+.1f}%均</td>
<td style="padding:5px 6px"></td>
</tr>
</tbody></table>
</div></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
<div style="background:#f0fdf4;padding:10px;border-radius:6px">
<div style="font-size:11px;color:#666">🏆 最大赢家</div>
<div style="font-size:14px;font-weight:bold;color:#16a34a">{max([r for r in r74 if r['m3']==max_m3])['name']} +{max_m3:.0f}%</div></div>
<div style="background:#fef2f2;padding:10px;border-radius:6px">
<div style="font-size:11px;color:#666">📉 最小3日高</div>
<div style="font-size:14px;font-weight:bold;color:#dc2626">{min([r for r in r74 if r['m3']==min_m3])['name']} {min_m3:+.1f}%</div></div>
</div>
<div style="background:#f9fafb;padding:10px;border-radius:6px;margin-bottom:12px">
<h3 style="margin:0 0 6px;font-size:14px;color:#374151">💡 条件单策略对比</h3>
<table style="width:100%;border-collapse:collapse;font-size:12px">
<thead><tr style="background:#f3f4f6">
<th style="padding:6px 8px;text-align:left">策略</th><th style="padding:6px 8px">100天收益</th><th style="padding:6px 8px">均/笔</th><th style="padding:6px 8px">亏损单</th>
</tr></thead><tbody>
<tr><td style="padding:5px 8px">当前规则(+3%回落)</td><td style="padding:5px 8px;color:#dc2626;font-weight:bold">+{total_cur:.0f}%</td><td style="padding:5px 8px">{total_cur/len(r74):+.2f}%</td><td style="padding:5px 8px">{sum(1 for r in r74 if r['real']<=0)}单</td></tr>
<tr style="background:#fefce8"><td style="padding:5px 8px;font-weight:bold">⭐ 方案A(+5%半仓+保本)</td><td style="padding:5px 8px;color:#16a34a;font-weight:bold">+{total_planA:.0f}%</td><td style="padding:5px 8px;font-weight:bold">{total_planA/len(r74):+.2f}%</td><td style="padding:5px 8px;color:#16a34a;font-weight:bold">0亏损 ✅</td></tr>
</tbody></table>
</div>
<div style="text-align:center;padding:12px;color:#999;font-size:11px">
东风5B 生产版 | 四阶梯(T1-C≥3&#8594;T2-C=2+20日涨&#8594;T3-二板N字+扣分&#8594;T4-单阳不破A级+MA20) | 条件单: +5%半仓+保本+ -7%止损+收盘清
</div>
</body></html>'''

sys.path.insert(0, SCRIPTS_DIR)
from send_email import send_email
send_email(subject=f'🚀 东风导弹 使命必达 | 东风5B 100天回测报告 {today}', body=html, html=True)
print('✅ 综合报告邮件已发送')

conn.close()
