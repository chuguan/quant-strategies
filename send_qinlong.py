     1|#!/usr/bin/env python3
     2|"""擒龙MAX结果发送到1254628314@qq.com"""
     3|import sys, os, subprocess
     4|sys.path.insert(0, os.path.dirname(__file__))
     5|from send_email import send_email
     6|
     7|US_UP = '#ff4757'
     8|
     9|# Top10数据
    10|top10 = [
    11|    ("艾华集团","603989",28.42,"+9.98%",113),
    12|    ("新大陆","000997",24.81,"+10.02%",107),
    13|    ("恒通股份","603223",10.70,"+9.97%",103),
    14|    ("三力制药","603439",14.29,"+10.01%",103),
    15|    ("光华科技","002741",25.36,"+10.02%",103),
    16|    ("新疆众和","600888",10.31,"+10.03%",98),
    17|    ("川润股份","002272",24.70,"+10.02%",98),
    18|    ("华锋股份","002806",16.79,"+10.03%",98),
    19|    ("澳柯玛","600336",8.65,"+7.32%",97),
    20|    ("奋达科技","002681",5.84,"+7.55%",97),
    21|]
    22|
    23|cards = ""
    24|for i, (name, code, price, pct, score) in enumerate(top10):
    25|    cls = "#ffd700" if i == 0 else ("#c0c0c0" if i == 1 else ("#cd7f32" if i == 2 else "#888"))
    26|    gold = "🥇" if i == 0 else ("🥈" if i == 1 else ("🥉" if i == 2 else f"{i+1}"))
    27|    cards += f"""<tr style="border-bottom:1px solid #2a2a3e">
    28|<td style="padding:8px;text-align:center;color:{cls};font-weight:bold;font-size:16px">{gold}</td>
    29|<td style="padding:8px;font-weight:bold;color:#fff;font-size:14px">{name}</td>
    30|<td style="padding:8px;color:#888;font-size:12px">{code}</td>
    31|<td style="padding:8px;text-align:center;color:#ff6b35;font-size:14px">{price:.2f}</td>
    32|<td style="padding:8px;text-align:center;color:{US_UP};font-weight:bold;font-size:14px">{pct}</td>
    33|<td style="padding:8px;text-align:center;color:#58a6ff;font-weight:bold;font-size:14px">{score}分</td>
    34|</tr>"""
    35|
    36|html = f"""<!DOCTYPE html>
    37|<html><head><meta charset="utf-8"></head>
    38|<body style="font-family:微软雅黑,Helvetica,sans-serif;background:#0d1117;color:#fff;padding:20px;max-width:680px;margin:auto">
    39|
    40|<div style="text-align:center;padding:28px 20px;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;margin-bottom:18px">
    41|<h1 style="color:#ff6b35;margin:0;font-size:28px">🐉 擒龙MAX</h1>
    42|<p style="color:#888;font-size:13px;margin:8px 0">2026-05-25 | 实时API全市场扫描</p>
    43|</div>
    44|
    45|<div style="background:linear-gradient(135deg,#0f3460,#16213e);border-radius:12px;padding:18px;margin:14px 0">
    46|<h3 style="color:#ff6b35;margin:0 0 12px 0;font-size:16px">🏆 Top 10 擒龙MAX</h3>
    47|<table style="width:100%;border-collapse:collapse;font-size:14px">
    48|<tr style="background:#0f3460;color:#888"><th style="padding:8px">#</th><th style="text-align:left">名称</th><th>代码</th><th>价格</th><th>涨幅</th><th>评分</th></tr>
    49|{cards}
    50|</table>
    51|</div>
    52|
    53|<div style="background:#16213e;border-radius:12px;padding:18px;margin:14px 0">
    54|<h4 style="color:#ff6b35;margin:0 0 10px 0;font-size:14px">📊 扫描统计</h4>
    55|<div style="font-size:13px;color:#fff;line-height:1.8">
    56|• 全市场扫描：<b style="color:#ff6b35">3092只</b><br>
    57|• 评分通过：<b style="color:#58a6ff">153只</b>（前10上榜）<br>
    58|• 耗时：<b style="color:#7bed9f">6秒</b>（K线缓存已预热）<br>
    59|• 🔴 红色 = 上涨（中国习惯）<br>
    60|• ⚡ 建议：尾盘14:55买入Top3，挂+5%止盈
    61|</div>
    62|</div>
    63|
    64|<div style="text-align:center;padding:14px;color:#555;font-size:11px;border-top:1px solid #222;margin-top:16px">
    65|<p>⚠️ 仅供参考，不构成投资建议 | 数据来源：腾讯实时API</p>
    66|</div>
    67|</body></html>"""
    68|
    69|send_email(['1254628314@qq.com'], '🐉 擒龙MAX', html, html=True)
    70|print("✅ 已发送到 1254628314@qq.com")
    71|