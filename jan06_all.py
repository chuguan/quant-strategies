#!/usr/bin/env python3
"""2026-01-06 全部股票分析 — 1~7%+排除ST过滤"""
import pickle, os, time, sys
sys.stdout.reconfigure(line_buffering=True)

CACHE = r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"

print("📡 加载..."); t0=time.time()
with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']; names=cache['names']

ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

target="2026-01-06"
cands=data.get(target,[])
print(f"📅 {target}: {len(cands)}只原始候选")

# 分别收集：原版冠军 vs 过滤后的全部候选
for c in cands:
    sh=max(0,35-c['s']*1.2) if c['s']<30 else 0
    c['total']=round(sh+min(c['b']*3,25)+min(c['a']*2,16),1)

orig_best=max(cands, key=lambda x:x['total'])
print(f"❌ 原版冠军: {names.get(orig_best['code'],'?')}({orig_best['code']})")
print(f"   实体{orig_best['b']:.2f}% 涨幅{orig_best['p']:+.2f}% 上影{orig_best['s']:.1f}% → 次日{orig_best['n']:+.1f}%")

# 新版过滤
filt=[c for c in cands if 1<=c['b']<7 and c['code'] not in ST]
filt.sort(key=lambda x:x['total'], reverse=True)
print(f"  1~7%+排除ST: {len(filt)}只")

# 输出全部
print(f"\n{'='*95}")
print(f"📋 全部 {len(filt)}只候选")
print(f"{'='*95}")
print(f"{'排名':<4} {'名称':<10} {'代码':<12} {'涨跌幅':>7} {'收盘':>7} {'实体':>6} {'上影':>6} {'ATR':>6} {'总分':>5} {'次日':>6} {'评分细节':<20}")
print("-"*90)

for rank,c in enumerate(filt,1):
    sh=round(max(0,35-c['s']*1.2) if c['s']<30 else 0,1)
    bd=round(min(c['b']*3,25),1)
    at=round(min(c['a']*2,16),1)
    nh=f"{c['n']:+.1f}%" if c['n'] else "N/A"
    detail=f"上{sh}+实{bd}+A{at}"
    mk="🏆" if rank==1 else ""
    # 赢家标记
    if c['n'] and c['n']>=2.5:
        print(f"{rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['p']:>+6.2f}% {c['cl']:>7.2f} {c['b']:>5.2f}% {c['s']:>5.1f}% {c['a']:>5.2f}% {c['total']:>5.1f} {nh:>6} ✅ {detail}")
    else:
        print(f"{rank:<4} {names.get(c['code'],'—'):<10} {c['code']:<12} {c['p']:>+6.2f}% {c['cl']:>7.2f} {c['b']:>5.2f}% {c['s']:>5.1f}% {c['a']:>5.2f}% {c['total']:>5.1f} {nh:>6}    {detail}")

# 统计
wins=sum(1 for c in filt if c['n'] and c['n']>=2.5)
losses=sum(1 for c in filt if c['n'] and c['n']<2.5)
no_data=sum(1 for c in filt if not c['n'])
print(f"\n📊 共{len(filt)}只: 赢{wins}只 输{losses}只 无数据{no_data}只")
print(f"   胜率: {wins/(wins+losses)*100:.1f}% ({wins}/{wins+losses})")

# 原版冠军在过滤后的位置
orig_rank=next((i+1 for i,c in enumerate(filt) if c['code']==orig_best['code']), None)
if orig_rank:
    print(f"\n📌 原版冠军({orig_best['code']})在过滤后排名第{orig_rank}")
else:
    print(f"\n📌 原版冠军({orig_best['code']})实体{orig_best['b']:.2f}%，已被实体%过滤排除")

# 新冠军
if filt:
    nb=filt[0]
    print(f"\n{'='*95}")
    print(f"🏆 新冠军: {names.get(nb['code'],'?')}({nb['code']})")
    print(f"   涨幅{nb['p']:+.2f}% 实体{nb['b']:.2f}% 上影{nb['s']:.1f}% 总分{nb['total']}")
    print(f"   次日: {nb['n']:+.1f}%" if nb['n'] else "   次日: 无数据")

print(f"\n⏱ {time.time()-t0:.2f}秒")
