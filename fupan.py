#!/usr/bin/env python3
"""V13+V42+V50 尾盘选股验证复盘 — 读sqllite选股日志，验证今日表现"""
import subprocess, json, os, sys, sqlite3
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
TODAY = datetime.now().strftime('%Y-%m-%d')
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

def curl_get(url, timeout=8):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url],capture_output=True,timeout=timeout+5)
        return r.stdout.decode('gbk',errors='replace')
    except: return ''

def get_last_trade():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT DISTINCT date FROM data_cache WHERE date<? AND close>0 ORDER BY date DESC LIMIT 1", (TODAY,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None

def get_selection(ver, date):
    """返回 {'top3':[...], 'top10':[...]}"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    r = c.execute("""
        SELECT c_code,c_name,c_price,s_code,s_name,s_price,t_code,t_name,t_price,top10_json,run_time
        FROM daily_selection_log WHERE version=? AND date=? ORDER BY id DESC LIMIT 1
    """, (ver, date)).fetchone()
    conn.close()
    if not r:
        return None
    top3 = [
        {'code':r[0],'name':r[1],'price':r[2]},
        {'code':r[3],'name':r[4],'price':r[5]},
        {'code':r[6],'name':r[7],'price':r[8]},
    ]
    run_time_str = r[10] if len(r) > 10 else ''
    top10 = []
    if r[9]:
        try:
            p = json.loads(r[9])
            for i in range(min(10, len(p))):
                top10.append({'name':p[i]['name'],'code':p[i]['code'],'price':p[i]['price'],'score':p[i].get('sc',0)})
            for i in range(min(3, len(p))):
                top3[i]['price'] = p[i].get('price', top3[i]['price'])
                top3[i]['score'] = p[i].get('sc', 0)
        except:
            pass
    return {'top3': top3, 'top10': top10, 'run_time': run_time_str}

def check_today_high(stocks):
    codes = [s['code'] for s in stocks]
    results = {}
    for i in range(0, len(codes), 50):
        chunk = codes[i:i+50]
        symbols = [f'{PREFIX(c)}{c}' for c in chunk]
        text = curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}', timeout=10)
        for line in text.split('\n'):
            if '~' not in line: continue
            parts = line.split('~')
            if len(parts) < 40: continue
            try:
                results[parts[2]] = {'high': float(parts[33]), 'now': float(parts[3]), 'close': float(parts[4])}
            except:
                pass
    return results

# ===== 主流程 =====
now = datetime.now()
is_pm = now.hour >= 15
label = '盘后15:05' if is_pm else '午盘11:40'
suffix = '盘后' if is_pm else '午盘'
print(f'📋 V13+V42+V50 尾盘验证复盘 | {TODAY} {label}', flush=True)

last_date = get_last_trade()
if not last_date:
    print('❌ 无交易日数据')
    sys.exit(1)
print(f'📅 验证: 昨{last_date}尾盘选股 → 今{TODAY}表现', flush=True)

# 版本配置
ver_order = ['V13', 'V42', 'V50']
ver_labels = {
    'V13': 'V13 尾盘(14:48)',
    'V42': 'V42 尾盘(14:50旧)',
    'V50': 'V50 尾盘(14:50🆕)',
}
ver_colors = {'V13':'#e74c3c', 'V42':'#4a90d9', 'V50':'#2ecc71'}

data = {}
top10_data = {}
run_times = {}
for ver in ver_order:
    sel = get_selection(ver, last_date)
    if sel:
        data[ver] = sel['top3']
        top10_data[ver] = sel['top10']
        run_times[ver] = sel.get('run_time', '')
        tm = f' ({sel["run_time"]})' if sel.get('run_time') else ''
        print(f'  ✅ {ver}: {sel["top3"][0]["name"]}({sel["top3"][0]["code"]}){tm}', flush=True)
    else:
        print(f'  ⏳ {ver}: 无记录', flush=True)

if not data:
    print(f'\n📭 昨日（{last_date}）无选股记录，仅展示今日选股', flush=True)
    has_yesterday = False
else:
    has_yesterday = True
    all_stocks = [s for lst in data.values() for s in lst]
    for lst in top10_data.values():
        all_stocks.extend(lst)
    today_data = check_today_high(all_stocks)
    if not today_data:
        print('❌ 无法获取今日行情')
        sys.exit(1)

# 今日Top10
today_top10 = {}
for ver in ver_order:
    sel = get_selection(ver, TODAY)
    if sel:
        today_top10[ver] = sel['top10']

# ===== 生成HTML =====
# 冠亚季军验证表
all_html = ''
summary_parts = []
if has_yesterday:
    for ver in ver_order:
        if ver not in data: continue
        stocks = data[ver]
        rows = ''
        ok_count = 0
        for i, s in enumerate(stocks):
            code = s['code']; buy = s['price']
            td = today_data.get(code, {})
            high = td.get('high', 0)
            pct = (high - buy) / buy * 100 if high and buy else 0
            ok = pct >= 2.5
            if ok: ok_count += 1
            score = s.get('score', '')
            rows += f'<tr><td>{i+1}</td><td>{s["name"]}</td><td>{code}</td><td>¥{buy:.2f}</td><td>{f"{score:.0f}" if score else "—"}</td>'
            rows += f'<td style="color:{"#e74c3c" if ok else "#27ae60"};font-weight:bold">{pct:+.1f}%</td>'
            rows += f'<td>{"✅" if ok else "❌"}</td></tr>\n'
        tm = f' ({run_times.get(ver,"")[:5]})' if run_times.get(ver) else ''
        all_html += f'''<div class="ver-block" style="border-left-color:{ver_colors[ver]}">
<h3>📌 {ver_labels[ver]}{tm}</h3>
<p style="font-size:12px;color:#666">昨{last_date}尾盘选股 → 今{TODAY}</p>
<table><thead><tr><th>#</th><th>名称</th><th>代码</th><th>买入价</th><th>评分</th><th>次日最高涨幅</th><th>结果</th></tr></thead><tbody>
{rows}</tbody></table>
<p style="font-size:13px;font-weight:bold">达标率: {ok_count}/3 = {ok_count*100//3}%</p>
</div>'''
        summary_parts.append(f'{ver} {ok_count}/3={ok_count*100//3}%')
    summary = ' | '.join(summary_parts) if summary_parts else '暂无验证数据'
else:
    summary = '📭 昨日无选股记录，仅展示今日Top10'

# Top10对比表（多版本动态列）
top10_header = '<tr><th>#</th>'
for v in ver_order:
    c = ver_colors.get(v, '#333')
    top10_header += f'<th style="color:{c}">{ver_labels.get(v, v)}</th><th>价格</th><th>评分</th><th>次日最高涨幅</th><th>结果</th>'
top10_header += '</tr>\n'
top10_html = top10_header
max_len = max((len(top10_data.get(v,[])) for v in ver_order), default=0)
for i in range(max_len):
    medal = '🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else f'{i+1}'
    row = f'<tr><td>{medal}</td>'
    for v in ver_order:
        lst = top10_data.get(v, [])
        if i < len(lst):
            s = lst[i]
            code = s.get('code','')
            buy = s.get('price',0)
            td = today_data.get(code, {}) if has_yesterday else {}
            high = td.get('high', 0)
            pct = (high - buy) / buy * 100 if high and buy else 0
            ok = pct >= 2.5
            pct_s = f'+{pct:.1f}%' if pct >= 0 else f'{pct:.1f}%'
            pct_c = '#e74c3c' if ok else '#27ae60'
            cell = f'{s.get("name","")}<br><span style="font-size:10px;color:#999">{code}</span>'
            sc = f'{s.get("score",0):.1f}'
            pr = f'¥{buy:.2f}' if buy else '—'
            row += f'<td style="text-align:left;padding-left:8px">{cell}</td><td>{pr}</td><td>{sc}</td>'
            row += f'<td style="color:{pct_c};font-weight:bold">{pct_s}</td><td>{"✅" if ok else "❌"}</td>'
        else:
            row += '<td colspan="5"></td>'
    row += '</tr>\n'
    top10_html += row

# 今日Top10表（多版本）
today_header = '<tr><th>#</th>'
for v in ver_order:
    c = ver_colors.get(v, '#333')
    today_header += f'<th style="color:{c}">{ver_labels.get(v, v)}</th><th>价格</th><th>评分</th>'
today_header += '</tr>\n'
today_top10_html = today_header if today_top10 else ''
if today_top10:
    ml = max((len(today_top10.get(v,[])) for v in ver_order), default=0)
    for i in range(ml):
        medal = '🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else f'{i+1}'
        row = f'<tr><td>{medal}</td>'
        for v in ver_order:
            lst = today_top10.get(v, [])
            if i < len(lst):
                s = lst[i]
                cell = f'{s.get("name","")}<br><span style="font-size:10px;color:#999">{s.get("code","")}</span>'
                sc = f'{s.get("score",0):.1f}'
                pr = f'¥{s.get("price",0):.2f}' if s.get("price") else '—'
                row += f'<td style="text-align:left;padding-left:8px">{cell}</td><td>{pr}</td><td>{sc}</td>'
            else:
                row += '<td colspan="3"></td>'
        row += '</tr>\n'
        today_top10_html += row
    today_top10_section = f'''<div class="card" style="background:#f0f8ff;border-radius:8px;padding:12px;margin:12px 0;border-top:2px solid #4a90d9">
<h3>📌 今日选股 Top10（{TODAY}）</h3>
<div style="overflow-x:auto">
<table class="top10-table" style="min-width:600px">
<thead>{today_header}</thead>
<tbody>{today_top10_html}</tbody>
</table></div>
</div>'''
else:
    today_top10_section = ''

html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>V13+V42+V50尾盘验证复盘 {TODAY}</title>
<style>
body{{font-family:'微软雅黑',sans-serif;padding:15px;color:#2c3e50;font-size:13px;line-height:1.5}}
h2{{color:#b8860b;border-bottom:2px solid #b8860b;padding-bottom:5px}}
h3{{color:#2c3e50;margin:15px 0 8px}}
table{{width:100%;border-collapse:collapse;margin:8px 0}}
th{{background:#f0f0f0;padding:6px 4px;text-align:center;border-bottom:2px solid #dfe6e9;font-size:11px}}
td{{padding:4px 3px;text-align:center;border-bottom:1px solid #f0f0f0}}
.ver-block{{background:#f5f6fa;border-radius:8px;padding:12px;margin:12px 0;border-left:4px solid #b8860b}}
.summary{{background:#fff8e1;border-radius:8px;padding:10px;margin:10px 0;text-align:center;font-size:14px;font-weight:bold}}
.footer{{text-align:center;font-size:11px;color:#95a5a6;margin:15px 0}}
.top10-table th{{font-size:11px}}
.top10-table td{{font-size:12px}}
.tag-time{{background:#f0f0f0;border-radius:3px;padding:1px 5px;font-size:10px;color:#666;margin-left:5px}}
</style></head><body>
<h2>📊 V13+V42+V50 尾盘选股验证复盘</h2>
<p style="font-size:12px;color:#666">📅 {TODAY} {label} | 验证昨{last_date}尾盘选股今日表现</p>

<div class="summary">{summary}</div>

{all_html}

<div class="card" style="background:#f5f6fa;border-radius:8px;padding:12px;margin:12px 0;border-top:2px solid #b8860b">
<h3>📋 V13 vs V42 vs V50 昨日Top10对比</h3>
<div style="overflow-x:auto">
<table class="top10-table" style="min-width:600px">
<thead>{top10_header}</thead>
<tbody>{top10_html}</tbody>
</table></div>
<p style="font-size:11px;color:#95a5a6;margin-top:4px">达标标准：次日最高涨幅 ≥ 2.5%</p>
</div>

{today_top10_section}

<div class="footer">
<p>达标标准：次日最高涨幅 ≥ 2.5% | 数据源：14:50选股日志(sqllite) + 腾讯实时行情 | Hermes Agent</p>
</div>
</body></html>'''

arch = os.path.join(SCRIPTS_DIR, 'email_archive')
os.makedirs(arch, exist_ok=True)
fp = os.path.join(arch, f'{TODAY}_复盘_{suffix}.html')
with open(fp, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'📁 已存档: {fp}', flush=True)

try:
    sender = os.path.join(SCRIPTS_DIR, 'send_email.py')
    subj = f'【{suffix}自动化复盘】V13+V42+V50尾盘验证复盘 {suffix} {TODAY}'
    r = subprocess.run([sys.executable, sender, subj, html, '--html'], timeout=60, capture_output=True, text=True)
    print(f'📧 {r.stdout.strip()}', flush=True)
except Exception as e:
    print(f'❌ 邮件失败: {e}', flush=True)
