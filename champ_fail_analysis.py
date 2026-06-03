#!/usr/bin/env python3
"""
深度分析：冠军输但亚军赢的情况 — 找出p+a评分失败的原因
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

MIN_CHG=1.0; MAX_CHG=8.0

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

fn=lambda c: c['p']+c['a']

# ═══ 分析冠军输亚军赢的案例 ═══
print("═══ 冠军输但亚军赢的情况分析 ═══")
for yr in ['2025']:  # 先看2025
    data=filter_data(yr)
    champ_fail=[]  # (dt, 冠军, 亚军)
    for dt in sorted(data.keys()):
        cands=sorted(data[dt], key=fn, reverse=True)
        if len(cands)<2: continue
        champ=cands[0]; runner_up=cands[1]
        if champ['n']<2.5 and runner_up['n']>=2.5:
            champ_fail.append((dt, champ, runner_up))
    
    print(f"\n{yr}: {len(champ_fail)}天冠军输但亚军赢")
    
    # 特征对比
    if champ_fail:
        print(f"\n{'='*90}")
        print(f"{'日期':<12} {'冠军代码':<12} {'涨跌幅':>6} {'实体':>6} {'上影':>6} {'ATR':>6} {'收盘位':>6} {'p+a分':>7} {'次日高':>7}")
        print(f"{'':<12} {'亚军代码':<12} {'涨跌幅':>6} {'实体':>6} {'上影':>6} {'ATR':>6} {'收盘位':>6} {'p+a分':>7} {'次日高':>7}")
        print("-"*90)
        for dt, champ, ru in champ_fail:
            # 冠军
            c1=champ; c2=ru
            name1=cache['names'].get(c1['code'],'?'); name2=cache['names'].get(c2['code'],'?')
            print(f"{dt:<12} {name1:<6}/{c1['code']:<12} {c1['p']:>+5.1f} {c1['b']:>5.1f} {c1['s']:>5.1f} {c1['a']:>5.1f} {c1['cl']:>5.1f} {c1['p']+c1['a']:>6.1f} {c1['n']:>+6.1f}%")
            print(f"{'':12} {name2:<6}/{c2['code']:<12} {c2['p']:>+5.1f} {c2['b']:>5.1f} {c2['s']:>5.1f} {c2['a']:>5.1f} {c2['cl']:>5.1f} {c2['p']+c2['a']:>6.1f} {c2['n']:>+6.1f}%")
            print(f"{'':12} {'→差':>18} {c1['p']-c2['p']:>+5.1f} {c1['b']-c2['b']:>+5.1f} {c1['s']-c2['s']:>+5.1f} {c1['a']-c2['a']:>+5.1f} {c1['cl']-c2['cl']:>+5.1f} {c1['p']+c1['a']-c2['p']-c2['a']:>+6.1f}")
            print()

# ═══ 总结特征 ═══
print("\n═══ 冠军失败案例的特征规律 ═══")
for yr in ['2025','2026']:
    data=filter_data(yr)
    all_fails=[]
    for dt in sorted(data.keys()):
        cands=sorted(data[dt], key=fn, reverse=True)
        if len(cands)<2: continue
        champ=cands[0]; ru=cands[1]
        if champ['n']<2.5 and ru['n']>=2.5:
            all_fails.append((champ, ru))
    
    print(f"\n{yr} ({len(all_fails)}天冠军输):")
    if not all_fails: continue
    
    # 冠军特征均值 vs 亚军特征均值
    for feat_name, key in [('涨跌幅','p'),('实体','b'),('上影','s'),('ATR','a'),('收盘位','cl')]:
        c_avg=sum(c[1][key] for c in all_fails)/len(all_fails)
        r_avg=sum(c[2][key] for c in all_fails)/len(all_fails)
        print(f"  {feat_name}: 冠军={c_avg:.2f}  亚军={r_avg:.2f}  差={c_avg-r_avg:+.2f}")
    
    # p+a差值与次日涨幅的关系
    score_diff=[(c[1]['p']+c[1]['a'] - c[2]['p']-c[2]['a'], c[1]['n'], c[2]['n']) for c in all_fails]
    avg_diff=sum(d[0] for d in score_diff)/len(score_diff)
    print(f"  p+a分差均值: {avg_diff:.2f}")
    print(f"  冠军次日均: {sum(d[1] for d in score_diff)/len(score_diff):.1f}%")
    print(f"  亚军次日均: {sum(d[2] for d in score_diff)/len(score_diff):.1f}%")
    
    # 冠军和亚军同特征同涨跌幅时的表现差异
    same_p=[c for c in all_fails if abs(c[1]['p']-c[2]['p'])<0.5]
    print(f"  涨跌幅相近(差<0.5%)的{len(same_p)}天: 冠军p+a={c[1]['p']+c[1]['a'] if c[1] else 0:.1f} 亚军p+a={c[2]['p']+c[2]['a'] if len(c)>2 else 0:.1f}")
