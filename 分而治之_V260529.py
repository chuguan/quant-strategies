"""
分而治之 V260529 — 按基本准则重构
- 4行情×4独立评分（从子策略文件动态加载）
- L→L5分级（各策略独立放宽参数）
- >8只门槛，不满弃权
- 各行情最优版本：
  横盘=V260529-07(macd_w0.2+vr_b4) / 跌日=V260529-08(p_w1.0)
  真实涨日=V260529-05(p_w1.5) / 虚涨日=原始极简
- 注意：calc_historical_win_rate已弃用（调score_stock不存在），
  统一测试请用 分而治之_统一测试.py
"""
import os, sys, json, re, time, subprocess, pickle
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)

HEADERS = {'User-Agent': 'Mozilla/5.0'}
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

LEVEL_NAMES = ['L', 'L1', 'L2', 'L3', 'L4', 'L5']  # 6级

# ========== 子策略定义（从各子策略文件加载LEVELS） ==========
SUB_STRATEGIES = {
    'real_up': {'module': '分而治之_真实涨日_评分策略', 'name': '真实涨日', 'score_fn': 'score'},
    'fake_up': {'module': '分而治之_虚涨日_评分策略', 'name': '虚涨日', 'score_fn': 'score'},
    'down': {'module': '分而治之_跌日_评分策略', 'name': '跌日', 'score_fn': 'score'},
    'flat': {'module': '分而治之_横盘_评分策略', 'name': '横盘', 'score_fn': 'score'},
}

def get_sub_strategy(mkt_key):
    """加载子策略模块获取LEVELS和评分参数"""
    import importlib
    info = SUB_STRATEGIES[mkt_key]
    mod = importlib.import_module(info['module'])
    levels = mod.LEVELS
    params = mod.PARAMS.copy() if hasattr(mod, 'PARAMS') else {}
    # 将L0重命名为L，并添加L5
    renamed = []
    for lv in levels:
        name = lv['name']
        if name == 'L0':
            name = 'L'
        renamed.append({**lv, 'name': name})
    # 手动添加L5（最宽松）——从L4继续放宽
    if levels:
        l4 = levels[-1]
        l5 = {
            'name': 'L5',
            'p_min': max(l4['p_min']-2, -8),
            'p_max': min(l4['p_max']+1, 8),
            'vr_min': max(l4['vr_min']-0.1, 0.1),
            'vr_max': l4['vr_max']+1.0,
            'hs_min': max(l4['hs_min']-0.2, 0.1),
            'hs_max': l4['hs_max']+10,
            'sz_max': l4['sz_max']+200,
            'cl_min': max(l4['cl_min']-10, 0),
            'cl_max': min(l4['cl_max']+2, 100),
        }
        renamed.append(l5)
    return renamed, info['name'], params

# ========== V260528 公共评分基准（已迁移至子策略文件） ==========
# 各行情评分权重从子策略文件加载，不再硬编码

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
    df = recs[:idx+1]; n = len(df)
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
    dif = ema12 - ema26; dea = dif; mg = 1 if dif > 0 else 0
    if n >= 9:
        h9 = max(high[-9:]); l9 = min(low[-9:])
        rsv = (close[-1]-l9)/(h9-l9+1e-10)*100
        k_val = rsv*2/3+50/3; d_val = k_val*2/3+50/3; j_val = 3*k_val-2*d_val
        kdj_golden = 1 if k_val > d_val else 0
    else: k_val=d_val=j_val=50; kdj_golden=0
    if n >= 21:
        h21 = max(high[-21:]); l21 = min(low[-21:])
        wr = 100*(h21-close[-1])/(h21-l21+1e-10)
    else: wr=50
    if n >= 20:
        h20 = max(high[-20:]); l20 = min(low[-20:])
        cl = (close[-1]-l20)/(h20-l20+1e-10)*100
    else: cl=50
    return {'ma5':round(ma5,2),'ma10':round(ma10,2),'ma20':round(ma20,2),'ma60':round(ma60,2),
            'above_ma5':above_ma5,'dif_val':round(dif,3),'dea_val':round(dea,3),
            'macd_golden':mg,'k_val':round(k_val,1),'d_val':round(d_val,1),'j_val':round(j_val,1),
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
        text = curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}', timeout=8)
        for line in text.split('\n'):
            if '~' not in line: continue
            parts = line.split('~')
            if len(parts) < 40: continue
            try:
                nm = parts[1]; code = parts[2]
                if not nm or 'ST' in nm or '*ST' in nm or '退' in nm: continue
                if not IS_MAIN(code): continue
                price = float(parts[3]); prev_c = float(parts[4])
                pct = round((price/prev_c-1)*100, 2) if prev_c else 0
                vol_r = float(parts[38]) if parts[38] else 0
                hsl = 0
                try: hsl = float(parts[46]) if parts[46] and float(parts[46]) < 100 else 0
                except: pass
                pe = float(parts[39]) if parts[39] else 0
                sz = 0
                try: sz = float(parts[44])/1e8 if parts[44] else 0
                except: pass
                active[code] = {'name':nm,'price':price,'p':pct,'vol_ratio':vol_r,'hsl':hsl,'pe':pe,'sz':sz}
            except: pass
    print(f'📡 实时: {len(active)}只 ({time.time()-t0:.0f}s)', flush=True)
    return active

def classify_market(stocks_all):
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

def filter_by_level(stocks_all, indicators, level):
    """用单级参数过滤"""
    pool = []
    for code, s in stocks_all.items():
        p = s['p']
        if p < level['p_min'] or p > level['p_max']: continue
        if p >= 8: continue
        vr = s['vol_ratio']
        if vr < level['vr_min'] or vr > level['vr_max']: continue
        hsl = s['hsl']
        if hsl < level['hs_min'] or hsl > level['hs_max']: continue
        if s['sz'] >= level['sz_max']: continue
        ind = indicators.get(code)
        if not ind: continue
        cl = ind['cl']
        if cl < level['cl_min'] or cl > level['cl_max']: continue
        pool.append({'code':code, 'nm':s['name'], 'price':s['price'], 'p':p, 'vr':vr, 'hsl':hsl,
                      'sz':s['sz'], 'pe':s['pe'], 'ind':ind})
    return pool

def score_stock(item, module, fn_name):
    """调子策略模块的V5通用评分函数"""
    score_fn = getattr(module, fn_name)
    stock = {
        'p': item['p'], 'cl': item['ind']['cl'],
        'vr': item['vr'], 'hsl': item['hsl'],
        'dif': item['ind']['dif_val'], 'mg': item['ind']['macd_golden'],
        'a5': item['ind']['above_ma5'], 'wrv': item['ind']['wr'],
        'jv': item['ind']['j_val'], 'kv': item['ind']['k_val'],
        'dv': item['ind']['d_val'], 'kdj_g': item['ind']['kdj_golden'],
        'buy_c': item['price'], 'pos_in_day': item['ind'].get('pos_in_day', 50),
    }
    return score_fn(stock)

def get_dp(code, date_str, days=5):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp):
        mkt = PREFIX(code)
        fp2 = os.path.join(CACHE_DIR, f'{mkt}{code}.json')
        if os.path.exists(fp2): fp = fp2
        else: return ['—']*days, '—', '—'
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i, k in enumerate(kdata) if k.get('date') == date_str), None)
        if idx is None: return ['—']*days, '—', '—'
        buy_c = kdata[idx]['close']
        results = []
        next_close = '—'; next_high = '—'
        for d in range(1, days+1):
            if idx + d < len(kdata):
                hp = (kdata[idx+d]['high']/buy_c-1)*100
                results.append(f'{hp:.1f}')
                if d == 1:
                    next_close = f'{(kdata[idx+1]["close"]/buy_c-1)*100:.1f}'
                    next_high = f'{hp:.1f}'
            else: results.append('—')
        return results, next_close, next_high
    except: return ['—']*days, '—', '—'

# ========== 历史胜率核算（用cache数据） ==========
def calc_historical_win_rate(mkt_key, module, levels, max_days=333):
    """回测该策略的历史冠军胜率（用子策略模块的评分函数）"""
    try:
        d = pickle.load(open(os.path.join(SCRIPTS_DIR, 'big_cache_full.pkl'), 'rb'))
        data, real, names = d['data'], d['real'], d['names']
        # 验证缓存完整性：应有至少3400只唯一股票才算完整
        all_codes = set()
        for dt in list(data.keys())[:5]:
            for s in data[dt]:
                all_codes.add(s.get('code',''))
        if len(all_codes) < 3100:  # 缓存不完整，跳过
            return None
    except:
        return None
    dates = sorted(x for x in data.keys() if '2025-01-01' <= x < '2026-06-01')[-max_days:]
    
    def classify_mkt_hist(stocks):
        if not stocks: return 'flat'
        ps = [s.get('p',0) or 0 for s in stocks]
        vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
        if not ps: return 'flat'
        avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
        hot = sum(1 for p in ps if 5 <= p <= 8)
        if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
        if avg_p < -0.5: return 'down'
        return 'flat'
    
    # 从子策略模块获取评分函数名
    fn_name = 'score'
    score_fn = getattr(module, fn_name, None)
    if not score_fn:
        print(f'  ⚠️ 找不到评分函数')
        return None
    
    wins = 0; total = 0
    for dt in dates:
        stocks = data.get(dt, [])
        if not stocks: continue
        m = classify_mkt_hist(stocks)
        if m != mkt_key: continue
        
        pool = None
        for lv in levels:
            pool = []
            for s in stocks:
                code = s.get('code',''); p = s.get('p',0) or 0
                if p < lv['p_min'] or p > lv['p_max']: continue
                if p >= 8: continue
                vr = s.get('vol_ratio',0) or 0
                if vr < lv['vr_min'] or vr > lv['vr_max']: continue
                ri = real.get(code)
                if not ri: continue
                hsl = (ri.get('hsl',0) or 0)
                if hsl < lv['hs_min'] or hsl > lv['hs_max']: continue
                if (ri.get('shizhi',0) or 0) >= lv['sz_max']: continue
                nm = names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl = s.get('cl',0)
                if cl < lv['cl_min'] or cl > lv['cl_max']: continue
                if (s.get('n',0) or 0) <= 0: continue
                pool.append(s)
            if len(pool) > 8: break
            pool = None
        if not pool or len(pool) <= 8: continue
        
        scored = []
        for s in pool:
            stock = {
                'p': s.get('p',0) or 0, 'cl': s.get('cl',0),
                'vr': s.get('vol_ratio',0) or 0,
                'hsl': (real.get(s['code'],{}).get('hsl',0) or 0),
                'dif': s.get('dif_val',0) or 0, 'mg': s.get('macd_golden',0),
                'a5': s.get('above_ma5',0) or 0, 'wrv': s.get('wr_val',0) or 50,
                'jv': s.get('j_val',0) or 0, 'kv': s.get('k_val',0) or 0,
                'dv': s.get('d_val',0) or 0,
                'kdj_g': s.get('kdj_golden',0) or 0,
                'buy_c': s.get('close',0) or 0,
                'pos_in_day': s.get('pos_in_day', 50) or 50,
            }
            sc = score_fn(stock)
            nh = s.get('n',0) or 0
            scored.append({'sc':sc, 'nh':nh})
        
        if not scored: continue
        scored.sort(key=lambda x: (-x['sc']))
        total += 1
        if scored[0]['nh'] >= 2.5: wins += 1
    
    if total == 0: return None
    return round(wins*100/total, 1), wins, total


# ========== 主流程 ==========
t0 = time.time()
today = datetime.now().strftime('%Y-%m-%d')

# 1. 加载实时数据
stocks_all = get_live_stocks()

# 2. K线指标
codes_list = list(stocks_all.keys())
indicators = {}
with ThreadPoolExecutor(max_workers=16) as pool:
    def fcalc(c):
        r = fetch_kline(c)
        if not r: return c, None
        return c, calc_indicators(r, len(r)-1)
    futs = {pool.submit(fcalc, c): c for c in codes_list[:3000]}
    for fut in as_completed(futs):
        c, ind = fut.result()
        if ind: indicators[c] = ind
print(f'📊 K线: {len(indicators)}只 ({time.time()-t0:.0f}s)', flush=True)

# 3. 行情分类
mkt = classify_market(stocks_all)
import importlib
SUB_MODULE = importlib.import_module(SUB_STRATEGIES[mkt]['module'])
SCORE_FN = SUB_STRATEGIES[mkt]['score_fn']
levels, mkt_name, weights = get_sub_strategy(mkt)
mkt_names = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
mkt_display = mkt_names.get(mkt, mkt)

print(f'📌 行情: {mkt_display}', flush=True)

# 4. L→L5分级筛选
used_level = None
cand = []
for lv in levels:
    pool = filter_by_level(stocks_all, indicators, lv)
    if len(pool) > 8:
        used_level = lv['name']
        for item in pool:
            sc = score_stock(item, SUB_MODULE, SCORE_FN)
            buy_c = item['price']
            ind = item['ind']
            trend = '📈 多头' if ind['above_ma5'] and ind['dif_val'] > 0 else ('📊 横盘' if ind['above_ma5'] else '📉 偏弱')
            fund = '🔥 放量' if item['vr'] > 1.2 else ('➡ 正常' if item['vr'] > 0.6 else '📉 缩量')
            cand.append({
                'nm': item['nm'][:12], 'code': item['code'], 'buy_c': buy_c,
                'p': item['p'], 'cl': ind['cl'], 'vr': item['vr'], 'hsl': item['hsl'],
                'sz': item['sz'], 'pe': item['pe'], 'score': sc,
                'next_close_pct': '—', 'd1': '—', 'd1v':'—','d2v':'—','d3v':'—','d4v':'—','d5v':'—',
                'trend': trend, 'fund': fund,
            })
        print(f'📌 分级: {used_level} → {len(cand)}只 (≥8达标)', flush=True)
        break
    print(f'  {lv["name"]}: {len(pool)}只 (<8继续降级)')

if not cand:
    print('❌ 5级全过不足8只，当日弃权')
    sys.exit(0)

cand.sort(key=lambda x: (-x['score'], -x['p']))

# 5. 历史胜率核算
hist_result = calc_historical_win_rate(mkt, SUB_MODULE, levels)
if hist_result:
    hist_rate, hist_w, hist_t = hist_result
    print(f'📊 历史胜率({mkt_display}): {hist_w}/{hist_t}={hist_rate}%', flush=True)
else:
    hist_rate = hist_w = hist_t = None

print(f'\n🏆 冠军: {cand[0]["nm"]}({cand[0]["code"]}) 评分{cand[0]["score"]}', flush=True)

# ========== HTML输出（同V260528模板风格） ==========
RED = '#e74c3c'
GREEN = '#27ae60'
GOLD = '#b8860b'
ORANGE = '#e67e22'
BG = '#ffffff'
CARD = '#f5f6fa'
LINE = '#dfe6e9'
TEXT = '#2c3e50'
DIM = '#95a5a6'
BRIGHT = '#1a1a2e'
HEAD = '#636e72'

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
    except: return f'<span style="color:{DIM}">{val_str}</span>'

html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:15px;background:{BG};font-family:-apple-system,'微软雅黑','PingFang SC',sans-serif;color:{TEXT};font-size:13px">

<div style="max-width:680px;margin:0 auto;background:{BG};border-radius:10px">

<!-- 头部 -->
<div style="text-align:center;padding:22px 15px 14px;border-bottom:2px solid #d4a84b;background:linear-gradient(180deg,#2a2b4e 0%,{BG} 100%)">
<div style="font-size:22px;font-weight:800;letter-spacing:5px;color:#d4a84b;text-shadow:0 0 20px rgba(212,168,75,0.3)">分而治之 · V260529</div>
<div style="font-size:12px;color:{GOLD};margin-top:6px;letter-spacing:2px">⚡ {mkt_display} · 分级{used_level} · L→L5</div>
<div style="font-size:11px;color:{DIM};margin-top:4px;letter-spacing:1px">{today} · 候选 {len(cand)}只</div>
</div>'''

# 历史胜率卡片
if hist_rate is not None:
    html += f'''
<div style="display:flex;gap:8px;margin:12px 0;flex-wrap:wrap;justify-content:center">
<div style="flex:1;min-width:80px;max-width:130px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:20px;font-weight:700;color:#f85149">{hist_rate}%</div>
<div style="font-size:9px;color:#8b949e;margin-top:2px">历史胜率({mkt_display})</div></div>
<div style="flex:1;min-width:80px;max-width:130px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:20px;font-weight:700;color:#58a6ff">分级{used_level}</div>
<div style="font-size:9px;color:#8b949e;margin-top:2px">使用级别</div></div>
<div style="flex:1;min-width:80px;max-width:130px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:20px;font-weight:700;color:#d29922">{len(cand)}</div>
<div style="font-size:9px;color:#8b949e;margin-top:2px">候选池</div></div>
<div style="flex:1;min-width:80px;max-width:130px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:20px;font-weight:700;color:#7ee787">{hist_t}</div>
<div style="font-size:9px;color:#8b949e;margin-top:2px">回测天数</div></div>
</div>'''
else:
    html += f'''
<div style="display:flex;gap:8px;margin:12px 0;flex-wrap:wrap;justify-content:center">
<div style="flex:1;min-width:80px;max-width:130px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:20px;font-weight:700;color:#58a6ff">实时API</div>
<div style="font-size:9px;color:#8b949e;margin-top:2px">今日数据</div></div>
<div style="flex:1;min-width:80px;max-width:130px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center">
<div style="font-size:20px;font-weight:700;color:#d29922">{len(cand)}</div>
<div style="font-size:9px;color:#8b949e;margin-top:2px">今日候选</div></div>
</div>'''

# Top3卡片
medals = ['🥇', '🥈', '🥉']
medal_colors = ['#d4a84b', '#a0a0c0', '#8a7a5a']
html += '<div style="padding:10px 0">'

for i, c in enumerate(cand[:3]):
    html += f'''
<div style="background:{CARD};border-radius:8px;padding:12px 14px;margin-top:8px;border-left:3px solid {medal_colors[i]}">
<div style="display:flex;align-items:center;justify-content:space-between">
<div style="display:flex;align-items:center;gap:6px">
<span style="font-size:14px">{medals[i]}</span>
<span style="font-size:14px;color:{BRIGHT};font-weight:600">{c['nm'][:8]}</span>
<span style="font-size:11px;color:{DIM}">{c['code'][-6:]}</span>
</div>
<span style="font-size:11px;color:{DIM}">评分 {c['score']}</span>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-top:8px;font-size:11px">
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0"><div style="color:{DIM};font-size:10px">买入</div><div style="color:{BRIGHT};font-size:12px;font-weight:600">{c['buy_c']:.2f}</div></div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0"><div style="color:{DIM};font-size:10px">当日涨</div><div style="font-size:12px">{pct_format(str(c['p']).replace("+",""))}</div></div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0"><div style="color:{DIM};font-size:10px">次日涨幅</div><div style="font-size:12px">{pct_format(c['next_close_pct'].replace("+",""))}</div></div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0"><div style="color:{DIM};font-size:10px">次日最高</div><div style="font-size:12px">{pct_format(c['d1'].replace("+",""))}</div></div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr;gap:6px;margin-top:6px;font-size:11px">
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">CL</span><br><span style="color:{GOLD}">{c['cl']:.0f}%</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">量比</span><br><span style="color:{BRIGHT}">{c['vr']:.2f}</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">换手</span><br><span style="color:{BRIGHT}">{c['hsl']:.1f}%</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">市值</span><br><span style="color:{BRIGHT}">{c['sz']:.0f}亿</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">PE</span><br><span style="color:{BRIGHT}">{c['pe'] if c['pe'] != '—' else '—'}</span></div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:4px;font-size:10px">
<div style="text-align:center;background:{BG}33;border-radius:4px;padding:3px 0"><span style="color:{DIM}">趋势</span> <span style="color:{GOLD}">{c['trend']}</span></div>
<div style="text-align:center;background:{BG}33;border-radius:4px;padding:3px 0"><span style="color:{DIM}">资金</span> <span style="color:{ORANGE}">{c['fund']}</span></div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr;gap:4px;margin-top:5px;font-size:10px">'''
    for d, lab in enumerate(['D+1','D+2','D+3','D+4','D+5']):
        val = [c['d1v'], c['d2v'], c['d3v'], c['d4v'], c['d5v']][d]
        if val == '—':
            html += f'<div style="text-align:center;border-radius:3px;padding:2px 0;background:{BG}44"><span style="color:{DIM}">{lab}</span><br><span style="color:{DIM}">—</span></div>'
        else:
            html += f'<div style="text-align:center;border-radius:3px;padding:2px 0;background:{BG}44"><span style="color:{DIM};font-size:9px">{lab}</span><br>{pct_format(val)}</div>'
    html += '</div></div>'

# 全部候选表格
html += f'''
<div style="margin-top:16px;font-size:11px;color:{DIM}">全部候选（{len(cand)}只）· 分级{used_level}</div>
<div style="background:{CARD};border-radius:6px;overflow-x:auto;-webkit-overflow-scrolling:touch;margin-top:4px">
<table style="min-width:860px;border-collapse:collapse;font-size:10px;white-space:nowrap">
<tr style="border-bottom:1px solid {LINE}">
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:24px">#</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:64px">名称</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:56px">编码</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:44px">买入价</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:38px">当日%</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:38px">次收%</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:38px">次高%</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">CL%</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">量比</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">换手</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:34px">PE</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:46px">市值</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:80px">趋势</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:60px">资金</th>
<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:32px">评分</th>
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
    if nc_val != '—': html += f'<td style="padding:5px 2px;text-align:center">{pct_format(nc_val, "")}</td>'
    else: html += f'<td style="padding:5px 2px;text-align:center"><span style="color:{DIM}">—</span></td>'
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

# 底部
html += f'''
<div style="text-align:center;font-size:9px;color:{DIM};padding:12px 0 5px;border-top:1px solid {LINE};margin-top:12px;line-height:1.6">
分而治之 V260529 · L→L5分级 · 8只门槛 · 4行情×4独立评分<br>
<span style="color:{RED}">红涨</span> · <span style="color:{GREEN}">绿跌</span> · 基准评分: V260528优化版(透支-8/MACD+3)<br>
今日行情: {mkt_display} · 使用级别: {used_level} · {len(cand)}只候选
</div>
</div>
</body>
</html>'''

# 存档+发送
ARCHIVE_DIR = os.path.expanduser('~/AppData/Local/hermes/email_archive')
os.makedirs(ARCHIVE_DIR, exist_ok=True)
archive_path = os.path.join(ARCHIVE_DIR, f'{today}_分而治之_V260529.html')
with open(archive_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'📁 已存档: {archive_path}')

# ========== 发邮件 ==========
from send_email import send_email
send_email(['1254628314@qq.com','314913203@qq.com'],
           f'分而治之 V260529 · 尾盘选股 {today}', html, html=True)
print(f'✅ 邮件已发送 - {today} V260529')

# ========== 更新缓存（实时API数据写入big_cache_full.pkl） ==========
try:
    cache_path = os.path.join(SCRIPTS_DIR, 'big_cache_full.pkl')
    if os.path.exists(cache_path):
        cc = pickle.load(open(cache_path, 'rb'))
        if today in cc['data']:
            today_cache = {s['code']: s for s in cc['data'][today]}
            updated = 0
            for code, s in stocks_all.items():
                if code in today_cache:
                    today_cache[code]['p'] = s['p']
                    today_cache[code]['vol_ratio'] = s['vol_ratio']
                    # 实时换手、市值、PE也更新
                    ri = cc['real'].get(code, {})
                    ri['hsl'] = s['hsl']
                    ri['shizhi'] = s['sz']
                    ri['pe'] = s['pe']
                    updated += 1
            cc['data'][today] = list(today_cache.values())
            pickle.dump(cc, open(cache_path, 'wb'))
            print(f'💾 缓存已更新({today}): {updated}只股票', flush=True)
        else:
            # 今天不在缓存中，新增
            entries = []
            for code, s in stocks_all.items():
                entries.append({
                    'code': code, 'p': s['p'], 'vol_ratio': s['vol_ratio'],
                    'cl': 50, 'dif_val': 0, 'macd_golden': 0, 'above_ma5': 0,
                    'wr_val': 50, 'k_val': 50, 'd_val': 50, 'j_val': 50,
                    'kdj_golden': 0, 'n': 0, 'close': s['price'],
                })
                cc['real'][code] = {'hsl': s['hsl'], 'pe': s['pe'], 'shizhi': s['sz']}
                cc['names'][code] = s['name']
            cc['data'][today] = entries
            pickle.dump(cc, open(cache_path, 'wb'))
            print(f'💾 缓存新增({today}): {len(entries)}只股票', flush=True)
except Exception as e:
    print(f'⚠️ 缓存更新失败: {e}', flush=True)

# 微信摘要
top3_line = ''
for i, c in enumerate(cand[:3]):
    nc = c['next_close_pct'] if c['next_close_pct'] != '—' else '待确认'
    top3_line += f"\n{'🥇🥈🥉'[i]} {c['nm'][:8]} | 买入{c['buy_c']:.2f} | 当日{c['p']:+.1f}% | 次日{nc}%"

print(f"\n━━━ 分而治之 V260529 {today} ━━━")
print(f"行情: {mkt_display} | 分级: {used_level} | 候选: {len(cand)}只")
if hist_rate: print(f"📊 历史胜率({mkt_display}): {hist_rate}% ({hist_w}/{hist_t}天)")
print(top3_line)
print(f"\n邮件已发 → 3人")
