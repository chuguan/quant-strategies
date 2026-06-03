#!/usr/bin/env python3
"""1月6日 — 正确过滤：涨跌幅% 1%~7%"""
import pickle, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"

with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']; names=cache['names']

cands=data["2026-01-06"]
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

filt=[]
for c in cands:
    if c['code'] in ST: continue
    p=c['p']  # 涨跌幅%
    if not (1 <= p < 7): continue  # 正确过滤！用涨跌幅%
    sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
    c['total']=round(sh+min(c['b']*3,25)+min(c['a']*2,16),1)
    filt.append(c)

filt.sort(key=lambda x:x['total'], reverse=True)
print(f"📅 2026-01-06  原始: {len(cands)}只  涨跌幅1~7%过滤: {len(filt)}只")

print(f"\n{'='*95}")
print(f"🏆 TOP10 — 买入价 vs 次日最高/收盘")
print(f"{'='*95}")
print(f"{'排名':<4} {'名称':<10} {'代码':<12} {'买入价':>7} {'涨跌幅':>7} {'总分':>5} {'次日最高':>8} {'次日收盘':>8}")
print("-"*70)

for rank,c in enumerate(filt[:10],1):
    nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
    nc_r=round((c['n'] if c['n'] else 0),1)  # placeholder
    # Need close data for next day
    nc="N/A"
    print(f"{rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['cl']:>7.2f} {c['p']:>+6.2f}% {c['total']:>5.1f} {nh:>8} {nc:>8}")

# 对比：原来用实体%过滤的版本
old_filt=[c for c in cands if c['code'] not in ST and 1<=c['b']<7]
print(f"\n📊 对比")
print(f"  实体%过滤: {len(old_filt)}只")
print(f"  涨跌幅%过滤: {len(filt)}只")
diff=set(c['code'] for c in old_filt) - set(c['code'] for c in filt)
print(f"  实体%版有但涨跌幅%版没有的: {len(diff)}只")
for code in list(diff)[:5]:
    old_c=next(c for c in old_filt if c['code']==code)
    print(f"    {names.get(code,'?')}({code}) 涨跌幅{old_c['p']:+.2f}% 实体{old_c['b']:.2f}%")
