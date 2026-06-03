     1|     1|#!/usr/bin/env python3
     2|     2|"""早盘简报发送脚本"""
     3|     3|import sys, os
     4|     4|sys.path.insert(0, os.path.dirname(__file__))
     5|     5|from send_email import send_email
     6|     6|
     7|     7|today_str = '2026-05-25 周一'
     8|     8|
     9|     9|html = f"""<!DOCTYPE html>
    10|    10|<html><head><meta charset="utf-8"></head>
    11|    11|<body style="font-family:微软雅黑,Helvetica,sans-serif;background:#0d1117;color:#e0e0e0;padding:20px;max-width:680px;margin:auto">
    12|    12|
    13|    13|<div style="text-align:center;padding:25px 20px;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;margin-bottom:18px">
    14|    14|<h1 style="color:#ff6b35;margin:0;font-size:26px">📰 天机早报</h1>
    15|    15|<p style="color:#888;font-size:13px;margin:8px 0 0 0">{today_str} | 美股+A股 | 资金流向</p>
    16|    16|</div>
    17|    17|
    18|    18|<div style="background:linear-gradient(135deg,#0f3460,#16213e);border-radius:12px;padding:18px;margin:14px 0">
    19|    19|<h3 style="color:#ff6b35;margin:0 0 12px 0;font-size:16px">🇺🇸 美股上周五（5/22）</h3>
    20|    20|<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">
    21|    21|<div style="flex:1;min-width:140px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
    22|    22|<div style="color:#888;font-size:12px">道琼斯</div>
    23|    23|<div style="color:#ff6b35;font-size:20px;font-weight:bold">50579</div>
    24|    24|<div style="color:#7bed9f;font-size:13px">+145 (+0.29%) 📈</div>
    25|    25|</div>
    26|    26|<div style="flex:1;min-width:140px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
    27|    27|<div style="color:#888;font-size:12px">纳斯达克</div>
    28|    28|<div style="color:#ff6b35;font-size:20px;font-weight:bold">26343</div>
    29|    29|<div style="color:#ff4757;font-size:13px">-37 (-0.14%) 📉</div>
    30|    30|</div>
    31|    31|</div>
    32|    32|
    33|    33|<h4 style="color:#c0c0c0;margin:14px 0 8px 0;font-size:14px">🏆 美股板块TOP3</h4>
    34|    34|<div style="background:#1a1a2e;border-left:4px solid #ffd700;padding:10px 12px;margin:4px 0;border-radius:4px;font-size:13px">
    35|    35|<strong style="color:#ffd700">🥇 能源 XLE</strong> <span style="color:#7bed9f">+0.85%</span> — 原油反弹带动<br>
    36|    36|<strong style="color:#c0c0c0">🥈 医疗 XLV</strong> <span style="color:#7bed9f">+0.54%</span> — 防御性资金流入<br>
    37|    37|<strong style="color:#cd7f32">🥉 半导体 SMH</strong> <span style="color:#7bed9f">+0.36%</span> — AI算力需求持续
    38|    38|</div>
    39|    39|
    40|    40|<h4 style="color:#c0c0c0;margin:14px 0 8px 0;font-size:14px">📡 美股最新重大消息</h4>
    41|    41|<div style="background:#1a1a2e;padding:10px 12px;border-radius:4px;font-size:13px;color:#ccc;line-height:1.7">
    42|    42|• 美联储会议纪要显示多数官员支持年内降息，市场预期9月降息概率上升<br>
    43|    43|• 英伟达AI芯片订单超预期，带动半导体板块走强<br>
    44|    44|• 原油价格反弹至$76/桶，能源股领涨大盘
    45|    45|</div>
    46|    46|</div>
    47|    47|
    48|    48|<div style="background:linear-gradient(135deg,#0f3460,#16213e);border-radius:12px;padding:18px;margin:14px 0">
    49|    49|<h3 style="color:#ff6b35;margin:0 0 12px 0;font-size:16px">🇨🇳 A股上周五（5/22）</h3>
    50|    50|<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">
    51|    51|<div style="flex:1;min-width:120px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
    52|    52|<div style="color:#888;font-size:12px">上证</div>
    53|    53|<div style="color:#ff6b35;font-size:20px;font-weight:bold">4112</div>
    54|    54|<div style="color:#7bed9f;font-size:13px">+0.41% 📈</div>
    55|    55|</div>
    56|    56|<div style="flex:1;min-width:120px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
    57|    57|<div style="color:#888;font-size:12px">深证</div>
    58|    58|<div style="color:#ff6b35;font-size:20px;font-weight:bold">15597</div>
    59|    59|<div style="color:#7bed9f;font-size:13px">+1.40% 📈</div>
    60|    60|</div>
    61|    61|<div style="flex:1;min-width:120px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
    62|    62|<div style="color:#888;font-size:12px">创业板</div>
    63|    63|<div style="color:#ff6b35;font-size:20px;font-weight:bold">3938</div>
    64|    64|<div style="color:#7bed9f;font-size:13px">+1.62% 📈</div>
    65|    65|</div>
    66|    66|</div>
    67|    67|<p style="font-size:13px;color:#aaa;margin:12px 0 0 0;line-height:1.6">
    68|    68|🔍 上周四暴跌后周五企稳反弹，创业板领涨<br>
    69|    69|⚡ 本周关注：上证4070支撑，创业板能否持续领涨
    70|    70|</p>
    71|    71|</div>
    72|    72|
    73|    73|<div style="background:#16213e;border-radius:12px;padding:18px;margin:14px 0">
    74|    74|<h3 style="color:#ff6b35;margin:0 0 10px 0;font-size:16px">🔗 美股→A股映射</h3>
    75|    75|<div style="font-size:13px;color:#ccc;line-height:1.7">
    76|    76|• <strong style="color:#ffa502">能源股领涨</strong> → A股石油石化、煤炭板块<br>
    77|    77|• <strong style="color:#ffa502">半导体走强</strong> → A股半导体设备、封测受益<br>
    78|    78|• <strong style="color:#ffa502">医疗板块稳健</strong> → 创新药、医疗器械<br>
    79|    79|• <strong style="color:#ffa502">道指新高</strong> → 全球风险偏好提升，利好外资流入
    80|    80|</div>
    81|    81|</div>
    82|    82|
    83|    83|<div style="background:#16213e;border-radius:12px;padding:18px;margin:14px 0">
    84|    84|<h3 style="color:#ff6b35;margin:0 0 10px 0;font-size:16px">🔥 本周关注</h3>
    85|    85|<div style="font-size:13px;color:#ccc;line-height:1.8">
    86|    86|<strong style="color:#7bed9f">1.</strong> 国务院常务会议对新能源产业的部署<br>
    87|    87|<strong style="color:#7bed9f">2.</strong> 能源+半导体板块美股映射联动<br>
    88|    88|<strong style="color:#7bed9f">3.</strong> 上证4070支撑位决定本周方向<br>
    89|    89|<strong style="color:#7bed9f">4.</strong> 北向资金流向，上周五有回流迹象
    90|    90|</div>
    91|    91|</div>
    92|    92|
    93|    93|<div style="text-align:center;padding:14px;color:#555;font-size:11px;border-top:1px solid #222;margin-top:16px">
    94|    94|<p>⚠️ 本报告仅供参考，不构成投资建议。</p>
    95|    95|</div></body></html>"""
    96|    96|
    97|    97|send_email(['1254628314@qq.com'], f'天机早报 {today_str}', html, html=True)
    98|    98|print("✅ 已发送到 1254628314@qq.com")
    99|    99|