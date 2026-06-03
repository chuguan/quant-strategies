#!/usr/bin/env python
"""检查所有策略文件使用的字段与数据库是否一致"""
import os, re

SCRIPTS = r'C:\Users\12546\AppData\Local\hermes\scripts'

# 所有评分策略文件
score_files = []
for v in ['V13','V13A','V13B','V13C']:
    d = os.path.join(SCRIPTS, 'release', v, '评分策略')
    if os.path.exists(d):
        for f in sorted(os.listdir(d)):
            if f.endswith('.py'):
                score_files.append(os.path.join(d, f))

print('评分策略文件: %d个\n' % len(score_files))

for fp in score_files:
    rel = os.path.relpath(fp, SCRIPTS)
    with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
        txt = f.read()
    
    used = []
    for fld in ['p','cl','vr','dif','mg','wrv','jv','kv','dv','a5','kdj_g','pos_in_day','hsl','shizhi','nm','t4_shadow','slope5','cons_up','volume']:
        pat = r"\['" + fld + r"'\]"
        if re.search(pat, txt):
            used.append(fld)
    
    lv = set()
    for k in ['p_min','p_max','vr_min','vr_max','hs_min','hs_max','sz_max','cl_min','cl_max']:
        if k in txt:
            lv.add(k)
    
    print('%s' % rel)
    print('  字段: %s' % ' '.join(used))
    if lv:
        print('  分级: %s' % lv)

print()
print('--- V13_生产.py stock_dict字段 ---')
fp = os.path.join(SCRIPTS, 'V13_生产.py')
with open(fp, 'r', encoding='utf-8') as f:
    txt = f.read()

d_keys = set()
for m in re.finditer(r"'(\w+)':\s*\w+\.get\([^,]+", txt):
    k = m.group(1)
    if len(k) <= 15:
        d_keys.add(k)
print('  %s' % sorted(d_keys))

print()
print('--- V13_实时策略引擎.py ---')
fp2 = os.path.join(SCRIPTS, 'V13_实时策略引擎.py')
if os.path.exists(fp2):
    with open(fp2, 'r', encoding='utf-8') as f:
        txt2 = f.read()
    if 'v13_quant.db' in txt2:
        print('  数据源: SQLite OK')
    else:
        print('  数据源: 未使用SQLite <<<')
    if '.pkl' in txt2:
        print('  仍引用pickle <<<')
    if 'big_cache' in txt2:
        print('  引用big_cache <<<')

print()
print('--- V13_日报.py ---')
fp3 = os.path.join(SCRIPTS, 'V13_日报.py')
if os.path.exists(fp3):
    with open(fp3, 'r', encoding='utf-8') as f:
        txt3 = f.read()
    if 'v13_quant.db' in txt3:
        print('  数据源: SQLite OK')
    else:
        print('  数据源: 未使用SQLite <<<')
    if '.pkl' in txt3:
        print('  仍引用pickle <<<')
    if 'big_cache' in txt3:
        print('  引用big_cache <<<')
