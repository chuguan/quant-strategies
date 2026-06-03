"""超人策略原版 — 按月分析"""
import pickle
from collections import defaultdict

with open('big_cache.pkl','rb') as f:
    c = pickle.load(f)
d, real, names = c['data'], c['real'], c['names']
dates = sorted(d.keys())

def superman_original(dt):
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
    
    if not cand: return None, []
    cand.sort(key=lambda x: (-x[0], -x[3]))
    return cand[0], cand[:3]

for year in ['2025','2026']:
    yrs = [dt for dt in dates if dt.startswith(year)]
    by_month = defaultdict(list)
    for dt in yrs:
        c, top3 = superman_original(dt)
        if c:
            month = dt[:7]
            by_month[month].append({'dt':dt,'champ':c,'top3':top3})
    
    print(f'\n{"="*70}')
    print(f'  {year}年 超人策略 按月统计')
    print(f'{"="*70}')
    print(f'{"月份":<8} {"天数":<5} {"达2.5%":<8} {"达5%":<8} {"均涨幅":<8} {"冠军达标率":<12}')
    print(f'{"":-<70}')
    
    total_days, total_hit2, total_hit5, total_n = 0, 0, 0, []
    for month in sorted(by_month.keys()):
        data = by_month[month]
        nv = [r['champ'][4] for r in data]
        hit2 = sum(1 for v in nv if v >= 2.5)
        hit5 = sum(1 for v in nv if v >= 5)
        avg = sum(nv)/len(nv)
        total_days += len(nv)
        total_hit2 += hit2
        total_hit5 += hit5
        total_n.extend(nv)
        
        bar = '█' * int(hit2/len(nv)*20) + '░' * (20 - int(hit2/len(nv)*20))
        print(f'{month:<8} {len(data):<5} {hit2:<5}({hit2/len(data)*100:5.1f}%) {hit5:<5}({hit5/len(data)*100:5.1f}%) {avg:<8.2f}% {bar}')
    
    avg_total = sum(total_n)/len(total_n) if total_n else 0
    print(f'{"":-<70}')
    print(f'{"合计":<8} {total_days:<5} {total_hit2:<5}({total_hit2/total_days*100:5.1f}%) {total_hit5:<5}({total_hit5/total_days*100:5.1f}%) {avg_total:<8.2f}%')

# 2026年每月详情: Top3冠军、评分、入场价、次日最高
print(f'\n{"="*70}')
print(f'  2026年 每月冠军详情')
print(f'{"="*70}')
for month in sorted(by_month.keys()):
    if not month.startswith('2026'): continue
    data = by_month[month]
    print(f'\n--- {month} ({len(data)}天) ---')
    for r in data[:5]:  # 前5天
        c = r['champ']
        ns = f'{c[4]:+.2f}%' if c[4] else 'N/A'
        ok = '🔥' if c[4] >= 5 else ('✅' if c[4] >= 2.5 else '❌')
        print(f'  {r["dt"]}: {c[1]}({c[2]}) 评{c[0]} 买{c[10]:.2f} 涨{c[3]:.1f}% → {ns} {ok}')
    if len(data) > 5:
        print(f'  ... 还有{len(data)-5}天')
