     1|     1|#!/usr/bin/env python3
     2|     2|import sys, os, subprocess
     3|     3|sys.path.insert(0, os.path.dirname(__file__))
     4|     4|from send_email import send_email
     5|     5|
     6|     6|# 运行擒龙MAX
     7|     7|r = subprocess.run(['python','qinlong_max.py'], capture_output=True, text=True, timeout=180,
     8|     8|    cwd=os.path.expanduser('~/AppData/Local/hermes/hermes-agent'))
     9|     9|output = r.stdout
    10|    10|
    11|    11|today = '2026-05-25'
    12|    12|US_UP = '#ff4757'
    13|    13|
    14|    14|lines = output.strip().split('\n')
    15|    15|top10 = []
    16|    16|in_top = False
    17|    17|for line in lines:
    18|    18|    if 'TOP 10' in line:
    19|    19|        in_top = True
    20|    20|        continue
    21|    21|    if in_top and line.strip().startswith(('1.','2.','3.','4.','5.','6.','7.','8.','9.','10.')):
    22|    22|        top10.append(line)
    23|    23|
    24|    24|cards = ""
    25|    25|for i, line in enumerate(top10):
    26|    26|    parts = line.strip().split()
    27|    27|    rank = parts[0].rstrip('.')
    28|    28|    name = parts[1]
    29|    29|    try:
    30|    30|        price = parts[2] if '.' in parts[2] else parts[3]
    31|    31|        pct = next(p for p in parts if p.startswith('+') or p.startswith('-'))
    32|    32|        score = next(p for p in parts if p.endswith('分'))
    33|    33|    except:
    34|    34|        price, pct, score = '?', '?', '?'
    35|    35|    ok = '🔥' if i < 3 else '✅'
    36|    36|    cards += f"""<tr style="border-bottom:1px solid #2a2a3e">
    37|    37|<td style="padding:8px;text-align:center;color:#ffd700;font-weight:bold">{rank}</td>
    38|    38|<td style="padding:8px;font-weight:bold;color:#fff">{name}</td>
    39|    39|<td style="padding:8px;text-align:center;color:#ff6b35">{price}</td>
    40|    40|<td style="padding:8px;text-align:center;color:{US_UP}">{pct}</td>
    41|    41|<td style="padding:8px;text-align:center;color:#ff6b35;font-weight:bold">{score}</td>
    42|    42|</tr>"""
    43|    43|
    44|    44|html = f"""<!DOCTYPE html>
    45|    45|<html><head><meta charset="utf-8"></head>
    46|    46|<body style="font-family:微软雅黑,Helvetica,sans-serif;background:#0d1117;color:#fff;padding:20px;max-width:680px;margin:auto">
    47|    47|
    48|    48|<div style="text-align:center;padding:25px 20px;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;margin-bottom:18px">
    49|    49|<h1 style="color:#ff6b35;margin:0;font-size:26px">🐉 擒龙MAX</h1>
    50|    50|<p style="color:#888;font-size:13px;margin:8px 0 0 0">{today} | 实时API | 3092只扫描</p>
    51|    51|</div>
    52|    52|
    53|    53|<div style="background:linear-gradient(135deg,#0f3460,#16213e);border-radius:12px;padding:18px;margin:14px 0">
    54|    54|<h3 style="color:#ff6b35;margin:0 0 12px 0;font-size:16px">🏆 Top 10 擒龙MAX</h3>
    55|    55|<table style="width:100%;border-collapse:collapse;font-size:14px">
    56|    56|<tr style="background:#0f3460;color:#888"><th style="padding:8px">#</th><th style="text-align:left">名称</th><th>价格</th><th>涨幅</th><th>评分</th></tr>
    57|    57|{cards}
    58|    58|</table>
    59|    59|</div>
    60|    60|
    61|    61|<div style="background:#16213e;border-radius:12px;padding:18px;margin:14px 0">
    62|    62|<table style="width:100%;border-collapse:collapse;font-size:13px;color:#aaa">
    63|    63|</table>
    64|    64|</div>
    65|    65|
    66|    66|<div style="text-align:center;padding:14px;color:#555;font-size:11px;border-top:1px solid #222;margin-top:16px">
    67|    67|<p>⚠️ 本报告仅供参考，不构成投资建议。数据来源：腾讯实时API。</p>
    68|    68|</div>
    69|    69|</body></html>"""
    70|    70|
    71|    71|send_email(['1254628314@qq.com'], f'擒龙MAX {today}', html, html=True)
    72|    72|print("✅ 已发送")
    73|    73|