#!/usr/bin/env python3
"""
每天买Top3的精确回测
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

print("="*70)
print("📊 每日买Top3策略回测（全仓3万，每只1万）")
print("="*70)

for yr in ['2025','2026']:
    data=filter_data(yr)
    dates=sorted(data.keys())
    
    # 统计
    any_win=0  # 至少有1只达标的交易日
    all_3_win=0  # 3只全部达标的交易日
    no_win=0  # 3只全部失败的交易日
    
    avg_high_1=0  # #1的次日平均涨幅
    avg_high_2=0
    avg_high_3=0
    total_high=0  # 3只合计
    
    for dt in dates:
        cands=sorted(data[dt], key=fn, reverse=True)[:3]
        wins=sum(1 for c in cands if c['n']>=TARGET)
        if wins>=1: any_win+=1
        if wins==3: all_3_win+=1
        if wins==0: no_win+=1
        
        if len(cands)>=1: avg_high_1+=cands[0]['n']
        if len(cands)>=2: avg_high_2+=cands[1]['n']
        if len(cands)>=3: avg_high_3+=cands[2]['n']
        for c in cands: total_high+=c['n']
    
    N=len(dates)
    print(f"\n{yr} ({N}个交易日):")
    print(f"  ✅ 每天3只 = 3×{N}={3*N}笔交易")
    print(f"  🏆 当日至少赢1只: {any_win}/{N} = {any_win/N*100:.1f}%")
    print(f"  🥇 当日3只全赢: {all_3_win}/{N} = {all_3_win/N*100:.1f}%")
    print(f"  ❌ 当日3只全输: {no_win}/{N} = {no_win/N*100:.1f}%")
    print(f"\n  单只平均次日涨幅:")
    print(f"    #1冠军: {avg_high_1/N:+.1f}%")
    print(f"    #2亚军: {avg_high_2/N:+.1f}%")
    print(f"    #3季军: {avg_high_3/N:+.1f}%")
    print(f"    3只平均: {total_high/(3*N):+.1f}%")
    
    # 每日平均收益（假设每只1万）
    daily_return=total_high/(N)/100*10000  # 3万本金, 平均每日收益
    print(f"\n  每日平均收益:")
    print(f"    每日期望收益: {total_high/N:.1f}% × 3万 = 约{total_high/N*30000/100:.0f}元")
    print(f"    年化收益(250天): 约{total_high/N*300*30000/100:.0f}元")

# ═══ 最新选股：Top3 ═══
print(f"\n{'='*70}")
print("🏆 最新 Top3 推荐（每日买入）")
print("="*70)

latest=sorted([dt for dt in data_cache if dt.startswith('2026')])[-1]
cands=[c for c in data_cache.get(latest,[]) if c['code'] not in ST and MIN_CHG <= c['p'] < MAX_CHG]
for c in cands: c['sc']=round(fn(c),2)
cands.sort(key=lambda x:x['sc'], reverse=True)
cands=cands[:10]

print(f"\n📅 {latest} 推荐买入Top3:")
for i,(c) in enumerate(cands[:3],1):
    name=names.get(c['code'],'?')
    print(f"  {i}. {name}({c['code']}) 买入{c['close']:.2f} 涨{c['p']:+.1f}% ATR{c['a']:.1f}% 评分{c['sc']:.1f}")

# 上一天验证
prev_dt=sorted([dt for dt in data_cache if dt.startswith('2026')])[-2]
prev=[c for c in data_cache.get(prev_dt,[]) if c['code'] not in ST and MIN_CHG <= c['p'] < MAX_CHG and c['n'] is not None]
for c in prev: c['sc']=round(fn(c),2)
prev.sort(key=lambda x:x['sc'], reverse=True)
print(f"\n📅 {prev_dt} 实盘验证:")
for i,c in enumerate(prev[:3],1):
    name=names.get(c['code'],'?')
    hit="✅" if c['n']>=2.5 else "❌"
    print(f"  {i}. {name}({c['code']}) 买入{c['close']:.2f} → 次日最高{c['n']:+.1f}% {hit}")
