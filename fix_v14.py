"""修复V14评分文件"""
import os, py_compile

D = os.path.expanduser('~/AppData/Local/hermes/scripts/release/V14/评分策略')
INSERT = [
    '\n',
    '    # V14新增：前7天有大阳+洗盘信号\n',
    '    d1 = s.get("d1", 0); d2 = s.get("d2", 0); d3 = s.get("d3", 0)\n',
    '    p_today = s.get("p", 0)\n',
    '    max_4d = max(p_today, d1, d2, d3)\n',
    '    min_4d = min(d1, d2, d3) if min(d1, d2, d3) < 0 else 0\n',
    '    if p.get("use_max_p_bonus", 1):\n',
    '        if max_4d >= 9.5: score += p.get("max_p_bonus_zt", 8)\n',
    '        elif max_4d >= 7.0: score += p.get("max_p_bonus_big", 5)\n',
    '        elif max_4d >= 5.0: score += p.get("max_p_bonus_med", 3)\n',
    '    if p.get("use_min_p_bonus", 1):\n',
    '        if min_4d <= -7.0: score += p.get("min_p_bonus_deep", 5)\n',
    '        elif min_4d <= -5.0: score += p.get("min_p_bonus_mid", 3)\n',
    '        elif min_4d <= -3.0: score += p.get("min_p_bonus_light", 1)\n',
    '    if p.get("use_cl_optimal", 1):\n',
    '        cl_val = s.get("cl", 50)\n',
    '        cl_lo = p.get("cl_optimal_lo", 40)\n',
    '        cl_hi = p.get("cl_optimal_hi", 75)\n',
    '        if cl_lo <= cl_val <= cl_hi:\n',
    '            score += p.get("cl_optimal_bonus", 3)\n',
]

for fn in ['分而治之_V10_跌日_评分策略.py', '分而治之_V10_横盘_评分策略.py',
           '分而治之_V10_虚涨日_评分策略.py', '分而治之_V10_真实涨日_评分策略.py']:
    fp = os.path.join(D, fn)
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找函数内最后一个return
    # 先找到def score(
    def_pos = content.find('def score(')
    if def_pos < 0: print(f'{fn}: 无score函数'); continue
    
    # 找到函数体内的最后一个return
    func_body = content[def_pos:]
    last_return = func_body.rfind('\nreturn ')
    if last_return < 0:
        last_return = func_body.rfind('\n    return ')
    if last_return < 0: print(f'{fn}: 无return'); continue
    
    # 在return前插入
    insert_pos = def_pos + last_return
    content = content[:insert_pos] + '\n' + ''.join(INSERT) + content[insert_pos:]
    
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    
    try:
        py_compile.compile(fp, doraise=True)
        print(f'✅ {fn}')
    except py_compile.PyCompileError as e:
        print(f'❌ {fn}: {e}')
