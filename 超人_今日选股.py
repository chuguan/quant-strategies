"""超人策略v2.1 — 实时选今日（2026-05-25）"""
import sys, os, json, subprocess, pickle
from datetime import datetime

# 加载缓存中的名称和实时数据
with open('big_cache.pkl','rb') as f:
    cache = pickle.load(f)
names = cache['names']
real_cache = cache['real']

# 优化版参数
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

# 获取今日主板股实时行情
print('获取今日实时行情...', flush=True)
# 先用缓存里的股票列表
all_codes = list(names.keys())
all_sh = [c for c in all_codes if c.startswith('sh6')]
all_sz = [c for c in all_codes if c.startswith('sz00') or c.startswith('sz001') or c.startswith('sz002')]
all_main = all_sh + all_sz

# 换手率、市值从实时缓存获取
# 实时涨幅从腾讯API获取
import urllib.request

def fetch_realtime(code):
    """获取单个股票实时行情"""
    try:
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,1,qfq'
        r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=5)
        data = json.loads(r.read())
        d = data.get('data',{}).get(code,{})
        qt = d.get('qt',{}).get(code,[])
        if len(qt) >= 5:
            name = qt[1]
            price = float(qt[3])
            prev = float(qt[4])
            pct = (price/prev-1)*100 if prev > 0 else 0
            high = float(qt[29]) if len(qt) > 29 else price
            low = float(qt[30]) if len(qt) > 30 else price
            cl = (price-low)/(high-low)*100 if high != low else 50
            return {'code':code,'name':name,'price':price,'pct':pct,'high':high,'low':low,'cl':cl}
    except:
        pass
    return None

# 用批量API获取
print(f'扫描{len(all_main[:200])}只主板股...', flush=True)
candidates = []
checked = 0

# 先通过行情API筛选涨5~8%
batch_url = 'https://web.ifzq.gtimg.cn/appstock/app/hq/v2/hq?codes='
codes_str = ','.join(all_main[:500])
try:
    r = urllib.request.urlopen(urllib.request.Request(batch_url+codes_str, headers={'User-Agent':'Mozilla/5.0'}), timeout=10)
    data = json.loads(r.read())
    qt_data = data.get('data',{}).get('qt',[])
    for item in qt_data:
        if len(item) < 30: continue
        try:
            code = item[2]
            price = float(item[3])
            prev = float(item[4])
            pct = (price/prev-1)*100
            high = float(item[29])
            low = float(item[30])
            name = item[1]
            
            if pct < 5 or pct > 8: continue
            
            # 获取换手率/市值
            ri = real_cache.get(code, {})
            hsl = (ri.get('hsl',0) or 0)
            if hsl < 5 or hsl > 18: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz >= 150: continue
            if 'ST' in name or '*ST' in name: continue
            
            vr = 1.0  # 默认量比
            cl = (price-low)/(high-low)*100 if high != low else 50
            sc = score_stock(pct, vr, cl)
            
            candidates.append((sc, name, code, pct, vr, cl, hsl, sz, price))
        except:
            continue
        checked += 1
except Exception as e:
    print(f'API错误: {e}', flush=True)

candidates.sort(key=lambda x: (-x[0], -x[3]))
print(f'检查{checked}只, 候选{len(candidates)}只', flush=True)
print(f'{"#":<3} {"名称":<10} {"代码":<10} {"评分":<5} {"涨幅%":<7} {"量比":<6} {"CL%":<5} {"换手%":<6} {"市值":<7} {"现价":<8}', flush=True)
print('-'*70, flush=True)
for i, c in enumerate(candidates[:10], 1):
    print(f'{i:<3} {c[1][:8]:<10} {c[2]:<10} {c[0]:<5} {c[3]:<7.1f} {c[4]:<6.2f} {c[5]:<5.0f} {c[6]:<6.1f} {c[7]:<7.0f} {c[8]:<8.2f}', flush=True)
