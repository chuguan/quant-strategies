"""批量更新V48评分：加振幅+实体因子"""
from hermes_tools import patch

files = [
    ('跌日', 'p', 'w', 's', 'stock'),
    ('真实涨日', 'p', 'w', 's', 'stock'),
]

new_penalty = '''
    # ═══ V48：振幅+实体加分 ═══
    amp_48 = stock.get('amplitude', 0) or 0
    body_48 = stock.get('body_pct', 0) or 0
    s += min(amp_48 / 6.0, 1) * 12   # 振幅加分：振幅6%满分12分
    s += min(body_48 / 5.0, 1) * 8    # 实体加分：实体5%满分8分
'''

for fname in files:
    name = fname[0]
    p = patch(
        path=f'/c/Users/12546/AppData/Local/hermes/scripts/release/V48/评分策略/分而治之_V10_{name}_评分策略.py',
        old_string='''    return round(s, 1)''',
        new_string=f'''{new_penalty}
    return round(s, 1)''',
        replace_all=True
    )
    print(f"{name}: {p['success']}")
