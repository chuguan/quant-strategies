#!/usr/bin/env python
"""检查回测结果是否被用作选股条件"""
import os, re

SCRIPTS = r'C:\Users\12546\AppData\Local\hermes\scripts'

targets = [
    os.path.join(SCRIPTS, 'V13_生产.py'),
    os.path.join(SCRIPTS, 'V13_实时策略引擎.py'),
    os.path.join(SCRIPTS, 'V13_日报.py'),
    os.path.join(SCRIPTS, 'post_process.py'),
    os.path.join(SCRIPTS, 'daily_data_collect.py'),
]
for v in ['V13','V13A','V13B','V13C']:
    d = os.path.join(SCRIPTS, 'release', v, '评分策略')
    if os.path.exists(d):
        for f in sorted(os.listdir(d)):
            if f.endswith('.py'):
                targets.append(os.path.join(d, f))

patterns = [
    ('回测成绩选股', r'backtest.*(result|data|score|res)'),
    ('历史胜率选股', r'(历史|历史战绩|累计胜).*[=:>]'),
    ('win_rate', r'win[_ ]rate|胜率[=:].*[0-9]'),
    ('past_records', r'past.*(win|score|result)'),
]

print('≡≡≡ 回测结果作为选股条件检查 ≡≡≡')
found = False
for fp in targets:
    rel = os.path.relpath(fp, SCRIPTS)
    with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        for tp, pat in patterns:
            if re.search(pat, s, re.IGNORECASE):
                print('  %s L%d [%s] %s' % (rel, no, tp, s[:100]))
                found = True
                break

if not found:
    print('  ✅ 未发现回测结果用于选股')

# 评分策略中的BACKTEST注释（纯信息，不影响选股）
print()
print('=== 评分策略BACKTEST标记(注释用) ===')
for fp in targets:
    if '评分策略' in fp:
        with open(fp, 'r', encoding='utf-8') as f:
            content = f.read()
        m = re.search(r'BACKTEST\s*=\s*["\']([^"\']+)["\']', content)
        if m:
            rel = os.path.relpath(fp, SCRIPTS)
            print('  %s: %s' % (rel, m.group(1)))
