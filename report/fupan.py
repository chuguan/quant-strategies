#!/usr/bin/env python3
"""V13+V42+V50+1180 尾盘选股验证复盘 — 仅昨天+今天，运行记录最后"""
import subprocess, json, os, sys, sqlite3
from datetime import datetime, timedelta

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/prod')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
TODAY = datetime.now().strftime('%Y-%m-%d')
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'
VER_ORDER = ['1180', 'V54_V50', 'V53_V42', 'V50', 'V42', 'V52_V13', 'V13']

def curl_get(url, timeout=8):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url],capture_output=True,timeout=timeout+5)
        return r.stdout.decode('gbk',errors='replace')
    except: return ''

def get_today_highs(codes):
    results = {}
    for i in range(0, len(codes), 50):
        chunk = codes[i:i+50]
        symbols = [f'{PREFIX(c)}{c}' for c in chunk]
        text = curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}', timeout=10)
        for line in text.split('\n'):
            if '~' not in line: continue
            parts = line.split('~')
            if len(parts) < 40: continue
            try: results[parts[2]] = {'high': float(parts[33])}
            except: pass
    return results

def get_candidates(date, version):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    rows = c.execute('''
        SELECT code, name, price, pct, score, cl, vr, hsl, wr, dif, rank, run_time, market_type, used_level, pool_size
        FROM selection_candidates WHERE version=? AND date=? ORDER BY run_time DESC, rank ASC
    ''', (version, date)).fetchall()
    conn.close()
    if not rows: return None
    # 按run_time分组，每批次10只
    from collections import OrderedDict
    runs = OrderedDict()
    for r in rows:
        rt = r[11] or ''
        if rt not in runs: runs[rt] = []
        if len(runs[rt]) < 10:
            runs[rt].append({
                'code':r[0], 'name':r[1], 'price':r[2], 'p':r[3], 'score':r[4],
                'cl':r[5], 'vr':r[6], 'hsl':r[7], 'wr':r[8], 'dif':r[9]
            })
    # 转成列表
    run_list = []
    for rt, stocks in runs.items():
        r0 = rows[0] if False else None
        # 从原始行取meta
        orig = [x for x in rows if x[11]==rt][0]
        run_list.append({
            'stocks': stocks,
            'run_time': rt,
            'market': orig[12] or '',
            'level': orig[13] or '',
            'pool_size': orig[14] or 0
        })
    return run_list  # 返回多个运行的列表

def get_backup_candidates(date, version):
    db_date = date.replace('-', '')
    db_path = os.path.join(SCRIPTS_DIR, f'backup/v13_quant_{db_date}.db')
    if not os.path.exists(db_path): return None
    conn = sqlite3.connect(db_path, timeout=10)
    c = conn.cursor()
    c.execute("PRAGMA table_info(daily_selection_log)")
    col_names = [ci[1] for ci in c.fetchall()]
    rows = c.execute('SELECT * FROM daily_selection_log WHERE version=? AND date=? ORDER BY rowid', (version, date)).fetchall()
    conn.close()
    if not rows: return None
    rd = dict(zip(col_names, rows[0]))
    top10 = json.loads(rd['top10_json']) if rd.get('top10_json') else []
    stocks = []
    for s in top10:
        stocks.append({
            'code':s.get('code',''), 'name':s.get('name',''), 'price':s.get('price',0),
            'score':s.get('sc',0), 'p':s.get('p',0),
            'cl':s.get('cl',0), 'vr':s.get('vr',0), 'hsl':s.get('hs',0),
            'wr':s.get('wr',0), 'dif':s.get('dif',0)
        })
    return [{
        'stocks': stocks,
        'run_time': rd.get('run_time',''),
        'market': rd.get('market_type',''),
        'level': rd.get('used_level',''),
        'pool_size': rd.get('pool_size',0)
    }]

def get_candidates_wrapper(date, version):
    r = get_candidates(date, version)
    if r: return r
    try:
        return get_backup_candidates(date, version)
    except:
        return None

def get_available_runs():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    rows = c.execute('''
        SELECT date, version, run_time, market_type, used_level, pool_size, COUNT(*) as cnt
        FROM selection_candidates GROUP BY date, version, run_time
        ORDER BY date DESC, run_time DESC
    ''').fetchall()
    conn.close()
    backup_runs = []
    for db_name in ['v13_quant_20260601.db', 'v13_quant_20260602.db']:
        db_path = os.path.join(SCRIPTS_DIR, f'backup/{db_name}')
        if not os.path.exists(db_path): continue
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        try:
            rows2 = c.execute('''
                SELECT date, version, run_time, market_type, used_level, pool_size, 10 as cnt
                FROM daily_selection_log ORDER BY date DESC, run_time DESC
            ''').fetchall()
            backup_runs.extend(rows2)
        except: pass
        conn.close()
    all_runs = list(rows) + backup_runs
    seen = set()
    result = []
    for r in all_runs:
        key = (r[0], r[1], str(r[2])[:16])
        if key not in seen:
            seen.add(key)
            result.append(r)
    result.sort(key=lambda x: (x[0], str(x[2])), reverse=True)
    return result

# ===== 主流程 =====
now = datetime.now()
is_pm = now.hour >= 15
label = '盘后15:05' if is_pm else '午盘11:40'
suffix = '盘后' if is_pm else '午盘'
print(f'V13+V42+V50+1180 尾盘验证复盘 | {TODAY} {label}', flush=True)

# 只取昨天和今天
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
target_dates = [yesterday, TODAY]  # 先昨天(实战复盘)再今天(精研选股)

# 只保留尾盘时段(14:30~15:15)的数据，排除凌晨测试跑
def is_tail_time_run(rt):
    if not rt or len(rt) < 16: return False
    try:
        h, m = int(rt[11:13]), int(rt[14:16])
        return (h == 14 and m >= 30) or (h == 15 and m <= 15)
    except: return False

# 收集数据
day_data = {}
for d in target_dates:
    day_data[d] = {}  # {version: [run1, run2, ...]}
    for v in VER_ORDER:
        runs_list = get_candidates_wrapper(d, v)
        if not runs_list: continue
        # 只保留尾盘时段运行
        filtered = [run for run in runs_list if is_tail_time_run(run['run_time'])]
        if filtered: day_data[d][v] = filtered

# 获取实时行情
all_stocks = set()
for d, vdata in day_data.items():
    for v, runs_list in vdata.items():
        for run in runs_list:
            for s in run['stocks']: all_stocks.add(s['code'])
today_highs = get_today_highs(list(all_stocks)) if all_stocks else {}
print(f'获取到 {len(today_highs)} 只实时行情', flush=True)

# 运行记录
runs = get_available_runs()
print(f'运行记录: {len(runs)}条', flush=True)

# ===== HTML =====
VC = {'1180':'#9b59b6', 'V54_V50':'#00b894', 'V53_V42':'#00cec9', 'V52_V13':'#fdcb6e', 'V50':'#2ecc71', 'V42':'#4a90d9', 'V13':'#e74c3c'}
WEEKDAY = {0:'周一',1:'周二',2:'周三',3:'周四',4:'周五',5:'周六',6:'周日'}
LVL_CN = {'L0':'第一轮','L1':'第二轮','L2':'第三轮','L3':'第四轮','L4':'第五轮'}
NL = chr(10)

def is_tail_time(rt):
    """14:00~15:00尾盘采集时间"""
    if not rt or len(rt) < 16: return False
    try:
        h, m = int(rt[11:13]), int(rt[14:16])
        return (h == 14) or (h == 15 and m == 0)
    except: return False

def gen_verify_block(ver, stocks, highs, market, run_time):
    rows = ''
    cnt = 0
    for i, s in enumerate(stocks):
        code = s['code']; buy = s['price']
        td = highs.get(code, {})
        high = td.get('high', 0)
        pct = (high - buy) / buy * 100 if high and buy else 0
        ok = pct >= 2.5
        if ok: cnt += 1
        mark = '&#9989;' if ok else '&#10060;'
        color = '#e74c3c' if ok else '#27ae60'
        rows += '<tr>'
        rows += f'<td>{mark}</td>'
        rows += f'<td style="color:{color};font-weight:bold">{pct:+.1f}%</td>'
        rows += f'<td>{s["name"]}</td><td>{code}</td>'
        rows += f'<td>{buy:.2f}</td>'
        rows += f'<td>{s.get("p",0):.1f}%</td>'
        rows += f'<td>{s.get("score",0):.0f}</td>'
        rows += f'<td>{s.get("cl",0):.0f}</td>'
        rows += f'<td>{s.get("vr",0):.2f}</td>'
        rows += f'<td>{s.get("hsl",0):.1f}</td>'
        rows += f'<td>{s.get("wr",0):.0f}</td>'
        rows += f'<td>{s.get("dif",0):.1f}</td>'
        rows += '</tr>'
    n = len(stocks)
    pc = cnt * 100 // n if n else 0
    hdr = f'{ver} | {market} | {run_time[11:16]} | 达标 {cnt}/{n}={pc}%'
    return hdr, rows

def gen_today_block(ver, stocks, run_time, market):
    rows = ''
    for i, s in enumerate(stocks):
        medal = '&#129351;' if i==0 else '&#129352;' if i==1 else '&#129353;' if i==2 else f'{i+1}'
        rows += '<tr>'
        rows += f'<td>{medal}</td><td>&#9203;</td><td>&mdash;</td>'
        rows += f'<td>{s["name"]}</td><td>{s["code"]}</td>'
        rows += f'<td>{s.get("price",0):.2f}</td>'
        rows += f'<td>{s.get("p",0):.1f}%</td>'
        rows += f'<td>{s.get("score",0):.0f}</td>'
        rows += f'<td>{s.get("cl",0):.0f}</td>'
        rows += f'<td>{s.get("vr",0):.2f}</td>'
        rows += f'<td>{s.get("hsl",0):.1f}</td>'
        rows += f'<td>{s.get("wr",0):.0f}</td>'
        rows += f'<td>{s.get("dif",0):.1f}</td>'
        rows += '</tr>'
    hdr = f'{ver} | {market} | {run_time[11:16]}'
    return hdr, rows

# ---- 卡片生成 ----
cards = ''
for d in target_dates:
    vdata = day_data.get(d, {})
    if not vdata: continue
    
    try:
        wd = WEEKDAY[datetime.strptime(d, '%Y-%m-%d').weekday()]
        date_label = d + '（' + wd + '）'
    except:
        date_label = d
    
    is_today = (d == TODAY)
    highs = {}
    if not is_today:
        highs = today_highs
    
    inner = ''
    for v in VER_ORDER:
        runs_list = vdata.get(v)
        if not runs_list: continue
        for run in runs_list:
            stocks = run['stocks']
            run_time = run['run_time']
            market = run['market']
            
            if is_today:
                hdr, tbl = gen_today_block(v, stocks, run_time, market)
                th = '<tr><th>#</th><th>结果</th><th>次日最高</th><th>名称</th><th>代码</th><th>价格</th><th>涨幅</th><th>评分</th><th>CL</th><th>VR</th><th>HSL</th><th>WR</th><th>DIF</th></tr>'
            else:
                hdr, tbl = gen_verify_block(v, stocks, highs, market, run_time)
                th = '<tr><th>结果</th><th>次日最高</th><th>名称</th><th>代码</th><th>买入价</th><th>涨幅</th><th>评分</th><th>CL</th><th>VR</th><th>HSL</th><th>WR</th><th>DIF</th></tr>'
            
            color = VC.get(v, '#333')
            block = ''
            block += '<div style="margin:6px 0">'
            block += f'<div style="font-size:12px;font-weight:bold;color:{color};padding:4px 6px;background:#f5f5f5;border-left:3px solid {color}">{hdr}</div>'
            block += '<div style="overflow-x:auto">'
            block += '<table style="border-collapse:collapse;font-size:11px;min-width:500px">'
            block += '<thead>' + th + '</thead>'
            block += '<tbody>' + tbl + '</tbody></table></div></div>'
            inner += block
    
    if inner:
        card_title = (date_label + ' 精研选股') if is_today else (date_label + ' 实战复盘')
        card = ''
        card += '<div style="background:#fafafa;border:1px solid #ddd;border-radius:6px;margin:10px 0">'
        card += '<div style="font-size:14px;font-weight:bold;color:#b8860b;padding:8px 10px;background:#fff8e1;border-bottom:1px solid #ddd">' + card_title + '</div>'
        card += '<div style="padding:6px 8px">' + inner + '</div></div>'
        cards += card

# ---- 运行记录（放最后） ----
def calc_win_rate(date, ver, highs):
    """计算某日某版本的D+1达标率"""
    runs_list = get_candidates_wrapper(date, ver)
    if not runs_list: return '—'
    cnt = 0
    total = 0
    for run in runs_list:
        for s in run['stocks']:
            code = s['code']; buy = s['price']
            td = highs.get(code, {})
            high = td.get('high', 0)
            if high and buy:
                pct = (high - buy) / buy * 100
                if pct >= 2.5: cnt += 1
                total += 1
    if total == 0: return '—'
    return f'{cnt}/{total}={cnt*100//total}%'

run_rows = ''
for r in runs:
    date, ver, rt, market, level, pool, cnt = r[0], r[1], str(r[2])[:16], r[3] or '', r[4] or '', r[5] or 0, r[6] or 0
    if not is_tail_time_run(rt): continue  # 只显示尾盘时段
    lvl_cn = LVL_CN.get(level, level) if level else ''
    rt_style = ''
    if is_tail_time(rt):
        rt_style = ' style="color:#e74c3c;font-weight:bold"'
    # 算胜率（昨日的D+1=今日，用实时行情）
    wr = calc_win_rate(date, ver, today_highs)
    run_rows += f'<tr><td>{date}</td><td>{ver}</td>'
    run_rows += f'<td{rt_style}>{rt}</td>'
    run_rows += f'<td>{wr}</td>'  # 胜率放最前面
    run_rows += f'<td>{market}</td><td>{lvl_cn}</td><td>{pool}</td></tr>'

run_table = ''
if run_rows:
    run_table = f'''
<div style="background:#fafafa;border:1px solid #ddd;border-radius:6px;margin:10px 0">
<div style="font-size:14px;font-weight:bold;color:#b8860b;padding:8px 10px;background:#fff8e1;border-bottom:1px solid #ddd">运行记录</div>
<div style="overflow-x:auto">
<table style="border-collapse:collapse;font-size:12px;min-width:500px">
<thead><tr><th>日期</th><th>版本</th><th>运行时间</th><th>胜率</th><th>行情</th><th>级别</th><th>池大小</th></tr></thead>
<tbody>{run_rows}</tbody>
</table></div></div>'''

# ---- 组装 ----
html = '<!DOCTYPE html>' + NL
html += '<html><head><meta charset="utf-8">'
html += '<title>尾盘实战复盘 ' + TODAY + '</title>' + NL
html += '<style>' + NL
html += 'body{font-family:微软雅黑,sans-serif;padding:10px;color:#2c3e50;font-size:13px;line-height:1.5}' + NL
html += 'h2{color:#b8860b;text-align:center;font-size:18px;margin:8px 0}' + NL
html += 'table{border-collapse:collapse;font-size:11px;width:100%}' + NL
html += 'th{background:#f0f0f0;padding:3px 4px;text-align:center;border-bottom:1px solid #ddd;font-size:10px;white-space:nowrap}' + NL
html += 'td{padding:2px 4px;text-align:center;border-bottom:1px solid #eee}' + NL
html += '.footer{text-align:center;font-size:10px;color:#95a5a6;margin:10px 0}' + NL
html += '</style></head><body>' + NL
html += '<h2>' + TODAY + ' 尾盘实战复盘 (V13+V42+V50+1180+V52_V13+V53_V42+V54_V50)</h2>' + NL
html += '<p style="text-align:center;font-size:11px;color:#999;margin:0 0 10px">' + label + '</p>' + NL
html += cards
html += run_table
html += '<div class="footer"><p>达标标准：次日最高涨幅 &ge; 2.5% | 数据源：sqllite选股日志 + 腾讯实时行情</p></div>' + NL
html += '</body></html>'

arch = os.path.join(SCRIPTS_DIR, 'email_archive')
os.makedirs(arch, exist_ok=True)
fp = os.path.join(arch, TODAY + '_复盘_' + suffix + '.html')
with open(fp, 'w', encoding='utf-8') as f: f.write(html)
print('已存档: ' + fp, flush=True)

try:
    sys.path.insert(0, os.path.join(SCRIPTS_DIR, 'lib')); sys.path.insert(0, SCRIPTS_DIR)
    from send_email import send_email
    subj = '【' + suffix + '自动化复盘】V13+V42+V50+1180尾盘验证复盘 ' + suffix + ' ' + TODAY
    ok = send_email(subject=subj, body=html, html=True, force=True)
    print(f'邮件: {"✅成功" if ok else "❌失败"}', flush=True)
except Exception as e:
    print('邮件失败: ' + str(e), flush=True)
