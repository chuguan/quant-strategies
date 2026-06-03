#!/usr/bin/env python3
"""排名分析 — 评分高的 vs 实际涨得好的"""
import pickle, os, sys
sys.stdout.reconfigure(line_buffering=True)
CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"

ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']; names=cache['names']

target="2026-01-06"
cands=data[target]

filt=[]
for c in cands:
    if c['code'] in ST: continue
    if not (1 <= c['p'] < 7): continue
    sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
    c['total']=round(sh+min(c['b']*3,25)+min(c['a']*2,16),1)
    filt.append(c)

print(f"📅 {target} — 涨跌幅1~7%+排除ST = {len(filt)}只\n")

# ═══ 按评分排名 ═══
filt_by_score=sorted(filt, key=lambda x:x['total'], reverse=True)
print("="*90)
print("🏆 按评分排名 TOP10")
print("="*90)
print(f"{'排名':<4} {'名称':<10} {'代码':<12} {'买入价':>7} {'涨跌幅':>6} {'总分':>5} {'实体':>5} {'上影':>5} {'ATR':>5} {'次日最高':>8}")
print("-"*75)
for rank,c in enumerate(filt_by_score[:10],1):
    nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
    mk="🏆" if rank==1 else ""
    print(f"{rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['cl']:>7.2f} {c['p']:>+5.2f}% {c['total']:>5.1f} {c['b']:>4.2f}% {c['s']:>4.1f}% {c['a']:>4.2f}% {nh:>8} {mk}")

# ═══ 按次日最高排名 ═══
filt_by_next=[c for c in filt if c['n'] is not None]
filt_by_next.sort(key=lambda x:x['n'], reverse=True)
print("\n"+"="*90)
print("⭐ 按次日最高排名 TOP10（实际表现最好）")
print("="*90)
print(f"{'排名':<4} {'名称':<10} {'代码':<12} {'买入价':>7} {'涨跌幅':>6} {'评分':>5} {'实体':>5} {'上影':>5} {'ATR':>5} {'次日最高':>8}")
print("-"*75)
for rank,c in enumerate(filt_by_next[:10],1):
    print(f"{rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['cl']:>7.2f} {c['p']:>+5.2f}% {c['total']:>5.1f} {c['b']:>4.2f}% {c['s']:>4.1f}% {c['a']:>4.2f}% {c['n']:>+7.1f}%")

# ═══ 分析：赢家和输家的特征差异 ═══
print("\n"+"="*90)
print("📊 赢家(次日≥2.5%) vs 输家(次日<2.5%) — 特征对比")
print("="*90)

winners=[c for c in filt if c['n'] and c['n']>=2.5]
losers=[c for c in filt if c['n'] and c['n']<2.5]

def avg(lst,k): return round(sum(c[k] for c in lst if c[k] is not None)/len(lst),2)

print(f"{'特征':<10} {'赢家(71只)':>12} {'输家(82只)':>12} {'差值':>8} {'结论':>12}")
print("-"*55)
for key,nm in [('p','涨跌幅'),('b','实体%'),('s','上影%'),('a','ATR%'),
               ('total','总分'),('cl','收盘价')]:
    wa=avg(winners,key); la=avg(losers,key)
    diff=wa-la
    if key=='s': conc="越短越好" if diff<0 else ""
    elif key=='p': conc="越高越好" if diff>0 else ""
    elif key=='b': conc="实体要大" if diff>0 else ""
    elif key=='a': conc="波动要大" if diff>0 else ""
    elif key=='total': conc="评分有效" if diff>0 else ""
    elif key=='cl': conc=""
    else: conc=""
    print(f"{nm:<10} {wa:>10.2f}% {la:>10.2f}% {diff:>+7.2f}% {conc}")

# ═══ 评分前20的实际表现 ═══
print("\n"+"="*90)
print("🔍 评分前20名 — 实际赢了几个？")
print("="*90)
top20=filt_by_score[:20]
w20=sum(1 for c in top20 if c['n'] and c['n']>=2.5)
print(f"  评分前20中实际赢了: {w20}/20 ({w20/20*100:.0f}%)")
print(f"  全部158只中赢了: {len(winners)}/158 ({len(winners)/158*100:.0f}%)")
print(f"  → 评分前20命中率{'高于' if w20/20>len(winners)/158 else '低于'}整体{w20/20*100-len(winners)/158*100:+.0f}%")

# ═══ 评分漏掉的好票 ═══
print("\n"+"="*90)
print("😱 评分漏掉的好票（评分低但次日涨得好）")
print("="*90)
# 次日最高排名靠前但评分靠后的
overlooked=[c for c in filt if c['n'] and c['n']>=7.0]
overlooked.sort(key=lambda x:x['n'], reverse=True)
print(f"{'名称':<10} {'代码':<12} {'评分':>5} {'次日最高':>8} {'涨跌幅':>7} {'实体':>5} {'上影':>5} {'ATR':>5}")
print("-"*58)
for c in overlooked[:8]:
    print(f"{names.get(c['code'],'—'):<10} {c['code']:<12} {c['total']:>5.1f} {c['n']:>+7.1f}% {c['p']:>+6.2f}% {c['b']:>4.2f}% {c['s']:>4.1f}% {c['a']:>4.2f}%")

# ═══ 评分排错的好票 ═══
print("\n"+"="*90)
print("📌 评分排错的好票（放到前10肯定更好）")
print("="*90)
all_filt=[c for c in filt if c['n'] is not None]
# 哪些票次日≥5%但评分不在前10
high_next=[c for c in all_filt if c['n']>=5.0]
high_next_sorted=sorted(high_next, key=lambda x:x['total'], reverse=True)
print(f"{'名称':<10} {'代码':<12} {'评分排名':>8} {'评分':>5} {'次日最高':>8}{'':>4}{'特征':>40}")
print("-"*75)
for c in high_next_sorted:
    rank_in_filt=next(i+1 for i,x in enumerate(filt_by_score) if x['code']==c['code'])
    feat=f"实体{c['b']:.1f}% 上影{c['s']:.0f}% ATR{c['a']:.1f}%"
    print(f"{names.get(c['code'],'—'):<10} {c['code']:<12} 第{rank_in_filt:>3}名 {c['total']:>5.1f} {c['n']:>+7.1f}%     {feat}")

print(f"\n⏱ 0.0秒")
