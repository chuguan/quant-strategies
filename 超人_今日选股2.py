"""超人策略v2.1 — 今日选股"""
import urllib.request, json, pickle, time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 加载缓存
with open('big_cache.pkl','rb') as f:
    c = pickle.load(f)
names, real = c['names'], c['real']
all_codes = list(names.keys())

# 只取主板
main_codes = [c for c in all_codes if c.startswith('sh6') or c.startswith('sz00') or c.startswith('sz001') or c.startswith('sz002')]
print(f'主板股: {len(main_codes)}只', flush=True)

def score_stock(pct, vr, cl):
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

def fetch_realtime(code):
    """获取实时行情"""
    try:
        url = f'http://qt.gtimg.cn/q={code}'
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/4.0'})
        r = urllib.request.urlopen(req, timeout=3)
        txt = r.read().decode('gbk')
        if '=' not in txt: return None
        parts = txt.split('=')[1].strip(';').strip('"').split('~')
        if len(parts) < 40: return None
        name = parts[1]
        price = float(parts[3]) if parts[3] else 0
        prev = float(parts[4]) if parts[4] else 0
        if prev == 0: return None
        pct = (price/prev-1)*100
        high = float(parts[33]) if parts[33] else price
        low = float(parts[34]) if parts[34] else price
        vol_ratio = float(parts[38]) if parts[38] else 0
        cl = (price-low)/(high-low)*100 if high != low else 50
        return {'code':code, 'name':name, 'price':price, 'pct':pct, 'vr':vol_ratio, 'cl':cl}
    except:
        return None

# 实时查询，每批50只
print('获取实时行情（分批查询）...', flush=True)
all_stocks = {}
batch_size = 50
for start in range(0, min(2000, len(main_codes)), batch_size):
    batch = main_codes[start:start+batch_size]
    codes_str = ','.join(batch)
    try:
        url = f'http://qt.gtimg.cn/q={codes_str}'
        r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Mozilla/4.0'}), timeout=5)
        txt = r.read().decode('gbk')
        
        # 每行格式: v_market_code="...~...~..."
        lines = txt.strip().split(';\n')
        for line in lines:
            if '="' not in line: continue
            try:
                parts = line.split('="')[1].strip('";').split('~')
                if len(parts) < 40: continue
                code = parts[2]
                name = parts[1]
                price = float(parts[3]) if parts[3] else 0
                prev = float(parts[4]) if parts[4] else 0
                if prev == 0: continue
                pct = (price/prev-1)*100
                high = float(parts[33]) if parts[33] else price
                low = float(parts[34]) if parts[34] else price
                vr = float(parts[38]) if parts[38] else 0
                cl = (price-low)/(high-low)*100 if high != low else 50
                
                # 过滤
                if pct < 5 or pct > 8: continue
                if vr < 0.5: continue
                if 'ST' in name or '*ST' in name: continue
                
                # 换手/市值从缓存
                ri = real.get(code, {})
                hsl = (ri.get('hsl',0) or 0)
                if hsl < 5 or hsl > 18: continue
                sz = (ri.get('shizhi',0) or 0)
                if sz >= 150: continue
                
                sc = score_stock(pct, vr, cl)
                all_stocks[code] = (sc, name, code, pct, vr, cl, hsl, sz, price)
            except:
                continue
    except Exception as e:
        print(f'  批次{start}错误: {e}', flush=True)
    time.sleep(0.1)

if not all_stocks:
    print('无候选股票，可能API数据格式不对', flush=True)
    print('尝试另一种方式...', flush=True)
    # 用curl再试
    import subprocess
    test = subprocess.run(['curl','-s','--max-time','5','http://qt.gtimg.cn/q=sh600000'], capture_output=True, text=True)
    print(f'测试curl: {test.stdout[:200]}', flush=True)
    exit()

sorted_stocks = sorted(all_stocks.values(), key=lambda x: (-x[0], -x[3]))
print(f'\n共{len(sorted_stocks)}只候选', flush=True)
print(f'{"#":<3} {"名称":<10} {"代码":<10} {"评分":<5} {"涨%":<6} {"量比":<6} {"CL%":<5} {"换手%":<6} {"市值":<6} {"现价":<8}', flush=True)
print('-'*68, flush=True)
for i, s in enumerate(sorted_stocks[:10], 1):
    print(f'{i:<3} {s[1][:8]:<10} {s[2]:<10} {s[0]:<5} {s[3]:<6.1f} {s[4]:<6.2f} {s[5]:<5.0f} {s[6]:<6.1f} {s[7]:<6.0f} {s[8]:<8.2f}', flush=True)
