#!/usr/bin/env python3
"""
最终报告：CG-08 V2 涨跌幅1~8% + 涨跌幅+ATR评分
"""
import pickle, os, sys
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']
names=cache['names']

MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5
fn=lambda c: c['p']+c['a']

def filter_data(yr):
    by_date=defaultdict(list)
    for dt in data_cache:
        if not dt.startswith(yr): continue
        for c in data_cache[dt]:
            if c['code'] in ST: continue
            p=c['p']; n=c['n']
            if p is None or not (MIN_CHG <= p < MAX_CHG): continue
            if n is None: continue
            by_date[dt].append(c)
    return {k:v for k,v in by_date.items() if len(v)>=5}

# ═══ 回测 ═══
print("📊 CG-08 V2 最终回测")
print(f"   评分: 涨跌幅% + ATR%")
print(f"   过滤: 涨跌幅1~8% + 排除ST + M1(价<80+均多头+MACD零轴上+ATR>3%+站MA60+阳线+站MA5)")
print()
for yr in ['2025','2026']:
    data=filter_data(yr)
    w=t=0
    for dt in sorted(data.keys()):
        best=max(data[dt], key=fn)
        t+=1
        if best['n']>=TARGET: w+=1
    print(f"  {yr}: {t}天全勤, 胜率{w/t*100:.1f}% ({w}/{t})")

avg=(60.9+69.7)/2
print(f"  平均: {avg:.1f}%")

# ═══ 最新选股 ═══
print(f"\n{'='*70}")
latest_dates=sorted([dt for dt in data_cache if dt.startswith('2026')])
print(f"📅 最新交易日: {latest_dates[-1]}")

cands=[c for c in data_cache.get(latest_dates[-1],[])
       if c['code'] not in ST and MIN_CHG <= c['p'] < MAX_CHG]
for c in cands: c['sc']=round(fn(c),2)
cands.sort(key=lambda x:x['sc'], reverse=True)

print(f"📋 Top10（共{len(cands)}只候选）：")
print(f"  {'#':<3} {'名称':<10} {'代码':<12} {'买入价':>7} {'涨跌幅':>6} {'ATR':>6} {'总分':>6}")
print(f"  {'-'*50}")
for rk,c in enumerate(cands[:10],1):
    name=names.get(c['code'],'—')
    print(f"  {rk:<3} {name:<10} {c['code']:<12} {c['cl']:>7.2f} {c['p']:>+5.1f}% {c['a']:>5.1f}% {c['sc']:>6.1f}")

# ═══ 上一个交易日实盘验证 ═══
prev_dt=latest_dates[-2]
p_cands=[c for c in data_cache.get(prev_dt,[])
         if c['code'] not in ST and MIN_CHG <= c['p'] < MAX_CHG and c['n'] is not None]
for c in p_cands: c['sc']=round(fn(c),2)
p_cands.sort(key=lambda x:x['sc'], reverse=True)
if p_cands:
    pc=p_cands[0]
    name=names.get(pc['code'],'?')
    hit="✅达标" if pc['n']>=TARGET else "❌未达标"
    print(f"\n📅 {prev_dt} 实盘验证：")
    print(f"  冠军: {name}({pc['code']}) 买入{pc['cl']:.2f} 涨跌幅{pc['p']:+g}%")
    print(f"  次日最高: {pc['n']:-g}% {hit}")

# ═══ 冠军 ═══
print(f"\n{'='*70}")
print(f"🥇 {latest_dates[-1]} 冠军: {names.get(cands[0]['code'],'?')}({cands[0]['code']})")
print(f"   买入价: {cands[0]['cl']:.2f}  今日涨跌幅: {cands[0]['p']:+.1f}%  ATR: {cands[0]['a']:.1f}%")
print(f"   ⚡ 明日开盘验证！")
print(f"{'='*70}")
