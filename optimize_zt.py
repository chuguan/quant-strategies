#!/usr/bin/env python3
"""排除涨停的v14优化 → 冲90%胜率"""
import json, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\.cand_cache.json"
OUTPUT = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\exclude_zt_results.json"

print("📡 加载缓存..."); t0=time.time()
with open(CACHE_FILE,'rb') as f: cache=json.loads(f.read().decode('utf-8'))
data_2025 = defaultdict(list)
data_2026 = defaultdict(list)
for c in cache['cands_2025']: data_2025[c['d']].append(c)
for c in cache['cands_2026']: data_2026[c['d']].append(c)
data_2025={k:v for k,v in data_2025.items() if len(v)>=5}
data_2026={k:v for k,v in data_2026.items() if len(v)>=5}
print(f"✅ 2025:{len(data_2025)}天 2026:{len(data_2026)}天, {time.time()-t0:.1f}秒")

for yr_data in [data_2025, data_2026]:
    for dt,cands in yr_data.items():
        for c in cands:
            c['ba'] = min(c['b']*3,25) + min(c['a']*2,16)

def run_bt(cands_by_date, shadow_fn, max_pct=None):
    """运行回测，可选排除涨幅超过max_pct的"""
    wins=0; total=0
    for dt,cands in cands_by_date.items():
        filtered = cands
        if max_pct is not None:
            # 注意这里cands没有涨幅数据（缓存只有shadow/body/atr/next_high）
            # 我们需要涨幅数据 — 但缓存只有这些字段：d,s,b,a,n
            # 我们只能通过实体%估算涨幅
            # 涨幅 ≈ 实体%（如果上影=0且下影=0，则涨幅=实体%）
            # 但更准确地说，我们用实体%来近似
            filtered = [c for c in cands if c['b'] <= max_pct]
            if len(filtered) < 5:
                filtered = cands  # 不够5只就全用
        
        if not filtered: continue
        best_score=-1; best_next=None
        for c in filtered:
            sc = shadow_fn(c['s']) + c['ba']
            if sc > best_score:
                best_score=sc
                best_next=c['n']
        total+=1
        if best_next and best_next>=2.5: wins+=1
    return wins,total

def v14sh(s):
    return max(0,35-s*1.2) if s<30 else 0

# ═══ 跑不同涨停排除阈值 ═══
print(f"\n{'='*80}")
print("🏆 排除涨停测试 — 不同实体%上限制")
print(f"{'='*80}")
print(f"{'实体上限':<10} {'2025胜率':>12} {'2025天数':>10} {'2026胜率':>12} {'2026天数':>10} {'平均':>8}")
print("-"*55)

results=[]
# 实体% ≈ 当日涨幅（当上影=0时）
for limit in [99, 10, 9, 8.5, 8, 7.5, 7, 6.5, 6, 5.5, 5, 4.5, 4]:
    w25,t25=run_bt(data_2025,v14sh,limit)
    w26,t26=run_bt(data_2026,v14sh,limit)
    avg=(w25/t25*100 + w26/t26*100)/2 if t25 and t26 else 0
    results.append((avg,limit,w25,t25,w26,t26))
    mk="🔥" if avg>84 else ("✅" if avg>82 else "")
    print(f"{'无限制' if limit==99 else f'≤{limit}%':<10} {w25/t25*100:>5.1f}%/{t25:>3}d {t25:>10} {w26/t26*100:>5.1f}%/{t26:>3}d {t26:>10} {avg:>5.2f}% {mk}")

results.sort(reverse=True)
best=results[0]
print(f"\n{'='*80}")
print(f"🥇 最优: 实体≤{best[1]}% → 平均{best[0]:.2f}%")
print(f"   2025: {best[2]/best[3]*100 if best[3] else 0:.1f}%/{best[3]}d")
print(f"   2026: {best[4]/best[5]*100 if best[5] else 0:.1f}%/{best[5]}d")

# ═══ 现在做评分优化（排除涨停后） ═══
print(f"\n{'='*80}")
print("📊 排除涨停后(v14原评分不够用), 尝试新评分方案")
print(f"{'='*80}")

best_limit = best[1]  # 最优的实体上限

# 实体上限截断后，v14评分中实体分的权重需要调整（涨停没了）
# 新评分方案：
schemes = [
    ("v14原版", lambda s,b,a: (max(0,35-s*1.2) if s<30 else 0) + min(b*3,25) + min(a*2,16)),
    ("S1:上影权重加倍", lambda s,b,a: (max(0,60-s*2) if s<30 else 0) + min(b*2,15) + min(a*2,16)),
    ("S2:上影更重要", lambda s,b,a: (max(0,40-s*1.5) if s<30 else 0) + min(b*2,15) + min(a*2,16)),
    ("S3:ATR最重要", lambda s,b,a: (max(0,30-s*1.2) if s<30 else 0) + min(b*1.5,10) + min(a*3,25)),
    ("S4:实体不重要", lambda s,b,a: (max(0,35-s*1.2) if s<30 else 0) + min(b*1,8) + min(a*2,16)),
    ("S5:上影+ATR", lambda s,b,a: (max(0,40-s*1.5) if s<30 else 0) + min(b*1,8) + min(a*3,25)),
    ("S6:纯ATR", lambda s,b,a: (max(0,20-s*1) if s<30 else 0) + min(b*1,8) + min(a*4,30)),
    ("S7:上影罚+ATR", lambda s,b,a: (max(0,50-s*2) if s<25 else 0) + min(b*1,5) + min(a*3,25)),
    ("S8:平衡版", lambda s,b,a: (max(0,35-s*1.5) if s<30 else 0) + min(b*2,15) + min(a*3,25)),
    ("S9:重ATR轻实体", lambda s,b,a: (max(0,30-s*1.2) if s<30 else 0) + min(b*1,10) + min(a*4,30)),
    ("S10:三因子均衡", lambda s,b,a: (max(0,33-s*1.3) if s<30 else 0) + min(b*2.5,18) + min(a*2.5,20)),
]

def run_bt_scored(cands_by_date, score_fn, max_body=None):
    wins=0; total=0
    for dt,cands in cands_by_date.items():
        filtered = cands
        if max_body is not None:
            filtered = [c for c in cands if c['b'] <= max_body]
            if len(filtered) < 5: filtered = cands
        if not filtered: continue
        best_score=-1; best_next=None
        for c in filtered:
            sc = score_fn(c['s'],c['b'],c['a'])
            if sc > best_score:
                best_score=sc
                best_next=c['n']
        total+=1
        if best_next and best_next>=2.5: wins+=1
    return wins,total

print(f"{'方案':<20} {'2025胜率':>12} {'2026胜率':>12} {'平均':>8}")
print("-"*55)
score_results=[]
for name,fn in schemes:
    w25,t25=run_bt_scored(data_2025,fn,best_limit)
    w26,t26=run_bt_scored(data_2026,fn,best_limit)
    avg=(w25/t25*100 + w26/t26*100)/2 if t25 and t26 else 0
    score_results.append((avg,name,w25,t25,w26,t26))
    mk="🔥" if avg>84 else ("✅" if avg>82 else "")
    print(f"{name:<20} {w25/t25*100:>5.1f}%/{t25:>3}d {w26/t26*100:>5.1f}%/{t26:>3}d {avg:>5.2f}% {mk}")

score_results.sort(reverse=True)
print(f"\n{'='*80}")
print(f"🥇 最终最优方案:")
sr=score_results[0]
print(f"   {sr[1]}")
print(f"   实体≤{best_limit}% + 评分{sr[1]}")
print(f"   2025: {sr[2]/sr[3]*100:.1f}%/{sr[3]}d  2026: {sr[4]/sr[5]*100:.1f}%/{sr[5]}d")
print(f"   平均: {sr[0]:.2f}%")

# 保存
import json as j
j.dump({"exclude_limit":best_limit,"best_scheme":sr[1],"avg":round(sr[0],2),
        "y25":{"w":sr[2],"t":sr[3],"pct":round(sr[2]/sr[3]*100,1)},
        "y26":{"w":sr[4],"t":sr[5],"pct":round(sr[4]/sr[5]*100,1)}}, open(OUTPUT,'w'))

print(f"\n⏱ {time.time()-t0:.1f}秒")
💾 结果已保存到: {OUTPUT}
