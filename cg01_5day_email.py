     1|     1|#!/usr/bin/env python3
     2|     2|"""CG-01 近5日Top5选股合并邮件 — 含D+1~D+5每日分解"""
     3|     3|import json, os, sys, time
     4|     4|from datetime import datetime
     5|     5|sys.path.insert(0, os.path.dirname(__file__))
     6|     6|from send_email import send_email
     7|     7|
     8|     8|RECIPIENTS = ["1254628314@qq.com"]
     9|     9|TOP5_CACHE = os.path.join(os.path.dirname(__file__), '..', 'hermes-agent', 'top5_cache_CG-01_mar-may.txt')
    10|    10|CHAMP_CACHE = os.path.join(os.path.dirname(__file__), '..', 'hermes-agent', 'champion_cache_CG-01_mar-may.txt')
    11|    11|
    12|    12|def star_rating(s):
    13|    13|    if s >= 85: return "⭐⭐⭐⭐⭐"
    14|    14|    elif s >= 75: return "⭐⭐⭐⭐"
    15|    15|    elif s >= 65: return "⭐⭐⭐"
    16|    16|    elif s >= 55: return "⭐⭐"
    17|    17|    return "⭐"
    18|    18|
    19|    19|def build_html(all_dates_data, ov_avg, hit5_rate, hit10_rate, total_picks):
    20|    20|    now = datetime.now()
    21|    21|    all_cards = ""
    22|    22|
    23|    23|    for date_str in sorted(all_dates_data.keys(), reverse=True):
    24|    24|        data = all_dates_data[date_str]
    25|    25|        t5 = data['top5']
    26|    26|        champ = data['champion']
    27|    27|        
    28|    28|        # Top5表格
    29|    29|        t5_rows = ""
    30|    30|        for i, r in enumerate(t5):
    31|    31|            rank_icon = "🥇" if i==0 else ("🥈" if i==1 else ("🥉" if i==2 else f"{i+1}"))
    32|    32|            is_best = "最优选" if i==0 else ""
    33|    33|            sc = "score-high" if r['score'] >= 85 else ("score-mid" if r['score'] >= 70 else "")
    34|    34|            stars = star_rating(r['score'])
    35|    35|            pc = "up" if r['pct'] > 0 else "down"
    36|    36|            m5 = r.get('max5')
    37|    37|            if m5 is not None:
    38|    38|                m5s = f"{m5:+.1f}%"
    39|    39|                m5c = "up" if m5 >= 10 else ("warn" if m5 >= 5 else "down")
    40|    40|            else:
    41|    41|                m5s = "—"
    42|    42|                m5c = ""
    43|    43|            t5_rows += f'<tr>'
    44|    44|            t5_rows += f'<td class="rank">{rank_icon}</td>'
    45|    45|            t5_rows += f'<td><strong>{r["name"]}</strong><span class="code">{r["code"]}</span></td>'
    46|    46|            t5_rows += f'<td class="num {sc}">{r["score"]}<span class="stars">{stars}</span></td>'
    47|    47|            t5_rows += f'<td class="num">{r["price"]:.2f}</td>'
    48|    48|            t5_rows += f'<td class="num {pc}">{r["pct"]:+.2f}%</td>'
    49|    49|            t5_rows += f'<td class="num {m5c}"><strong>{m5s}</strong></td>'
    50|    50|            t5_rows += f'<td style="text-align:center;color:#d29922;font-size:10px">{is_best}</td>'
    51|    51|            t5_rows += f'</tr>'
    52|    52|
    53|    53|        # 冠军D+1~D+5逐日分解
    54|    54|        daily = champ.get('daily', [])
    55|    55|        d_labels = []
    56|    56|        d_cols = ""
    57|    57|        d_icons = ""
    58|    58|        if daily:
    59|    59|            for di, dd in enumerate(daily):
    60|    60|                dl = dd.get('date', '')[5:] or f"D+{di+1}"
    61|    61|                d_labels.append(dl)
    62|    62|                v = dd['high']
    63|    63|                arr = dd.get('arrow', '')
    64|    64|                vc = "up" if v >= 5 else ("warn" if v >= 2 else "down")
    65|    65|                # 图标（同qinlong模板规则）
    66|    66|                prev_best = max(d["high"] for d in daily[:di]) if di > 0 else v
    67|    67|                if v < -3: icon = "💀"
    68|    68|                elif di == 0: icon = "🚀"
    69|    69|                elif v >= prev_best - 1.5: icon = "🚀"
    70|    70|                elif v <= prev_best - 3: icon = "💀"
    71|    71|                elif v < daily[di-1]["high"]: icon = "🏃"
    72|    72|                else: icon = "🔥"
    73|    73|                d_cols += f'<td class="num {vc}">{v:+.1f}%{arr}</td>'
    74|    74|                d_icons += f'<td class="num" style="font-size:14px">{icon}</td>'
    75|    75|
    76|    76|        d_headers = "".join(f'<th>{dl}</th>' for dl in d_labels)
    77|    77|
    78|    78|        # 达标统计（本日Top5）
    79|    79|        vals = [s.get('max5') for s in t5 if s.get('max5') is not None]
    80|    80|        day_hit5 = sum(1 for v in vals if v >= 5)
    81|    81|        day_hit10 = sum(1 for v in vals if v >= 10)
    82|    82|        day_avg = sum(vals)/len(vals) if vals else 0
    83|    83|        avg_cls = "up" if day_avg >= 10 else ("warn" if day_avg >= 5 else "down")
    84|    84|
    85|    85|        all_cards += f'''
    86|    86|        <div class="day-card">
    87|    87|            <div class="day-header" style="text-align:center">
    88|    88|                <div class="day-title" style="justify-content:center">
    89|    89|                    <span class="day-date">📅 {date_str}</span>
    90|    90|                    <span class="day-badge {avg_cls}">Top5均 <strong>{day_avg:+.1f}%</strong></span>
    91|    91|                    <span class="day-badge blue">达标5%+ <strong>{day_hit5}/{len(vals)}</strong></span>
    92|    92|                    <span class="day-badge up">达标10%+ <strong>{day_hit10}/{len(vals)}</strong></span>
    93|    93|                </div>
    94|    94|                <div class="hit-bar"><div class="hit-fill" style="width:{day_hit5*100//len(vals) if vals else 0}%"></div></div>
    95|    95|            </div>
    96|    96|            <div style="padding:0">
    97|    97|                <!-- 最优选冠军详情 -->'''
    98|    98|
    99|    99|        if champ.get('name'):
   100|   100|            c_name = champ['name']
   101|   101|            c_code = champ.get('code', '')
   102|   102|            c_score = champ.get('qscore', 0)
   103|   103|            c_price = champ.get('kl_close', 0)
   104|   104|            c_max5 = champ.get('max5', '—')
   105|   105|            c_max5s = f"{c_max5:+.1f}%" if isinstance(c_max5, (int,float)) else "—"
   106|   106|
   107|   107|            all_cards += f'''
   108|   108|                <div class="champ-section">
   109|   109|                    <div class="champ-label">🏆 最优选：{c_name} {c_code} | 评分{c_score} | 买入价{c_price:.2f} | 5日最高{c_max5s}</div>
   110|   110|                    <div class="scroll-wrap">
   111|   111|                        <table>
   112|   112|                            <thead><tr><th style="width:36px">#</th><th>D+1</th><th>D+2</th><th>D+3</th><th>D+4</th><th>D+5</th></tr></thead>
   113|   113|                            <tbody><tr><td class="rank">最高</td>{d_cols}</tr><tr><td class="rank">信号</td>{d_icons}</tr></tbody>
   114|   114|                        </table>
   115|   115|                    </div>
   116|   116|                </div>'''
   117|   117|
   118|   118|        all_cards += f'''
   119|   119|                <details open>
   120|   120|                    <summary style="padding:8px 16px;font-size:12px;color:#8b949e;text-align:left;border-bottom:1px solid #21262d;cursor:pointer">📊 Top5 榜单</summary>
   121|   121|                    <div class="scroll-wrap">
   122|   122|                        <table>
   123|   123|                            <thead><tr><th style="width:28px">#</th><th>名称</th><th>⭐评分</th><th>买入价</th><th>当天%</th><th>↗5日最高</th><th>备注</th></tr></thead>
   124|   124|                            <tbody>{t5_rows}</tbody>
   125|   125|                        </table>
   126|   126|                    </div>
   127|   127|                </details>
   128|   128|            </div>
   129|   129|        </div>'''
   130|   130|
   131|   131|    html = f'''<!DOCTYPE html>
   132|   132|<html lang="zh-CN">
   133|   133|<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
   134|   134|<style>
   135|   135|*{{margin:0;padding:0;box-sizing:border-box}}
   136|   136|body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#0d1117;color:#e6edf3;padding:10px}}
   137|   137|.container{{max-width:620px;margin:0 auto;overflow-x:hidden}}
   138|   138|.scroll-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -4px;padding:0 4px}}
   139|   139|.scroll-wrap::-webkit-scrollbar{{height:6px}}
   140|   140|.scroll-wrap::-webkit-scrollbar-thumb{{background:#30363d;border-radius:3px}}
   141|   141|.header{{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);border-radius:12px;padding:16px 20px;margin-bottom:12px;border:1px solid #30363d;text-align:center}}
   142|   142|.header h1{{font-size:18px;color:#58a6ff}}
   143|   143|.header .sub{{font-size:10px;color:#8b949e;margin-top:2px}}
   144|   144|.stats{{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;justify-content:center}}
   145|   145|.stat-box{{flex:1;min-width:80px;max-width:140px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;text-align:center}}
   146|   146|.stat-box .num{{font-size:20px;font-weight:700}}
   147|   147|.stat-box .lbl{{font-size:9px;color:#8b949e;margin-top:2px}}
   148|   148|.stat-box.green .num{{color:#f85149}} .stat-box.blue .num{{color:#58a6ff}} .stat-box.orange .num{{color:#d29922}} .stat-box.purple .num{{color:#a371f7}}
   149|   149|.day-card{{background:#161b22;border:1px solid #30363d;border-radius:10px;margin-bottom:12px;overflow:hidden}}
   150|   150|.day-header{{background:#1c2128;padding:10px 12px;border-bottom:1px solid #30363d}}
   151|   151|.day-title{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
   152|   152|.day-date{{font-size:15px;font-weight:700;color:#e6edf3}}
   153|   153|.day-badge{{font-size:10px;padding:2px 6px;border-radius:10px;background:#21262d;color:#8b949e;white-space:nowrap}}
   154|   154|.day-badge.up{{background:#f8514922;color:#f85149;border:1px solid #f8514944}}
   155|   155|.day-badge.warn{{background:#d2992222;color:#d29922;border:1px solid #d2992244}}
   156|   156|.day-badge.blue{{background:#58a6ff22;color:#58a6ff;border:1px solid #58a6ff44}}
   157|   157|.hit-bar{{margin:6px 12px 0;height:3px;background:#21262d;border-radius:2px;overflow:hidden}}
   158|   158|.hit-fill{{height:100%;background:linear-gradient(90deg,#f85149,#58a6ff);border-radius:2px}}
   159|   159|.champ-section{{background:#1a1a2e;margin:4px;border:1px solid #d2992244;border-radius:8px;padding:8px 12px}}
   160|   160|.champ-label{{font-size:11px;color:#d29922;font-weight:600;margin-bottom:6px;padding:4px 0}}
   161|   161|details summary{{list-style:none;user-select:none;font-size:11px}}
   162|   162|details summary::-webkit-details-marker{{display:none}}
   163|   163|details summary:hover{{background:#1c212866}}
   164|   164|table{{width:100%;border-collapse:collapse;font-size:11px;min-width:520px}}
   165|   165|th{{background:#161b22;padding:5px 3px;text-align:center;font-weight:500;color:#8b949e;font-size:8px;letter-spacing:0.2px;border-bottom:1px solid #30363d;white-space:nowrap}}
   166|   166|td{{padding:5px 3px;text-align:center;border-bottom:1px solid #21262d;white-space:nowrap}}
   167|   167|tr:last-child td{{border-bottom:none}}
   168|   168|tr:hover td{{background:#1c212844}}
   169|   169|.rank{{text-align:center;width:36px;font-size:12px}}
   170|   170|.num{{font-family:"JetBrains Mono","Consolas","Courier New",monospace;text-align:center}}
   171|   171|.stars{{font-size:7px;margin-left:2px}}
   172|   172|.up{{color:#f85149}} .down{{color:#3fb950}} .warn{{color:#d29922}}
   173|   173|.score-high{{color:#58a6ff;font-weight:700}} .score-mid{{color:#d29922}}
   174|   174|.code{{color:#8b949e;font-size:9px;margin-left:2px}}
   175|   175|.footer{{text-align:center;color:#484f58;font-size:8px;padding:10px 0}}
   176|   176|@media screen and (max-width:480px){{
   177|   177|  body{{padding:6px}}
   178|   178|  .header h1{{font-size:16px}}
   179|   179|  table{{font-size:10px;min-width:450px}}
   180|   180|  td,th{{padding:4px 2px}}
   181|   181|  .stat-box .num{{font-size:17px}}
   182|   182|  .day-date{{font-size:13px}}
   183|   183|}}
   184|   184|</style></head><body>
   185|   185|<div class="container">
   186|   186|    <div class="header">
   187|   187|        <h1>🐉 尾盘选股 <span style="font-size:14px;color:#8b949e">{now.strftime("%Y-%m-%d %H:%M")}</span></h1>
   188|   188|        <div class="sub">CG-01 · 近5日Top5回顾 · 达标5%+<strong>{hit5_rate}%</strong></div>
   189|   189|    </div>
   190|   190|    <div class="stats">
   191|   191|        <div class="stat-box green"><div class="num">{ov_avg:+.1f}%</div><div class="lbl">平均最高</div></div>
   192|   192|        <div class="stat-box blue"><div class="num">{hit5_rate}%</div><div class="lbl">达标5%+</div></div>
   193|   193|        <div class="stat-box orange"><div class="num">{hit10_rate}%</div><div class="lbl">达标10%+</div></div>
   194|   194|        <div class="stat-box purple"><div class="num">{total_picks}只</div><div class="lbl">总选股</div></div>
   195|   195|    </div>
   196|   196|    {all_cards}
   197|   197|    <div class="footer">尾盘选股指标 · CG-01 · 数据:腾讯财经+新浪财经</div>
   198|   198|</div></body></html>'''
   199|   199|    return html
   200|   200|
   201|   201|def main():
   202|   202|    # 读取缓存
   203|   203|    with open(TOP5_CACHE) as f:
   204|   204|        top5_all = json.load(f)
   205|   205|    with open(CHAMP_CACHE) as f:
   206|   206|        champ_all = json.load(f)
   207|   207|    
   208|   208|    # 找到最近5个有选股的交易日
   209|   209|    dates_with_picks = sorted([d for d in top5_all.keys()], reverse=True)
   210|   210|    last5 = dates_with_picks[:5]
   211|   211|    
   212|   212|    print(f"🐉 近5日选股回顾 — {last5[0]} ~ {last5[-1]}")
   213|   213|    
   214|   214|    # 构建数据
   215|   215|    all_data = {}
   216|   216|    total_vals = []
   217|   217|    total_hit5 = 0
   218|   218|    total_hit10 = 0
   219|   219|    
   220|   220|    for dt in last5:
   221|   221|        t5 = top5_all[dt]
   222|   222|        champ = champ_all.get(dt, {})
   223|   223|        all_data[dt] = {'top5': t5, 'champion': champ}
   224|   224|        vals = [s.get('max5') for s in t5 if s.get('max5') is not None]
   225|   225|        total_vals.extend(vals)
   226|   226|        total_hit5 += sum(1 for v in vals if v >= 5)
   227|   227|        total_hit10 += sum(1 for v in vals if v >= 10)
   228|   228|    
   229|   229|    ov_avg = sum(total_vals)/len(total_vals) if total_vals else 0
   230|   230|    hit5_rate = total_hit5*100//len(total_vals) if total_vals else 0
   231|   231|    hit10_rate = total_hit10*100//len(total_vals) if total_vals else 0
   232|   232|    
   233|   233|    html = build_html(all_data, ov_avg, hit5_rate, hit10_rate, len(total_vals))
   234|   234|    
   235|   235|    print(f"  📊 {len(last5)}天, 共{len(total_vals)}只, 均{ov_avg:+.1f}%, 达标5%+:{hit5_rate}% 达标10%+:{hit10_rate}%")
   236|   236|    print(f"  📧 发送中...", end=" ", flush=True)
   237|   237|    now = datetime.now()
   238|   238|    today_str = now.strftime("%Y-%m-%d")
   239|   239|    send_email(RECIPIENTS, f"尾盘选股 {today_str}", html, html=True)
   240|   240|    print("✅")
   241|   241|    print(f"✅ 完成! 1封合并邮件已发送")
   242|   242|
   243|   243|if __name__ == "__main__":
   244|   244|    main()
   245|   245|