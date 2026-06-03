"""超人策略 — Top3 回测（按月）"""
import pickle
from collections import defaultdict

with open('big_cache.pkl','rb') as f:
    c = pickle.load(f)
d, real, names = c['data'], c['real'], c['names']
dates = sorted(d.keys())

def superman_top3(dt):
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
    
    if not cand: return []
    cand.sort(key=lambda x: (-x[0], -x[3]))
    return cand[:3]

for year in ['2025','2026']:
    yrs = [dt for dt in dates if dt.startswith(year)]
    by_month = defaultdict(lambda: {'days':0, 'c1_n':[], 'c2_n':[], 'c3_n':[], 'top3_best':[], 'any_hit2':0})
    
    for dt in yrs:
        top3 = superman_top3(dt)
        if not top3: continue
        m = dt[:7]
        by_month[m]['days'] += 1
        if len(top3) >= 1: by_month[m]['c1_n'].append(top3[0][4])
        if len(top3) >= 2: by_month[m]['c2_n'].append(top3[1][4])
        if len(top3) >= 3: by_month[m]['c3_n'].append(top3[2][4])
        # Top3中任意一只达2.5%
        if any(t[4] >= 2.5 for t in top3):
            by_month[m]['any_hit2'] += 1
        # Top3最佳涨幅
        by_month[m]['top3_best'].append(max(t[4] for t in top3))
    
    print(f'\n{"="*80}')
    print(f'  {year}年 超人策略 Top3 按月统计')
    print(f'{"="*80}')
    header = f'{"月份":<8} {"天":<4} {"冠军均%":<8} {"亚军均%":<8} {"季军均%":<8} {"Top3均%":<8} {"任意达标%":<10}'
    print(header)
    print(f'{"":-<80}')
    
    t_d, t1, t2, t3, ta, th = 0, [], [], [], [], 0
    for month in sorted(by_month.keys()):
        m = by_month[month]
        a1 = sum(m['c1_n'])/len(m['c1_n']) if m['c1_n'] else 0
        a2 = sum(m['c2_n'])/len(m['c2_n']) if m['c2_n'] else 0
        a3 = sum(m['c3_n'])/len(m['c3_n']) if m['c3_n'] else 0
        ab = sum(m['top3_best'])/len(m['top3_best']) if m['top3_best'] else 0
        ah = m['any_hit2']/m['days']*100 if m['days'] else 0
        
        t_d += m['days']
        t1.extend(m['c1_n']); t2.extend(m['c2_n']); t3.extend(m['c3_n'])
        th += m['any_hit2']
        
        print(f'{month:<8} {m["days"]:<4} {a1:<8.2f} {a2:<8.2f} {a3:<8.2f} {ab:<8.2f} {ah:<10.1f}')
    
    ta1 = sum(t1)/len(t1) if t1 else 0
    ta2 = sum(t2)/len(t2) if t2 else 0
    ta3 = sum(t3)/len(t3) if t3 else 0
    tah = th/t_d*100 if t_d else 0
    print(f'{"":-<80}')
    print(f'{"合计":<8} {t_d:<4} {ta1:<8.2f} {ta2:<8.2f} {ta3:<8.2f} {"":<8} {tah:<10.1f}')

# 2026近10天Top3详情
print(f'\n{"="*80}')
print(f'  2026年5月 Top3 详情')
print(f'{"="*80}')
for dt in [d for d in dates if d.startswith('2026-05')]:
    top3 = superman_top3(dt)
    if not top3: continue
    print(f'\n{dt} ({len(top3)}只候选):')
    for i, t in enumerate(top3, 1):
        ns = f'{t[4]:+.2f}%' if t[4] else 'N/A'
        ok = '🔥' if t[4] >= 5 else ('✅' if t[4] >= 2.5 else '❌')
        print(f'  #{i} {t[1]}({t[2]}) 评{t[0]} 买{t[10]:.2f} 涨{t[3]:.1f}% → {ns} {ok}')
    # Top3任1达标
    any_ok = any(t[4] >= 2.5 for t in top3)
    print(f'  Top3任意达标: {"✅" if any_ok else "❌"}')
