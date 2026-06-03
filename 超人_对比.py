"""超人策略 — 冠军vs亚军vs季军 全面对比"""
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
    by_month = defaultdict(lambda: {'d':0, 'c1':[], 'c2':[], 'c3':[], 'top3_any':0, 'top2_any':0})
    
    for dt in yrs:
        top3 = superman_top3(dt)
        if not top3: continue
        m = dt[:7]
        by_month[m]['d'] += 1
        if len(top3) >= 1: by_month[m]['c1'].append(top3[0][4])
        if len(top3) >= 2: by_month[m]['c2'].append(top3[1][4])
        if len(top3) >= 3: by_month[m]['c3'].append(top3[2][4])
        if any(t[4] >= 2.5 for t in top3):
            by_month[m]['top3_any'] += 1
        if any(t[4] >= 2.5 for t in top3[:2]):
            by_month[m]['top2_any'] += 1
    
    print(f'\n{"="*110}')
    print(f'  {year}年 超人策略 冠/亚/季军 全面对比')
    print(f'{"="*110}')
    print(f'{"月份":<6} {"天":<4} {"冠均%":<7} {"冠达2.5":<11} {"冠达5%":<10} ', end='')
    print(f'{"亚均%":<7} {"亚达2.5":<11} {"季均%":<7} {"季达2.5":<11} ', end='')
    print(f'{"Top2任达":<10} {"Top3任达":<10}')
    print(f'{"":-<110}')
    
    td, tc1, tc2, tc3, tt2, tt3 = 0, [], [], [], 0, 0
    for month in sorted(by_month.keys()):
        m = by_month[month]
        a1 = sum(m['c1'])/len(m['c1']) if m['c1'] else 0
        a2 = sum(m['c2'])/len(m['c2']) if m['c2'] else 0
        a3 = sum(m['c3'])/len(m['c3']) if m['c3'] else 0
        h1 = sum(1 for v in m['c1'] if v >= 2.5)
        h5 = sum(1 for v in m['c1'] if v >= 5)
        h2 = sum(1 for v in m['c2'] if v >= 2.5)
        h3 = sum(1 for v in m['c3'] if v >= 2.5)
        
        td += m['d']; tc1.extend(m['c1']); tc2.extend(m['c2']); tc3.extend(m['c3'])
        tt2 += m['top2_any']; tt3 += m['top3_any']
        
        p1 = h1/len(m['c1'])*100 if m['c1'] else 0
        p5 = h5/len(m['c1'])*100 if m['c1'] else 0
        p2 = h2/len(m['c2'])*100 if m['c2'] else 0
        p3 = h3/len(m['c3'])*100 if m['c3'] else 0
        pa2 = m['top2_any']/m['d']*100
        pa3 = m['top3_any']/m['d']*100
        
        print(f'{month:<6} {m["d"]:<4} {a1:<7.2f} {h1}/{len(m["c1"])}({p1:5.1f}%) {h5}({p5:4.1f}%) ', end='')
        print(f'{a2:<7.2f} {h2}/{len(m["c2"])}({p2:5.1f}%) ', end='')
        print(f'{a3:<7.2f} {h3}/{len(m["c3"])}({p3:5.1f}%) ', end='')
        print(f'{pa2:<10.1f} {pa3:<10.1f}')
    
    # 合计
    a1 = sum(tc1)/len(tc1) if tc1 else 0
    a2 = sum(tc2)/len(tc2) if tc2 else 0
    a3 = sum(tc3)/len(tc3) if tc3 else 0
    h1 = sum(1 for v in tc1 if v >= 2.5)
    h5 = sum(1 for v in tc1 if v >= 5)
    h2 = sum(1 for v in tc2 if v >= 2.5)
    h3 = sum(1 for v in tc3 if v >= 2.5)
    
    print(f'{"":-<110}')
    pa1 = h1/len(tc1)*100 if tc1 else 0
    pa5 = h5/len(tc1)*100 if tc1 else 0
    pa2 = h2/len(tc2)*100 if tc2 else 0
    pa3 = h3/len(tc3)*100 if tc3 else 0
    print(f'{"合计":<6} {td:<4} {a1:<7.2f} {h1}/{len(tc1)}({pa1:5.1f}%) {h5}({pa5:4.1f}%) ', end='')
    print(f'{a2:<7.2f} {h2}/{len(tc2)}({pa2:5.1f}%) ', end='')
    print(f'{a3:<7.2f} {h3}/{len(tc3)}({pa3:5.1f}%) ', end='')
    print(f'{tt2/td*100:<10.1f} {tt3/td*100:<10.1f}')
    
    print(f'\n  🔑 关键结论：', flush=True)
    print(f'  冠军达2.5%: {pa1:.1f}% | 亚军达2.5%: {pa2:.1f}% | 季军达2.5%: {pa3:.1f}%', flush=True)
    print(f'  Top2任意达标: {tt2/td*100:.1f}% | Top3任意达标: {tt3/td*100:.1f}%', flush=True)
    if len(tc2) > 0:
        print(f'  亚军均: {a2:.2f}% vs 冠军均: {a1:.2f}%', flush=True)
