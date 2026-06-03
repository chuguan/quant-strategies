#!/usr/bin/env python3
"""
自适应公式切换：用最近10天的表现动态选公式
不同月份，p+a, p×a, p+a², p+a+cl等公式各领风骚
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

MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5

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

# 定义6种候选公式
formulas = {
    'p+a': lambda c: c['p']+c['a'],
    'p×a': lambda c: c['p']*c['a'],
    'p+a²': lambda c: c['p']+c['a']*c['a'],
    'p+a+cl/100': lambda c: c['p']+c['a']+c['cl']*0.01,
    'p+a+b×0.05': lambda c: c['p']+c['a']+c['b']*0.05,
    'p+a+b×0.05+s×0.03': lambda c: c['p']+c['a']+c['b']*0.05+c['s']*0.03,
}

# 滚动窗口自适应
def adaptive_backtest(data, window=10):
    """用前window天的胜率选最佳公式"""
    dates=sorted(data.keys())
    w=t=0
    fn_usage=defaultdict(int)
    
    for i, dt in enumerate(dates):
        if i < window:
            fn=formulas['p+a']  # 默认
        else:
            # 前window天每个公式的冠军胜率
            perf={}
            for name, fn_c in formulas.items():
                wins=0
                for j in range(i-window, i):
                    d=dates[j]
                    best=max(data[d], key=fn_c)
                    if best['n']>=TARGET: wins+=1
                perf[name]=wins/window
            best_name=max(perf, key=perf.get)
            fn=formulas[best_name]
            fn_usage[best_name]+=1
        
        best=max(data[dt], key=fn)
        t+=1
        if best['n']>=TARGET: w+=1
    
    return w/t*100, w, t, dict(fn_usage)

data25=filter_data('2025')
data26=filter_data('2026')

print("═══ 自适应公式切换（滚动窗口选胜率最高的公式） ═══")
print(f"{'窗口':<8} {'2025':>8} {'2026':>8} {'平均':>8}")
print("-"*35)

for window in [5, 10, 15, 20, 30]:
    wr25,_,_,u25=adaptive_backtest(data25, window)
    wr26,_,_,u26=adaptive_backtest(data26, window)
    avg=(wr25+wr26)/2
    print(f"{window:<8} {wr25:>7.1f}% {wr26:>7.1f}% {avg:>7.1f}%")
    # 显示哪些公式被选中最多次
    top25=sorted(u25.items(), key=lambda x:x[1], reverse=True)[:3]
    top26=sorted(u26.items(), key=lambda x:x[1], reverse=True)[:3]
    print(f"  {'':8} 2025最多: {top25}")
    print(f"  {'':8} 2026最多: {top26}")

# ═══ 另一种思路：两阶段选股 ═══
print("\n\n═══ 两阶段法：先用p+a选Top5，再用第2公式选冠军 ═══")
# 阶段1: p+a排Top5
# 阶段2: 在Top5里用另一套规则重排

stage2_formulas = {
    '↑实体%': lambda c: c['b'],
    '↑ATR': lambda c: c['a'],
    '↑收盘位': lambda c: c['cl'],
    '↓实体%': lambda c: -c['b'],
    '↓ATR': lambda c: -c['a'],
    '↑上影%': lambda c: c['s'],
    'p-a': lambda c: c['p']-c['a'],
    '实体×收盘位': lambda c: c['b']*c['cl'],
    '收盘位-实体': lambda c: c['cl']-c['b'],
}

print(f"{'阶段2公式':<16} {'2025':>8} {'2026':>8} {'平均':>8}")
print("-"*42)
base_wr=(60.9+69.7)/2
baseline_name=f"【基准p+a】{base_wr:.1f}%"
results=[]

for name, fn2 in stage2_formulas.items():
    for yr_name, data in [('2025',data25),('2026',data26)]:
        w=t=0
        for dt in sorted(data.keys()):
            # 阶段1: p+a 选 Top5
            top5=sorted(data[dt], key=lambda c:c['p']+c['a'], reverse=True)[:5]
            # 阶段2: 在Top5里用fn2选冠军
            best=max(top5, key=fn2)
            t+=1
            if best['n']>=TARGET: w+=1
        wr=w/t*100 if t>0 else 0
        if yr_name=='2025':
            wr25=wr
        else:
            wr26=wr
    
    avg=(wr25+wr26)/2
    results.append((avg, wr25, wr26, name))
    print(f"{name:<16} {wr25:>7.1f}% {wr26:>7.1f}% {avg:>7.1f}%")

print(f"\n{'基准p+a':<16} {60.9:>7.1f}% {69.7:>7.1f}% {(60.9+69.7)/2:>7.1f}%")
print(f"{'🥇 p+a冠军(原)':<16} {60.9:>7.1f}% {69.7:>7.1f}% {(60.9+69.7)/2:>7.1f}%")
results.sort(key=lambda x:x[0], reverse=True)
print(f"\n🏆 两阶段最优: {results[0][3]} = {results[0][0]:.1f}%")

# ═══ 终极方案：三重评分叠加 ═══
print("\n\n═══ 终极：三重评分叠加（p+a+cl权重+实体+上影 全量搜索） ═══")
best_avg=0
best_params=None
for w_cl in [0, 0.005, 0.01, 0.02, 0.03, 0.05]:
    for w_b in [0, 0.01, 0.02, 0.03, 0.05, 0.08]:
        for w_s in [0, 0.01, 0.02, 0.03, 0.05]:
            for w_a in [1.0, 1.2, 1.5, 1.8, 2.0]:
                if w_cl==0 and w_b==0 and w_s==0 and w_a==1.0:
                    continue
                fn=lambda c, w1=w_cl, w2=w_b, w3=w_s, w4=w_a: c['p']+c['a']*w4+c['cl']*w1+c['b']*w2+c['s']*w3
                w25=sum(1 for dt in sorted(data25.keys()) if max(data25[dt], key=fn)['n']>=TARGET)/max(len(data25),1)*100
                w26=sum(1 for dt in sorted(data26.keys()) if max(data26[dt], key=fn)['n']>=TARGET)/max(len(data26),1)*100
                avg=(w25+w26)/2
                if avg>best_avg:
                    best_avg=avg
                    best_params=(w_cl, w_b, w_s, w_a, w25, w26)

print(f"🏆 最优：p+a×{best_params[3]}+cl×{best_params[0]}+b×{best_params[1]}+s×{best_params[2]}")
print(f"   两年均={best_avg:.1f}% (2025={best_params[4]:.1f}%, 2026={best_params[5]:.1f}%)")
