#!/usr/bin/env python3
"""
找具体案例：冠军跌但亚军/季军涨的日子
输出股票名称+代码，方便用户自己去翻K线
"""
import pickle, os
from collections import defaultdict

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']
names=cache['names']

MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5
fn=lambda c: c['p']+c['a']*1.5+c.get('dif_val',0)*0.5

# 找2026年最新的案例
data=defaultdict(list)
for dt in data_cache:
    if not dt.startswith('2026'): continue
    for c in data_cache[dt]:
        if c['code'] in ST: continue
        p=c['p']; n=c['n']
        if p is None or not (MIN_CHG <= p < MAX_CHG): continue
        if n is None: continue
        data[dt].append(c)

data={k:v for k,v in data.items() if len(v)>=5}
dates=sorted(data.keys())

print("═══ 案例搜索：冠军跌但第2/3名涨 ═══")
print()

all_cases=[]
for dt in reversed(dates):  # 从最近开始找
    cands=sorted(data[dt], key=fn, reverse=True)
    if len(cands)<3: continue
    c1, c2, c3 = cands[0], cands[1], cands[2]
    
    # 找：冠军失败（n<2.5），且第2或第3名成功（n>=2.5）
    if c1['n'] < 2.5 and (c2['n'] >= 2.5 or c3['n'] >= 2.5):
        all_cases.append((dt, c1, c2, c3))
        
        name1=names.get(c1['code'],'?'); name2=names.get(c2['code'],'?'); name3=names.get(c3['code'],'?')
        
        print(f"📅 {dt}")
        print(f"  {'':>4} {'名称':<10} {'代码':<12} {'涨跌幅':>6} {'实体':>6} {'上影':>5} {'ATR':>5} {'收盘位':>5} {'DIF':>6} {'评分':>6} {'次日高':>6}")
        print(f"  {'─'*70}")
        print(f"  {'🥇':<4} {name1:<10} {c1['code']:<12} {c1['p']:>+5.1f}% {c1['b']:>5.1f}% {c1['s']:>4.1f}% {c1['a']:>4.1f}% {c1['cl']:>4.1f}% {c1.get('dif_val',0):>5.2f} {fn(c1):>5.1f} {c1['n']:>+5.1f}% {'❌' if c1['n']<2.5 else '✅'}")
        print(f"  {'🥈':<4} {name2:<10} {c2['code']:<12} {c2['p']:>+5.1f}% {c2['b']:>5.1f}% {c2['s']:>4.1f}% {c2['a']:>4.1f}% {c2['cl']:>4.1f}% {c2.get('dif_val',0):>5.2f} {fn(c2):>5.1f} {c2['n']:>+5.1f}% {'✅' if c2['n']>=2.5 else '❌'}")
        print(f"  {'🥉':<4} {name3:<10} {c3['code']:<12} {c3['p']:>+5.1f}% {c3['b']:>5.1f}% {c3['s']:>4.1f}% {c3['a']:>4.1f}% {c3['cl']:>4.1f}% {c3.get('dif_val',0):>5.2f} {fn(c3):>5.1f} {c3['n']:>+5.1f}% {'✅' if c3['n']>=2.5 else '❌'}")
        
        # 第2和第3名特征对比
        print(f"\n  🔍 第2名比冠军强在哪:")
        diffs=[]
        for feat,label in [('p','涨跌幅'),('b','实体'),('s','上影'),('a','ATR'),('cl','收盘位'),('vol_ratio','量比'),('ma5_slope','MA5斜率')]:
            diff=c2.get(feat,c1.get(feat,0))-c1.get(feat,0)
            dirr='高' if diff>0 else '低'
            diffs.append(f"{label}{dirr}{abs(diff):.1f}")
        print(f"  {' '.join(diffs)}")
        
        print()
        
        # 只找最近3个案例就够了
        if len(all_cases) >= 3:
            break

# 再找2025年的3个典型案例
print("\n═══ 2025年典型案例 ═══")
data25=defaultdict(list)
for dt in data_cache:
    if not dt.startswith('2025'): continue
    for c in data_cache[dt]:
        if c['code'] in ST: continue
        p=c['p']; n=c['n']
        if p is None or not (MIN_CHG <= p < MAX_CHG): continue
        if n is None: continue
        data25[dt].append(c)
data25={k:v for k,v in data25.items() if len(v)>=5}

cases_2025=[]
for dt in sorted(data25.keys(), reverse=True):
    cands=sorted(data25[dt], key=fn, reverse=True)
    if len(cands)<3: continue
    c1, c2, c3 = cands[0], cands[1], cands[2]
    if c1['n'] < 2.5 and (c2['n'] >= 2.5 or c3['n'] >= 2.5):
        cases_2025.append((dt, c1, c2, c3))
        
        name1=names.get(c1['code'],'?'); name2=names.get(c2['code'],'?'); name3=names.get(c3['code'],'?')
        print(f"📅 {dt}")
        print(f"  {'🥇':<4} {name1:<10} {c1['code']:<12} 涨{c1['p']:+.1f}% 收盘位{c1['cl']:.0f}% ATR{c1['a']:.1f}% 次日{c1['n']:+.1f}% ❌")
        print(f"  {'🥈':<4} {name2:<10} {c2['code']:<12} 涨{c2['p']:+.1f}% 收盘位{c2['cl']:.0f}% ATR{c2['a']:.1f}% 次日{c2['n']:+.1f}% ✅")
        print(f"  {'🥉':<4} {name3:<10} {c3['code']:<12} 涨{c3['p']:+.1f}% 收盘位{c3['cl']:.0f}% ATR{c3['a']:.1f}% 次日{c3['n']:+.1f}% {'✅' if c3['n']>=2.5 else '❌'}")
        print()
        
        if len(cases_2025) >= 5:
            break

print(f"\n共找到2026年{len(all_cases)}个案例, 2025年{len(cases_2025)}个案例")
print("你可以去翻这些股票的K线图看看——为什么第2名比第1名强")
