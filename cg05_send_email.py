     1|     1|#!/usr/bin/env python3
     2|     2|"""发送CG-05回测结果邮件"""
     3|     3|import json, os, sys
     4|     4|sys.path.insert(0, os.path.dirname(__file__))
     5|     5|from send_email import send_email
     6|     6|
     7|     7|BASE = os.path.dirname(__file__)
     8|     8|RESULT_FILE = os.path.join(BASE, "cg05_year_backtest_result.json")
     9|     9|
    10|    10|with open(RESULT_FILE) as f:
    11|    11|    data = json.load(f)
    12|    12|
    13|    13|summary = data["summary"]
    14|    14|results = data["all_results"]
    15|    15|
    16|    16|# 构建HTML邮件
    17|    17|html = """<!DOCTYPE html>
    18|    18|<html lang="zh-CN">
    19|    19|<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
    20|    20|<style>
    21|    21|*{margin:0;padding:0;box-sizing:border-box}
    22|    22|body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#0d1117;color:#e6edf3;padding:12px}
    23|    23|.container{max-width:640px;margin:0 auto}
    24|    24|.header{background:linear-gradient(135deg,#1a1a2e,#0f3460);border-radius:12px;padding:16px;margin-bottom:12px;border:1px solid #30363d;text-align:center}
    25|    25|.header h1{font-size:18px;color:#58a6ff}
    26|    26|.header .sub{font-size:10px;color:#8b949e;margin-top:3px}
    27|    27|.card{background:#161b22;border:1px solid #30363d;border-radius:10px;margin-bottom:10px;overflow:hidden}
    28|    28|.card-title{padding:10px 14px;font-size:13px;font-weight:700;background:#1c2128;border-bottom:1px solid #30363d;color:#e6edf3}
    29|    29|.card-body{padding:10px 14px}
    30|    30|table{width:100%;border-collapse:collapse;font-size:11px}
    31|    31|th{background:#161b22;padding:6px 4px;text-align:center;font-weight:600;color:#8b949e;font-size:9px;border-bottom:1px solid #30363d}
    32|    32|td{padding:5px 4px;text-align:center;border-bottom:1px solid #21262d}
    33|    33|.up{color:#f85149}
    34|    34|.down{color:#3fb950}
    35|    35|.best{color:#d29922;font-weight:700}
    36|    36|.highlight{background:#1a1a2e}
    37|    37|.footer{text-align:center;color:#484f58;font-size:9px;padding:10px 0}
    38|    38|.month-table td{font-size:10px}
    39|    39|</style></head><body>
    40|    40|<div class="container">
    41|    41|<div class="header">
    42|    42|<h1>🐉 CG-05 参数寻优 — 全年90交易日回测</h1>
    43|    43|<div class="sub">2026年1月~5月 · 3427只沪深主板股 · CG-05 vs CG-01原版</div>
    44|    44|</div>"""
    45|    45|
    46|    46|# 汇总表
    47|    47|html += '<div class="card"><div class="card-title">📊 策略对比总表</div><div class="card-body"><table>'
    48|    48|html += '<thead><tr><th>策略</th><th>出票</th><th>10%+</th><th>胜率10%</th><th>5%+</th><th>胜率5%</th><th>平均最高</th></tr></thead><tbody>'
    49|    49|for r in summary:
    50|    50|    is_best = "best" if r["rate10"] >= 50 else ""
    51|    51|    html += f'<tr><td class="{is_best}">{r["name"]}</td>'
    52|    52|    html += f'<td>{r["total_days"]}天</td>'
    53|    53|    html += f'<td>{r["hit10"]}天</td>'
    54|    54|    html += f'<td class="up">{r["rate10"]}%</td>'
    55|    55|    html += f'<td>{r["hit5"]}天</td>'
    56|    56|    html += f'<td class="up">{r["rate5"]}%</td>'
    57|    57|    html += f'<td class="up">{r["avg_max5"]:+.1f}%</td></tr>'
    58|    58|html += '</tbody></table></div></div>'
    59|    59|
    60|    60|# CG-05参数
    61|    61|html += f'<div class="card"><div class="card-title">🔧 CG-05 优化参数 (Top1🥇)</div><div class="card-body"><table>'
    62|    62|html += '<thead><tr><th>参数</th><th>CG-01原版</th><th class="best">CG-05</th></tr></thead><tbody>'
    63|    63|params_map = [
    64|    64|    ("涨幅范围", "3~5%", "4~5%"),
    65|    65|    ("MA5斜率", "≥8%", "≥10%"),
    66|    66|    ("收盘位置", "≥40%", "≥50%"),
    67|    67|    ("量比上限", "≤3.0x", "≤2.5x"),
    68|    68|    ("J线比率", "≥10%", "≥15%")
    69|    69|]
    70|    70|for name, old, new in params_map:
    71|    71|    html += f'<tr><td>{name}</td><td>{old}</td><td class="up"><strong>{new}</strong></td></tr>'
    72|    72|html += '</tbody></table></div></div>'
    73|    73|
    74|    74|# 按月对比
    75|    75|html += '<div class="card"><div class="card-title">📅 按月胜率对比 (10%+达标率)</div><div class="card-body month-table"><table>'
    76|    76|html += '<thead><tr><th>月份</th><th>CG-01</th><th>CG-05</th></tr></thead><tbody>'
    77|    77|for r in results:
    78|    78|    if "原版" in r["name"]:
    79|    79|        cg01_days = {d["date"][:7] for d in r["days"]}
    80|    80|        cg01_monthly = {}
    81|    81|        for m in ["2026-01","2026-02","2026-03","2026-04","2026-05"]:
    82|    82|            mdays = [d for d in r["days"] if d["date"].startswith(m)]
    83|    83|            mt = len(mdays)
    84|    84|            mh = sum(1 for d in mdays if d["max5"] >= 10)
    85|    85|            cg01_monthly[m] = (mt, mh)
    86|    86|    elif "Top1" in r["name"]:
    87|    87|        for m in ["2026-01","2026-02","2026-03","2026-04","2026-05"]:
    88|    88|            mdays = [d for d in r["days"] if d["date"].startswith(m)]
    89|    89|            mt = len(mdays)
    90|    90|            mh = sum(1 for d in mdays if d["max5"] >= 10)
    91|    91|            mr = round(mh/mt*100,1) if mt else 0
    92|    92|            c01t, c01h = cg01_monthly[m]
    93|    93|            c01r = round(c01h/c01t*100,1) if c01t else 0
    94|    94|            better = "up" if mr > c01r else "down"
    95|    95|            html += f'<tr><td><strong>{m}</strong></td><td>{c01t}天 {c01r}%</td><td class="{better}">{mt}天 <strong>{mr}%</strong></td></tr>'
    96|    96|html += '</tbody></table></div></div>'
    97|    97|
    98|    98|# 结论
    99|    99|html += '<div class="card"><div class="card-title">🏆 结论</div><div class="card-body" style="font-size:11px;line-height:1.6">'
   100|   100|html += '<p>✅ <strong>CG-05 胜率59.5%</strong> vs CG-01 36.0%，提升23.5个百分点</p>'
   101|   101|html += '<p>✅ 平均最高涨幅 <strong>+12.4%</strong> vs +9.0%，多赚3.4%</p>'
   102|   102|html += '<p>✅ 4月胜率高达 <strong>87.5%</strong>，均+17.9%</p>'
   103|   103|html += '<p>⚠️ 出票从75天减少到37天（更严但更精）</p>'
   104|   104|html += '</div></div>'
   105|   105|
   106|   106|html += '<div class="footer">Hermes Agent · CG-05 参数寻优 · 2026-05-24</div>'
   107|   107|html += '</div></body></html>'
   108|   108|
   109|   109|# 发送
   110|   110|recipients = ["1254628314@qq.com"]
   111|   111|print(f"📧 发送到: {', '.join(recipients)}")
   112|   112|send_email(recipients, "🐉 CG-05 参数寻优回测结果 2026-05-24", html, html=True)
   113|   113|print("✅ 完成!")
   114|   114|