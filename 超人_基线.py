"""超人策略基线分析"""
import pickle
with open('big_cache.pkl','rb') as f:
    c = pickle.load(f)
d, real, names = c['data'], c['real'], c['names']
dates = sorted(d.keys())

# 检查2026年n值分布
import statistics
for year in ['2025','2026']:
    yrs = [dt for dt in dates if dt.startswith(year)]
    n_vals = []
    for dt in yrs:
        for s in d[dt]:
            n = s.get('n',0) or 0
            if n:
                n_vals.append(n)
                break
    if n_vals:
        hit25 = sum(1 for v in n_vals if v >= 2.5)
        hit5 = sum(1 for v in n_vals if v >= 5)
        avg = statistics.mean(n_vals) if n_vals else 0
        print(f'{year}: {len(yrs)}天, 达2.5%:{hit25}({hit25/len(yrs)*100:.1f}%), 达5%:{hit5}({hit5/len(yrs)*100:.1f}%), 均:{avg:.2f}%')

# 检查超人原版在2026年的表现
from collections import defaultdict

def superman_original(dt):
    """原版超人v2评分"""
    stocks = d.get(dt, [])
    cand = []
    for s in stocks:
        p = s['p']
        if p < 5 or p > 8: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < 1.0: continue
        ri = real.get(s['code'])
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > 15: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= 200: continue
        nm = names.get(s['code'],'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > 100: continue
        cl = s.get('cl',0)
        
        sc = 10
        if 5 <= p <= 6.5: sc += 15
        elif 6.5 < p <= 7: sc += 8
        elif 4.5 <= p < 5: sc += 5
        if 70 <= cl <= 85: sc += 15
        elif 85 < cl <= 90: sc += 5
        elif 60 <= cl < 70: sc += 3
        if cl > 90: sc -= 20
        if p > 7: sc -= 15
        if 1.2 <= vr <= 2.0: sc += 10
        elif 2.0 < vr <= 3.0: sc += 5
        elif 1.0 <= vr < 1.2: sc += 3
        if vr > 3: sc -= 15
        
        nv = s.get('n',0) or 0
        cand.append((sc, nm, s['code'], p, nv, vr, cl, hsl, sz, jv, s.get('close',0)))
    
    if not cand: return None
    cand.sort(key=lambda x: (-x[0], -x[3]))
    return cand[0]

for year in ['2025','2026']:
    yrs = [dt for dt in dates if dt.startswith(year)]
    results = []
    for dt in yrs:
        c = superman_original(dt)
        if c:
            results.append(c)
    nv = [r[4] for r in results]
    hit25 = sum(1 for v in nv if v >= 2.5)
    hit5 = sum(1 for v in nv if v >= 5)
    avg = sum(nv)/len(nv)
    print(f'\n超人原版 {year}: {len(results)}天, 冠军达2.5%:{hit25}({hit25/len(results)*100:.1f}%), 达5%:{hit5}({hit5/len(results)*100:.1f}%), 均:{avg:.2f}%')
    # 展示最近的5天
    for dt in ['2026-05-19','2026-05-20','2026-05-21','2026-05-22']:
        c = superman_original(dt)
        if c:
            ns = f'{c[4]:.2f}%' if c[4] else 'N/A'
            ok = '🔥' if c[4] >= 5 else ('✅' if c[4] >= 2.5 else '❌')
            print(f'  {dt}: {c[1]}({c[2]}) 评{c[0]} 涨{c[3]:.1f}% CL{c[6]:.0f}% 量{c[5]:.2f} 换{c[7]:.0f}% 买{c[10]:.2f} 次日高{ns} {ok}')
