#!/usr/bin/env python3
"""
第5轮：Top3投票法 + 放宽M1条件
核心思路：候选池里好票很多，优化选冠军的策略
"""
import pickle, os, sys, math
from collections import defaultdict, Counter

sys.stdout.reconfigure(line_buffering=True)

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']

MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5

def filter_data(yr):
    by_date=defaultdict(list)
    for dt in data_cache:
        if not dt.startswith(yr): continue
        for c in data_cache[dt]:
            if c['code'] in ST: continue
            p=c['p']
            if p is None or not (MIN_CHG <= p < MAX_CHG): continue
            if c['n'] is None: continue
            by_date[dt].append(c)
    return {k:v for k,v in by_date.items() if len(v)>=5}

data25=filter_data('2025')
data26=filter_data('2026')

fn1=lambda c: c['p']+c['a']

# ═══ 多公式投票法 ═══
print("═══ 多公式投票法（从Top3/5里选交集/投票最多的） ═══")
fn2=lambda c: c['p']*c['a']
fn3=lambda c: c['p']+min(c['a'],6)
fn4=lambda c: c['p']*2+c['a']
fn5=lambda c: max(c['p'],3)+c['a']

fns=[('p+a',fn1),('p×a',fn2),('p+min(a,6)',fn3),('2p+a',fn4),('max(p,3)+a',fn5)]

def vote_top_n(data, n_vote=3):
    """N个公式各选Top K，取出现次数最多的"""
    w=t=0
    for dt in sorted(data.keys()):
        votes=Counter()
        for name,fn in fns:
            cands=sorted(data[dt], key=fn, reverse=True)
            for c in cands[:n_vote]:
                votes[c['code']]+=1
        # 投票最多的
        best_code=votes.most_common(1)[0][0]
        best=None
        for c in data[dt]:
            if c['code']==best_code:
                best=c; break
        t+=1
        if best['n']>=TARGET: w+=1
    return w/t*100, w, t

for n in [2,3,5]:
    wr25,_,_=vote_top_n(data25, n)
    wr26,_,_=vote_top_n(data26, n)
    print(f"  Top{n}投票法: 2025={wr25:.1f}%  2026={wr26:.1f}%  平均={(wr25+wr26)/2:.1f}%")

# ═══ 9宫格：3种核心策略 × 3种选法 ═══
print("\n═══ 9宫格对比 ═══")
strategies=[
    ("冠军(p+a)", lambda data: [(max(data[dt], key=fn1),dt) for dt in sorted(data.keys())]),
    ("冠军(p×a)", lambda data: [(max(data[dt], key=fn2),dt) for dt in sorted(data.keys())]),
    ("冠军(2p+a)", lambda data: [(max(data[dt], key=fn4),dt) for dt in sorted(data.keys())]),
    ("Top3中涨幅最大", lambda data: [
        (max(sorted(data[dt], key=fn1, reverse=True)[:3], key=lambda c: c['p']), dt)
        for dt in sorted(data.keys())
    ]),
    ("Top3中ATR最大", lambda data: [
        (max(sorted(data[dt], key=fn1, reverse=True)[:3], key=lambda c: c['a']), dt)
        for dt in sorted(data.keys())
    ]),
    ("Top3中实体最大", lambda data: [
        (max(sorted(data[dt], key=fn1, reverse=True)[:3], key=lambda c: c['b']), dt)
        for dt in sorted(data.keys())
    ]),
    ("随机Top5", lambda data: [
        (__import__('random').choice(sorted(data[dt], key=fn1, reverse=True)[:5]), dt)
        for dt in sorted(data.keys())
    ]),
]

for name, picker in strategies:
    wr25=wr26=0; w25=t25=w26=t26=0
    for best,dt in picker(data25):
        t25+=1
        if best['n']>=TARGET: w25+=1
    for best,dt in picker(data26):
        t26+=1
        if best['n']>=TARGET: w26+=1
    wr25=w25/t25*100 if t25>0 else 0
    wr26=w26/t26*100 if t26>0 else 0
    print(f"  {name:<16}: 2025={wr25:.1f}%  2026={wr26:.1f}%  平均={(wr25+wr26)/2:.1f}% ({t25+t26}天)")

# ═══ 关键分析: 冠军和Top3的差异是什么 ═══
print("\n═══ 冠军vs亚军差距分析 ═══")
for yr,data in [('2025',data25),('2026',data26)]:
    gap_wins=0; gap_losses=0; gap_total=0
    same=0
    for dt in sorted(data.keys()):
        cands=sorted(data[dt], key=fn1, reverse=True)
        if len(cands)<2: continue
        champ=cands[0]
        runner_up=cands[1]
        champ_win=1 if champ['n']>=TARGET else 0
        runner_win=1 if runner_up['n']>=TARGET else 0
        gap_total+=1
        if champ_win==1 and runner_win==1: same+=1
        if champ_win==1 and runner_win==0: gap_wins+=1
        if champ_win==0 and runner_win==1: gap_losses+=1
        if champ_win==0 and runner_win==0: same+=1
    print(f"  {yr}: 冠军赢+亚军赢={same}次, 冠军赢但亚军输={gap_wins}次, 冠军输但亚军赢={gap_losses}次")
    print(f"    → 换亚军则{gap_losses}次多赢{gap_losses}/{gap_total}={gap_losses/gap_total*100:.1f}%")

# ═══ 特征相关性分析：哪些特征预示次日大涨 ═══
print("\n═══ 特征相关性：哪些特征和次日最高涨幅最相关？ ═══")
all_cands=[]
for dt in sorted(data25.keys()):
    for c in data25[dt]:
        all_cands.append(c)
for dt in sorted(data26.keys()):
    for c in data26[dt]:
        all_cands.append(c)

import statistics
# 按次日涨幅高低分两组：赢家(n>=2.5) vs 输家(n<2.5)
winners=[c for c in all_cands if c['n']>=TARGET]
losers=[c for c in all_cands if c['n']<TARGET]
print(f"  总样本: {len(all_cands)}  赢家: {len(winners)} ({len(winners)/len(all_cands)*100:.1f}%)  输家: {len(losers)}")

for feat_name, key in [('涨跌幅p','p'),('实体b','b'),('上影s','s'),('ATR a','a'),('收盘位cl','cl')]:
    w_avg=statistics.mean([c[key] for c in winners]) if winners else 0
    l_avg=statistics.mean([c[key] for c in losers]) if losers else 0
    w_med=sorted([c[key] for c in winners])[len(winners)//2] if winners else 0
    l_med=sorted([c[key] for c in losers])[len(losers)//2] if losers else 0
    # p+a 评分对比
    w_sc_avg=statistics.mean([c['p']+c['a'] for c in winners]) if winners else 0
    l_sc_avg=statistics.mean([c['p']+c['a'] for c in losers]) if losers else 0
    print(f"  {feat_name}: 赢家均值={w_avg:.2f} 输家均值={l_avg:.2f} 差距={w_avg-l_avg:+.2f}")

print(f"  p+a评分: 赢家均值={w_sc_avg:.2f} 输家均值={l_sc_avg:.2f} 差距={w_sc_avg-l_sc_avg:+.2f}")
