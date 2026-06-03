"""超人v2.1 回测5/20 — 新模板：选股+5日横行"""
import pickle, json, os
from concurrent.futures import ThreadPoolExecutor

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
with open('big_cache.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']

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

def get_future_kline(code, buy_date, buy_price, n=5):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return []
    try:
        with open(fp,'r') as f:
            kd = json.load(f)
        after = []
        found = False
        for k in kd:
            if k.get('date','') == buy_date: found = True; continue
            if found and len(after) < n:
                after.append({
                    'date': k.get('date',''),
                    'close': k.get('close',0),
                    'high': k.get('high',0),
                    'close_chg': (k.get('close',0)/buy_price-1)*100,
                    'high_chg': (k.get('high',0)/buy_price-1)*100,
                })
            elif found: break
        return after
    except: return []

dt = '2026-05-20'
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
    bp = s.get('close',0)
    
    sig = []
    if s.get('macd_golden',0): sig.append('MACD💎')
    if s.get('kdj_golden',0): sig.append('KDJ💎')
    if s.get('is_yang',0): sig.append('收阳☀️')
    above_ma5 = s.get('above_ma5',0)
    ma5_str = '✅站MA5' if above_ma5 else '❌破MA5'
    
    ind = ri.get('industry','—') or '—'
    cand.append((sc, nm, code, pct, vr, cl, hsl, sz, jv, bp, ' '.join(sig), ind, ma5_str, s))

cand.sort(key=lambda x: (-x[0], -x[3]))

# 获取5日数据
top_n = min(10, len(cand))
for i, c in enumerate(cand[:top_n]):
    nd = get_future_kline(c[2], dt, c[9], 5)
    cand[i] = c + (nd,)

# ===== 输出 =====
print(f'========================================================================================================================')
print(f'  超人v2.1优化版 — {dt} 选股 | 尾盘买入 | 5日收盘累计涨幅%')
print(f'========================================================================================================================')

# 第一段：选股结果
print(f'\n【一、今日选股】')
print(f'{"#":<3} {"名称":<10} {"代码":<10} {"选入价":<9} {"涨%":<7} {"评分":<5} {"MA5":<8} {"板块":<12} {"信号":<22}')
print(f'{"":-<95}')
for i, c in enumerate(cand[:top_n], 1):
    sc, nm, code, pct, vr, cl, hsl, sz, jv, bp, sig, ind, ma5_str = c[:13]
    if pct >= 7:   pd = f'{pct:.1f}%🔥'
    elif pct >= 5: pd = f'{pct:.1f}%📈'
    elif pct >= 0: pd = f'{pct:.1f}%⬆️'
    else:          pd = f'{pct:.1f}%⬇️'
    print(f'{i:<3} {nm[:8]:<10} {code:<10} {bp:<9.2f} {pd:<7} {sc:<5} {ma5_str:<8} {ind[:10]:<12} {sig:<22}')

# 第二段：5日横行
print(f'\n【二、D+1~D+5 收盘累计涨幅%（较买入价）】')
header = f'{"#":<3} {"名称":<10} {"代码":<10}'
for d in range(1,6): header += f' {"D+"+str(d):>9}'
header += f' {"5日最高%":>9} {"达标?":<6}'
print(header)
print(f'{"":-<95}')

for i, c in enumerate(cand[:top_n], 1):
    sc, nm, code, pct, vr, cl, hsl, sz, jv, bp = c[:10]
    sig, ind, ma5_str = c[10], c[11], c[12]
    nd = c[14] if len(c) > 14 else []
    row = f'{i:<3} {nm[:8]:<10} {code:<10}'
    
    max5 = 0
    for d_idx in range(5):
        if d_idx < len(nd):
            cp = nd[d_idx]['close_chg']
            hp = nd[d_idx]['high_chg']
            max5 = max(max5, hp)
            if cp >= 2.5:  row += f'  {cp:>+5.1f}%✅'
            elif cp >= 0:  row += f'  {cp:>+5.1f}%⬆️'
            else:          row += f'  {cp:>+5.1f}%⬇️'
        else:
            row += f'  {"---":>7}'
    
    res = '🔥' if max5 >= 5 else ('✅' if max5 >= 2.5 else '❌')
    row += f'  {max5:>6.2f}%  {res:<4}'
    print(row)

# 第三段：Top3 详细战绩
print(f'\n【三、Top3 详细战绩】')
for i, c in enumerate(cand[:3], 1):
    sc, nm, code, pct, vr, cl, hsl, sz, jv, bp = c[:10]
    sig, ind, ma5_str = c[10], c[11], c[12]
    s = c[13]
    nd = c[14] if len(c) > 14 else []
    
    max5 = max((d['high_chg'] for d in nd), default=0)
    best_close = max((d['close_chg'] for d in nd), default=0)
    close_ok = sum(1 for d in nd if d['close_chg'] >= 2.5)
    high_ok = sum(1 for d in nd if d['high_chg'] >= 2.5)
    res = '🔥' if max5 >= 5 else ('✅' if max5 >= 2.5 else '❌')
    
    print(f'\n #{i} {nm}({code}) | 评分{sc} | {ma5_str} | 板块:{ind} | {res}')
    print(f'  买入价:{bp:.2f} | 当日涨:{pct:+.1f}% | 量比:{vr:.2f} | CL:{cl:.0f}% | 换手:{hsl:.1f}% | 市值:{sz:.0f}亿')
    print(f'  信号:{sig}')
    print(f'  {"日期":<12} {"收盘价":>8} {"累计涨%":>9} {"当日涨%":>9}')
    print(f'  {"":-<45}')
    print(f'  {"买入日 "+dt:<12} {bp:>8.2f} {"+0.00%":>9} {"+0.00%":>9} ⬇️买入')
    for d_idx, d in enumerate(nd):
        cc = d['close_chg']
        dd = (d['close']/nd[d_idx-1]['close']-1)*100 if d_idx > 0 else (d['close']/bp-1)*100
        print(f'  D+{d_idx+1} {d["date"]:<10} {d["close"]:>8.2f} {cc:>+8.2f}% {dd:>+8.2f}%', end='')
        if cc >= 2.5: print(f' ✅')
        elif cc >= 0: print(f' ⬆️')
        else: print(f' ⬇️')
    
    print(f'  5日最高涨幅: {max5:+.2f}% | 最佳收盘涨幅: {best_close:+.2f}%')
    print(f'  收盘达2.5%: {close_ok}/{len(nd)}天 | 盘中达2.5%: {high_ok}/{len(nd)}天')

# 总结
print(f'\n【四、总结】')
hit5 = sum(1 for c in cand[:top_n] if max((d['high_chg'] for d in (c[14] if len(c)>14 else [])), default=0) >= 5)
hit25 = sum(1 for c in cand[:top_n] if max((d['high_chg'] for d in (c[14] if len(c)>14 else [])), default=0) >= 2.5)
close_hit = sum(1 for c in cand[:top_n] if max((d['close_chg'] for d in (c[14] if len(c)>14 else [])), default=0) >= 2.5)
valid = sum(1 for c in cand[:top_n] if len(c) > 14 and c[14])
print(f'  Top{top_n} | 5日盘中达5%: {hit5}/{valid} | 盘中达2.5%: {hit25}/{valid} | 收盘达2.5%: {close_hit}/{valid}')
