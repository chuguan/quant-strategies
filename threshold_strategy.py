#!/usr/bin/env python3
"""
绝招：阈值策略 — 冠军评分不高就不出手！
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
# 最优公式
fn=lambda c: c['p']+c['a']*1.5+c.get('dif_val',0)*0.5

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

print("═══ 阈值策略：冠军评分高于阈值才出手 ═══")
print(f"{'阈值':<6} {'2025胜率':>10} {'2025天数':>10} {'2026胜率':>10} {'2026天数':>10} {'平均胜率':>10}")
print("-"*55)

data25=filter_data('2025')
data26=filter_data('2026')

# 先看评分分布
all_scores=[]
for dt in sorted(data25.keys()):
    best=max(data25[dt], key=fn)
    all_scores.append(fn(best))

print(f"  评分范围: {min(all_scores):.1f} ~ {max(all_scores):.1f}")
print(f"  评分中位数: {sorted(all_scores)[len(all_scores)//2]:.1f}")
print()

for threshold in [8, 10, 11, 12, 13, 14, 15, 16, 18, 20, 25]:
    for yr_name, data in [('2025',data25),('2026',data26)]:
        w=t=0
        for dt in sorted(data.keys()):
            best=max(data[dt], key=fn)
            if fn(best)>=threshold:
                t+=1
                if best['n']>=TARGET: w+=1
        if yr_name=='2025':
            wr25=w/t*100 if t>0 else 0; d25=t
        else:
            wr26=w/t*100 if t>0 else 0; d26=t
    avg=(wr25+wr26)/2
    print(f"{threshold:<6} {wr25:>9.1f}% {d25:>9}天 {wr26:>9.1f}% {d26:>9}天 {avg:>9.1f}%")

# ═══ 多阈值策略：取前3的差异 ═══
print("\n═══ 双选策略：买Top2（各半仓） ═══")
# 如果买Top2，只要有一只达标就算
for threshold in [0, 8, 10, 12, 14]:
    for yr_name, data in [('2025',data25),('2026',data26)]:
        w=t=0
        for dt in sorted(data.keys()):
            cands=sorted(data[dt], key=fn, reverse=True)
            if len(cands)<2: continue
            best1=cands[0]; best2=cands[1]
            score=fn(best1)
            if score<threshold: continue
            t+=1
            # 两票中任意一只达标就算赢
            if best1['n']>=TARGET or best2['n']>=TARGET: w+=1
        if yr_name=='2025':
            wr25=w/t*100 if t>0 else 0; d25=t
        else:
            wr26=w/t*100 if t>0 else 0; d26=t
    avg=(wr25+wr26)/2
    print(f"  阈值{threshold}: {wr25:.1f}%({d25}天) / {wr26:.1f}%({d26}天) / 均{avg:.1f}%")

# ═══ 最重要的：5月22日冠军是多少分？ ═══
print(f"\n{'='*70}")
print("📋 最新交易日选股（big_cache）")
latest=sorted([dt for dt in data_cache if dt.startswith('2026')])[-1]
print(f"📅 {latest}")

cands=[c for c in data_cache.get(latest,[]) if c['code'] not in ST and MIN_CHG <= c['p'] < MAX_CHG]
for c in cands:
    c['sc']=round(fn(c),2)
cands.sort(key=lambda x:x['sc'], reverse=True)

# Top10
print(f"{'#':<3} {'名称':<10} {'代码':<12} {'买入价':>7} {'涨跌幅':>5} {'ATR':>5} {'DIF':>5} {'总分':>6}")
print("-"*55)
for rk,c in enumerate(cands[:10],1):
    name=names.get(c['code'],'?')
    print(f"{rk:<3} {name:<10} {c['code']:<12} {c['close']:>7.2f} {c['p']:>+4.1f} {c['a']:>4.1f} {c.get('dif_val',0):>4.2f} {c['sc']:>6.1f}")

print(f"\n🥇 冠军: {names.get(cands[0]['code'],'?')}({cands[0]['code']}) 评分{cands[0]['sc']:.1f}")
prev_dt=sorted([dt for dt in data_cache if dt.startswith('2026')])[-2]
prev=[c for c in data_cache.get(prev_dt,[]) if c['code'] not in ST and MIN_CHG <= c['p'] < MAX_CHG and c['n'] is not None]
if prev:
    for c in prev: c['sc']=round(fn(c),2)
    prev.sort(key=lambda x:x['sc'], reverse=True)
    pc=prev[0]
    print(f"📅 {prev_dt} 实盘验证:")
    print(f"  冠军: {names.get(pc['code'],'?')}({pc['code']}) 买入{pc['close']} 评{pc['sc']}")
    print(f"  次日最高: {pc['n']:+.1f}% {'✅' if pc['n']>=TARGET else '❌'}")

# 回测结果
print(f"\n{'='*70}")
print("📊 最终版回测")
wr25b=sum(1 for dt in sorted(data25.keys()) if max(data25[dt], key=fn)['n']>=TARGET)/max(len(data25),1)*100
wr26b=sum(1 for dt in sorted(data26.keys()) if max(data26[dt], key=fn)['n']>=TARGET)/max(len(data26),1)*100
print(f"  公式: p×1 + a×1.5 + DIF×0.5")
print(f"  2025: {len(data25)}天全勤, 胜率{wr25b:.1f}%")
print(f"  2026: {len(data26)}天全勤, 胜率{wr26b:.1f}%")
print(f"  平均: {(wr25b+wr26b)/2:.1f}%")
