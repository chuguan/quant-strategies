     1|     1|"""收盘擒龙MAX — HTML模板 + 微信推送 + 共享盘"""
     2|     2|import sys, os, subprocess, re
     3|     3|from datetime import datetime
     4|     4|
     5|     5|QL_MAX = os.path.expanduser("~/AppData/Local/hermes/hermes-agent/qinlong_max.py")
     6|     6|SHARE_DIR = "G:/股票数据/擒龙MAX结果"
     7|     7|
     8|     8|if "--force" not in sys.argv and datetime.now().weekday() >= 5:
     9|     9|    print("非交易日，跳过"); sys.exit(0)
    10|    10|
    11|    11|# 运行擒龙MAX
    12|    12|env = os.environ.copy(); env["PYTHONUNBUFFERED"] = "1"
    13|    13|r = subprocess.run([sys.executable, QL_MAX], capture_output=True, text=True, timeout=180, env=env)
    14|    14|output = r.stdout
    15|    15|if r.stderr: output += "\n" + r.stderr[:500]
    16|    16|
    17|    17|# 输出到微信
    18|    18|print(output)
    19|    19|
    20|    20|# 存文件
    21|    21|today = datetime.now().strftime("%Y-%m-%d")
    22|    22|os.makedirs(SHARE_DIR, exist_ok=True)
    23|    23|fp = os.path.join(SHARE_DIR, f"擒龙MAX_{today}.txt")
    24|    24|with open(fp, "w", encoding="utf-8") as f: f.write(output)
    25|    25|print(f"\n📁 结果已保存: {fp}")
    26|    26|
    27|    27|# ─── 构建HTML邮件 ─────────────────────────
    28|    28|US_UP = '#ff4757'  # 上涨=红
    29|    29|US_DN = '#7bed9f'  # 下跌=绿
    30|    30|
    31|    31|lines = output.strip().split('\n')
    32|    32|top10 = []
    33|    33|in_top = False
    34|    34|summary = ""
    35|    35|for line in lines:
    36|    36|    if 'TOP 10' in line: in_top = True; continue
    37|    37|    if '耗时' in line: summary = line
    38|    38|    if in_top and line.strip().startswith(('1.','2.','3.','4.','5.','6.','7.','8.','9.','10.')):
    39|    39|        top10.append(line)
    40|    40|
    41|    41|def parse_top(line):
    42|    42|    parts = line.strip().split()
    43|    43|    if len(parts) < 5: return None
    44|    44|    rank = parts[0].rstrip('.')
    45|    45|    name = parts[1]
    46|    46|    price = next((p for p in parts if p.replace('.','',1).replace('-','',1).isdigit() and '.' in p), '?')
    47|    47|    pct = next((p for p in parts if p.startswith(('+','-')) and '%' in p), '?')
    48|    48|    score = next((p for p in parts if '分' in p), '?')
    49|    49|    return {'rank': rank, 'name': name, 'price': price, 'pct': pct, 'score': score}
    50|    50|
    51|    51|cards = ""
    52|    52|for i, line in enumerate(top10[:10]):
    53|    53|    d = parse_top(line)
    54|    54|    if not d: continue
    55|    55|    pct_val = float(d['pct'].replace('%',''))
    56|    56|    pct_clr = US_UP if pct_val >= 0 else US_DN
    57|    57|    score_val = int(d['score'].replace('分',''))
    58|    58|    score_clr = '#ff6b35' if score_val >= 100 else ('#ffa502' if score_val >= 80 else '#888')
    59|    59|    cards += f"""<tr style="border-bottom:1px solid #2a2a3e">
    60|    60|<td style="padding:8px;text-align:center;font-weight:bold;color:#ffd700">#{d['rank']}</td>
    61|    61|<td style="padding:8px;font-weight:bold;color:#fff">{d['name'][:8]}</td>
    62|    62|<td style="padding:8px;text-align:center;color:#ff6b35">{d['price']}</td>
    63|    63|<td style="padding:8px;text-align:center;color:{pct_clr};font-weight:bold">{d['pct']}</td>
    64|    64|<td style="padding:8px;text-align:center;color:{score_clr};font-weight:bold">{d['score']}</td>
    65|    65|</tr>"""
    66|    66|
    67|    67|html = f"""<!DOCTYPE html>
    68|    68|<html><head><meta charset="utf-8"></head>
    69|    69|<body style="font-family:微软雅黑,Helvetica,sans-serif;background:#0d1117;color:#fff;padding:20px;max-width:680px;margin:auto">
    70|    70|
    71|    71|<div style="text-align:center;padding:28px 20px;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;margin-bottom:18px">
    72|    72|<h1 style="color:#ff6b35;margin:0;font-size:26px">🐉 擒龙MAX 收盘结果</h1>
    73|    73|<p style="color:#888;font-size:13px;margin:8px 0 0 0">{today} | 实时API全市场扫描</p>
    74|    74|</div>
    75|    75|
    76|    76|<div style="background:linear-gradient(135deg,#0f3460,#16213e);border-radius:12px;padding:18px;margin:14px 0">
    77|    77|<h3 style="color:#ff6b35;margin:0 0 12px 0;font-size:16px">🏆 擒龙MAX Top 10</h3>
    78|    78|<table style="width:100%;border-collapse:collapse;font-size:13px">
    79|    79|<tr style="background:#0f3460;color:#888"><th style="padding:8px">#</th><th style="text-align:left">名称</th><th>价格</th><th>涨幅</th><th>评分</th></tr>
    80|    80|{cards}
    81|    81|</table>
    82|    82|</div>
    83|    83|
    84|    84|<div style="background:#16213e;border-radius:12px;padding:18px;margin:14px 0">
    85|    85|<h4 style="color:#888;margin:0 0 10px 0;font-size:13px">📊 扫描统计</h4>
    86|    86|<div style="font-size:13px;color:#fff;line-height:1.8">
    87|    87|• 全市场扫描完成<br>
    88|    88|• 评分通过数：{summary}<br>
    89|    89|• ⚡ 建议：尾盘14:55买入Top3<br>
    90|    90|• 🔴 上涨用红色  🟢 下跌用绿色
    91|    91|</div>
    92|    92|</div>
    93|    93|
    94|    94|<div style="text-align:center;padding:14px;color:#555;font-size:11px;border-top:1px solid #222;margin-top:16px">
    95|    95|<p>⚠️ 仅供参考，不构成投资建议 | 数据来源：腾讯实时API</p>
    96|    96|</div>
    97|    97|</body></html>"""
    98|    98|
    99|    99|# ─── 邮件发送 ─────────────────────────────
   100|   100|EMAIL_TO_LIST = ["1254628314@qq.com"]
   101|   101|EMAIL_TITLE = f"擒龙MAX收盘结果_{today}"
   102|   102|try:
   103|   103|    from email.mime.text import MIMEText
   104|   104|    from email.header import Header
   105|   105|    import ssl, smtplib
   106|   106|    SENDER = "xiaozhufenfen88@163.com"
   107|   107|    PASSWORD = "YZmfTbTsvXWbSnFy"
   108|   108|    msg = MIMEText(html, "html", "utf-8")
   109|   109|    msg["From"] = SENDER
   110|   110|    msg["To"] = ", ".join(EMAIL_TO_LIST)
   111|   111|    msg["Subject"] = Header(EMAIL_TITLE, "utf-8")
   112|   112|    ctx = ssl.create_default_context()
   113|   113|    with smtplib.SMTP_SSL("smtp.163.com", 465, timeout=15) as svr:
   114|   114|        svr.login(SENDER, PASSWORD)
   115|   115|        svr.sendmail(SENDER, EMAIL_TO_LIST, msg.as_string())
   116|   116|    print(f"📧 邮件已发送到 {', '.join(EMAIL_TO_LIST)}")
   117|   117|except Exception as e:
   118|   118|    print(f"⚠️ 邮件发送失败: {e}")
   119|   119|