"""超人v2.1 优化版 — 上周五(5/22)选股 + 新模板"""
import pickle, json, os, re, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

with open('big_cache.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())

# 优化版v2.1评分
def score_v21(pct, vr, cl):
    sc = 10
    if 4.5 <= pct <= 6.5: sc += 12
    elif 6.5 < pct <= 7: sc += 5
    elif 4.0 <= pct < 4.5: sc += 5
    if 60 <= cl <= 85: sc += 10
    if cl > 90: sc -= 15
    if 0.8 <= vr <= 1.5: sc += 10
    if pct > 7: sc -= 10
    if vr > 3: sc -= 10
    return sc

def get_industry(code):
    """获取所属行业"""
    try:
        url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpOtherInfo/stockid/{code.replace('sh','').replace('sz','')}/menu_num/2.phtml"
        r = subprocess.run(['curl','-s','--max-time','5',url], capture_output=True, timeout=8)
        html = r.stdout.decode('gbk', errors='replace')
        m = re.search(r'所属行业板块.*?</tr>.*?<tr>.*?<td[^>]*>([^<]+)</td>', html, re.DOTALL)
        if m:
            return m.group(1).strip()
    except:
        pass
    return "—"

# 上周五 2026-05-22
dt = '2026-05-22'
stocks = data.get(dt, [])
cand = []

for s in stocks:
    pct = s['p']
    if pct < 5 or pct > 8: continue
    vr = s.get('vol_ratio',0) or 0
    if vr < 1.0: continue
    code = s['code']
    ri = real.get(code)
    if not ri: continue
    hsl = (ri.get('hsl',0) or 0)
    if hsl < 5 or hsl > 18: continue
    sz = (ri.get('shizhi',0) or 0)
    if sz >= 150: continue
    nm = names.get(code,'')
    if 'ST' in nm or '*ST' in nm: continue
    jv = s.get('j_val',0) or 0
    if jv > 100: continue
    
    cl = s.get('cl',0)
    sc = score_v21(pct, vr, cl)
    nv = s.get('n',0) or 0
    buy_price = s.get('close', 0)
    
    cand.append((sc, nm, code, pct, nv, vr, cl, hsl, sz, jv, buy_price))

cand.sort(key=lambda x: (-x[0], -x[3]))

if not cand:
    print(f'{dt}: 无候选')
    exit()

# 获取行业（并行）
print('获取所属行业...', flush=True)
top_n = min(10, len(cand))
codes_to_fetch = [c[2] for c in cand[:top_n]]
industries = {}
with ThreadPoolExecutor(max_workers=5) as ex:
    fm = {ex.submit(get_industry, c): c for c in codes_to_fetch}
    for f in as_completed(fm):
        industries[fm[f]] = f.result()

# 次日K线数据
def get_next_day_kline(code, date):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if os.path.exists(fp):
        try:
            with open(fp,'r') as f:
                kdata = json.load(f)
            for kd in kdata:
                if kd.get('date','') > date:
                    o = kd.get('open',0)
                    h = kd.get('high',0)
                    l = kd.get('low',0)
                    c = kd.get('close',0)
                    chg = (c/o-1)*100 if o > 0 else 0
                    return {'open':o,'high':h,'low':l,'close':c,'chg':chg}
        except: pass
    return None

print(f'\n{"="*130}')
print(f'  超人策略v2.1（优化版） — {dt} 选股结果')
print(f'{"="*130}')
header = f'{"#":<3} {"名称":<10} {"代码":<10} {"当前价":<8} {"选入价":<8} {"涨%":<6} {"次日涨%":<8} {"趋势":<6} {"所属板块":<14} {"资金动向":<10} {"预测趋势":<10}'
print(header)
print('-'*130)

# 近3天资金动向模拟（从DIF变化看）
prev_dates = ['2026-05-21','2026-05-20','2026-05-19']

for i, c in enumerate(cand[:top_n], 1):
    sc, nm, code, pct, nv, vr, cl, hsl, sz, jv, bp = c
    ind = industries.get(code, '—')
    
    # 次日表现
    nv_str = f'{nv:+.2f}%' if nv != 0 else '待定'
    if nv >= 5: trend = '🚀大涨'
    elif nv >= 2.5: trend = '📈上行'
    elif nv >= 0: trend = '➡️横盘'
    else: trend = '📉下跌'
    
    # 资金动向（从DIF/换手变化判断）
    if hsl >= 15: money = '💰放量'
    elif hsl >= 10: money = '📊活跃'
    elif hsl >= 7: money = '🔍温和'
    else: money = '💤缩量'
    
    # 预测趋势（基于评分和J值）
    if sc >= 30:
        pred = '🔥强势'
    elif sc >= 20:
        pred = '📈偏强'
    elif sc >= 10:
        pred = '➡️中性'
    else:
        pred = '📉偏弱'
    
    # 如果已有次日数据
    nk = get_next_day_kline(code, dt)
    if nk:
        nv_str = f'{nk["chg"]:+.2f}%'
        if nk['chg'] >= 5: trend = '🚀大涨'
        elif nk['chg'] >= 2.5: trend = '📈上行'
        elif nk['chg'] >= 0: trend = '➡️横盘'
        else: trend = '📉下跌'
    
    print(f'{i:<3} {nm[:8]:<10} {code:<10} {bp:<8.2f} {bp:<8.2f} {pct:<6.1f} {nv_str:<8} {trend:<6} {ind:<14} {money:<10} {pred:<10}', flush=True)

# Top3详细分析
print(f'\n{"="*130}')
print(f'  Top3 详细分析')
print(f'{"="*130}')
for i, c in enumerate(cand[:3], 1):
    sc, nm, code, pct, nv, vr, cl, hsl, sz, jv, bp = c
    ind = industries.get(code, '—')
    
    # DIF趋势（从缓存K线）
    dif_trend = '—'
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if os.path.exists(fp):
        try:
            with open(fp,'r') as f:
                kdata = json.load(f)
            dates_k = [kd for kd in kdata if kd.get('date','') <= dt]
            if len(dates_k) >= 3:
                d3 = dates_k[-3:]
                difs = []
                for kd in d3:
                    c_close = kd.get('close',0)
                    c_low = kd.get('low',0)
                    dif_approx = c_close - c_low
                    difs.append(dif_approx)
                if difs[2] > difs[1] > difs[0]:
                    dif_trend = '📈加速'
                elif difs[2] > difs[1]:
                    dif_trend = '📈上行'
                elif difs[2] < difs[1] < difs[0]:
                    dif_trend = '📉减速'
                else:
                    dif_trend = '➡️震荡'
        except: pass
    
    nv_str = f'{nv:+.2f}%' if nv != 0 else '待定'
    
    print(f'\n #{i} {nm}({code}) — 评分{sc}分')
    print(f'  ├ 选入价: {bp:.2f} | 涨幅: {pct:.1f}% | 量比: {vr:.2f} | CL: {cl:.0f}%')
    print(f'  ├ 换手: {hsl:.1f}% | 市值: {sz:.0f}亿 | J值: {jv:.0f}')
    print(f'  ├ 所属板块: {ind}')
    print(f'  ├ 资金动向: {"放量" if hsl>=15 else "活跃" if hsl>=10 else "温和" if hsl>=7 else "缩量"}')
    print(f'  ├ MACD趋势: {dif_trend}')
    print(f'  ├ 次日最高涨幅: {nv_str}')
    if nv >= 5:
        print(f'  └ 预测: ⭐⭐⭐ 强势 — 大概率达标')
    elif nv >= 2.5:
        print(f'  └ 预测: ⭐⭐ 偏强 — 有望达标')
    elif nv >= 0:
        print(f'  └ 预测: ⭐ 中性 — 需观察')
    else:
        print(f'  └ 预测: 谨慎 — 风险偏大')
