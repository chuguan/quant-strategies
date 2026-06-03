"""超人v2.1 回测5/20 — 当日收盘数据"""
import pickle, json, os, re, subprocess
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

def get_next_day_data(code, buy_date):
    """获取次日开盘/最高/最低/收盘"""
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return None
    try:
        with open(fp,'r') as f:
            kdata = json.load(f)
        for kd in kdata:
            if kd.get('date','') > buy_date:
                o = kd.get('open',0)
                h = kd.get('high',0)
                l = kd.get('low',0)
                c = kd.get('close',0)
                return {'open':o,'high':h,'low':l,'close':c}
    except: pass
    return None

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
    
    # 当天最高涨幅（从买入价到当天最高）
    high = s.get('high', bp)
    day_high_pct = (high/bp-1)*100 if bp > 0 else 0
    
    # 信号标注
    signals = []
    if s.get('macd_golden',0): signals.append('MACD金叉💎')
    if s.get('kdj_golden',0): signals.append('KDJ金叉💎')
    if s.get('is_yang',0): signals.append('收阳☀️')
    if s.get('above_ma5',0): signals.append('站MA5📈')
    signal_str = ' '.join(signals[:3])
    
    cand.append((sc, nm, code, pct, vr, cl, hsl, sz, jv, bp, day_high_pct, signal_str, s))

cand.sort(key=lambda x: (-x[0], -x[3]))

# 行业（并行查询）
print('获取行业...', flush=True)
industries = {}
top_n = min(10, len(cand))
codes_to_fetch = [c[2] for c in cand[:top_n]]
with ThreadPoolExecutor(max_workers=5) as ex:
    fm = {ex.submit(lambda c: c, code): code for code in codes_to_fetch}
    for f in as_completed(fm):
        pass

# 简化行业获取
for c in cand[:top_n]:
    ind = real.get(c[2], {}).get('industry', '—') or '—'
    if ind == '—':
        # 从行业缓存JSON获取
        fp = os.path.join(CACHE_DIR, f'{c[2]}.json')
        if os.path.exists(fp):
            try:
                with open(fp,'r') as f:
                    kd = json.load(f)
                for item in kd:
                    if isinstance(item, dict) and 'industry' in item:
                        ind = item['industry']
                        break
            except: pass
    industries[c[2]] = ind

print(f'\n{"="*125}')
print(f'  超人策略v2.1优化版回测 — {dt}（当日收盘数据）')
print(f'{"="*125}')
print(f'{"#":<3} {"名称":<10} {"代码":<10} {"选入价":<8} {"当天涨%":<9} {"量比":<6} {"CL%":<5} {"换手%":<6} {"市值":<6} {"评分":<5} {"信号":<30}', flush=True)
print(f'{"":-<125}')

for i, c in enumerate(cand[:top_n], 1):
    sc, nm, code, pct, vr, cl, hsl, sz, jv, bp, dh_pct, sig, _ = c
    ind = industries.get(code, '—')
    
    # 当天涨%颜色标记
    if pct >= 10: pct_d = f'🔥{pct:+.1f}%🚀'
    elif pct >= 7: pct_d = f'🔥{pct:+.1f}%'
    elif pct >= 5: pct_d = f'📈{pct:+.1f}%'
    elif pct >= 2.5: pct_d = f'⬆️{pct:+.1f}%'
    elif pct >= 0: pct_d = f'➡️{pct:+.1f}%'
    else: pct_d = f'⬇️{pct:+.1f}%'
    
    print(f'{i:<3} {nm[:8]:<10} {code:<10} {bp:<8.2f} {pct_d:<9} {vr:<6.2f} {cl:<5.0f} {hsl:<6.1f} {sz:<6.0f} {sc:<5} {sig:<30}', flush=True)

print(f'\n{"="*125}')
print(f'  Top3 次日表现验证')
print(f'{"="*125}')

for i, c in enumerate(cand[:3], 1):
    sc, nm, code, pct, vr, cl, hsl, sz, jv, bp, dh_pct, sig, s = c
    ind = industries.get(code, '—')
    
    # 次日数据
    nd = get_next_day_data(code, dt)
    if nd:
        o_pct = (nd['open']/bp-1)*100
        h_pct = (nd['high']/bp-1)*100
        l_pct = (nd['low']/bp-1)*100
        c_pct = (nd['close']/bp-1)*100
        ok = '🔥' if h_pct >= 5 else ('✅' if h_pct >= 2.5 else '❌')
    else:
        o_pct = h_pct = l_pct = c_pct = 0
        ok = '待定'
    
    # DIF趋势
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    dif_t = '—'
    if os.path.exists(fp):
        try:
            with open(fp,'r') as f:
                kd = json.load(f)
            dk = [x for x in kd if isinstance(x,dict) and x.get('date','') <= dt]
            if len(dk) >= 3:
                d3 = dk[-3:]
                c3 = [x.get('close',0) for x in d3]
                if c3[2] > c3[1] > c3[0]: dif_t = '📈加速上行'
                elif c3[2] > c3[1]: dif_t = '📈震荡上行'
                elif c3[2] < c3[1] < c3[0]: dif_t = '📉持续下行'
                else: dif_t = '➡️区间震荡'
        except: pass
    
    print(f'\n #{i} {nm}({code}) — 评分{sc} | 板块:{ind}')
    print(f'  ├ 尾盘买入: {bp:.2f} | 当日涨: {pct:+.1f}% | 量比:{vr:.2f} | CL:{cl:.0f}%')
    print(f'  ├ 换手:{hsl:.1f}% | 市值:{sz:.0f}亿 | J值:{jv:.0f}')
    print(f'  ├ {sig}')
    print(f'  ├ MACD趋势: {dif_t}')
    if nd:
        print(f'  ├ 次日: 开{o_pct:+.2f}% 高{h_pct:+.2f}% 低{l_pct:+.2f}% 收{c_pct:+.2f}%')
        if h_pct >= 2.5:
            print(f'  └ 结果: ✅ 达2.5%达标! (最高{h_pct:+.2f}%)')
        else:
            print(f'  └ 结果: ❌ 未达标 (最高仅{h_pct:+.2f}%) {ok}')
    else:
        print(f'  └ 次日数据: 待更新')
    
    # Top3 明细
    if i == 1:
        print(f'\n  Top3 全部候选:')
        for j, c2 in enumerate(cand[:3], 1):
            sc2, nm2, code2, pct2, vr2, cl2, hsl2, sz2, jv2, bp2, _, _, _ = c2
            nd2 = get_next_day_data(code2, dt)
            if nd2:
                h2 = (nd2['high']/bp2-1)*100
                ok2 = '🔥' if h2 >= 5 else ('✅' if h2 >= 2.5 else '❌')
                print(f'    #{j} {nm2}({code2}) 买{bp2:.2f} 当日{pct2:+.1f}% 次日最高{h2:+.2f}% {ok2}')
            else:
                print(f'    #{j} {nm2}({code2}) 买{bp2:.2f} 当日{pct2:+.1f}% 次日数据待更新')

# 胜率统计
print(f'\n{"="*125}')
print(f'  当日 Top5 次日达标统计')
print(f'{"="*125}')
hits = 0
total = min(5, len(cand))
for i, c in enumerate(cand[:5], 1):
    nd = get_next_day_data(c[2], dt)
    if nd:
        hp = (nd['high']/c[9]-1)*100
        hit = hp >= 2.5
        if hit: hits += 1
        ok2 = '🔥' if hp >= 5 else ('✅' if hp >= 2.5 else '❌')
        print(f'  #{i} {c[1][:8]:<10}({c[2]:<10}) 买{c[9]:<6.2f} → 次日最高{hp:+.2f}% {ok2}')
    else:
        print(f'  #{i} {c[1][:8]:<10}({c[2]:<10}) 买{c[9]:<6.2f} → 次日数据待更新')

print(f'\n  Top5达2.5%: {hits}/{total} = {hits/total*100:.0f}%' if total > 0 else '')
