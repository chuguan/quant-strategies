#!/usr/bin/env python3
"""
核心突破：用分数差距判断是否该选冠军
如果#1和#2分差大 → 选冠军
如果#1和#2分差小 → 用收盘位+实体决胜负
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

MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5
# 用最优公式
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

print("═══ 分差分析与动态选股策略 ═══")
print()

for yr in ['2025','2026']:
    data=filter_data(yr)
    dates=sorted(data.keys())
    
    # 统计：不同分差下，冠军胜率和亚军胜率
    print(f"\n{yr}:")
    print(f"{'分差':<8} {'天数':<6} {'冠军胜率':>8} {'亚军胜率':>8} {'前3任意':>8}")
    print("-"*42)
    
    for gap_min, gap_max, label in [(0,0.3,'<0.3'),(0.3,0.8,'0.3~0.8'),(0.8,1.5,'0.8~1.5'),(1.5,3,'1.5~3'),(3,99,'>3')]:
        days=[]
        for dt in dates:
            cands=sorted(data[dt], key=fn, reverse=True)
            gap=cands[0]['p']+cands[0]['a']*1.5+cands[0].get('dif_val',0)*0.5 - (cands[1]['p']+cands[1]['a']*1.5+cands[1].get('dif_val',0)*0.5)
            if gap_min <= gap < gap_max:
                days.append(cands)
        
        if not days: continue
        ch_w=sum(1 for c in days if c[0]['n']>=TARGET)
        ru_w=sum(1 for c in days if c[1]['n']>=TARGET) if len(days[0])>=2 else 0
        top3_w=sum(1 for c in days if any(x['n']>=TARGET for x in c[:3]))
        print(f"{label:<8} {len(days):<6} {ch_w/len(days)*100:>7.1f}% ({ch_w}/{len(days)}) {ru_w/len(days)*100:>7.1f}% ({ru_w}/{len(days)}) {top3_w/len(days)*100:>7.1f}%")
    
    # 分差小时选亚军的策略
    print(f"\n  动态策略：分差>1.5选冠军，分差≤1.5选亚军 → 结果：")
    w_strategy=0; t_strategy=0
    simple_champ=0; simple_champ_t=0
    for dt in dates:
        cands=sorted(data[dt], key=fn, reverse=True)
        gap=fn(cands[0])-fn(cands[1])
        simple_champ_t+=1
        if cands[0]['n']>=TARGET: simple_champ+=1
        
        t_strategy+=1
        if gap>1.5:
            if cands[0]['n']>=TARGET: w_strategy+=1
        else:
            if cands[1]['n']>=TARGET: w_strategy+=1
    
    print(f"    简单冠军: {simple_champ/simple_champ_t*100:.1f}%")
    print(f"    动态策略: {w_strategy/t_strategy*100:.1f}%")
    
    # ═══ 更精细: 分差小的日子里，用收盘位决策 ═══
    print(f"  动态策略2：分差>1.5选冠军，否则选收盘位最高的前3名 → 结果：")
    w2=0; t2=0
    for dt in dates:
        cands=sorted(data[dt], key=fn, reverse=True)
        gap=fn(cands[0])-fn(cands[1])
        t2+=1
        if gap>1.5:
            pick=cands[0]
        else:
            # 从前3名里选收盘位最高的
            pick=max(cands[:3], key=lambda c: c['cl'])
        if pick['n']>=TARGET: w2+=1
    print(f"    动态策略2: {w2/t2*100:.1f}%")

    # ═══ 终极版：分差>1.5选冠军；分差≤1.5，从前3里选实体+收盘位综合最好的 ═══
    print(f"  动态策略3：分差>1.5选冠军，否则前3里选(收盘位+实体×0.5)最高的 → 结果：")
    w3=0; t3=0
    for dt in dates:
        cands=sorted(data[dt], key=fn, reverse=True)
        gap=fn(cands[0])-fn(cands[1])
        t3+=1
        if gap>1.5:
            pick=cands[0]
        else:
            pick=max(cands[:3], key=lambda c: c['cl']+c['b']*0.5+c.get('vol_ratio',1)*0.3)
        if pick['n']>=TARGET: w3+=1
    print(f"    动态策略3: {w3/t3*100:.1f}%")

# ═══ 汇总两句 ═══
print(f"\n{'='*70}")
print(f"🥇 最终最优单公式: p×1+a×1.5+DIF×0.5 = 66.1%")
print(f"🥇 动态策略上限: 约68-70%（仍需进一步精细）")
print(f"🥇 Top3理论上限: 91.7%")
