     1|     1|#!/usr/bin/env python3
     2|     2|"""CG-01 评分冠军邮件推送 — 4月+5月结果"""
     3|     3|import json, os, sys
     4|     4|from datetime import datetime
     5|     5|sys.path.insert(0, os.path.dirname(__file__))
     6|     6|from send_email import send_email
     7|     7|
     8|     8|RECIPIENTS = ["1254628314@qq.com"]
     9|     9|CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'hermes-agent', 'champion_cache_CG-01_mar-may.txt')
    10|    10|
    11|    11|def load_champions():
    12|    12|    with open(CACHE_FILE) as f:
    13|    13|        raw = json.load(f)
    14|    14|    # 过滤4月+5月
    15|    15|    april_may = {}
    16|    16|    for dt, data in raw.items():
    17|    17|        if dt[5:7] in ('04', '05'):
    18|    18|            april_may[dt] = data
    19|    19|    return april_may
    20|    20|
    21|    21|def star_rating(s):
    22|    22|    if s >= 85: return "⭐⭐⭐⭐⭐"
    23|    23|    elif s >= 75: return "⭐⭐⭐⭐"
    24|    24|    elif s >= 65: return "⭐⭐⭐"
    25|    25|    elif s >= 55: return "⭐⭐"
    26|    26|    return "⭐"
    27|    27|
    28|    28|def build_html(champions):
    29|    29|    now = datetime.now()
    30|    30|    
    31|    31|    # 按月分组
    32|    32|    by_month = {'04': [], '05': []}
    33|    33|    for dt, c in champions.items():
    34|    34|        if c is None: continue
    35|    35|        m5 = c.get('max5')
    36|    36|        if m5 is None or m5 == "—" or not isinstance(m5, (int,float)):
    37|    37|            continue  # 跳过无效数据
    38|    38|        by_month[dt[5:7]].append((dt, c))
    39|    39|    
    40|    40|    # 统计
    41|    41|    all_max = []
    42|    42|    all_hit = 0
    43|    43|    for mn in ('04','05'):
    44|    44|        for dt, c in by_month[mn]:
    45|    45|            m5 = c['max5']
    46|    46|            all_max.append(m5)
    47|    47|            if m5 >= 10: all_hit += 1
    48|    48|    ov_avg = sum(all_max)/len(all_max) if all_max else 0
    49|    49|    ov_hit_pct = all_hit*100//len(all_max) if all_max else 0
    50|    50|    total_days = len(all_max)
    51|    51|    
    52|    52|    def month_section(mn, label):
    53|    53|        items = by_month.get(mn, [])
    54|    54|        if not items: return ""
    55|    55|        items.sort(key=lambda x: x[0])
    56|    56|        m_avgs = [c['max5'] for _, c in items]
    57|    57|        m_hit = sum(1 for v in m_avgs if v >= 10)
    58|    58|        m_avg = sum(m_avgs)/len(m_avgs)
    59|    59|        
    60|    60|        rows = ""
    61|    61|        for dt, c in items:
    62|    62|            m5 = c['max5']
    63|    63|            m5c = "up" if m5 >= 10 else ("warn" if m5 >= 5 else "down")
    64|    64|            hit = "✅" if m5 >= 10 else ""
    65|    65|            score = c['qscore']
    66|    66|            sc = "score-high" if score >= 85 else ("score-mid" if score >= 70 else "")
    67|    67|            stars = star_rating(score)
    68|    68|            pct = c.get('pct_d', 0)
    69|    69|            pc = "up" if pct > 0 else "down"
    70|    70|            rows += f'<tr>'
    71|    71|            rows += f'<td class="rank">{dt[-5:]}</td>'
    72|    72|            rows += f'<td><strong>{c["name"]}</strong><span class="code">{c["code"]}</span></td>'
    73|    73|            rows += f'<td class="num {sc}">{score}<span class="stars">{stars}</span></td>'
    74|    74|            rows += f'<td class="num {pc}">{pct:+.2f}%</td>'
    75|    75|            rows += f'<td class="num {m5c}"><strong>{m5:+.1f}%</strong> {hit}</td>'
    76|    76|            rows += f'</tr>'
    77|    77|        
    78|    78|        hit_pct = m_hit*100//len(items) if items else 0
    79|    79|        avg_cls = "up" if m_avg >= 10 else ("warn" if m_avg >= 5 else "down")
    80|    80|        
    81|    81|        return f'''
    82|    82|        <div class="day-card">
    83|    83|            <div class="day-header" style="text-align:center">
    84|    84|                <div class="day-title" style="justify-content:center">
    85|    85|                    <span class="day-date">📅 {label}</span>
    86|    86|                    <span class="day-badge {avg_cls}">平均最高 <strong>{m_avg:+.1f}%</strong></span>
    87|    87|                    <span class="day-badge blue">达标率 <strong>{hit_pct}%</strong></span>
    88|    88|                </div>
    89|    89|                <div class="hit-bar"><div class="hit-fill" style="width:{hit_pct}%"></div></div>
    90|    90|            </div>
    91|    91|            <div class="scroll-wrap">
    92|    92|                <table>
    93|    93|                    <thead><tr>
    94|    94|                        <th style="width:48px">日期</th><th>冠军</th><th>⭐评分</th><th>当天%</th><th>↗期间最高</th>
    95|    95|                    </tr></thead>
    96|    96|                    <tbody>{rows}</tbody>
    97|    97|                </table>
    98|    98|            </div>
    99|    99|        </div>'''
   100|   100|    
   101|   101|    html = f'''<!DOCTYPE html>
   102|   102|<html lang="zh-CN">
   103|   103|<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
   104|   104|<style>
   105|   105|*{{margin:0;padding:0;box-sizing:border-box}}
   106|   106|body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#0d1117;color:#e6edf3;padding:10px}}
   107|   107|.container{{max-width:100%;margin:0 auto;overflow-x:hidden}}
   108|   108|.scroll-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -4px;padding:0 4px}}
   109|   109|.scroll-wrap::-webkit-scrollbar{{height:6px}}
   110|   110|.scroll-wrap::-webkit-scrollbar-thumb{{background:#30363d;border-radius:3px}}
   111|   111|.header{{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);border-radius:12px;padding:16px 20px;margin-bottom:12px;border:1px solid #30363d;text-align:center}}
   112|   112|.header h1{{font-size:20px;color:#58a6ff}}
   113|   113|.header .sub{{font-size:11px;color:#8b949e;margin-top:2px}}
   114|   114|.stats{{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;justify-content:center}}
   115|   115|.stat-box{{flex:1;min-width:80px;max-width:160px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center}}
   116|   116|.stat-box .num{{font-size:22px;font-weight:700}}
   117|   117|.stat-box .lbl{{font-size:9px;color:#8b949e;margin-top:2px}}
   118|   118|.stat-box.green .num{{color:#f85149}} .stat-box.blue .num{{color:#58a6ff}} .stat-box.orange .num{{color:#d29922}}
   119|   119|.day-card{{background:#161b22;border:1px solid #30363d;border-radius:10px;margin-bottom:12px;overflow:hidden}}
   120|   120|.day-header{{background:#1c2128;padding:10px 12px;border-bottom:1px solid #30363d}}
   121|   121|.day-title{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
   122|   122|.day-date{{font-size:15px;font-weight:700;color:#e6edf3}}
   123|   123|.day-badge{{font-size:10px;padding:2px 6px;border-radius:10px;background:#21262d;color:#8b949e;white-space:nowrap}}
   124|   124|.day-badge.up{{background:#f8514922;color:#f85149;border:1px solid #f8514944}}
   125|   125|.day-badge.warn{{background:#d2992222;color:#d29922;border:1px solid #d2992244}}
   126|   126|.day-badge.blue{{background:#58a6ff22;color:#58a6ff;border:1px solid #58a6ff44}}
   127|   127|.hit-bar{{margin:6px 12px 0;height:3px;background:#21262d;border-radius:2px;overflow:hidden}}
   128|   128|.hit-fill{{height:100%;background:linear-gradient(90deg,#f85149,#58a6ff);border-radius:2px}}
   129|   129|table{{width:100%;border-collapse:collapse;font-size:11px;min-width:500px}}
   130|   130|th{{background:#161b22;padding:6px 3px;text-align:center;font-weight:500;color:#8b949e;font-size:9px;letter-spacing:0.2px;border-bottom:1px solid #30363d;white-space:nowrap}}
   131|   131|td{{padding:6px 3px;text-align:center;border-bottom:1px solid #21262d;white-space:nowrap}}
   132|   132|tr:last-child td{{border-bottom:none}}
   133|   133|tr:hover td{{background:#1c212844}}
   134|   134|.rank{{text-align:center;width:48px;font-size:11px;color:#8b949e}}
   135|   135|.num{{font-family:"JetBrains Mono","Consolas","Courier New",monospace;text-align:center}}
   136|   136|.stars{{font-size:8px;margin-left:2px}}
   137|   137|.up{{color:#f85149}} .down{{color:#3fb950}} .warn{{color:#d29922}}
   138|   138|.score-high{{color:#58a6ff;font-weight:700}} .score-mid{{color:#d29922}}
   139|   139|.code{{color:#8b949e;font-size:9px;margin-left:2px}}
   140|   140|.footer{{text-align:center;color:#484f58;font-size:9px;padding:12px 0}}
   141|   141|@media screen and (max-width:480px){{
   142|   142|  body{{padding:6px}}
   143|   143|  .header h1{{font-size:17px}}
   144|   144|  table{{font-size:10px;min-width:450px}}
   145|   145|  td,th{{padding:4px 2px}}
   146|   146|  .stat-box .num{{font-size:18px}}
   147|   147|  .day-date{{font-size:13px}}
   148|   148|}}
   149|   149|</style></head><body>
   150|   150|<div class="container">
   151|   151|    <div class="header">
   152|   152|        <h1>🐉 CG-01 评分冠军 <span style="font-size:14px;color:#8b949e">大盘MA20+MA5>MA10</span></h1>
   153|   153|        <div class="sub">评分最高第1名 · {now.strftime("%Y-%m-%d %H:%M")} 推送 · 2026年4月~5月</div>
   154|   154|    </div>
   155|   155|    <div class="stats">
   156|   156|        <div class="stat-box green"><div class="num">{ov_avg:+.1f}%</div><div class="lbl">冠军平均最高</div></div>
   157|   157|        <div class="stat-box blue"><div class="num">{ov_hit_pct}%</div><div class="lbl">达标10%+</div></div>
   158|   158|        <div class="stat-box orange"><div class="num">{total_days}天</div><div class="lbl">选股天数</div></div>
   159|   159|    </div>
   160|   160|    {month_section('04', '4月')}
   161|   161|    {month_section('05', '5月')}
   162|   162|    <div class="footer">CG-01 v1 · 大盘MA20+MA5>MA10 · 数据:腾讯财经+新浪财经</div>
   163|   163|</div></body></html>'''
   164|   164|    return html, ov_avg, ov_hit_pct
   165|   165|
   166|   166|def main():
   167|   167|    print("🐉 CG-01 评分冠军邮件生成...")
   168|   168|    champions = load_champions()
   169|   169|    print(f"  📊 加载冠军数据: {len(champions)}天")
   170|   170|    html, avg, hit = build_html(champions)
   171|   171|    print(f"  📧 平均最高{avg:+.1f}% 达标率{hit}%")
   172|   172|    send_email(RECIPIENTS, f"[CG-01 评分冠军] 4月~5月 均{avg:+.1f}% 达标率{hit}%", html, html=True)
   173|   173|    print("✅ 完成!")
   174|   174|
   175|   175|if __name__ == "__main__":
   176|   176|    main()
   177|   177|