"""超人v2.1 今日选股 — 腾讯K线API逐个查"""
import urllib.request, json, pickle, time, sys

with open('big_cache.pkl','rb') as f:
    cache = pickle.load(f)
names, real = cache['names'], cache['real']
codes = [c for c in names if c.startswith('sh6') or c.startswith('sz00') or c.startswith('sz001') or c.startswith('sz002')]
print(f'主板: {len(codes)}只', flush=True)

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

# 用腾讯的qt接口批量查
# 格式: http://qt.gtimg.cn/q=sh600000,sh600001,...
# 返回GBK编码的文本，每行格式: v_sh600000="1~名称~代码~最新价~昨收~...~...~量比~...";
print('查询实时行情...', flush=True)
all_stocks = {}
step = 50
for start in range(0, min(1000, len(codes)), step):
    batch = codes[start:start+step]
    qs = ','.join(batch)
    try:
        import subprocess
        r = subprocess.run(['curl','-s','--max-time','5',f'http://qt.gtimg.cn/q={qs}'], capture_output=True, timeout=10)
        txt = r.stdout.decode('gbk', errors='replace')
        for line in txt.strip().split(';\n'):
            line = line.strip()
            if not line or '="' not in line:
                continue
            try:
                parts = line.split('="')[1].strip('";').split('~')
                if len(parts) < 40:
                    continue
                code = parts[2]
                name = parts[1]
                price = float(parts[3]) if parts[3] else 0
                prev = float(parts[4]) if parts[4] else 0
                if prev == 0:
                    continue
                pct = round((price/prev-1)*100, 2)
                high = float(parts[33]) if parts[33] else price
                low = float(parts[34]) if parts[34] else price
                vol_ratio = float(parts[38]) if parts[38] else 0
                cl = round((price-low)/(high-low)*100, 1) if high != low else 50
                
                if pct < 5 or pct > 8:
                    continue
                if vol_ratio < 0.5:
                    continue
                if 'ST' in name or '*ST' in name:
                    continue
                
                ri = real.get(code, {})
                hsl = (ri.get('hsl',0) or 0)
                if hsl < 5 or hsl > 18:
                    continue
                sz = (ri.get('shizhi',0) or 0)
                if sz >= 150:
                    continue
                
                sc = score_stock(pct, vol_ratio, cl)
                all_stocks[code] = (sc, name, code, pct, vol_ratio, cl, hsl, sz, price)
            except Exception as e:
                pass
    except Exception as e:
        pass
    if start % 200 == 0:
        print(f'  已查{start+step}只, 候选{len(all_stocks)}只', flush=True)
    time.sleep(0.05)

if not all_stocks:
    print('无候选', flush=True)
    # 试单个查
    print('逐个检查...', flush=True)
    for c in codes[:200]:
        try:
            import subprocess
            r = subprocess.run(['curl','-s','--max-time','3',f'http://qt.gtimg.cn/q={c}'], capture_output=True, timeout=5)
            txt = r.stdout.decode('gbk', errors='replace')
            if '="' not in txt: continue
            parts = txt.split('="')[1].strip('";').split('~')
            if len(parts) < 40: continue
            name = parts[1]
            price = float(parts[3]) if parts[3] else 0
            prev = float(parts[4]) if parts[4] else 0
            if prev == 0: continue
            pct = (price/prev-1)*100
            if pct < 5 or pct > 8: continue
            vr = float(parts[38]) if parts[38] else 0
            high = float(parts[33]) if parts[33] else price
            low = float(parts[34]) if parts[34] else price
            cl = (price-low)/(high-low)*100 if high != low else 50
            ri = real.get(c, {})
            hsl = (ri.get('hsl',0) or 0)
            if hsl < 5 or hsl > 18: continue
            sz = (ri.get('shizhi',0) or 0)
            if sz >= 150: continue
            if 'ST' in name or '*ST' in name: continue
            sc = score_stock(pct, vr, cl)
            all_stocks[c] = (sc, name, c, pct, vr, cl, hsl, sz, price)
        except: pass
    print(f'  逐个查完, 候选{len(all_stocks)}只', flush=True)

sorted_stocks = sorted(all_stocks.values(), key=lambda x: (-x[0], -x[3]))
print(f'\n今日候选: {len(sorted_stocks)}只', flush=True)
print(f'{"#":<3} {"名称":<10} {"代码":<10} {"评分":<5} {"涨%":<6} {"量比":<6} {"CL%":<5} {"换手%":<6} {"市值":<6} {"现价":<8}', flush=True)
print('-'*68, flush=True)
for i, s in enumerate(sorted_stocks[:10], 1):
    print(f'{i:<3} {s[1][:8]:<10} {s[2]:<10} {s[0]:<5} {s[3]:<6.1f} {s[4]:<6.2f} {s[5]:<5.0f} {s[6]:<6.1f} {s[7]:<6.0f} {s[8]:<8.2f}', flush=True)
