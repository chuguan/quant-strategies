     1|     1|#!/usr/bin/env python3
     2|     2|"""CG-01 尾盘选股优选 — 全期冠军表 + 近5日Top5"""
     3|     3|import json, os, sys
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
    19|    19|def build_html(champ_all, top5_all, last5_dates, ov_avg, hit5_rate, hit10_rate, total_picks):
    20|    20|    now = datetime.now()
    21|    21|    today_str = now.strftime("%Y-%m-%d")
    22|    22|    time_str = now.strftime("%H:%M")
    23|    23|
    24|    24|    # ═══ 1. 全期冠军大表 ═══
    25|    25|    champ_rows = ""
    26|    26|    champ_max_list = []
    27|    27|    champ_hit5 = 0
    28|    28|    champ_hit10 = 0
    29|    29|    champ_total = 0
    30|    30|    champ_sorted = sorted(champ_all.keys(), reverse=True)  # 最新在前
    31|    31|    for dt in champ_sorted:
    32|    32|        c = champ_all[dt]
    33|    33|        if c is None: continue
    34|    34|        m5 = c.get('max5')
    35|    35|        m5_val = m5 if isinstance(m5, (int,float)) else None
    36|    36|        if m5_val is not None:
    37|    37|            champ_max_list.append(m5_val)
    38|    38|            champ_total += 1
    39|    39|            if m5_val >= 5: champ_hit5 += 1
    40|    40|            if m5_val >= 10: champ_hit10 += 1
    41|    41|        pc = "up" if c.get('pct_d', 0) > 0 else "down"
    42|    42|        
    43|    43|        # D+1~D+5 每日数据（最高 + 收盘）
    44|    44|        daily = c.get('daily', [])
    45|    45|        day_cells = ""
    46|    46|        best_5d = None
    47|    47|        for di in range(5):
    48|    48|            if di < len(daily):
    49|    49|                dh = daily[di].get('high')
    50|    50|                dc = daily[di].get('close')
    51|    51|                if best_5d is None or (dh is not None and dh > best_5d):
    52|    52|                    best_5d = dh
    53|    53|                h_cls = "up" if dh is not None and dh >= 0 else ("down" if dh is not None and dh < 0 else "")
    54|    54|                c_cls = "up" if dc is not None and dc >= 0 else ("down" if dc is not None and dc < 0 else "")
    55|    55|                h_str = f"{dh:+.1f}%" if dh is not None else "—"
    56|    56|                c_str = f"{dc:+.1f}%" if dc is not None else "—"
    57|    57|                day_cells += f'<td class="num">{h_str}<br><span class="cp">{c_str}</span></td>'
    58|    58|            else:
    59|    59|                day_cells += '<td class="num na">—</td>'
    60|    60|        
    61|    61|        # 5日最高盈利
    62|    62|        if best_5d is not None:
    63|    63|            b5c = "up" if best_5d >= 5 else "warn" if best_5d >= 2 else "down"
    64|    64|            best_5d_str = f'{best_5d:+.1f}%'
    65|    65|        else:
    66|    66|            b5c = ""
    67|    67|            best_5d_str = "—"
    68|    68|        
    69|    69|        # 大盘涨跌
    70|    70|        idx_pct = c.get('index_pct')
    71|    71|        if idx_pct is not None:
    72|    72|            idx_cls = "up" if idx_pct >= 0 else "down"
    73|    73|            idx_str = f"{idx_pct:+.2f}%"
    74|    74|        else:
    75|    75|            idx_cls = ""
    76|    76|            idx_str = "—"
    77|    77|        
    78|    78|        champ_rows += f'<tr>' \
    79|    79|            f'<td>{dt}</td>' \
    80|    80|            f'<td><strong>{c["name"]}</strong><span class="code">{c["code"]}</span></td>' \
    81|    81|            f'<td class="num" style="color:#58a6ff;font-weight:700">{c["qscore"]}</td>' \
    82|    82|            f'<td class="num">{c.get("kl_close",0):.2f}</td>' \
    83|    83|            f'<td class="num {pc}">{c.get("pct_d",0):+.2f}%</td>' \
    84|    84|            f'{day_cells}' \
    85|    85|            f'<td class="num {b5c}"><strong>{best_5d_str}</strong></td>' \
    86|    86|            f'<td class="num {idx_cls}">{idx_str}</td></tr>'
    87|    87|
    88|    88|    champ_avg = sum(champ_max_list)/len(champ_max_list) if champ_max_list else 0
    89|    89|    champ_hit_pct = champ_hit5*100//champ_total if champ_total else 0
    90|    90|
    91|    91|    # ═══ 2. 近5日Top5卡片 ═══
    92|    92|    all_cards = ""
    93|    93|    for date_str in last5_dates:
    94|    94|        t5 = top5_all.get(date_str, [])
    95|    95|        champ = champ_all.get(date_str, {})
    96|    96|        if not t5: continue
    97|    97|
    98|    98|        t5_rows = ""
    99|    99|        for i, r in enumerate(t5):
   100|   100|            rank_icon = "🥇" if i==0 else ("🥈" if i==1 else ("🥉" if i==2 else f"{i+1}"))
   101|   101|            is_best = "最优选" if i==0 else ""
   102|   102|            sc = "score-high" if r['score'] >= 85 else ("score-mid" if r['score'] >= 70 else "")
   103|   103|            stars = star_rating(r['score'])
   104|   104|            pc = "up" if r['pct'] > 0 else "down"
   105|   105|            m5 = r.get('max5')
   106|   106|            if m5 is not None:
   107|   107|                m5s = f"{m5:+.1f}%"
   108|   108|                m5c = "up" if m5 >= 5 else "down"
   109|   109|            else:
   110|   110|                m5s = "—"
   111|   111|                m5c = ""
   112|   112|            t5_rows += f'<tr><td class="rank">{rank_icon}</td>' \
   113|   113|                f'<td><strong>{r["name"]}</strong><span class="code">{r["code"]}</span></td>' \
   114|   114|                f'<td class="num {sc}">{r["score"]}<span class="stars">{stars}</span></td>' \
   115|   115|                f'<td class="num">{r["price"]:.2f}</td>' \
   116|   116|                f'<td class="num {pc}">{r["pct"]:+.2f}%</td>' \
   117|   117|                f'<td class="num {m5c}"><strong>{m5s}</strong></td>' \
   118|   118|                f'<td style="text-align:center;color:#d29922;font-size:10px">{is_best}</td></tr>'
   119|   119|
   120|   120|        # 冠军 D+1~D+5
   121|   121|        daily = champ.get('daily', [])
   122|   122|        d_cols = ""
   123|   123|        d_icons = ""
   124|   124|        if daily:
   125|   125|            for di, dd in enumerate(daily):
   126|   126|                v = dd['high']
   127|   127|                arr = dd.get('arrow', '')
   128|   128|                vc = "up" if v >= 5 else ("warn" if v >= 2 else "down")
   129|   129|                prev_best = max(d["high"] for d in daily[:di]) if di > 0 else v
   130|   130|                if v < -3: icon = "💀"
   131|   131|                elif di == 0: icon = "🚀"
   132|   132|                elif v >= prev_best - 1.5: icon = "🚀"
   133|   133|                elif v <= prev_best - 3: icon = "💀"
   134|   134|                elif v < daily[di-1]["high"]: icon = "🏃"
   135|   135|                else: icon = "🔥"
   136|   136|                d_cols += f'<td class="num {vc}">{v:+.1f}%{arr}</td>'
   137|   137|                d_icons += f'<td class="num" style="font-size:14px">{icon}</td>'
   138|   138|
   139|   139|        vals = [s.get('max5') for s in t5 if s.get('max5') is not None]
   140|   140|        day_hit5 = sum(1 for v in vals if v >= 5)
   141|   141|        day_avg = sum(vals)/len(vals) if vals else 0
   142|   142|        avg_cls = "up" if day_avg >= 5 else "warn"
   143|   143|
   144|   144|        all_cards += f'''
   145|   145|<div class="day-card">
   146|   146|    <div class="day-header" style="text-align:center">
   147|   147|        <div class="day-title" style="justify-content:center">
   148|   148|            <span class="day-date">📅 {date_str}</span>
   149|   149|            <span class="day-badge {avg_cls}">Top5均 <strong>{day_avg:+.1f}%</strong></span>
   150|   150|            <span class="day-badge blue">达标5%+ <strong>{day_hit5}/{len(vals)}</strong></span>
   151|   151|        </div>
   152|   152|        <div class="hit-bar"><div class="hit-fill" style="width:{day_hit5*100//len(vals) if vals else 0}%"></div></div>
   153|   153|    </div>
   154|   154|    <div style="padding:0">'''
   155|   155|
   156|   156|        if champ.get('name'):
   157|   157|            c_name = champ['name']
   158|   158|            c_code = champ.get('code', '')
   159|   159|            c_score = champ.get('qscore', 0)
   160|   160|            c_price = champ.get('kl_close', 0)
   161|   161|            c_max5 = champ.get('max5', '—')
   162|   162|            c_max5s = f"{c_max5:+.1f}%" if isinstance(c_max5, (int,float)) else "—"
   163|   163|            all_cards += f'''
   164|   164|        <div class="champ-section">
   165|   165|            <div class="champ-label">🏆 最优选：{c_name} {c_code} | 评分{c_score} | 买入价{c_price:.2f} | 5日最高{c_max5s}</div>
   166|   166|            <div class="scroll-wrap">
   167|   167|                <table><thead><tr><th style="width:36px">#</th><th>D+1</th><th>D+2</th><th>D+3</th><th>D+4</th><th>D+5</th></tr></thead>
   168|   168|                <tbody><tr><td class="rank">最高</td>{d_cols}</tr><tr><td class="rank">信号</td>{d_icons}</tr></tbody></table>
   169|   169|            </div>
   170|   170|        </div>'''
   171|   171|
   172|   172|        all_cards += f'''
   173|   173|        <details open>
   174|   174|            <summary style="padding:8px 16px;font-size:12px;color:#8b949e;text-align:left;border-bottom:1px solid #21262d;cursor:pointer">📊 Top5 榜单</summary>
   175|   175|            <div class="scroll-wrap">
   176|   176|                <table><thead><tr><th style="width:28px">#</th><th>名称</th><th>⭐评分</th><th>买入价</th><th>当天%</th><th>↗5日最高</th><th>备注</th></tr></thead>
   177|   177|                <tbody>{t5_rows}</tbody></table>
   178|   178|            </div>
   179|   179|        </details>
   180|   180|    </div>
   181|   181|</div>'''
   182|   182|
   183|   183|    html = f'''<!DOCTYPE html>
   184|   184|<html lang="zh-CN">
   185|   185|<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
   186|   186|<style>
   187|   187|*{{margin:0;padding:0;box-sizing:border-box}}
   188|   188|body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#0d1117;color:#e6edf3;padding:10px}}
   189|   189|.container{{max-width:640px;margin:0 auto;overflow-x:hidden}}
   190|   190|.scroll-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -4px;padding:0 4px}}
   191|   191|.scroll-wrap::-webkit-scrollbar{{height:6px}}
   192|   192|.scroll-wrap::-webkit-scrollbar-thumb{{background:#30363d;border-radius:3px}}
   193|   193|.header{{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);border-radius:12px;padding:16px 20px;margin-bottom:12px;border:1px solid #30363d;text-align:center}}
   194|   194|.header h1{{font-size:20px;color:#58a6ff}}
   195|   195|.header .sub{{font-size:10px;color:#8b949e;margin-top:2px}}
   196|   196|.stats{{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;justify-content:center}}
   197|   197|.stat-box{{flex:1;min-width:72px;max-width:120px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px 6px;text-align:center}}
   198|   198|.stat-box .num{{font-size:18px;font-weight:700}}
   199|   199|.stat-box .lbl{{font-size:8px;color:#8b949e;margin-top:1px}}
   200|   200|.stat-box.green .num{{color:#f85149}} .stat-box.blue .num{{color:#58a6ff}} .stat-box.orange .num{{color:#d29922}} .stat-box.purple .num{{color:#a371f7}}
   201|   201|.section-title{{font-size:14px;font-weight:700;color:#e6edf3;padding:8px 4px 4px 4px;margin-bottom:4px}}
   202|   202|.day-card{{background:#161b22;border:1px solid #30363d;border-radius:10px;margin-bottom:10px;overflow:hidden}}
   203|   203|.day-header{{background:#1c2128;padding:8px 12px;border-bottom:1px solid #30363d}}
   204|   204|.day-title{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
   205|   205|.day-date{{font-size:14px;font-weight:700;color:#e6edf3}}
   206|   206|.day-badge{{font-size:9px;padding:1px 5px;border-radius:8px;background:#21262d;color:#8b949e;white-space:nowrap}}
   207|   207|.day-badge.up{{background:#f8514922;color:#f85149;border:1px solid #f8514944}}
   208|   208|.day-badge.warn{{background:#d2992222;color:#d29922;border:1px solid #d2992244}}
   209|   209|.day-badge.blue{{background:#58a6ff22;color:#58a6ff;border:1px solid #58a6ff44}}
   210|   210|.hit-bar{{margin:4px 12px 0;height:3px;background:#21262d;border-radius:2px;overflow:hidden}}
   211|   211|.hit-fill{{height:100%;background:linear-gradient(90deg,#f85149,#58a6ff);border-radius:2px}}
   212|   212|.champ-section{{background:#1a1a2e;margin:4px;border:1px solid #d2992244;border-radius:8px;padding:6px 10px}}
   213|   213|.champ-label{{font-size:10px;color:#d29922;font-weight:600;margin-bottom:4px}}
   214|   214|details summary{{list-style:none;user-select:none;font-size:11px}}
   215|   215|details summary::-webkit-details-marker{{display:none}}
   216|   216|details summary:hover{{background:#1c212866}}
   217|   217|table{{width:100%;border-collapse:collapse;font-size:10px;min-width:480px}}
   218|   218|th{{background:#161b22;padding:4px 2px;text-align:center;font-weight:500;color:#8b949e;font-size:8px;letter-spacing:0.1px;border-bottom:1px solid #30363d;white-space:nowrap}}
   219|   219|td{{padding:4px 2px;text-align:center;border-bottom:1px solid #21262d;white-space:nowrap}}
   220|   220|tr:last-child td{{border-bottom:none}}
   221|   221|tr:hover td{{background:#1c212844}}
   222|   222|.rank{{text-align:center;width:28px;font-size:11px}}
   223|   223|.num{{font-family:"Consolas","Courier New",monospace;text-align:center;line-height:1.3}}
   224|   224|.cp{{font-size:8px}}
   225|   225|.na{{color:#484f58}}
   226|   226|.stars{{font-size:7px;margin-left:2px}}
   227|   227|.up{{color:#f85149}} .down{{color:#3fb950}} .warn{{color:#d29922}}
   228|   228|.score-high{{color:#58a6ff;font-weight:700}} .score-mid{{color:#d29922}}
   229|   229|.code{{color:#8b949e;font-size:8px;margin-left:2px}}
   230|   230|.footer{{text-align:center;color:#484f58;font-size:8px;padding:8px 0}}
   231|   231|@media screen and (max-width:480px){{
   232|   232|  body{{padding:6px}}
   233|   233|  .header h1{{font-size:17px}}
   234|   234|  table{{font-size:9px;min-width:400px}}
   235|   235|  td,th{{padding:3px 1px}}
   236|   236|  .stat-box .num{{font-size:16px}}
   237|   237|  .day-date{{font-size:12px}}
   238|   238|}}
   239|   239|</style></head><body>
   240|   240|<div class="container">
   241|   241|    <div class="header">
   242|   242|        <h1>🐉 尾盘选股优选 <span style="font-size:13px;color:#8b949e">{today_str} {time_str}</span></h1>
   243|   243|        <div class="sub">CG-01 · 全期冠军 · 达标5%+<strong>{champ_hit_pct}%</strong> · 近5日达标<strong>{hit5_rate}%</strong></div>
   244|   244|    </div>
   245|   245|    <div class="stats">
   246|   246|        <div class="stat-box green"><div class="num">{champ_avg:+.1f}%</div><div class="lbl">冠军均最高</div></div>
   247|   247|        <div class="stat-box blue"><div class="num">{champ_hit_pct}%</div><div class="lbl">冠军达标5%+</div></div>
   248|   248|        <div class="stat-box orange"><div class="num">{champ_total}天</div><div class="lbl">总选股</div></div>
   249|   249|        <div class="stat-box purple"><div class="num">{total_picks}只</div><div class="lbl">近5日选股</div></div>
   250|   250|    </div>
   251|   251|
   252|   252|    <div class="section-title">📋 全期冠军表（近3月 · 最新在前）</div>
   253|   253|    <div class="day-card">
   254|   254|        <div class="scroll-wrap">
   255|   255|            <table style="min-width:600px">
   256|   256|                <thead><tr><th>日期</th><th>最优选</th><th>评分</th><th>买入价</th><th>当天%</th><th>D+1</th><th>D+2</th><th>D+3</th><th>D+4</th><th>D+5</th><th>5日最高<br>盈利</th><th>大盘<br>涨跌</th></tr></thead>
   257|   257|                <tbody>{champ_rows}</tbody>
   258|   258|            </table>
   259|   259|        </div>
   260|   260|    </div>
   261|   261|
   262|   262|    <div class="section-title">📊 近5日Top5明细</div>
   263|   263|    {all_cards}
   264|   264|    <div class="footer">尾盘选股优选 · CG-01 · 达标线≥5% · 数据:腾讯财经+新浪财经</div>
   265|   265|</div></body></html>'''
   266|   266|    return html
   267|   267|
   268|   268|def main():
   269|   269|    with open(TOP5_CACHE) as f:
   270|   270|        top5_all = json.load(f)
   271|   271|    with open(CHAMP_CACHE) as f:
   272|   272|        champ_all = json.load(f)
   273|   273|
   274|   274|    # 近5个有选股的交易日
   275|   275|    dates_with_picks = sorted([d for d in top5_all.keys()], reverse=True)
   276|   276|    last5 = dates_with_picks[:5]
   277|   277|
   278|   278|    print(f"🐉 尾盘选股优选 — 全期{len(dates_with_picks)}天 + 近5日回顾 {last5[0]} ~ {last5[-1]}")
   279|   279|
   280|   280|    # 全期统计
   281|   281|    now = datetime.now()
   282|   282|    today_str = now.strftime("%Y-%m-%d")
   283|   283|
   284|   284|    # 近5日统计
   285|   285|    total_vals = []
   286|   286|    total_hit5 = 0
   287|   287|    for dt in last5:
   288|   288|        t5 = top5_all.get(dt, [])
   289|   289|        vals = [s.get('max5') for s in t5 if s.get('max5') is not None]
   290|   290|        total_vals.extend(vals)
   291|   291|        total_hit5 += sum(1 for v in vals if v >= 5)
   292|   292|    ov_avg = sum(total_vals)/len(total_vals) if total_vals else 0
   293|   293|    hit5_rate = total_hit5*100//len(total_vals) if total_vals else 0
   294|   294|    hit10_rate = sum(1 for v in total_vals if v >= 10)*100//len(total_vals) if total_vals else 0
   295|   295|
   296|   296|    html = build_html(champ_all, top5_all, last5, ov_avg, hit5_rate, hit10_rate, len(total_vals))
   297|   297|
   298|   298|    print(f"  📊 全期{len(dates_with_picks)}天冠军, 近5日{len(total_vals)}只, 均{ov_avg:+.1f}%, 达标5%+:{hit5_rate}%")
   299|   299|    print(f"  📧 发送中...", end=" ", flush=True)
   300|   300|    send_email(RECIPIENTS, f"尾盘选股优选 {today_str}", html, html=True)
   301|   301|    print("✅ 完成!")
   302|   302|
   303|   303|if __name__ == "__main__":
   304|   304|    main()
   305|   305|