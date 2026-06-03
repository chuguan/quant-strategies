#!/usr/bin/env python3
"""
关键分析：前3名里，赢家 vs 输家的特征区别
找出什么条件下#2/#3比#1更值得买
"""
import pickle, os
from collections import defaultdict

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

print("═══ 前3名内：赢家 vs 输家特征差异分析 ═══")
print()

for yr in ['2025','2026']:
    data=filter_data(yr)
    
    # 收集：在"前3名中至少有一个赢家"的日子里，
    # 赢家(次日≥2.5%) vs 输家(次日<2.5%) 的特征对比
    winners=[]  # 前3名中赢家的特征
    losers=[]   # 前3名中输家的特征
    winner_days=0
    total_days=0
    
    for dt in sorted(data.keys()):
        cands=sorted(data[dt], key=fn, reverse=True)[:3]
        total_days+=1
        has_winner=False
        for c in cands:
            if c['n']>=TARGET:
                winners.append(c)
                has_winner=True
            else:
                losers.append(c)
        if has_winner:
            winner_days+=1
    
    print(f"\n{yr}:")
    print(f"  总天数: {total_days}, 前3有赢家: {winner_days} ({winner_days/total_days*100:.1f}%)")
    print(f"  赢家样本: {len(winners)}, 输家样本: {len(losers)}")
    
    if not winners or not losers:
        continue
    
    # 特征对比
    print(f"\n  {'特征':<12} {'赢家均值':>8} {'输家均值':>8} {'差距':>8} {'建议':<20}")
    print(f"  {'-'*56}")
    for feat_name, key in [('涨跌幅p','p'),('实体b','b'),('上影s','s'),('ATR a','a'),('收盘位cl','cl')]:
        w_avg=sum(c[key] for c in winners)/len(winners)
        l_avg=sum(c[key] for c in losers)/len(losers)
        diff=w_avg-l_avg
        # 简单建议方向
        if diff>0:
            suggest=f"越高越好(+{diff:.2f})"
        else:
            suggest=f"越低越好({diff:.2f})"
        print(f"  {feat_name:<12} {w_avg:>8.2f} {l_avg:>8.2f} {diff:>+8.2f} {suggest}")

# ═══ 单独看冠军输+亚军赢的案例 ═══
print("\n\n═══ 最关键：冠军输但亚军赢的情况 → 什么条件下亚军更好？ ═══")

for yr in ['2025','2026']:
    data=filter_data(yr)
    champ_fails=[]
    for dt in sorted(data.keys()):
        cands=sorted(data[dt], key=fn, reverse=True)
        if len(cands)<2: continue
        if cands[0]['n']<TARGET and cands[1]['n']>=TARGET:
            champ_fails.append((cands[0], cands[1]))
    
    print(f"\n{yr}: {len(champ_fails)}天冠军输且亚军赢")
    
    if not champ_fails:
        continue
    
    # 关键问题：当冠军和亚军的p+a分差很小时，谁更好？
    close=[(c,r) for c,r in champ_fails if abs((c['p']+c['a'])-(r['p']+r['a']))<1]
    big=[(c,r) for c,r in champ_fails if abs((c['p']+c['a'])-(r['p']+r['a']))>=1]
    print(f"  分差<1的{len(close)}天, 分差≥1的{len(big)}天")
    
    # 分差小的案例中，什么特征决定了亚军赢？
    print(f"\n  分差<1时，冠军 vs 亚军特征对比:")
    print(f"  {'特征':<10} {'冠军':>8} {'亚军':>8} {'差':>8}")
    for feat_name, key in [('涨跌幅','p'),('实体','b'),('上影','s'),('ATR','a'),('收盘位','cl')]:
        c_avg=sum(c[0][key] for c in close)/len(close)
        r_avg=sum(c[1][key] for c in close)/len(close)
        print(f"  {feat_name:<10} {c_avg:>8.2f} {r_avg:>8.2f} {r_avg-c_avg:>+8.2f}")
    
    # 重磅发现：在什么条件下冠军最容易被反超？
    print(f"\n  冠军被反超时的共性特征（39天均值）:")
    c_avg_p=sum(c[0]['p'] for c in champ_fails)/len(champ_fails)
    c_avg_a=sum(c[0]['a'] for c in champ_fails)/len(champ_fails)
    c_avg_b=sum(c[0]['b'] for c in champ_fails)/len(champ_fails)
    c_avg_s=sum(c[0]['s'] for c in champ_fails)/len(champ_fails)
    c_avg_cl=sum(c[0]['cl'] for c in champ_fails)/len(champ_fails)
    r_avg_p=sum(c[1]['p'] for c in champ_fails)/len(champ_fails)
    r_avg_a=sum(c[1]['a'] for c in champ_fails)/len(champ_fails)
    r_avg_b=sum(c[1]['b'] for c in champ_fails)/len(champ_fails)
    r_avg_s=sum(c[1]['s'] for c in champ_fails)/len(champ_fails)
    r_avg_cl=sum(c[1]['cl'] for c in champ_fails)/len(champ_fails)
    
    print(f"  冠军: 涨跌幅{c_avg_p:.1f}% 实体{c_avg_b:.1f}% 上影{c_avg_s:.1f}% ATR{c_avg_a:.1f}% 收盘位{c_avg_cl:.1f}%")
    print(f"  亚军: 涨跌幅{r_avg_p:.1f}% 实体{r_avg_b:.1f}% 上影{r_avg_s:.1f}% ATR{r_avg_a:.1f}% 收盘位{r_avg_cl:.1f}%")
    
    # 核心总结
    print(f"\n  🔑 关键差异:")
    for fn,key,name in [('涨跌幅','p','p'),('实体','b','实体'),('ATR','a','ATR'),('收盘位','cl','收盘位')]:
        c_v=sum(c[0][key] for c in champ_fails)/len(champ_fails)
        r_v=sum(c[1][key] for c in champ_fails)/len(champ_fails)
        print(f"     {name}: 亚军{'+' if r_v>c_v else ''}{r_v-c_v:+.1f}")
