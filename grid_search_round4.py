#!/usr/bin/env python3
"""
第4轮：动态评分 + 放宽M1条件
"""
import pickle, os, sys, math
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']

MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5

def filter_data(yr, min_atr=0, body_gte=0, close_pos_gte=0):
    """带可选放宽条件的过滤"""
    by_date=defaultdict(list)
    for dt in data_cache:
        if not dt.startswith(yr): continue
        for c in data_cache[dt]:
            if c['code'] in ST: continue
            p=c['p']; a=c['a']; b=c['b']; cl=c['cl']
            if p is None or not (MIN_CHG <= p < MAX_CHG): continue
            if c['n'] is None: continue
            if a < min_atr: continue
            if b < body_gte: continue
            if cl < close_pos_gte: continue
            by_date[dt].append(c)
    return {k:v for k,v in by_date.items() if len(v)>=5}

def test(data, fn):
    w=t=0
    for dt in sorted(data.keys()):
        best=max(data[dt], key=fn)
        t+=1
        if best['n']>=TARGET: w+=1
    return w/t*100 if t>0 else 0, w, t

# ═══ 动态切换公式 ═══
print("═══ 动态公式1: 当月最近20天p+a vs p+a², 选胜率高的 ═══")
# 从2025-02开始，每月用上个月的胜率对比来决定当前用哪个公式

data25=filter_data('2025')
data26=filter_data('2026')

fn1=lambda c: c['p']+c['a']
fn2=lambda c: c['p']+c['a']*c['a']
fn3=lambda c: c['p']*c['a']

def dynamic_backtest(data):
    """滚动窗口动态选公式"""
    all_dates=sorted(data.keys())
    w_total=0; t_total=0
    fn_usage={}
    
    for i, dt in enumerate(all_dates):
        # 用前20天决定今日公式
        if i < 20:
            fn=fn1  # 默认用p+a
        else:
            window=all_dates[max(0,i-20):i]
            # 每个公式在窗口内的胜率
            wr1=sum(1 for d in window if max(data[d], key=fn1)['n']>=TARGET)/len(window)
            wr2=sum(1 for d in window if max(data[d], key=fn2)['n']>=TARGET)/len(window)
            wr3=sum(1 for d in window if max(data[d], key=fn3)['n']>=TARGET)/len(window)
            best_fn=max([(wr1,fn1,'p+a'),(wr2,fn2,'p+a²'),(wr3,fn3,'p×a')], key=lambda x:x[0])
            fn=best_fn[1]
            fn_usage[best_fn[2]]=fn_usage.get(best_fn[2],0)+1
        
        best=max(data[dt], key=fn)
        t_total+=1
        if best['n']>=TARGET: w_total+=1
    
    return w_total/t_total*100, w_total, t_total, fn_usage

for label, data in [('2025',data25),('2026',data26)]:
    wr,w,t,usage=dynamic_backtest(data)
    print(f"  {label}: {wr:.1f}% ({w}/{t})")
    for fn,u in sorted(usage.items()):
        print(f"    {fn}: {u}次")
print()

# ═══ 放宽条件尝试 ═══
print("═══ 放宽条件 ═══")
candidates_list=[
    ("原版(ATR>3%+阳线+站MA5)", lambda yr: filter_data(yr, min_atr=3)),
    ("去掉ATR过滤", lambda yr: filter_data(yr, min_atr=0)),
    ("去掉阳线", lambda yr: {dt:[c for c in filter_data(yr, min_atr=0)[dt] if True] for dt in filter_data(yr, min_atr=0)}),
    # Actually we can't easily relax these from cache - cache data already pre-filtered
    # But we can check what data is in there
]

# What's the actual M1 pre-filter in the cache? Let me check
# The cache already filtered: 价<80 + 均线多头 + MACD零轴上 + ATR>3% + 站MA60 + 阳线 + 站MA5
# So all candidates already pass those. We can only further restrict or use what we have.

# ═══ 分析: 改选top-N候选而非仅冠军 ═══
print("═══ 分析5: 如果从Top3里选（用次日数据选最佳），上限是多少？ ═══")
for yr in ['2025','2026']:
    data=filter_data(yr)
    w1=t1=0
    w3=t3=0
    for dt in sorted(data.keys()):
        cands=sorted(data[dt], key=fn1, reverse=True)
        # Top1
        t1+=1
        if cands[0]['n']>=TARGET: w1+=1
        # Top3中最佳
        best_of_3=max(cands[:3], key=lambda c: c['n'])
        t3+=1
        if best_of_3['n']>=TARGET: w3+=1
    print(f"  {yr}: Top1={w1/t1*100:.1f}%  Top3中最佳={w3/t3*100:.1f}%（理论上限）")
print()

# ═══ 分析6: 不同候选数的胜率 ═══
print("═══ 分析6: 每天候选数分段统计（p+a评分，目标≥2.5%） ═══")
for yr in ['2025','2026']:
    data=filter_data(yr)
    buckets={"<10":[],"10~20":[],"20~50":[],"50+":[]}
    for dt in sorted(data.keys()):
        n=len(data[dt])
        best=max(data[dt], key=fn1)
        win=1 if best['n']>=TARGET else 0
        if n<10: buckets["<10"].append(win)
        elif n<20: buckets["10~20"].append(win)
        elif n<50: buckets["20~50"].append(win)
        else: buckets["50+"].append(win)
    print(f"  {yr}:")
    for label,wins in buckets.items():
        if wins:
            wr=sum(wins)/len(wins)*100
            print(f"    {label}: {wr:.1f}% ({sum(wins)}/{len(wins)})")

# ═══ 分析7: 跳过候选少的日子的影响 ═══
print("\n═══ 分析7: 如果只有候选≥N天才出手 ═══")
for min_cand in [5,10,15,20,30,50]:
    for yr in ['2025','2026']:
        data={k:v for k,v in filter_data(yr).items() if len(v)>=min_cand}
        wr,_,_=test(data, fn1)
        print(f"  ≥{min_cand}候选 {yr}: {wr:.1f}% ({len(data)}天)")
    print()
