#!/usr/bin/env python3
"""最新选股 — CG-07 v14 + 1~7%排除涨停 + 排除ST"""
import pickle, os, time, sys
sys.stdout.reconfigure(line_buffering=True)

CACHE = r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"

# 加载ST名单
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

print("📡 加载..."); t0=time.time()
with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']; names=cache['names']

# 找最新的2026年日期
dates_2026 = sorted([d for d in data if d.startswith("2026")], reverse=True)
target=dates_2026[0]
print(f"📅 最新数据: {target}")

cands=data[target]
print(f"  原始候选: {len(cands)}只")

# v14评分 + 过滤
filtered=[]
for c in cands:
    # ST排除
    if c['code'] in ST: continue
    # 实体1%~7%
    b=c['b']
    if b<1 or b>=7: continue
    # 主板过滤（已在缓存中做好）
    
    sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
    c['total']=round(sh+min(b*3,25)+min(c['a']*2,16),1)
    filtered.append(c)

filtered.sort(key=lambda x:x['total'], reverse=True)
print(f"  过滤后: {len(filtered)}只")

if not filtered:
    print("❌ 无候选")
    sys.exit(0)

print(f"\n{'='*95}")
print(f"🏆 CG-07 v14 最新选股 — {target}")
print(f"{'='*95}")
print(f"{'排名':<4} {'名称':<10} {'代码':<12} {'涨跌幅':>7} {'收盘':>7} {'实体':>6} {'上影':>6} {'总分':>5} {'次日':>6}")
print("-"*65)

for rank,c in enumerate(filtered[:30],1):
    sh=round(max(0,35-c['s']*1.2) if c['s']<30 else 0,1)
    bd=round(min(c['b']*3,25),1)
    at=round(min(c['a']*2,16),1)
    nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
    mk="🏆" if rank==1 else ""
    print(f"{rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['p']:>+6.2f}% {c['cl']:>7.2f} {c['b']:>5.2f}% {c['s']:>5.1f}% {c['total']:>5.1f} {nh:>6} {mk}")

# 冠军详情
c=filtered[0]
print(f"\n{'='*95}")
print(f"🥇 冠军: {names.get(c['code'],'?')}({c['code']})")
print(f"   收盘价: {c['cl']:.2f}  涨幅: {c['p']:+.2f}%")
print(f"   实体: {c['b']:.2f}% | 上影: {c['s']:.1f}% | ATR: {c['a']:.2f}%")
print(f"   总分: {c['total']}分")
print(f"   次日最高: {c['n']:+.1f}%" if c['n'] else "   次日最高: 无数据")

print(f"\n⏱ {time.time()-t0:.3f}秒")
