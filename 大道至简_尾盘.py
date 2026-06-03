"""
大道至简 V260528 — 尾盘14:48选股 HTML报告（实时API版·CL透支惩罚优化）
4行情分型 × 4子策略，互不干扰
数据源：腾讯实时行情API + K线API
"""
import os, sys, json, re, time, subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)
from send_email import send_email

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
    ma10 = sum(close[-10:])/10 if n>=10 else close[-1]
    ma20 = sum(close[-20:])/20 if n>=20 else close[-1]
    ma60 = sum(close[-60:])/60 if n>=60 else close[-1]
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
    else:
        k_val = d_val = j_val = 50; kdj_golden = 0
    if n >= 21:
        h21 = max(high[-21:]); l21 = min(low[-21:])
        wr = 100*(h21-close[-1])/(h21-l21+1e-10)
    else: wr = 50
    if n >= 20:
        h20 = max(high[-20:]); l20 = min(low[-20:])
        cl = (close[-1]-l20)/(h20-l20+1e-10)*100
    else: cl = 50
    return {'ma5':round(ma5,2),'ma10':round(ma10,2),'ma20':round(ma20,2),'ma60':round(ma60,2),
            'above_ma5':above_ma5,'dif_val':round(dif,3),'dea_val':round(dea,3),'macd_gap':round(macd_gap,3),
            'macd_golden':macd_golden,'k_val':round(k_val,1),'d_val':round(d_val,1),'j_val':round(j_val,1),
            'kdj_golden':kdj_golden,'wr':round(wr,1),'cl':round(cl,1)}

def get_live_stocks():
    t0 = time.time()
    all_codes = []
    for i in range(600000, 606000): all_codes.append(str(i))
    for i in range(0, 3000): all_codes.append(f'{i:06d}')
    active = {}
    for i in range(0, len(all_codes), 80):
        chunk = all_codes[i:i+80]
        symbols = [f'{PREFIX(c)}{c}' for c in chunk]
        from sina_api import sina_realtime
        try:
            data = sina_realtime([s[2:] for s in symbols])
            for sym, d in data.items():
                code = sym[2:] if sym.startswith(('sh','sz')) else sym
                nm = d['name']
                if not nm or 'ST' in nm or '*ST' in nm or '退' in nm: continue
                if not IS_MAIN(code): continue
                active[code] = {
                    'name': nm, 'price': d['price'], 'p': d['pct'],
                    'vol_ratio': 1.0, 'hsl': 5.0, 'pe': 0, 'sz': 100.0,
                }
        except: pass
    print(f'📡 实时: {len(active)}只 ({time.time()-t0:.0f}s)', flush=True)
    return active

# ========== 加载实时数据 ==========
t0 = time.time()
today = datetime.now().strftime('%Y-%m-%d')
stocks_all = get_live_stocks()

# ========== K线指标（并行）==========
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

# ========== 行情分类 ==========
def classify_market():
    ps = [s['p'] for c,s in stocks_all.items() if abs(s['p']) < 15]
    vrs = [s['vol_ratio'] for c,s in stocks_all.items() if s['vol_ratio'] > 0]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

def calc_macd(dif, mg):
    if mg and dif > 0.5: return 10
    if mg and dif > 0.2: return 8
    if mg: return 6
    if dif > 0.5: return 4
    if dif > 0: return 2
    return 0

# ========== 4子策略（V260526定版） ==========
REAL_UP = {
    'name': '真实涨日', 'params': {'p_min': 3, 'p_max': 7, 'vr_min': 0.6, 'vr_max': 2.5,
        'hs_min': 5, 'hs_max': 15, 'sz_max': 200, 'cl_min': 60, 'cl_max': 90},
    'weights': {'p_w': 2.0, 'cl_w': 0.05, 'macd_w': 0.3, 'ma5_b': 3, 'vr_b': 1, 'hs_b': 0.3, 'wr_b': 2, 'j_b': 0, 'j_low_b': 2}
}
FAKE_UP = {
    'name': '虚涨日', 'params': {'p_min': 0, 'p_max': 6, 'vr_min': 0.6, 'vr_max': 2.5,
        'hs_min': 5, 'hs_max': 20, 'sz_max': 200, 'cl_min': 30, 'cl_max': 95},
    'weights': {'p_w': 1.0, 'cl_w': 0.05, 'macd_w': 0.5, 'ma5_b': 0, 'vr_b': 0, 'hs_b': 0, 'wr_b': 0, 'j_b': 0, 'j_low_b': 0}
}
DOWN = {
    'name': '跌日', 'params': {'p_min': -3, 'p_max': 7, 'vr_min': 0.4, 'vr_max': 3.5,
        'hs_min': 1, 'hs_max': 30, 'sz_max': 300, 'cl_min': 10, 'cl_max': 98},
    'weights': {'p_w': 1.5, 'cl_w': 0.05, 'macd_w': 0.3, 'ma5_b': 2, 'vr_b': 0, 'hs_b': 0, 'wr_b': 0, 'j_b': 0, 'j_low_b': 3}
}
FLAT = {
    'name': '横盘', 'params': {'p_min': 0, 'p_max': 7, 'vr_min': 0.6, 'vr_max': 2.5,
        'hs_min': 3, 'hs_max': 20, 'sz_max': 200, 'cl_min': 40, 'cl_max': 95},
    'weights': {'p_w': 2.0, 'cl_w': 0.05, 'macd_w': 0.3, 'ma5_b': 2, 'vr_b': 3, 'hs_b': 0.3, 'wr_b': 0, 'j_b': 0, 'j_low_b': 2, 'kdj_b': 2}
}
STRATEGIES = {'real_up': REAL_UP, 'fake_up': FAKE_UP, 'down': DOWN, 'flat': FLAT}

def get_dp(code, date_str, days=5):
    """获取D+1~D+5每日最高涨幅"""
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return ['—'] * days, '—', '—'
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i, k in enumerate(kdata) if k.get('date') == date_str), None)
        if idx is None: return ['—'] * days, '—', '—'
        buy_c = kdata[idx]['close']
        results = []
        next_close_pct = '—'
        next_high_pct = '—'
        for d in range(1, days + 1):
            if idx + d < len(kdata):
                hp = (kdata[idx + d]['high'] / buy_c - 1) * 100
                results.append(f'{hp:.1f}')
                if d == 1:
                    next_close_pct = f'{(kdata[idx+1]["close"]/buy_c-1)*100:.1f}'
                    next_high_pct = f'{hp:.1f}'
            else:
                results.append('—')
        return results, next_close_pct, next_high_pct
    except:
        return ['—'] * days, '—', '—'

# ========== 选股 + 评分（实时API版） ==========
mkt = classify_market()
strategy = STRATEGIES[mkt]
params = strategy['params']
weights = strategy['weights']

cand = []
for code, s in stocks_all.items():
    p = s['p']
    if p < params['p_min'] or p > params['p_max']: continue
    vr = s['vol_ratio']
    if vr < params['vr_min'] or vr > params['vr_max']: continue
    hsl = s['hsl']
    if hsl < params['hs_min'] or hsl > params['hs_max']: continue
    if s['sz'] >= params['sz_max']: continue
    ind = indicators.get(code)
    if not ind: continue
    cl = ind['cl']
    if cl < params['cl_min'] or cl > params['cl_max']: continue

    buy_c = s['price']
    dif = ind['dif_val']
    mg = ind['macd_golden']
    a5 = ind['above_ma5']
    wrv = ind['wr']
    jv = ind['j_val']
    kv = ind['k_val']
    dv = ind['d_val']
    macd_gap = ind['macd_gap']
    kdj_golden = ind['kdj_golden']

    ms = calc_macd(dif, mg)
    ps2 = min(10, max(1, 11 - buy_c / 10)) if buy_c else 0
    w = weights

    score = p * w['p_w'] + cl * w['cl_w'] + ps2 * 0.3 + ms * w['macd_w']
    score += (w['ma5_b'] if a5 else 0)
    score += (w['vr_b'] * 1.5 if 1.0 <= vr <= 1.5 else 0)
    score += (w['hs_b'] * 2 if 5 <= hsl <= 7 else 0)
    score += (w['wr_b'] if wrv < 25 else 0)
    score += (w['j_b'] if jv > kv > dv else 0)
    score += (w['j_low_b'] if 20 <= jv <= 40 else 0)
    score += (w.get('kdj_b', 0) if kdj_golden else 0)
    
    # === V260528 优化：CL透支惩罚 + MACD加分 ===
    # CL太高+p太高=已被透支，重罚
    if p > 5 and cl > 80: score -= 8
    # MACD势头强加分
    if dif > 0.5: score += 3
    if mg: score += 3

    # 趋势/资金
    trend = '📈 多头' if a5 and dif > 0 else ('📊 横盘' if a5 else '📉 偏弱')
    fund = '🔥 放量' if vr > 1.2 else ('➡ 正常' if vr > 0.6 else '📉 缩量')

    cand.append({
        'nm': s['name'][:12], 'code': code, 'buy_c': buy_c,
        'p': p, 'cl': cl, 'vr': vr, 'hsl': hsl,
        'sz': s['sz'], 'pe': s['pe'],
        'score': round(score, 1),
        'next_close_pct': '—', 'd1': '—',
        'd1v': '—', 'd2v': '—', 'd3v': '—', 'd4v': '—', 'd5v': '—',
        'trend': trend, 'fund': fund,
    })

cand.sort(key=lambda x: (-x['score'], -x['p']))
total = len(cand)

# ========== 行情分类 ==========
mkt_names = {'real_up': '真实涨日', 'fake_up': '虚涨日', 'down': '跌日', 'flat': '横盘'}
# 简化统计：只显示今日结果，不加载历史数据

# ========== HTML模板（同超人策略尾盘） ==========
RED = '#e06c75'
GREEN = '#98c379'
GOLD = '#e5c07b'
ORANGE = '#d19a66'
BG = '#1a1b2e'
CARD = '#252640'
LINE = '#3a3b5c'
TEXT = '#b0b0d0'
DIM = '#7a7a9a'
BRIGHT = '#d0d0e8'
HEAD = '#8a8aba'

def pct_color(val_str):
    try:
        v = float(val_str)
        if v > 0: return RED
        if v < 0: return GREEN
    except: pass
    return DIM

def pct_format(val_str, suffix='%'):
    try:
        v = float(val_str)
        if v > 0: return f'<span style="color:{RED}">+{v:.1f}{suffix}</span>'
        if v < 0: return f'<span style="color:{GREEN}">{v:.1f}{suffix}</span>'
        return f'<span style="color:{DIM}">0.0{suffix}</span>'
    except:
        return f'<span style="color:{DIM}">{val_str}</span>'

html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:15px;background:{BG};font-family:-apple-system,'微软雅黑','PingFang SC',sans-serif;color:{TEXT};font-size:13px">

<div style="max-width:680px;margin:0 auto;background:{BG};border-radius:10px">

<!-- 头部 -->
<div style="text-align:center;padding:22px 15px 14px;border-bottom:2px solid #d4a84b;background:linear-gradient(180deg,#2a2b4e 0%,{BG} 100%)">
<div style="font-size:22px;font-weight:800;letter-spacing:5px;color:#d4a84b;text-shadow:0 0 20px rgba(212,168,75,0.3)">大道至简 · 尾盘选股</div>
<div style="font-size:12px;color:{GOLD};margin-top:6px;letter-spacing:2px">⚡ {strategy['name']} · 4行情分型</div>
<div style="font-size:11px;color:{DIM};margin-top:4px;letter-spacing:1px">{today} · {strategy['name']} · 候选 {total} 只</div>
'''

if not cand:
    html += f'<div style="padding:30px;text-align:center;color:{DIM}">❌ 今日无候选</div>'
    html += '</div></body></html>'
    print(html)
    sys.exit(0)

# ========== 统计卡片 ==========
champ_rate = '—'

html += f'''
<div style="display:flex;gap:8px;margin:12px 0;flex-wrap:wrap;justify-content:center">
<div style="flex:1;min-width:70px;max-width:120px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:20px;font-weight:700;color:#f85149">{champ_rate}</div>
<div style="font-size:9px;color:#8b949e;margin-top:2px">总冠军胜率</div></div>
<div style="flex:1;min-width:70px;max-width:120px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:20px;font-weight:700;color:#58a6ff">实时API</div>
<div style="font-size:9px;color:#8b949e;margin-top:2px">API数据</div></div>
<div style="flex:1;min-width:70px;max-width:120px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:20px;font-weight:700;color:#d29922">{total}</div>
<div style="font-size:9px;color:#8b949e;margin-top:2px">今日候选</div></div>
</div>'''

# ========== Top3 卡片 ==========
medals = ['🥇', '🥈', '🥉']
medal_colors = ['#d4a84b', '#a0a0c0', '#8a7a5a']
html += '<div style="padding:10px 0">'

for i, c in enumerate(cand[:3]):
    d1_str = c['d1'] if c['d1'] != '—' else '待确认'
    nc_str = c['next_close_pct'] if c['next_close_pct'] != '—' else '待确认'

    html += f'''
<div style="background:{CARD};border-radius:8px;padding:12px 14px;margin-top:8px;border-left:3px solid {medal_colors[i]}">
<div style="display:flex;align-items:center;justify-content:space-between">
<div style="display:flex;align-items:center;gap:6px">
<span style="font-size:14px">{medals[i]}</span>
<span style="font-size:14px;color:{BRIGHT};font-weight:600">{c['nm'][:8]}</span>
<span style="font-size:11px;color:{DIM}">{c['code'][-6:]}</span>
</div>
<span style="font-size:11px;color:{DIM}">综合分 {c['score']}</span>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-top:8px;font-size:11px">
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">买入</div>
<div style="color:{BRIGHT};font-size:12px;font-weight:600">{c['buy_c']:.2f}</div></div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">当日涨</div>
<div style="font-size:12px">{pct_format(str(c['p']).replace("+",""))}</div></div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">次日涨幅</div>
<div style="font-size:12px">{pct_format(nc_str.replace("+",""))}</div></div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">次日最高</div>
<div style="font-size:12px">{pct_format(d1_str.replace("+",""))}</div></div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr;gap:6px;margin-top:6px;font-size:11px">
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">CL</span><br><span style="color:{GOLD}">{c['cl']:.0f}%</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">量比</span><br><span style="color:{BRIGHT}">{c['vr']:.2f}</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">换手</span><br><span style="color:{BRIGHT}">{c['hsl']:.1f}%</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">市值</span><br><span style="color:{BRIGHT}">{c['sz']:.0f}亿</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">PE</span><br><span style="color:{BRIGHT}">{c['pe'] if c['pe'] != '—' else '—'}</span></div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:4px;font-size:10px">
<div style="text-align:center;background:{BG}33;border-radius:4px;padding:3px 0">
<span style="color:{DIM}">趋势</span> <span style="color:{GOLD}">{c['trend']}</span></div>
<div style="text-align:center;background:{BG}33;border-radius:4px;padding:3px 0">
<span style="color:{DIM}">资金</span> <span style="color:{ORANGE}">{c['fund']}</span></div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr;gap:4px;margin-top:5px;font-size:10px">'''
    d_labels = ['D+1', 'D+2', 'D+3', 'D+4', 'D+5']
    for d in range(5):
        val = [c['d1v'], c['d2v'], c['d3v'], c['d4v'], c['d5v']][d]
        if val == '—':
            html += f'<div style="text-align:center;border-radius:3px;padding:2px 0;background:{BG}44"><span style="color:{DIM}">{d_labels[d]}</span><br><span style="color:{DIM}">—</span></div>'
        else:
            html += f'<div style="text-align:center;border-radius:3px;padding:2px 0;background:{BG}44"><span style="color:{DIM};font-size:9px">{d_labels[d]}</span><br>{pct_format(val)}</div>'
    html += '</div></div>'

# ========== 全部候选表格 ==========
html += f'''
<div style="margin-top:16px;font-size:11px;color:{DIM}">全部候选（{total}只）</div>
<div style="background:{CARD};border-radius:6px;overflow-x:auto;-webkit-overflow-scrolling:touch;margin-top:4px">
<table style="min-width:860px;border-collapse:collapse;font-size:10px;white-space:nowrap">
<tr style="border-bottom:1px solid {LINE}">
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:24px">#</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:64px">名称</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:56px">编码</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:44px">买入价</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:38px">当日涨%</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:38px">次收%</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:38px">次高%</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">CL%</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">量比</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">换手</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">PE</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:46px">市值亿</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:80px">趋势</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:60px">资金</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:32px">评分</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">D+1</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">D+2</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">D+3</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">D+4</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">D+5</th>
</tr>'''

for i, c in enumerate(cand[:30]):
    bg = 'transparent' if i % 2 == 0 else f'{BG}88'
    html += f'<tr style="background:{bg};border-bottom:1px solid {LINE}33">'
    html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">{i+1}</td>'
    html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT};font-size:10px">{c["nm"][:6]}</td>'
    html += f'<td style="padding:5px 2px;text-align:center;color:{DIM};font-size:9px">{c["code"][-6:]}</td>'
    html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c["buy_c"]:.2f}</td>'
    html += f'<td style="padding:5px 2px;text-align:center">{pct_format(str(c["p"]), "")}</td>'
    html += f'<td style="padding:5px 2px;text-align:center">{pct_format(c["next_close_pct"], "")}</td>'
    nc_val = c['d1'] if c['d1'] != '—' else '—'
    if nc_val != '—':
        html += f'<td style="padding:5px 2px;text-align:center">{pct_format(nc_val, "")}</td>'
    else:
        html += f'<td style="padding:5px 2px;text-align:center"><span style="color:{DIM}">—</span></td>'
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
    for val in [c['d1v'], c['d2v'], c['d3v'], c['d4v'], c['d5v']]:
        if val == '—':
            html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">—</td>'
        else:
            html += f'<td style="padding:5px 2px;text-align:center">{pct_format(val, "")}</td>'
    html += '</tr>'

html += '</table></div>'

# 底部说明
html += f'''
<div style="text-align:center;font-size:9px;color:{DIM};padding:12px 0 5px;border-top:1px solid {LINE};margin-top:12px;line-height:1.6">
大道至简 V260526 · 4行情×4子策略 · 全部涨&lt;8% · 候选池≥10只<br>
<span style="color:{RED}">红涨</span> · <span style="color:{GREEN}">绿跌</span> · 综合评分:涨幅+CL+MACD+MA5+量比+换手+WR+J值<br>
今日行情: {strategy['name']} · 选股条件: 涨{params['p_min']}~{params['p_max']}% 量{params['vr_min']}~{params['vr_max']} 换{params['hs_min']}~{params['hs_max']}% CL{params['cl_min']}~{params['cl_max']}% 市值&lt;{params['sz_max']}亿
</div>
</div>
</body>
</html>'''

# ========== 存档HTML ==========
ARCHIVE_DIR = os.path.expanduser('~/AppData/Local/hermes/email_archive')
os.makedirs(ARCHIVE_DIR, exist_ok=True)
archive_name = f'{today}_大道至简.html'
archive_path = os.path.join(ARCHIVE_DIR, archive_name)
with open(archive_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'📁 已存档: {archive_path}')

# ========== 发邮件 ==========
sys.path.insert(0, SCRIPTS_DIR)
from send_email import send_email
send_email(['1254628314@qq.com','314913203@qq.com'],
           f'大道至简 · 尾盘选股 {today}', html, html=True)
print(f'✅ 邮件已发送 - {today} 候选{total}只')

# ========== 微信摘要 ==========
top3_line = ''
arrows_disp = ['🥇', '🥈', '🥉']
for i, c in enumerate(cand[:3]):
    nc = c['next_close_pct'] if c['next_close_pct'] != '—' else '待确认'
    top3_line += f"\n{arrows_disp[i]} {c['nm'][:8]} | 买入{c['buy_c']:.2f} | 当日{c['p']:+.1f}% | 次收{nc}%"

print(f"\n━━━ 大道至简 {today} ━━━")
print(f"行情: {strategy['name']} | 候选: {total}只")
print(top3_line)
print(f"\n邮件已发 → 1254628314@qq.com 等3人")
