#!/usr/bin/env python3
"""择优#1日报 — 定版
模板：零边距白底，红涨绿跌
内容：历史成绩 + 今日TOP10 + 达标/未达标/待验证三表
发送：默认只发Alan(1254628314)，--all发A组全5人
"""
import os, sys, json, sqlite3, smtplib, ssl, yaml, numpy as np, xgboost as xgb
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime, date

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
today = date.today().strftime('%Y-%m-%d')
if len(sys.argv) > 1:
    today = sys.argv[1]

SEND_ALL = '--all' in sys.argv  # 发全A组

conn = sqlite3.connect(DB_PATH, timeout=30)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# ==================== 数据准备 ====================

# 回填遗漏的次日数据
c.execute('''UPDATE meta_daily_records SET next_close_n = (
    SELECT ROUND((b2.close - meta_daily_records.price) / meta_daily_records.price * 100, 2)
    FROM bt_data b2 WHERE b2.code = meta_daily_records.code
    AND b2.date = (SELECT MIN(b3.date) FROM bt_data b3 WHERE b3.code = meta_daily_records.code AND b3.date > meta_daily_records.date AND b3.date GLOB '????-??-??')
    AND b2.close > 0
) WHERE meta_daily_records.next_close_n IS NULL AND meta_daily_records.date < ?''', (today,))
c.execute('''UPDATE meta_daily_records SET next_day_n = (
    SELECT ROUND((b2.high - meta_daily_records.price) / meta_daily_records.price * 100, 2)
    FROM bt_data b2 WHERE b2.code = meta_daily_records.code
    AND b2.date = (SELECT MIN(b3.date) FROM bt_data b3 WHERE b3.code = meta_daily_records.code AND b3.date > meta_daily_records.date AND b3.date GLOB '????-??-??')
    AND b2.high > 0
) WHERE meta_daily_records.next_day_n IS NULL AND meta_daily_records.date < ?''', (today,))
c.execute('''UPDATE meta_daily_records SET next_low_n = (
    SELECT ROUND((b2.low - meta_daily_records.price) / meta_daily_records.price * 100, 2)
    FROM bt_data b2 WHERE b2.code = meta_daily_records.code
    AND b2.date = (SELECT MIN(b3.date) FROM bt_data b3 WHERE b3.code = meta_daily_records.code AND b3.date > meta_daily_records.date AND b3.date GLOB '????-??-??')
    AND b2.low > 0
) WHERE meta_daily_records.next_low_n IS NULL AND meta_daily_records.date < ?''', (today,))

# win_2_5标签同步
c.execute('''UPDATE meta_daily_records SET win_2_5 = CASE
    WHEN next_day_n >= 2.5 THEN 1
    WHEN next_day_n < 2.5 AND next_day_n IS NOT NULL THEN 0
    ELSE NULL END
WHERE date < ? AND (win_2_5 IS NULL OR next_day_n != next_day_n)''', (today,))

# 补名称
c.execute('''UPDATE meta_daily_records SET name = (
    SELECT COALESCE(b.name, d.name, '') FROM bt_data b
    LEFT JOIN data_cache d ON d.code=b.code AND d.date=b.date
    WHERE b.code = meta_daily_records.code AND b.date = meta_daily_records.date
    AND (b.name != '' OR d.name != '')
    LIMIT 1
) WHERE name IS NULL OR name = '' ''')

conn.commit()

# ==================== 读全部记录 ====================
all_records = c.execute('''SELECT date, code, name, price, pct, model_prob, source_version,
    next_day_n, next_close_n, win_2_5, buy_time, source_rank
FROM meta_daily_records ORDER BY date DESC''').fetchall()

# 只取2个月内
cutoff = '2026-04-29'
all_records = [r for r in all_records if r['date'] >= cutoff]

# 今日数据
today_data = {}
pick_file = os.path.join(SCRIPTS_DIR, f'meta_pick_{today}.json')
if os.path.exists(pick_file):
    with open(pick_file, encoding='utf-8') as f:
        jd = json.load(f)
        today_data = jd.get('pick', {})

# ==================== 分表 + 统计 ====================
wins_html = losses_html = pending_html = ''
total_w = total_t = total_p = 0

for r in all_records:
    win = r['win_2_5']
    nhn = r['next_day_n']
    ncn = r['next_close_n']
    prob = r['model_prob'] or 0

    if win is not None:
        total_t += 1
        total_w += 1 if win == 1 else 0
    else:
        total_p += 1

    close_s = f'{ncn:+.2f}%' if ncn is not None else '待更新'
    nhn_s = f'{nhn:+.2f}%' if nhn is not None else '待更新'
    btm = (r['buy_time'] or '')[-8:]
    vs = r['source_version'] or ''
    rk = r['source_rank']
    vs_rk = f'{vs}#{rk}' if rk else vs

    nhn_color = '#dc2626' if nhn is not None and nhn >= 2.5 else ('#16a34a' if nhn is not None and nhn < 0 else '#333')
    cls_color = '#dc2626' if ncn is not None and ncn > 0 else ('#16a34a' if ncn is not None and ncn < 0 else '#333')

    row = f'<tr><td>{r["date"]}</td><td>{btm}</td><td>{r["code"]}</td><td>{r["name"] or ""}</td><td>{vs_rk}</td><td>{r["price"]:.2f}</td><td style="color:#dc2626">{r["pct"]:+.2f}%</td><td style="color:{nhn_color}">{nhn_s}</td><td style="color:{cls_color}">{close_s}</td><td>{prob*100:.0f}%</td></tr>'

    if win == 1:
        wins_html += row
    elif win == 0:
        losses_html += row
    else:
        pending_html += row

wr = total_w / total_t * 100 if total_t else 0

# ==================== 今日各策略评分TOP10 ====================
top10_html = ''
try:
    model2 = xgb.XGBClassifier()
    model2.load_model(os.path.join(SCRIPTS_DIR, 'meta_ranker_model.json'))
    vers_all = ['V13','V42','V88','V89','1180','V13_尾盘','V42_尾盘','V89_尾盘','VIP1']
    ver_enc2 = {v:i for i,v in enumerate(vers_all)}
    mkt2 = (c.execute('SELECT market FROM market_days WHERE date=?', (today,)).fetchone() or [None])[0] or 'flat'
    mkt_enc2 = {'real_up':0,'fake_up':1,'flat':2,'down':3}.get(mkt2, 2)

    cands = c.execute('''SELECT s.* FROM selection_candidates s WHERE s.date=?
        AND s.run_time IS NOT NULL AND s.run_time >= ? || ' 14:00' AND s.run_time <= ? || ' 15:00'
        AND s.rank <= 10''', (today, today, today)).fetchall()
    cols = [d[0] for d in c.description]
    scored = []
    seen = set()
    for r in cands:
        rd = {cols[i]: r[i] for i in range(len(cols))}
        feats = np.array([[
            rd.get('score',0) or 0, rd.get('cl',50) or 50, rd.get('vr',1.0) or 1.0, rd.get('hsl',3) or 3,
            rd.get('wr',50) or 50, rd.get('dif',0) or 0,
            rd.get('rank',99) or 99, ver_enc2.get(rd.get('version',''),0), mkt_enc2,
            rd.get('pct',0) or 0,
            1.0/(max(rd.get('rank',1),1)+1),
            (rd.get('score',0) or 0)*(rd.get('cl',50) or 50)/100.0,
            int((rd.get('dif',0) or 0)>0), int((rd.get('vr',1.0) or 1.0)<2.0),
            int((rd.get('cl',50) or 50)>60), int((rd.get('hsl',3) or 3)>3),
        ]])
        prob = model2.predict_proba(feats)[0,1]
        k = rd.get('code','')
        if k not in seen:
            seen.add(k)
            scored.append({'prob': prob, 'code': k, 'name': rd.get('name',''), 'version': rd.get('version',''), 'rank': rd.get('rank',0), 'score': rd.get('score',0), 'pct': rd.get('pct',0), 'price': rd.get('price',0)})
    scored.sort(key=lambda x: -x['prob'])
    top10_html = '<div class="wrap"><table><thead><tr><th>#</th><th>代码</th><th>名称</th><th>涨幅</th><th>价格</th><th>评分</th><th>策略</th></tr></thead><tbody>'
    # 补全空名称：从bt_data/data_cache查
    name_cache = {}
    for p in scored:
        if not p['name']:
            if p['code'] not in name_cache:
                nr = c.execute("SELECT name FROM bt_data WHERE code=? AND name!='' AND name IS NOT NULL LIMIT 1", (p['code'],)).fetchone()
                if not nr:
                    nr = c.execute("SELECT name FROM data_cache WHERE code=? AND name!='' AND name IS NOT NULL LIMIT 1", (p['code'],)).fetchone()
                name_cache[p['code']] = nr[0] if nr else p['code']
            p['name'] = name_cache[p['code']]
    
    for i, p in enumerate(scored[:10]):
        mark = '🥇' if i==0 else ('🥈' if i==1 else ('🥉' if i==2 else str(i+1)))
        pc = f'<span style="color:#dc2626">{p["pct"]:+.2f}%</span>' if p["pct"] else '<span style="color:#999">0%</span>'
        top10_html += f'<tr><td>{mark}</td><td>{p["code"]}</td><td>{p["name"] or p["code"]}</td><td>{pc}</td><td>{p["price"]:.2f}</td><td>{p["prob"]*100:.0f}%</td><td>{p["version"]}</td></tr>'
    top10_html += '</tbody></table></div>'
except Exception as e:
    top10_html = f'<p style="color:#999;font-size:11px">TOP10加载失败</p>'

# ==================== 今日卡片 ====================
td_code = today_data.get('code','') or (all_records[0]['code'] if all_records and all_records[0]['date']==today else '')
td_name = today_data.get('name','') or (all_records[0]['name'] if all_records and all_records[0]['date']==today else '')
td_price = today_data.get('price',0) or (all_records[0]['price'] if all_records and all_records[0]['date']==today else 0)
td_pct = today_data.get('pct',0) or (all_records[0]['pct'] if all_records and all_records[0]['date']==today else 0)
td_prob = today_data.get('prob',0) or (all_records[0]['model_prob'] if all_records and all_records[0]['date']==today else 0)

today_card = f'''<div style="background:#fff3e0;border:2px solid #ff9800;border-radius:8px;padding:12px;margin:12px 0;text-align:center">
<div style="font-size:20px;font-weight:bold;color:#e65100">🎯 择优#1 {today}</div>
<div style="font-size:24px;font-weight:bold;color:#dc2626;margin:6px 0">{td_code} {td_name}</div>
<div style="color:#666">买入价: {td_price:.2f} | 涨幅: <span style="color:#dc2626">{td_pct:+.2f}%</span></div>
<div style="color:#666">模型评分: {td_prob*100:.0f}%</div>
<div style="color:#f59e0b;font-weight:bold;margin-top:6px">⏳ 待验证 - 明日盘后更新</div>
</div>'''

# ==================== HTML 模板（零边距） ====================
html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,Helvetica,Arial,sans-serif;background:#fff;color:#333;font-size:13px}}
h1{{font-size:16px;border-bottom:2px solid #dc2626;padding:6px 3px;margin:0}}
h2{{font-size:14px;padding:10px 3px 4px}}
.wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{min-width:560px;width:100%;border-collapse:collapse;font-size:11px;white-space:nowrap}}
th{{background:#1a1a2e;color:#fff;padding:5px 3px;text-align:center;font-size:11px;white-space:nowrap}}
td{{padding:5px 3px;text-align:center;border-bottom:1px solid #eee}}
.footer{{padding:8px 3px;border-top:1px solid #eee;font-size:10px;color:#aaa;text-align:center}}
</style></head><body>
<h1>📊 择优#1 历史成绩</h1>
<div style="font-size:22px;font-weight:bold;color:#1565C0;margin:8px 0">胜率: {wr:.1f}% ({total_w}/{total_t}天)</div>
{today_card}
<h2>🏆 今日各策略评分TOP10</h2>
{top10_html}
<h2>✅ 达标 ({len([r for r in all_records if r['win_2_5']==1])}天)</h2>
<div class="wrap"><table><thead><tr><th>日期</th><th>时间</th><th>代码</th><th>名称</th><th>策略</th><th>买入价</th><th>当日%</th><th>次日最高%</th><th>次收%</th><th>评分</th></tr></thead><tbody>{wins_html}</tbody></table></div>
<h2>❌ 未达标 ({len([r for r in all_records if r['win_2_5']==0])}天)</h2>
<div class="wrap"><table><thead><tr><th>日期</th><th>时间</th><th>代码</th><th>名称</th><th>策略</th><th>买入价</th><th>当日%</th><th>次日最高%</th><th>次收%</th><th>评分</th></tr></thead><tbody>{losses_html}</tbody></table></div>
<h2>⏳ 待验证 ({total_p}天)</h2>
<div class="wrap"><table><thead><tr><th>日期</th><th>时间</th><th>代码</th><th>名称</th><th>策略</th><th>买入价</th><th>当日%</th><th>次日最高%</th><th>次收%</th><th>评分</th></tr></thead><tbody>{pending_html}</tbody></table></div>
<div class="footer">择优#1日报 | {datetime.now().strftime("%Y-%m-%d %H:%M")} | 仅参考不构成投资建议</div>
</body></html>'''

# ==================== 发送 ====================
yml = os.path.join(SCRIPTS_DIR, 'config', 'email_config.yaml')
cfg = yaml.safe_load(open(yml, encoding='utf-8'))
acct = cfg['email_a']

if SEND_ALL:
    recipients = ['1254628314@qq.com', '314913203@qq.com', '2603672569@qq.com', '2318162429@qq.com', '827969130@qq.com']
else:
    recipients = ['1254628314@qq.com']  # 默认只发Alan

subject = f'🎯 择优#1 {today} - {td_code} {td_name} (胜率{wr:.0f}%)'
ctx = ssl.create_default_context()

with smtplib.SMTP_SSL(acct['smtp_host'], acct['smtp_port'], context=ctx, timeout=15) as s:
    s.login(acct['sender'], acct['password'])
    for r in recipients:
        m = MIMEText(html, 'html', 'utf-8')
        m['Subject'] = Header(subject, 'utf-8')
        m['From'] = acct['sender']
        m['To'] = r
        s.sendmail(acct['sender'], [r], m.as_string())
        print(f'✅ {r}')

print(f'主题: {subject}')
print(f'胜率: {wr:.1f}% ({total_w}/{total_t}) 待验证: {total_p}')
conn.close()
