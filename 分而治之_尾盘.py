"""
分而治之 V4 — 尾盘14:50选股 HTML报告（腾讯实时API版）
4行情分型 × L1~L5分级筛选 + 独立评分
数据源：腾讯实时行情API + K线API
"""
import os, sys, json, re, time, subprocess, importlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)
from send_email import send_email

# ===== 评分模块加载 =====
SCORE_DIR = os.path.join(SCRIPTS_DIR, 'release', '分而治之', '评分')
sys.path.insert(0, SCORE_DIR)
score_mods = {}
for mn in ['真实涨日_评分', '虚涨日_评分', '跌日_评分', '横盘_评分']:
    mfp = os.path.join(SCORE_DIR, f'{mn}.py')
    spec = importlib.util.spec_from_file_location(mn, mfp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    score_mods[mn] = m

HEADERS = {'User-Agent': 'Mozilla/5.0'}
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

def curl_get(url, timeout=10):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url], capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except: return ''

def fetch_kline(code):
    mkt = PREFIX(code)
    kf = os.path.join(CACHE_DIR, f'{mkt}{code}.json')
    if os.path.exists(kf):
        try:
            with open(kf) as f: return json.load(f)
        except: pass
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt}{code},day,,,300,qfq'
    try:
        text = curl_get(url)
        d = json.loads(text) if text.strip().startswith('{') else {}
        sd = d.get('data',{}).get(f'{mkt}{code}',{})
        k = sd.get('qfqday',[])
        if not k:
            for key in sd:
                if isinstance(sd[key],list) and sd[key] and isinstance(sd[key][0],list): k=sd[key]; break
        if not k or len(k) < 80: return None
        recs = [{'date':x[0],'open':float(x[1]),'close':float(x[2]),'high':float(x[3]),'low':float(x[4]),'volume':float(x[5])} for x in k]
        os.makedirs(CACHE_DIR, exist_ok=True)
        json.dump(recs, open(kf,'w'))
        return recs
    except: return None

def calc_indicators(recs, idx):
    df = recs[:idx+1]
    n = len(df)
    if n < 60: return None
    close = [r['close'] for r in df]
    high = [r['high'] for r in df]
    low = [r['low'] for r in df]
    ma5 = sum(close[-5:])/5 if n>=5 else close[-1]
    above_ma5 = 1 if close[-1] > ma5 else 0
    ema12 = close[-1]; ema26 = close[-1]
    if n >= 26:
        for i in range(n-2, max(n-27, -1), -1):
            ema12 = close[i]*2/13 + ema12*11/13
            ema26 = close[i]*2/27 + ema26*25/27
    dif = ema12 - ema26; dea = dif; macd_gap = dif - dea; macd_golden = 1 if dif > 0 else 0
    if n >= 9:
        h9 = max(high[-9:]); l9 = min(low[-9:])
        rsv = (close[-1]-l9)/(h9-l9+1e-10)*100
        k_val = rsv*2/3+50/3; d_val = k_val*2/3+50/3; j_val = 3*k_val-2*d_val
        kdj_golden = 1 if k_val > d_val else 0
    else: k_val = d_val = j_val = 50; kdj_golden = 0
    if n >= 21:
        h21 = max(high[-21:]); l21 = min(low[-21:])
        wr = 100*(h21-close[-1])/(h21-l21+1e-10)
    else: wr = 50
    if n >= 20:
        h20 = max(high[-20:]); l20 = min(low[-20:])
        cl = (close[-1]-l20)/(h20-l20+1e-10)*100
    else: cl = 50
    # 收盘位置（当日）
    today_h = high[-1]; today_l = low[-1]
    pos_in_day = (close[-1]-today_l)/(today_h-today_l+1e-10)*100 if today_h > today_l else 50
    return {
        'above_ma5':above_ma5,'dif_val':round(dif,3),'macd_golden':macd_golden,
        'k_val':round(k_val,1),'d_val':round(d_val,1),'j_val':round(j_val,1),
        'kdj_golden':kdj_golden,'wr':round(wr,1),'cl':round(cl,1),
        'pos_in_day':round(pos_in_day,1),
    }

def get_live_stocks():
    t0 = time.time()
    active = {}
    # 枚举主板代码（用新浪API批量获取）
    all_symbols = []
    for prefix in ['600', '601', '603', '605', '000', '001', '002']:
        codes = [f'{prefix}{i:03d}' for i in range(1000)]
        for c in codes:
            all_symbols.append(('sh' if c.startswith(('6','9')) else 'sz') + c)
    
    # 新浪API批量获取（每批80只）
    from sina_api import sina_realtime
    for i in range(0, len(all_symbols), 80):
        chunk = all_symbols[i:i+80]
        try:
            data = sina_realtime([s[2:] for s in chunk])
            for sym, d in data.items():
                code = sym[2:] if sym.startswith(('sh','sz')) else sym
                nm = d['name']
                if not nm or 'ST' in nm or '*ST' in nm or '退' in nm: continue
                if not IS_MAIN(code): continue
                active[code] = {
                    'name': nm, 'price': d['price'], 'p': d['pct'],
                    'vol_ratio': 1.0, 'hsl': 5.0, 'pe': 0, 'sz': 100.0,
                }
        except:
            pass
    print(f'📡 实时: {len(active)}只 ({time.time()-t0:.0f}s)', flush=True)
    return active

# ===== 加载实时数据 =====
t0 = time.time()
today = datetime.now().strftime('%Y-%m-%d')
stocks_all = get_live_stocks()

# ===== K线指标 =====
codes_list = list(stocks_all.keys())
indicators = {}
with ThreadPoolExecutor(max_workers=16) as pool:
    def fcalc(c):
        r = fetch_kline(c)
        if not r: return c, None
        return c, calc_indicators(r, len(r)-1)
    futs = {pool.submit(fcalc, c): c for c in codes_list[:2000]}
    for fut in as_completed(futs):
        c, ind = fut.result()
        if ind: indicators[c] = ind
print(f'📊 K线: {len(indicators)}只 ({time.time()-t0:.0f}s)')

# ===== 行情分类 =====
def classify_market():
    ps = [s['p'] for c,s in stocks_all.items() if abs(s['p']) < 15]
    vrs = [s['vol_ratio'] for c,s in stocks_all.items() if s['vol_ratio'] > 0]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

market_names = {'real_up': '真实涨日', 'fake_up': '虚涨日', 'down': '跌日', 'flat': '横盘'}
score_name_map = {
    'real_up': '真实涨日_评分', 'fake_up': '虚涨日_评分',
    'down': '跌日_评分', 'flat': '横盘_评分'
}

# L1~L5筛选级别
LEVELS = {
    'real_up': [{'p_min':5.,'p_max':7.99},{'p_min':5.,'p_max':7.99},{'p_min':3.5,'p_max':7.99},{'p_min':2.,'p_max':7.99},{'p_min':-10.,'p_max':7.99}],
    'fake_up': [{'p_min':5.,'p_max':7.99},{'p_min':5.,'p_max':7.99},{'p_min':3.5,'p_max':7.99},{'p_min':2.,'p_max':7.99},{'p_min':-10.,'p_max':7.99}],
    'down': [{'p_min':-7.99,'p_max':-0.1},{'p_min':-10.,'p_max':-0.1},{'p_min':-10.,'p_max':5.},{'p_min':-10.,'p_max':7.},{'p_min':-10.,'p_max':7.99}],
    'flat': [{'p_min':5.,'p_max':7.99},{'p_min':5.,'p_max':7.99},{'p_min':0.5,'p_max':7.99},{'p_min':0.,'p_max':7.99},{'p_min':-10.,'p_max':7.99}],
}

mkt = classify_market()
mkt_name = market_names[mkt]
score_mod = score_mods[score_name_map[mkt]]
score_fn = score_mod.评分
levels = LEVELS[mkt]
print(f"📋 行情: {mkt_name}")

# ===== 选股 + 评分 =====
cand = []
for code, s in stocks_all.items():
    p = s['p']
    if p >= 8: continue
    ind = indicators.get(code)
    if not ind: continue
    
    buy_c = s['price']
    stock_dict = {
        'p': p, 'cl': ind['cl'], 'vr': s['vol_ratio'],
        'dif': ind['dif_val'], 'mg': ind['macd_golden'],
        'a5': ind['above_ma5'], 'wrv': ind['wr'],
        'jv': ind['j_val'], 'kv': ind['k_val'], 'dv': ind['d_val'],
        'kdj_g': ind['kdj_golden'],
        'buy_c': buy_c, 'pos_in_day': ind['pos_in_day'],
    }
    cand.append(stock_dict)

# L1~L5筛选
cand_pool = []
used_level = None
for li, lv in enumerate(levels):
    pool = [s for s in cand if lv['p_min'] <= s['p'] <= lv['p_max'] and s['p'] < 8]
    if len(pool) >= 8:
        cand_pool = pool[:200]; used_level = li+1; break
if not cand_pool:
    cand_pool = [s for s in cand if -10 <= s['p'] < 8][:200]
    used_level = 5

# 评分排序
scored = [(score_fn(s), s) for s in cand_pool]
scored.sort(key=lambda x: -x[0])

# 构建结果
results = []
for score_val, sd in scored:
    code_match = None
    for c, s in stocks_all.items():
        if s['price'] == sd['buy_c']:
            code_match = c
            break
    results.append({
        'nm': sd.get('name', code_match or '?')[:12],
        'code': code_match or '?',
        'buy_c': sd['buy_c'], 'p': sd['p'], 'cl': sd['cl'],
        'vr': sd['vr'], 'hsl': sd.get('hsl', 0), 'sz': sd.get('sz', 0),
        'pe': sd.get('pe', 0), 'score': round(score_val, 1),
        'trend': '📈 多头' if sd['a5'] and sd['dif'] > 0 else ('📊 横盘' if sd['a5'] else '📉 偏弱'),
        'fund': '🔥 放量' if sd['vr'] > 1.2 else ('➡ 正常' if sd['vr'] > 0.6 else '📉 缩量'),
    })

total = len(results)
print(f"🏆 冠军: {results[0]['nm']}({results[0]['code']}) 评分{results[0]['score']} L{used_level}")

# ===== HTML模板 =====
RED = '#e06c75'; GREEN = '#98c379'; GOLD = '#e5c07b'; ORANGE = '#d19a66'
BG = '#1a1b2e'; CARD = '#252640'; LINE = '#3a3b5c'; TEXT = '#b0b0d0'
DIM = '#7a7a9a'; BRIGHT = '#d0d0e8'; HEAD = '#8a8aba'

def pct_format(val_str, suffix='%'):
    try:
        v = float(val_str)
        if v > 0: return f'<span style="color:{RED}">+{v:.1f}{suffix}</span>'
        if v < 0: return f'<span style="color:{GREEN}">{v:.1f}{suffix}</span>'
        return f'<span style="color:{DIM}">0.0{suffix}</span>'
    except: return f'<span style="color:{DIM}">{val_str}</span>'

html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:15px;background:{BG};font-family:-apple-system,'微软雅黑','PingFang SC',sans-serif;color:{TEXT};font-size:13px">
<div style="max-width:680px;margin:0 auto;background:{BG};border-radius:10px">

<div style="text-align:center;padding:22px 15px 14px;border-bottom:2px solid #d4a84b;background:linear-gradient(180deg,#2a2b4e 0%,{BG} 100%)">
<div style="font-size:22px;font-weight:800;letter-spacing:5px;color:#d4a84b;text-shadow:0 0 20px rgba(212,168,75,0.3)">分而治之 · 尾盘选股</div>
<div style="font-size:12px;color:{GOLD};margin-top:6px;letter-spacing:2px">⚡ {mkt_name} · L1~L5分级筛选</div>
<div style="font-size:11px;color:{DIM};margin-top:4px;letter-spacing:1px">{today} · 候选 {total} 只 · 使用L{used_level}</div>
</div>'''

if not results:
    html += f'<div style="padding:30px;text-align:center;color:{DIM}">❌ 今日无候选</div></div></body></html>'
    print(html); sys.exit(0)

html += f'''
<div style="display:flex;gap:8px;margin:12px 0;flex-wrap:wrap;justify-content:center">
<div style="flex:1;min-width:70px;max-width:120px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:20px;font-weight:700;color:#f85149">L{used_level}</div>
<div style="font-size:9px;color:#8b949e;margin-top:2px">筛选级别</div></div>
<div style="flex:1;min-width:70px;max-width:120px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:20px;font-weight:700;color:#58a6ff">实时API</div>
<div style="font-size:9px;color:#8b949e;margin-top:2px">数据来源</div></div>
<div style="flex:1;min-width:70px;max-width:120px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:20px;font-weight:700;color:#d29922">{total}</div>
<div style="font-size:9px;color:#8b949e;margin-top:2px">今日候选</div></div>
</div>'''

# Top3卡片
medals = ['🥇', '🥈', '🥉']
medal_colors = ['#d4a84b', '#a0a0c0', '#8a7a5a']
html += '<div style="padding:10px 0">'
for i, c in enumerate(results[:3]):
    html += f'''
<div style="background:{CARD};border-radius:8px;padding:12px 14px;margin-top:8px;border-left:3px solid {medal_colors[i]}">
<div style="display:flex;align-items:center;justify-content:space-between">
<div style="display:flex;align-items:center;gap:6px">
<span style="font-size:14px">{medals[i]}</span>
<span style="font-size:14px;color:{BRIGHT};font-weight:600">{c['nm'][:8]}</span>
<span style="font-size:11px;color:{DIM}">{c['code'][-6:]}</span></div>
<span style="font-size:11px;color:{DIM}">综合分 {c['score']}</span></div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-top:8px;font-size:11px">
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">买入</div>
<div style="color:{BRIGHT};font-size:12px;font-weight:600">{c['buy_c']:.2f}</div></div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">当日涨</div>
<div style="font-size:12px">{pct_format(str(c['p']))}</div></div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">CL</div>
<div style="font-size:12px;color:{GOLD}">{c['cl']:.0f}%</div></div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">量比</div>
<div style="font-size:12px;color:{BRIGHT}">{c['vr']:.2f}</div></div></div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-top:6px;font-size:11px">
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">换手</span><br><span style="color:{BRIGHT}">{c['hsl']:.1f}%</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">市值</span><br><span style="color:{BRIGHT}">{c['sz']:.0f}亿</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">评分</span><br><span style="color:{GOLD};font-weight:600">{c['score']}</span></div></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:4px;font-size:10px">
<div style="text-align:center;background:{BG}33;border-radius:4px;padding:3px 0">
<span style="color:{DIM}">趋势</span> <span style="color:{GOLD}">{c['trend']}</span></div>
<div style="text-align:center;background:{BG}33;border-radius:4px;padding:3px 0">
<span style="color:{DIM}">资金</span> <span style="color:{ORANGE}">{c['fund']}</span></div></div>
</div>'''

# 全部候选表格
html += f'''
<div style="margin-top:16px;font-size:11px;color:{DIM}">全部候选（{total}只）</div>
<div style="background:{CARD};border-radius:6px;overflow-x:auto;-webkit-overflow-scrolling:touch;margin-top:4px">
<table style="min-width:700px;border-collapse:collapse;font-size:10px;white-space:nowrap">
<tr style="border-bottom:1px solid {LINE}">
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:24px">#</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:64px">名称</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:56px">编码</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:44px">买入价</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:38px">涨%</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">CL%</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">量比</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">换手</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">PE</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:46px">市值亿</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:80px">趋势</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:60px">资金</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:32px">评分</th>
</tr>'''

for i, c in enumerate(results[:30]):
    bg = 'transparent' if i % 2 == 0 else f'{BG}88'
    html += f'<tr style="background:{bg};border-bottom:1px solid {LINE}33">'
    html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">{i+1}</td>'
    html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT};font-size:10px">{c["nm"][:6]}</td>'
    html += f'<td style="padding:5px 2px;text-align:center;color:{DIM};font-size:9px">{c["code"][-6:]}</td>'
    html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c["buy_c"]:.2f}</td>'
    html += f'<td style="padding:5px 2px;text-align:center">{pct_format(str(c["p"]), "")}</td>'
    html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c["cl"]:.0f}</td>'
    html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c["vr"]:.2f}</td>'
    html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c["hsl"]:.1f}</td>'
    pe_str = f'{c["pe"]:.1f}' if isinstance(c['pe'], (int, float)) else '—'
    html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">{pe_str}</td>'
    html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">{c["sz"]:.0f}</td>'
    html += f'<td style="padding:5px 2px;text-align:center;color:{GOLD};font-size:9px">{c["trend"][:12]}</td>'
    fund_s = '🔥' if '放量' in c['fund'] else ('➡' if '正常' in c['fund'] else '📉')
    html += f'<td style="padding:5px 2px;text-align:center;color:{ORANGE};font-size:9px">{fund_s}</td>'
    html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT};font-weight:600">{c["score"]}</td>'
    html += '</tr>'

html += '</table></div>'

html += f'''
<div style="text-align:center;font-size:9px;color:{DIM};padding:12px 0 5px;border-top:1px solid {LINE};margin-top:12px;line-height:1.6">
分而治之 V4 · 4行情×L1~L5分级 · 全部涨&lt;8% · 候选池≥8只<br>
<span style="color:{RED}">红涨</span> · <span style="color:{GREEN}">绿跌</span> · 评分:涨幅+CL+MACD+MA5+量比+换手+WR+J值+收盘位置<br>
今日行情: {mkt_name} · 筛选级别: L{used_level} · 评分: {score_mod.NAME}
</div></div></body></html>'''

# ===== 存档 =====
ARCHIVE_DIR = os.path.expanduser('~/AppData/Local/hermes/email_archive')
os.makedirs(ARCHIVE_DIR, exist_ok=True)
archive_path = os.path.join(ARCHIVE_DIR, f'{today}_分而治之.html')
with open(archive_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'📁 已存档: {archive_path}')

# ===== 发邮件 =====
send_email(['1254628314@qq.com','314913203@qq.com'],
           f'分而治之 · 尾盘选股 {today}', html, html=True)
print(f'✅ 邮件已发送 - {today} 候选{total}只')

# ===== 微信摘要 =====
top3_line = ''
arrows_disp = ['🥇', '🥈', '🥉']
for i, c in enumerate(results[:3]):
    top3_line += f"\n{arrows_disp[i]} {c['nm'][:8]} | 买入{c['buy_c']:.2f} | 当日{c['p']:+.1f}% | 评分{c['score']}"

print(f"\n━━━ 分而治之 {today} ━━━")
print(f"行情: {mkt_name} | 级别: L{used_level} | 候选: {total}只")
print(top3_line)
print(f"\n邮件已发 → 1254628314@qq.com 等3人")
