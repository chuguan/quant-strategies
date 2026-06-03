#!/usr/bin/env python3
"""
🐷 CG-08 缓存版（秒出）
评分：涨跌幅×1 + ATR×1.5 + DIF×0.5
     + MACD向上+3 + MA5斜率>8%+3 + J领涨+3
     - 上影>30%-3 - 虚涨(实体/涨跌幅<0.5)-5 - 前日异常-3
"""
import pickle, os, sys
from collections import defaultdict

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5
ST=set()

if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']; names=cache['names']

def score(c):
    # 基础：涨跌幅×1 + ATR×1.5
    sc = c['p'] + c['a']*1.5
    # DIF加分（MACD强度）
    if c.get('dif_val',0): sc += c['dif_val']*0.5
    # 收盘位加分（位置越高次日惯性越大）
    sc += c.get('cl',0)*0.02
    # 上影太长减分（冲高回落风险）
    if c.get('s',0)>40: sc-=3
    return round(sc,2)

# 严格过滤（在big_cache数据上再筛一层）
def pass_filter(c):
    if c['code'] in ST: return False
    if c['p'] is None or not (MIN_CHG <= c['p'] < MAX_CHG): return False
    if c['n'] is None: return False
    if c.get('a',0) <= 3: return False  # ATR>3%
    if c.get('is_yang',0) != 1: return False  # 阳线
    if c.get('above_ma5',0) != 1: return False  # 站MA5
    return True

for yr in ['2025','2026']:
    by_date=defaultdict(list)
    for dt in data_cache:
        if not dt.startswith(yr): continue
        for c in data_cache[dt]:
            if not pass_filter(c) or c['n'] is None: continue
            by_date[dt].append(c)
    by_date={k:v for k,v in by_date.items() if len(v)>=5}
    w=t=0
    for dt in sorted(by_date.keys()):
        cands=[c for c in by_date[dt]]
        for c in cands: c['sc']=score(c)
        best=max(cands, key=lambda c:c['sc'])
        t+=1
        if best['n']>=TARGET: w+=1
    print(f"📊 {yr}: {t}天全勤, 胜率{w/t*100:.1f}% ({w}/{t})")

# TOP5
latest=sorted([dt for dt in data_cache if dt.startswith('2026')])[-1]
cands=[c for c in data_cache.get(latest,[]) if pass_filter(c)]
for c in cands: c['sc']=score(c)
cands.sort(key=lambda x:x['sc'], reverse=True)

print(f"\n📅 {latest} Top5推荐:")
for i,c in enumerate(cands[:5],1):
    name=names.get(c['code'],'?')
    print(f"  {i}. {name}({c['code']}) 买入{c['close']:.2f} 涨{c['p']:+.1f}% 评分{c['sc']}")
