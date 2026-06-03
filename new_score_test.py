#!/usr/bin/env python3
"""涨跌幅1~7%的票，重新设计评分规则"""
import pickle, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data=cache['data']

# 只保留1~7%的票 + 排除ST
batch=defaultdict(list)
for dt in sorted(data.keys()):
    for c in data[dt]:
        if c['code'] in ST: continue
        if not (1 <= c['p'] < 7): continue
        batch[dt].append(c)
batch={k:v for k,v in batch.items() if len(v)>=5}

print(f"📊 涨跌幅1~7%池: {sum(len(v) for v in batch.values())}条")
print(f"   涉及{len(batch)}天")

# ═══ 测试多种评分公式 ═══
def test(name, score_fn):
    wins=0; total=0
    for dt in sorted(batch.keys()):
        cands=batch[dt]
        best=max(cands, key=lambda c: score_fn(c))
        total+=1
        if best['n'] and best['n']>=2.5: wins+=1
    return wins/total*100 if total else 0, wins, total

schemes = [
    # ── v14原版（对照）──
    ("v14原版(上影扣分+实体+ATR)", lambda c: max(0,35-c['s']*1.2) if c['s']<30 else 0 + min(c['b']*3,25)+min(c['a']*2,16)),

    # ── 上影反转（越长越好）──
    ("A:上影得分=上影%×1", lambda c: c['s']*1 + c['b']*3 + c['a']*2),
    ("A2:上影得分=上影%×2", lambda c: c['s']*2 + c['b']*3 + c['a']*2),
    
    # ── 纯ATR+实体（去掉上影）──
    ("B:实体×3+ATR×2", lambda c: min(c['b']*3,25)+min(c['a']*2,16)),
    
    # ── 涨跌幅参与评分 ──
    ("C:涨跌幅×3", lambda c: min(c['p']*3,20) + min(c['a']*2,16)),
    
    # ── 实体×ATR（乘积）──
    ("D:实体×ATR", lambda c: min(c['b'],10)*min(c['a'],8)),
    
    # ── 收盘价位置（高/中/低）—— 收盘越高的越好 ──
    # 用上影估算：上影越小=收盘位置越高（对于阳线）
    ("E:100-上影(位置高)", lambda c: max(0,100-c['s'])),
    
    # ── 混合新思路 ──
    ("F:上影%+ATR%×2", lambda c: min(c['s'],30) + min(c['a']*2,16)),
    ("G:涨跌幅%+上影%", lambda c: c['p']*2 + c['s']*1),
    ("H:实体%×2+上影%", lambda c: c['b']*2 + c['s']*1),
    
    # ── 涨跌幅适中最好（3~5%加分）──
    ("I:涨跌幅适中3~5%+10", lambda c: (10 if 3<=c['p']<5 else 0) + c['a']*2),
]

print(f"\n{'='*80}")
print(f"🏆 涨跌幅1~7% — 评分规则测试")
print(f"{'='*80}")
print(f"{'方案':<28} {'两年均':>7} {'2025':>8} {'2026':>8}")
print("-"*55)

all_results={}
for name, fn in schemes:
    y25, w25, t25 = test(name, [dt for dt in sorted(batch.keys()) if dt.startswith("2025")])
    # This won't work because test() takes a dict not a list
    # Let me fix...

print("❌ 代码结构错误，重新来")
