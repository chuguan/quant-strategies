"""
V47: V42 + 透支过滤（基于6/1失败票分析）
"""
import os, sys, importlib, pickle

SCRIPTS_DIR = r'C:\Users\12546\AppData\Local\hermes\scripts'
RELEASE_DIR = os.path.join(SCRIPTS_DIR, 'release')

# 逐个修改评分策略文件，适配各自变量名
strategies = {
    '跌日': {
        'file': '分而治之_V10_跌日_评分策略.py',
        'penalty': '''
    # ═══ V47透支过滤 ═══
    if p > 6 and w < 20: s -= 15
    if v > 2 and p < 5: s -= 10
    if w < 10: s -= 8
'''
    },
    '真实涨日': {
        'file': '分而治之_V10_真实涨日_评分策略.py',
        'penalty': '''
    # ═══ V47透支过滤 ═══
    p__ = stock.get("p",0); w__ = stock.get("wrv",50); v__ = stock.get("vr",0)
    if p__ > 6 and w__ < 20: s -= 15
    if v__ > 2 and p__ < 5: s -= 10
    if w__ < 10: s -= 8
'''
    },
    '虚涨日': {
        'file': '分而治之_V10_虚涨日_评分策略.py',
        'penalty': '''
    # ═══ V47透支过滤 ═══
    p__ = stock.get("p",0); w__ = stock.get("wrv",50); v__ = stock.get("vr",0)
    if p__ > 6 and w__ < 20: score -= 15
    if v__ > 2 and p__ < 5: score -= 10
    if w__ < 10: score -= 8
'''
    },
    '横盘': {
        'file': '分而治之_V10_横盘_评分策略.py',
        'penalty1': '''
    # ═══ V47透支过滤 ═══
    if p_ > 6 and wrv_ < 20: bs -= 15
    if vr > 2 and p_ < 5: bs -= 10
    if wrv_ < 10: bs -= 8
''',
        'penalty2': '''
    # ═══ V47透支过滤 ═══
    pp = pp_ or stock.get('p',0)
    ww = w_ or stock.get('wrv',50)
    vv = v_ or stock.get('vr',0)
    if pp > 6 and ww < 20: bs -= 15
    if vv > 2 and pp < 5: bs -= 10
    if ww < 10: bs -= 8
'''
    }
}

v47_dir = os.path.join(RELEASE_DIR, 'V47', '评分策略')

# 处理跌日
fp = os.path.join(v47_dir, strategies['跌日']['file'])
with open(fp, 'r') as f: content = f.read()
# 找到return前的位置
lines = content.split('\n')
new_lines = []
for line in lines:
    if line.strip().startswith('return round'):
        for nl in strategies['跌日']['penalty'].split('\n'):
            new_lines.append(nl)
        new_lines.append(line)
    else:
        new_lines.append(line)
with open(fp, 'w') as f: f.write('\n'.join(new_lines))
print('✅ 跌日')

# 处理真实涨日
fp = os.path.join(v47_dir, strategies['真实涨日']['file'])
with open(fp, 'r') as f: content = f.read()
# V46的尾盘形态加分已经被替换了，找return前
if '# ═══ V47透支过滤 ═══' not in content:
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        if line.strip().startswith('return round'):
            for nl in strategies['真实涨日']['penalty'].split('\n'):
                new_lines.append(nl)
            new_lines.append(line)
        else:
            new_lines.append(line)
    with open(fp, 'w') as f: f.write('\n'.join(new_lines))
print('✅ 真实涨日')

# 处理虚涨日
fp = os.path.join(v47_dir, strategies['虚涨日']['file'])
with open(fp, 'r') as f: content = f.read()
if '# ═══ V47透支过滤 ═══' not in content:
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        if line.strip().startswith('return round'):
            for nl in strategies['虚涨日']['penalty'].split('\n'):
                new_lines.append(nl)
            new_lines.append(line)
        else:
            new_lines.append(line)
    with open(fp, 'w') as f: f.write('\n'.join(new_lines))
print('✅ 虚涨日')

# 处理横盘 - 第一个分支(CL<88)在return前
fp = os.path.join(v47_dir, strategies['横盘']['file'])
with open(fp, 'r') as f: content = f.read()
if '# ═══ V47透支过滤 ═══' not in content:
    # 横盘有两个return
    # 第一个return: 'return round(bs, 1)' (CL<88分支)
    # 第二个return: 'return round(bs,1)' (CL≥88分支)
    # 在第一个return前插入(用p_, wrv_, vr)
    content = content.replace(
        "        # 冲顶惩罚：横盘低位股涨太多或拉到位=明天没空间\n        if p_ > 5: bs -= 3\n        if stock.get('pos_in_day',50) > 70: bs -= 8\n        \n    # ═══ 尾盘形态加分（V46新增）═══\n    bs += _tail_end_score(stock)\n    \n        return round(bs, 1)",
        "        # 冲顶惩罚：横盘低位股涨太多或拉到位=明天没空间\n        if p_ > 5: bs -= 3\n        if stock.get('pos_in_day',50) > 70: bs -= 8\n        \n    # ═══ V47透支过滤 ═══\n    # 从stock取量比和WR\n    v_47 = stock.get('vr', 0) or 0\n    w_47 = stock.get('wrv', 50) or 50\n    if p_ > 6 and w_47 < 20: bs -= 15\n    if v_47 > 2 and p_ < 5: bs -= 10\n    if w_47 < 10: bs -= 8\n    \n        return round(bs, 1)"
    )
    
    # 第二个return前插入(用pp, w_)
    content = content.replace(
        "    # ═══ 尾盘形态加分（V46新增）═══\n    bs += _tail_end_score(stock)\n    \n    return round(bs,1)",
        "    # ═══ V47透支过滤 ═══\n    pp_47 = stock.get('p',0) or 0\n    ww_47 = stock.get('wrv',50) or 50\n    vv_47 = stock.get('vr',0) or 0\n    if pp_47 > 6 and ww_47 < 20: bs -= 15\n    if vv_47 > 2 and pp_47 < 5: bs -= 10\n    if ww_47 < 10: bs -= 8\n    \n    return round(bs,1)"
    )
    
    with open(fp, 'w') as f: f.write(content)
print('✅ 横盘')

print('\n全部策略已更新')
" 2>&1