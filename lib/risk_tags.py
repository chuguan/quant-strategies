#!/usr/bin/env python3
"""
风险标签系统 — 给选股结果打风险标签，不改评分逻辑
═══════════════════════════════════════════
基于4个失败案例（通宇通讯/海思科/水晶光电/盛新锂能）提炼的共性风险信号

用法:
    from risk_tags import get_risk_tags
    tags = get_risk_tags(stock_data, ind_data, market_avg_pct=0)
    # 返回: [('🔴 高位超买', 'CL>90+WR<10'), ('🟠 动力衰竭', 't4s>25'), ...]
"""

def get_risk_tags(s, ind, market_avg_pct=0):
    """
    分析股票数据，返回风险标签列表
    s: 股票基础数据 (含 p, vol_ratio, hsl 等)
    ind: 技术指标 (含 cl, wr_val, pos_in_day, dif 等)
    market_avg_pct: 全市场平均涨幅（用于判断超级行情）
    
    返回: [(标签emoji+名称, 技术原因说明), ...]
    """
    tags = []
    
    # ═══ 提取关键指标（安全取值）═══
    p = s.get('p', 0) or 0
    vr = s.get('vol_ratio', 0) or 0
    hsl = s.get('hsl', 0) or 0
    cl = ind.get('cl', s.get('cl', 50)) if ind else s.get('cl', 50)
    wr = ind.get('wr_val', s.get('wr_val', 50)) if ind else s.get('wr_val', 50)
    wrv = ind.get('wrv', s.get('wrv', 50)) if ind else s.get('wrv', 50)
    wr_val = wr if wr != 50 else wrv
    pos = ind.get('pos_in_day', s.get('pos_in_day', 50)) if ind else s.get('pos_in_day', 50)
    dif = ind.get('dif', s.get('dif_val', 0)) if ind else s.get('dif_val', 0)
    t4s = s.get('t4_shadow', 0) or 0
    sl5 = s.get('slope5', 0) or 0
    a5 = s.get('a5', ind.get('above_ma5', 0)) if ind else s.get('a5', 0)
    
    # 1️⃣ 高位超买 🔴 — CL>90 + WR<10
    if cl and wr_val and cl > 90 and wr_val < 10:
        tags.append(('🔴 高位超买', f'CL={cl:.0f} WR={wr_val:.0f} 水晶光电/盛新锂能式风险'))
    
    # 2️⃣ 收盘过高 🟡 — pos_in_day > 75
    if pos and pos > 75:
        tags.append(('🟡 收盘过高', f'pos={pos:.0f} 收盘位置偏高，明天空间受限'))
    
    # 3️⃣ 动力衰竭 🟠 — t4s > 25
    if t4s > 25:
        tags.append(('🟠 动力衰竭', f't4s={t4s:.0f} 4日上影线大，盛新锂能式风险'))
    
    # 4️⃣ 涨势偏弱 ⚪ — p < 2%
    if p < 2:
        tags.append(('⚪ 涨势偏弱', f'p={p:.1f}% 海思科式风险'))
    
    # 5️⃣ 超级行情跟风 📈 — 大盘均值>2%且涨幅适中（跟风票）
    if market_avg_pct > 2 and p < 5:
        tags.append(('📈 超级行情跟风', f'大盘均{market_avg_pct:+.1f}%, 通宇通讯式风险'))
    
    # 6️⃣ 缩量上涨 📉 — VR<0.9
    if vr and vr < 0.9:
        tags.append(('📉 缩量上涨', f'VR={vr:.2f} 华通线缆式风险'))
    
    # 7️⃣ 高换手 ⚠️ — HSL>12
    if hsl and hsl > 12:
        tags.append(('⚠️ 高换手', f'HSL={hsl:.1f}% 主力出货风险'))
    
    return tags


def risk_tags_html(tags):
    """
    将标签列表转为HTML小标签
    返回HTML字符串（多个span）
    """
    if not tags:
        return '<span style="display:inline-block;font-size:10px;padding:1px 5px;border-radius:3px;background:#e8f5e9;color:#2e7d32;margin-right:3px">✅ 无显著风险</span>'
    
    html_parts = []
    for emoji_name, reason in tags:
        # 根据级别选择颜色
        if '🔴' in emoji_name:
            bg, fg = '#ffebee', '#c62828'
        elif '🟠' in emoji_name:
            bg, fg = '#fff3e0', '#e65100'
        elif '🟡' in emoji_name:
            bg, fg = '#fff8e1', '#f57f17'
        elif '⚠️' in emoji_name:
            bg, fg = '#fff3e0', '#e65100'
        elif '📉' in emoji_name:
            bg, fg = '#fce4ec', '#ad1457'
        elif '📈' in emoji_name:
            bg, fg = '#e3f2fd', '#1565c0'
        else:
            bg, fg = '#f5f5f5', '#616161'
        html_parts.append(
            f'<span style="display:inline-block;font-size:10px;padding:1px 5px;'
            f'border-radius:3px;background:{bg};color:{fg};margin-right:3px" '
            f'title="{reason}">{emoji_name}</span>'
        )
    
    return ''.join(html_parts)


# 测试
if __name__ == '__main__':
    # 模拟4个失败案例
    tests = [
        ('通宇通讯 4/8', {'p':3.2, 'vol_ratio':1.1, 'hsl':5}, {'cl':85, 'wr_val':15, 'pos_in_day':55, 'dif':-0.5}, 3.18),
        ('海思科 4/15', {'p':0.1, 'vol_ratio':0.8, 'hsl':3}, {'cl':76, 'wr_val':24, 'pos_in_day':38, 'dif':0.2}, -0.39),
        ('水晶光电 4/21', {'p':3.9, 'vol_ratio':1.0, 'hsl':8}, {'cl':95, 'wr_val':5.5, 'pos_in_day':77, 'dif':1.5}, -0.13),
        ('盛新锂能 4/27', {'p':2.3, 'vol_ratio':0.9, 'hsl':6, 't4_shadow':25}, {'cl':92, 'wr_val':7.8, 'pos_in_day':49, 'dif':-1.0}, 0.42),
        ('江顺科技 6/8', {'p':6.53, 'vol_ratio':3.14, 'hsl':13.19, 't4_shadow':5}, {'cl':85, 'wr_val':20, 'pos_in_day':65, 'dif':1.5, 'above_ma5':1}, -2.26),
    ]
    for name, s, ind, mkt in tests:
        tags = get_risk_tags(s, ind, mkt)
        print(f'\n{name}:')
        if tags:
            for t in tags:
                print(f'  {t[0]} — {t[1]}')
        else:
            print('  ✅ 无风险信号')
