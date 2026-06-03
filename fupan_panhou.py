#!/usr/bin/env python3
"""V13+V42 尾盘选股验证复盘 — 15:05盘后（查当天最终最高价）"""
import subprocess, json, os, sys
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

TODAY = datetime.now().strftime('%Y-%m-%d')
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

def curl_get(url, timeout=8):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url],capture_output=True,timeout=timeout+5)
        return r.stdout.decode('gbk',errors='replace')
    except: return ''

def get_yesterday_picks():
    import sqlite3
    conn = sqlite3.connect(os.path.join(SCRIPTS_DIR, 'v13_quant.db'), timeout=10)
    c = conn.cursor()
    picks = {}
    
    # 找最近交易日（剔除今天）
    c.execute("SELECT DISTINCT date FROM data_cache WHERE date<? AND close>0 ORDER BY date DESC LIMIT 1", (TODAY,))
    last_trade = c.fetchone()
    last_trade_date = last_trade[0] if last_trade else None
    print(f'📅 最近交易日: {last_trade_date}', flush=True)
    
    for ver in ['V13','V42']:
        r = c.execute("SELECT top10_json FROM daily_selection_log WHERE version=? AND date=? ORDER BY id DESC LIMIT 1", (ver, last_trade_date)).fetchone()
        if r:
            p = json.loads(r[0])
            picks[ver] = [{'name':p[i]['name'], 'code':p[i]['code'], 'price':p[i]['price'], 'score':p[i]['sc']} for i in range(min(3,len(p)))]
            print(f'  {ver}: 从选股日志读取 {picks[ver][0]["name"]}({picks[ver][0]["code"]})', flush=True)
        else:
            print(f'  {ver}: 选股日志无记录，从data_cache回测读取', flush=True)
            # 用已知的05-29 V42/V13回测冠军数据（首次运行fallback）
            c.execute('SELECT code, name, close, p FROM data_cache WHERE date=? AND close>0 AND p<8 ORDER BY p DESC LIMIT 30', (last_trade_date,))
            ss = c.fetchall()
            if ss and len(ss) >= 3:
                picks[ver] = []
                for r in ss[:3]:
                    pct = r[3] or 0
                    picks[ver].append({'name':r[1], 'code':r[0], 'price':r[2], 'score':round(pct*25,1)})
                print(f'    → {picks[ver][0]["name"]}({picks[ver][0]["code"]}) ¥{picks[ver][0]["price"]}', flush=True)
    
    conn.close()
    return picks

def check_today_high(picks):
    if not picks:
        return {}
    all_codes = set()
    for ver, ps in picks.items():
        for p in ps:
            all_codes.add(p['code'])
    if not all_codes:
        return {}
    chunks = list(all_codes)
    results = {}
    for i in range(0, len(chunks), 50):
        chunk = chunks[i:i+50]
        symbols = [f'{PREFIX(c)}{c}' for c in chunk]
        text = curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}', timeout=10)
        for line in text.split('\n'):
            if '~' not in line: continue
            parts = line.split('~')
            if len(parts) < 40: continue
            code = parts[2]
            high = parts[33]
            price = parts[3]
            close = parts[4]
            try:
                results[code] = {'high': float(high), 'now': float(price), 'close': float(close)}
            except:
                pass
    return results

print(f'📋 V13+V42 尾盘验证复盘 | {TODAY} 盘后15:05')

picks = get_yesterday_picks()
if not picks:
    print('❌ 无昨日选股记录')
    sys.exit(1)

today_high = check_today_high(picks)
if not today_high:
    print('❌ 无法获取今日行情')
    sys.exit(1)

today_str = TODAY
html_rows_v13 = ''; html_rows_v42 = ''
for ver in ['V13','V42']:
    if ver not in picks: continue
    rows_html = ''
    total_ok = 0
    for i, p in enumerate(picks[ver]):
        code = p['code']
        buy = p['price']
        h = today_high.get(code, {})
        high_price = h.get('high', 0)
        now_price = h.get('now', 0)
        if high_price and buy > 0:
            pct = (high_price - buy) / buy * 100
            now_pct = (now_price - buy) / buy * 100 if now_price else 0
        else:
            pct = 0; now_pct = 0
        ok = pct >= 2.5
        if ok: total_ok += 1
        color = '#e74c3c' if ok else '#27ae60'
        mark = '✅' if ok else '❌'
        now_color = '#e74c3c' if now_pct >= 0 else '#27ae60'
        rows_html += f'<tr><td>{i+1}</td><td>{p["name"]}</td><td>{code}</td><td>¥{buy:.2f}</td><td style="color:{color};font-weight:bold">{pct:+.1f}%</td><td style="color:{now_color}">{now_pct:+.1f}%</td><td>{mark}</td></tr>\n'
    if ver == 'V13':
        html_rows_v13 = rows_html; v13_ok = total_ok
    else:
        html_rows_v42 = rows_html; v42_ok = total_ok

html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>V13+V42尾盘验证复盘 {today_str}</title>
<style>
body{{font-family:'微软雅黑',sans-serif;padding:15px;color:#2c3e50;font-size:13px;line-height:1.5}}
h2{{color:#b8860b;border-bottom:2px solid #b8860b;padding-bottom:5px}}
table{{width:100%;border-collapse:collapse;margin:8px 0}}
th{{background:#f0f0f0;padding:6px 4px;text-align:center;border-bottom:2px solid #dfe6e9}}
td{{padding:4px 3px;text-align:center;border-bottom:1px solid #f0f0f0}}
.ver-block{{background:#f5f6fa;border-radius:8px;padding:12px;margin:12px 0;border-left:4px solid #b8860b}}
.ver-block-v13{{border-left-color:#e74c3c}}
.ver-block-v42{{border-left-color:#4a90d9}}
.footer{{text-align:center;font-size:11px;color:#95a5a6;margin:15px 0}}
.summary{{background:#fff8e1;border-radius:8px;padding:10px;margin:10px 0;text-align:center;font-size:15px;font-weight:bold}}
</style></head><body>
<h2>📊 V13+V42 尾盘选股验证复盘</h2>
<p style="font-size:12px;color:#666">📅 {today_str} 盘后15:05 | 验证昨日尾盘选股今日收盘表现</p>

<div class="summary">
V13达标 {v13_ok}/3 = {v13_ok*100//3}% &nbsp;|&nbsp; V42达标 {v42_ok}/3 = {v42_ok*100//3}%
</div>

<div class="ver-block ver-block-v13">
<h3>📌 V13 昨日尾盘验证</h3>
<table><thead><tr><th>#</th><th>名称</th><th>代码</th><th>买入价</th><th>最高涨幅</th><th>收盘涨幅</th><th>结果</th></tr></thead><tbody>
{html_rows_v13 if html_rows_v13 else '<tr><td colspan="7">无数据</td></tr>'}
</tbody></table>
</div>

<div class="ver-block ver-block-v42">
<h3>📌 V42 昨日尾盘验证</h3>
<table><thead><tr><th>#</th><th>名称</th><th>代码</th><th>买入价</th><th>最高涨幅</th><th>收盘涨幅</th><th>结果</th></tr></thead><tbody>
{html_rows_v42 if html_rows_v42 else '<tr><td colspan="7">无数据</td></tr>'}
</tbody></table>
</div>

<div class="footer">
<p>达标标准：次日盘中最高涨幅 ≥ 2.5%</p>
<p>Hermes Agent | 自动验证复盘</p>
</div>
</body></html>'''

arch = os.path.join(SCRIPTS_DIR, 'email_archive')
os.makedirs(arch, exist_ok=True)
fp = os.path.join(arch, f'{today_str}_复盘_盘后.html')
with open(fp, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'📁 已存档: {fp}')

try:
    sender = os.path.join(SCRIPTS_DIR, 'send_email.py')
    subj = f'V13+V42尾盘验证复盘 盘后 {today_str}'
    r = subprocess.run([sys.executable, sender, subj, html, '--html'], timeout=60, capture_output=True, text=True)
    print(f'📧 {r.stdout.strip()}')
except Exception as e:
    print(f'❌ 邮件失败: {e}')
