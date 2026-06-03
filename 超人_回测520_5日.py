"""超人v2.1 回测5/20 — D+1~D+5 逐日收盘数据"""
import pickle, json, os
from concurrent.futures import ThreadPoolExecutor, as_completed

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

def get_next_5days(code, buy_date, buy_price):
    """获取买入后5个交易日的数据"""
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return []
    try:
        with open(fp,'r') as f:
            kdata = json.load(f)
        # 找到买入日之后的K线
        after = []
        found = False
        for kd in kdata:
            if kd.get('date','') == buy_date:
                found = True
                continue
            if found and len(after) < 5:
                after.append({
                    'date': kd.get('date',''),
                    'open': kd.get('open',0),
                    'high': kd.get('high',0),
                    'low': kd.get('low',0),
                    'close': kd.get('close',0),
                    'chg': (kd.get('close',0)/buy_price-1)*100 if buy_price > 0 else 0,
                    'high_chg': (kd.get('high',0)/buy_price-1)*100 if buy_price > 0 else 0
                })
            elif found:
                break
        return after
    except:
        return []

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
    bp = s.get('close', 0)
    
    signals = []
    if s.get('macd_golden',0): signals.append('MACD💎')
    if s.get('kdj_golden',0): signals.append('KDJ💎')
    if s.get('is_yang',0): signals.append('收阳☀️')
    if s.get('above_ma5',0): signals.append('MA5📈')
    sig = ' '.join(signals)
    
    cand.append((sc, nm, code, pct, vr, cl, hsl, sz, jv, bp, sig, code))

cand.sort(key=lambda x: (-x[0], -x[3]))

# 获取D+1~D+5
print('获取K线数据...', flush=True)
top_n = min(10, len(cand))
nd_cache = {}
for c in cand[:top_n]:
    nd_cache[c[2]] = get_next_5days(c[2], dt, c[9])

# 行业
ind_cache = {}
for c in cand[:top_n]:
    ri = real.get(c[2], {})
    ind_cache[c[2]] = ri.get('industry','—') or '—'

print(f'\n{"="*160}')
print(f'  超人v2.1优化版 — {dt} 选股 | D+1~D+5 逐日收盘增长')
print(f'{"="*160}')
print(f'{"#":<3} {"名称":<10} {"代码":<10} {"买入价":<8} {"当日涨%":<9} {"评分":<5} {"5日最高%":<9} {"5日均%":<8} {"结果":<6}')
print(f'{"":-<160}')

results_summary = []
for i, c in enumerate(cand[:top_n], 1):
    sc, nm, code, pct, vr, cl, hsl, sz, jv, bp, sig, _ = c
    nds = nd_cache.get(code, [])
    
    if pct >= 10: pct_d = f'🔥{pct:+.1f}%'
    elif pct >= 7: pct_d = f'{pct:+.1f}%🔥'
    elif pct >= 5: pct_d = f'{pct:+.1f}%📈'
    elif pct >= 2.5: pct_d = f'{pct:+.1f}%⬆️'
    elif pct >= 0: pct_d = f'{pct:+.1f}%➡️'
    else: pct_d = f'{pct:+.1f}%⬇️'
    
    if nds:
        max5 = max(d['high_chg'] for d in nds)
        avg5 = sum(d['chg'] for d in nds)/len(nds)
        # 收盘达2.5%
        close_hits = sum(1 for d in nds if d['chg'] >= 2.5)
        best_close = max(d['chg'] for d in nds)
        
        if max5 >= 5: res = '🔥大涨'
        elif max5 >= 2.5: res = '✅达标'
        elif max5 >= 0: res = '➡️横盘'
        else: res = '❌下跌'
        
        results_summary.append((i, nm, code, bp, pct, sc, max5, avg5, best_close, close_hits, res, nds))
        print(f'{i:<3} {nm[:8]:<10} {code:<10} {bp:<8.2f} {pct_d:<9} {sc:<5} {max5:<9.2f} {avg5:<8.2f} {res:<6}', flush=True)
    else:
        print(f'{i:<3} {nm[:8]:<10} {code:<10} {bp:<8.2f} {pct_d:<9} {sc:<5} {"—":<9} {"—":<8} {"无数据":<6}', flush=True)

# ===== D+1~D+5 逐日详表 =====
print(f'\n{"="*160}')
print(f'  Top5 D+1~D+5 逐日收盘增长明细（涨跌幅 = 收盘价/买入价 - 1）')
print(f'{"="*160}')

# 表头
header = f'{"#":<3} {"名称":<10} {"代码":<10} {"买入价":<8}'
for d in range(1,6):
    header += f' {"D+"+str(d):>9}'
header += f' {"5日最高":>9} {"最佳收盘":>9} {"达标天数":>9}'
print(header)
print(f'{"":-<160}')

for i, nm, code, bp, pct, sc, max5, avg5, best_close, close_hits, res, nds in results_summary:
    row = f'{i:<3} {nm[:8]:<10} {code:<10} {bp:<8.2f}'
    for d_idx, d in enumerate(nds):
        c_pct = d['chg']
        h_pct = d['high_chg']
        if c_pct >= 2.5:
            c_str = f'{c_pct:+.1f}%✅'
        elif c_pct >= 0:
            c_str = f'{c_pct:+.1f}%⬆️'
        else:
            c_str = f'{c_pct:+.1f}%⬇️'
        row += f' {c_str:>9}'
    row += f' {max5:>9.2f} {best_close:>9.2f} {close_hits:>4}/{len(nds):<3}'
    print(row, flush=True)

# ===== 每日详情 =====
print(f'\n{"="*160}')
print(f'  Top3 逐日详情')
print(f'{"="*160}')

for i, nm, code, bp, pct, sc, max5, avg5, best_close, close_hits, res, nds in results_summary[:3]:
    ind = ind_cache.get(code, '—')
    print(f'\n #{i} {nm}({code}) 评分{sc} 板块:{ind}')
    print(f'  ├ 买入: {bp:.2f} | 当日涨: {pct:+.1f}% | 5日最高: {max5:+.2f}% | 最佳收盘: {best_close:+.2f}% | {res}')
    print(f'  ├ {"日期":<12} {"开盘":>8} {"最高":>8} {"最低":>8} {"收盘":>8} {"收涨%":>8} {"累计%":>8}')
    print(f'  ├{"":-<60}')
    for d_idx, d in enumerate(nds):
        cum = d['chg']
        daily_chg = (d['close']/nds[d_idx-1]['close']-1)*100 if d_idx > 0 else (d['close']/bp-1)*100
        print(f'  ├ D+{d_idx+1} {d["date"]:<10} {d["open"]:>8.2f} {d["high"]:>8.2f} {d["low"]:>8.2f} {d["close"]:>8.2f} {daily_chg:>+7.2f}% {cum:>+7.2f}%')
    
    # 结果总结
    close_ok = sum(1 for d in nds if d['chg'] >= 2.5)
    high_ok = sum(1 for d in nds if d['high_chg'] >= 2.5)
    print(f'  └ 收盘达2.5%: {close_ok}/{len(nds)}天 | 盘中达2.5%: {high_ok}/{len(nds)}天')

# ===== 综合统计 =====
print(f'\n{"="*160}')
print(f'  综合统计')
print(f'{"="*160}')
hit5 = sum(1 for r in results_summary if r[6] >= 5)
hit25 = sum(1 for r in results_summary if r[6] >= 2.5)
best_close_hit = sum(1 for r in results_summary if r[9] >= 2.5)

if results_summary:
    print(f'  Top{len(results_summary)} | 5日最高达5%: {hit5}/{len(results_summary)} ({hit5/len(results_summary)*100:.0f}%)')
    print(f'  Top{len(results_summary)} | 5日最高达2.5%: {hit25}/{len(results_summary)} ({hit25/len(results_summary)*100:.0f}%)')
    print(f'  Top{len(results_summary)} | 收盘达2.5%: {best_close_hit}/{len(results_summary)} ({best_close_hit/len(results_summary)*100:.0f}%)')
