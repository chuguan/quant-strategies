#!/usr/bin/env python
"""全量扫描所有策略文件中的未来数据引用"""
import os, re

SCRIPTS = r'C:\Users\12546\AppData\Local\hermes\scripts'

files = []
for root, dirs, fnames in os.walk(SCRIPTS):
    for f in fnames:
        if f.endswith('.py') and not f.startswith('_'):
            fp = os.path.join(root, f)
            if any(x in fp for x in ['__pycache__','node_modules']):
                continue
            files.append(fp)

print('扫描: %d 个文件\n' % len(files))

patterns = {
    'n过滤选股': r"['\"]n['\"]\s*[<>=!]+\s*0|nh\s*[<>=!]+\s*0",
    'next字段': r"next_high|next_close|next_low|['\"]next_",
    'd1h-d5h': r"\bd1h\b|\bd2h\b|\bd3h\b|\bd4h\b|\bd5h\b",
    'n筛选': r"\.get\(['\"]n['\"]|\[['\"]n['\"]\]",
}

issues = []
for fp in sorted(files):
    rel = os.path.relpath(fp, SCRIPTS)
    try:
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except:
        continue
    
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        for tp, pat in patterns.items():
            if re.search(pat, s):
                issues.append((rel, no, tp, s[:120]))
                break

if issues:
    print('≡≡≡ 未来数据引用 %d处 ≡≡≡' % len(issues))
    prev = ''
    for fp, no, tp, code in issues:
        if fp != prev:
            print('\n%s' % fp)
            prev = fp
        print('  L%d [%s] %s' % (no, tp, code))
else:
    print('✅ 无未来数据引用')

# 特别检查V13_生产.py
print('\n=== V13_生产.py 详细检查 ===')
fp = os.path.join(SCRIPTS, 'V13_生产.py')
if os.path.exists(fp):
    with open(fp, 'r') as f:
        lines = f.readlines()
    for no, line in enumerate(lines, 1):
        if 'n' in line and ('[' in line or 'get(' in line or 'nh' in line):
            print('  L%d: %s' % (no, line.rstrip()[:100]))

# 检查所有评分策略
print('\n=== 评分策略 n字段检查 ===')
score_files = []
for v in ['V13','V13A','V13B','V13C']:
    d = os.path.join(SCRIPTS, 'release', v, '评分策略')
    if os.path.exists(d):
        for f in sorted(os.listdir(d)):
            if f.endswith('.py'):
                score_files.append(os.path.join(d, f))
for fp in score_files:
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'n' in content and ('[' in content or 'get(' in content):
        # 检查是否引用了n/nh字段
        for k in ["['n'", "['nh'", ".get('n'", ".get('nh']", "['next'"]:
            if k in content:
                rel = os.path.relpath(fp, SCRIPTS)
                print('  %s: 引用了%s' % (rel, k))
