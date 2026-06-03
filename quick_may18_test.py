#!/usr/bin/env python3
"""
快速复测5月18日 — 用big_cache.pkl，无需加载JSON！
"""
import pickle, os, sys
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

print("📡 加载big_cache...")
with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']
names=cache['names']
print(f"✅ {len(data_cache)}天, 总{sum(len(v) for v in data_cache.values())}条")

MIN_CHG=1.0; MAX_CHG=8.0

# big_cache的数据字段：
# p=涨跌幅, a=ATR%, b=实体%, s=上影%, cl=收盘位
# vol_ratio=量比, j_val=KJJ-J值, ma5_slope=MA5斜率, dif_val=DIF值
# n=次日最高%

def new_score(c):
    """新评分：基础 + 3个加分项"""
    sc = c['p'] + c['a']*1.5 + c.get('dif_val',0)*0.5
    
    # ① MACD向上（DIF>0）：+3分
    if c.get('dif_val',0) > 0:
        sc += 3
    
    # ② MA5斜率>8%：+3分
    if c.get('ma5_slope',0) > 8:
        sc += 3
    
    # ③ 这里简化，用J值向上替代斜率判断
    # big_cache有j_val但没有K/D值，用J值>50（偏强）+3分
    if c.get('j_val',0) > 50:
        sc += 3
    
    return sc

def old_score(c):
    return c['p'] + c['a']*1.5 + c.get('dif_val',0)*0.5

def test_date(dt):
    cands=[c for c in data_cache.get(dt,[]) 
           if c['code'] not in ST and MIN_CHG <= c['p'] < MAX_CHG and c['n'] is not None]
    if len(cands)<5: return print(f"❌ {dt} 候选不足5只")
    
    for c in cands:
        c['sc_new']=round(new_score(c),2)
        c['sc_old']=round(old_score(c),2)
    
    old_top=sorted(cands, key=lambda x:x['sc_old'], reverse=True)
    new_top=sorted(cands, key=lambda x:x['sc_new'], reverse=True)
    
    print(f"\n{'='*100}")
    print(f"📅 {dt} 共{len(cands)}只候选")
    print(f"{'='*100}")
    
    print(f"\n🏆 旧评分Top5（p+a×1.5+dif×0.5）")
    print(f"{'#':<3} {'名称':<10} {'代码':<14} {'涨跌幅':>6} {'ATR':>5} {'DIF':>6} {'MA5斜率':>8} {'J值':>5} {'总分':>6} {'次日高':>7}")
    print("-"*70)
    for i,c in enumerate(old_top[:5],1):
        name=names.get(c['code'],'?')
        hit='✅' if c['n']>=2.5 else '❌'
        print(f"{i:<3} {name:<10} {c['code']:<14} {c['p']:>+5.1f}% {c['a']:>4.1f}% {c.get('dif_val',0):>5.2f} {c.get('ma5_slope',0):>7.1f}% {c.get('j_val',0):>4.0f} {c['sc_old']:>5.1f} {c['n']:>+5.1f}% {hit}")
    
    print(f"\n🏆 新评分Top5（基础+MACD+斜率+J值加分）")
    print(f"{'#':<3} {'名称':<10} {'代码':<14} {'涨跌幅':>6} {'ATR':>5} {'DIF':>6} {'MA5斜率':>8} {'J值':>5} {'总分':>6} {'次日高':>7}")
    print("-"*70)
    for i,c in enumerate(new_top[:5],1):
        name=names.get(c['code'],'?')
        hit='✅' if c['n']>=2.5 else '❌'
        print(f"{i:<3} {name:<10} {c['code']:<14} {c['p']:>+5.1f}% {c['a']:>4.1f}% {c.get('dif_val',0):>5.2f} {c.get('ma5_slope',0):>7.1f}% {c.get('j_val',0):>4.0f} {c['sc_new']:>5.1f} {c['n']:>+5.1f}% {hit}")
    
    # 标注汇绿生态
    for label, top in [('旧', old_top), ('新', new_top)]:
        for i,c in enumerate(top):
            if 'sz001267' in c['code']:
                print(f"\n⚠️ 汇绿生态(sz001267)在{'旧' if label=='旧' else '新'}评分排第{i+1}名")

test_date("2026-05-18")
test_date("2026-04-15")
test_date("2026-03-31")
