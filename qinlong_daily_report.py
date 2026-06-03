     1|#!/usr/bin/env python3
     2|"""
     3|擒龙MAX 收盘回测推送脚本
     4|每天收盘后，回测最近一个交易日的结果，推送带D+1~D+5明细的HTML邮件
     5|"""
     6|import json, os, sys, time
     7|from datetime import datetime, timedelta
     8|
     9|sys.path.insert(0, os.path.dirname(__file__))
    10|from send_email import send_email
    11|sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'hermes-agent'))
    12|from qinlong_max import run_qinlong_max, analyze, fetch_kline, batch_query
    13|
    14|# ===== 配置 =====
    15|RECIPIENTS = ["1254628314@qq.com"]
    16|CACHE_FILE = os.path.join(os.path.dirname(__file__), "qinlong_history.json")
    17|
    18|def get_last_trading_day():
    19|    """获取最近一个交易日（今天如果是交易日则今天，否则向前找）"""
    20|    today = datetime.now()
    21|    # 尝试今天、昨天、前天...
    22|    for offset in range(0, 5):
    23|        d = today - timedelta(days=offset)
    24|        # 跳过周末
    25|        if d.weekday() >= 5:  # 5=周六, 6=周日
    26|            continue
    27|        return d.strftime("%Y-%m-%d")
    28|    return today.strftime("%Y-%m-%d")
    29|
    30|def load_history():
    31|    if os.path.exists(CACHE_FILE):
    32|        with open(CACHE_FILE) as f:
    33|            return json.load(f)
    34|    return []
    35|
    36|def save_history(entry):
    37|    history = load_history()
    38|    # 避免重复
    39|    for i, e in enumerate(history):
    40|        if e['date'] == entry['date']:
    41|            history[i] = entry
    42|            break
    43|    else:
    44|        history.append(entry)
    45|    with open(CACHE_FILE, 'w') as f:
    46|        json.dump(history, f, ensure_ascii=False, indent=2)
    47|    return history
    48|
    49|def get_daily_breakdown(code, market, buy_date, buy_price):
    50|    """获取D+1~D+5每日最高涨幅和收盘方向"""
    51|    recs = fetch_kline(code, market)
    52|    if not recs: return None
    53|    bi = None
    54|    for i, r in enumerate(recs):
    55|        if r["date"] == buy_date: bi = i; break
    56|    if bi is None: return None
    57|    after = recs[bi+1:bi+6]
    58|    if not after: return None
    59|    result = []
    60|    prev_close = buy_price
    61|    for r in after:
    62|        daily_high = round((r["high"] / buy_price - 1) * 100, 1)
    63|        chg = r["close"] - prev_close
    64|        arrow = "↑" if chg > 0 else ("↓" if chg < 0 else "→")
    65|        result.append({"high": daily_high, "arrow": arrow, "close": round(r["close"],2), "date": r["date"]})
    66|        prev_close = r["close"]
    67|    max5 = max(d["high"] for d in result) if result else None
    68|    return {"days": len(result), "max5": max5, "daily": result}
    69|
    70|def build_html(bt_date, top10, top3_detail, history):
    71|    """生成带D+1~D+5明细的HTML"""
    72|    now = datetime.now()
    73|    date_str = now.strftime("%Y-%m-%d")
    74|    time_str = now.strftime("%H:%M")
    75|
    76|    # ── Top10 列表 ──
    77|    top10_rows = ""
    78|    if top10:
    79|        for i, r in enumerate(top10[:10], 1):
    80|            cls = "gold" if i == 1 else ("silver" if i == 2 else ("bronze" if i == 3 else ""))
    81|            pct_cls = "up" if r['pct'] > 0 else "down"
    82|            score_cls = "score-high" if r['score'] >= 110 else ("score-mid" if r['score'] >= 90 else "")
    83|            top10_rows += f"""
    84|            <tr class="{cls}">
    85|                <td class="rank">{i}</td>
    86|                <td><strong>{r['name']}</strong><span class="code">{r['code']}</span></td>
    87|                <td class="num">{r['price']:.2f}</td>
    88|                <td class="num {pct_cls}">{r['pct']:+.2f}%</td>
    89|                <td class="num {score_cls}">{r['score']}分</td>
    90|                <td class="num">{r['macd_r']:.1f}%</td>
    91|                <td class="num">{r.get('vr',0):.2f}x</td>
    92|                <td class="num">{r.get('pos',0):.0f}%</td>
    93|                <td class="sigs">{r['sigs'][:50]}</td>
    94|            </tr>"""
    95|
    96|    # ── Top3 D+1~D+5 ──
    97|    t3_rows = ""
    98|    top3_avgs, top3_hits = [], 0
    99|    for i, r in enumerate(top3_detail, 1):
   100|        cls = "gold" if i == 1 else ("silver" if i == 2 else "bronze")
   101|        daily = r.get('daily', [])
   102|        m5 = r.get('max5')
   103|        m5s = f"{m5:+.1f}%" if m5 is not None else "—"
   104|        m5c = "up" if m5 and m5 >= 10 else ("warn" if m5 and m5 >= 5 else "down")
   105|        if m5: top3_avgs.append(m5)
   106|        if m5 and m5 >= 10: top3_hits += 1
   107|
   108|        daily_cols = ""
   109|        for di in range(5):
   110|            if di < len(daily):
   111|                v = daily[di]["high"]
   112|                arr = daily[di]["arrow"]
   113|                vc = "up" if v >= 5 else ("warn" if v >= 2 else "down")
   114|                daily_cols += f'<td class="num {vc}">{v:+.1f}%{arr}</td>'
   115|            else:
   116|                daily_cols += '<td class="num" style="color:#484f58">—</td>'
   117|
   118|        t3_rows += f"""
   119|        <tr class="{cls}">
   120|            <td class="rank">{i}</td>
   121|            <td><strong>{r['name']}</strong><span class="code">{r['code']}</span></td>
   122|            <td class="num">{r['price']:.2f}</td>
   123|            <td class="num {m5c}"><strong>{m5s}</strong></td>
   124|            <td class="num" style="color:#58a6ff">{r.get('score',0)}分</td>
   125|            {daily_cols}
   126|        </tr>"""
   127|
   128|    t3_avg = sum(top3_avgs)/len(top3_avgs) if top3_avgs else 0
   129|
   130|    # ── 最近5条回测历史 ──
   131|    recent5 = history[-5:] if len(history) >= 5 else history
   132|    hist_rows = ""
   133|    for entry in reversed(recent5):
   134|        d = entry['date']
   135|        t3 = entry.get('top3_detail', entry.get('top3', []))
   136|        for si, s in enumerate(t3[:3]):
   137|            m5 = s.get('max5')
   138|            m5s = f"{m5:+.1f}%" if m5 is not None else "—"
   139|            m5c = "up" if m5 and m5 >= 10 else ("warn" if m5 and m5 >= 5 else "down")
   140|            daily = s.get('daily', [])
   141|            hist_rows += f"""
   142|            <tr><td class="num">{d}</td>
   143|                <td><strong>{s['name']}</strong><span class="code">{s['code']}</span></td>
   144|                <td class="num {m5c}"><strong>{m5s}</strong></td>"""
   145|            for di in range(5):
   146|                if di < len(daily):
   147|                    v = daily[di]["high"]
   148|                    arr = daily[di]["arrow"]
   149|                    vc = "up" if v >= 5 else ("warn" if v >= 2 else "down")
   150|                    hist_rows += f'<td class="num {vc}">{v:+.1f}%{arr}</td>'
   151|                else:
   152|                    hist_rows += '<td class="num" style="color:#484f58">—</td>'
   153|            hist_rows += '</tr>'
   154|
   155|    # 累计统计
   156|    if history:
   157|        all_avgs, all_hits, all_tot = [], 0, 0
   158|        for e in history:
   159|            t3 = e.get('top3_detail', e.get('top3', []))
   160|            vals = [s.get('max5',0) or 0 for s in t3[:3]]
   161|            vals = [v for v in vals if v]
   162|            if vals: all_avgs.append(sum(vals)/len(vals))
   163|            all_hits += sum(1 for v in vals if v >= 10)
   164|            all_tot += len(vals)
   165|        ov_avg = sum(all_avgs)/len(all_avgs) if all_avgs else 0
   166|        ov_hit = f"{all_hits}/{all_tot}={all_hits*100//all_tot}%" if all_tot else "—"
   167|    else:
   168|        ov_avg, ov_hit = 0, "—"
   169|
   170|    html = f"""<!DOCTYPE html>
   171|<html lang="zh-CN">
   172|<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
   173|<style>
   174|* {{ margin:0; padding:0; box-sizing:border-box; }}
   175|body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif; background:#0d1117; color:#e6edf3; padding:15px; }}
   176|.container {{ max-width:1000px; margin:0 auto; }}
   177|.header {{ background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460); border-radius:10px; padding:18px 22px; margin-bottom:14px; border:1px solid #30363d; }}
   178|.header h1 {{ font-size:20px; color:#58a6ff; margin-bottom:2px; }}
   179|.header .sub {{ font-size:12px; color:#8b949e; }}
   180|.header .badge {{ display:inline-block; background:#1f6feb33; color:#58a6ff; border:1px solid #1f6feb66; border-radius:20px; padding:1px 10px; font-size:11px; margin-left:6px; }}
   181|.stats {{ display:flex; gap:10px; margin-bottom:14px; }}
   182|.stat-box {{ flex:1; background:#161b22; border:1px solid #30363d; border-radius:8px; padding:12px; text-align:center; }}
   183|.stat-box .num {{ font-size:22px; font-weight:700; }}
   184|.stat-box .label {{ font-size:10px; color:#8b949e; margin-top:2px; }}
   185|.stat-box.green .num {{ color:#3fb950; }} .stat-box.blue .num {{ color:#58a6ff; }}
   186|.stat-box.orange .num {{ color:#d29922; }} .stat-box.red .num {{ color:#f85149; }}
   187|.section {{ background:#161b22; border:1px solid #30363d; border-radius:8px; margin-bottom:12px; overflow-x:auto; }}
   188|.section-title {{ background:#1c2128; padding:10px 14px; font-size:14px; font-weight:600; color:#e6edf3; border-bottom:1px solid #30363d; }}
   189|.section-title span {{ color:#8b949e; font-weight:400; font-size:11px; margin-left:8px; }}
   190|table {{ width:100%; border-collapse:collapse; font-size:12px; min-width:600px; }}
   191|th {{ background:#1c2128; padding:8px 6px; text-align:left; font-weight:500; color:#8b949e; font-size:10px; text-transform:uppercase; letter-spacing:0.3px; border-bottom:1px solid #30363d; white-space:nowrap; }}
   192|td {{ padding:7px 6px; border-bottom:1px solid #21262d; white-space:nowrap; }}
   193|tr:last-child td {{ border-bottom:none; }}
   194|tr:hover td {{ background:#1c212866; }}
   195|tr.gold td:first-child {{ border-left:3px solid #d29922; }}
   196|tr.silver td:first-child {{ border-left:3px solid #8b949e; }}
   197|tr.bronze td:first-child {{ border-left:3px solid #a371f7; }}
   198|.rank {{ font-weight:700; text-align:center; width:24px; color:#8b949e; font-size:11px; }}
   199|.num {{ font-family:'JetBrains Mono','Consolas','Courier New',monospace; text-align:right; }}
   200|.up {{ color:#3fb950; }} .down {{ color:#f85149; }} .warn {{ color:#d29922; }}
   201|.score-high {{ color:#58a6ff; font-weight:700; }} .score-mid {{ color:#d29922; }}
   202|.code {{ color:#8b949e; font-size:10px; margin-left:3px; }}
   203|.sigs {{ font-size:10px; color:#8b949e; max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
   204|.footer {{ text-align:center; color:#484f58; font-size:10px; padding:14px 0; }}
   205|</style></head><body>
   206|<div class="container">
   207|    <div class="header">
   208|        <h1>🐉 擒龙MAX · 回测报告 <span class="badge">v9.0</span></h1>
   209|        <div class="sub">{date_str} {time_str} 推送 · 回测交易日: <strong>{bt_date}</strong> · 沪深主板全市场扫描 · 六重风控</div>
   210|    </div>
   211|    <div class="stats">
   212|        <div class="stat-box green"><div class="num">{t3_avg:+.1f}%</div><div class="label">{bt_date} Top3平均</div></div>
   213|        <div class="stat-box blue"><div class="num">{top3_hits}/3</div><div class="label">命中&gt;10%</div></div>
   214|        <div class="stat-box orange"><div class="num">{len(top10) if top10 else 0}</div><div class="label">当日候选</div></div>
   215|        <div class="stat-box red"><div class="num">{ov_avg:+.1f}%</div><div class="label">累计平均</div></div>
   216|    </div>
   217|
   218|    <!-- 当日Top10 -->
   219|    <div class="section">
   220|        <div class="section-title">🏆 {bt_date} 擒龙MAX Top10</div>
   221|        <table>
   222|            <thead><tr><th>#</th><th>名称</th><th>现价</th><th>涨幅</th><th>评分</th><th>MCD/价</th><th>量比</th><th>位置</th><th>信号</th></tr></thead>
   223|            <tbody>{top10_rows}</tbody>
   224|        </table>
   225|    </div>
   226|
   227|    <!-- Top3 D+1~D+5 -->
   228|    <div class="section">
   229|        <div class="section-title">📈 Top3 回测 D+1~D+5 <span>↗=5日最高 · ↑↓→=收盘方向</span></div>
   230|        <table>
   231|            <thead><tr><th>#</th><th>名称</th><th>买入</th><th>↗最高</th><th>评分</th><th>D+1</th><th>D+2</th><th>D+3</th><th>D+4</th><th>D+5</th></tr></thead>
   232|            <tbody>{t3_rows}</tbody>
   233|        </table>
   234|        <div style="padding:10px 14px;border-top:1px solid #21262d;font-size:13px;color:#8b949e;display:flex;gap:16px;">
   235|            <span>📊 <strong>{bt_date}</strong> Top3平均: <strong style="color:#3fb950">{t3_avg:+.1f}%</strong></span>
   236|            <span>＞10%: <strong style="color:#58a6ff">{top3_hits}/3</strong></span>
   237|        </div>
   238|    </div>
   239|
   240|    <!-- 最近5天回测 -->
   241|    <div class="section">
   242|        <div class="section-title">📊 最近{len(recent5)}天回测汇总</div>
   243|        <table>
   244|            <thead><tr><th>日期</th><th>名称</th><th>↗最高</th><th>D+1</th><th>D+2</th><th>D+3</th><th>D+4</th><th>D+5</th></tr></thead>
   245|            <tbody>{hist_rows}</tbody></table>
   246|        <div style="padding:8px 14px;border-top:1px solid #21262d;font-size:11px;color:#8b949e;">
   247|            累计 {len(history)}天 · 平均 <strong style="color:#3fb950">{ov_avg:+.1f}%</strong> · 命中率 <strong style="color:#58a6ff">{ov_hit}</strong>
   248|        </div>
   249|    </div>
   250|    <div class="footer">擒龙MAX v9.0 · 六重风控 · 收盘自动推送 · 数据: 腾讯财经+新浪财经</div>
   251|</div></body></html>"""
   252|    return html, t3_avg, top3_hits
   253|
   254|
   255|def main():
   256|    bt_date = get_last_trading_day()
   257|    print(f"🐉 擒龙MAX 收盘回测 — {bt_date}")
   258|    t0 = time.time()
   259|
   260|    # 1. 运行策略
   261|    print(f"  📡 回测 {bt_date}...")
   262|    top10, top_codes = run_qinlong_max(test_date=bt_date)
   263|
   264|    # 2. 获取Top3 D+1~D+5
   265|    print(f"  📊 获取Top3 D+1~D+5...")
   266|    top3 = top10[:3] if top10 else []
   267|    top3_detail = []
   268|    for r in top3:
   269|        dd = get_daily_breakdown(r['code'], r['market'], bt_date, r['price'])
   270|        top3_detail.append({
   271|            "name": r['name'], "code": r['code'], "price": round(r['price'],2),
   272|            "score": r['score'], "max5": dd['max5'] if dd else None,
   273|            "daily": dd['daily'] if dd else []
   274|        })
   275|
   276|    # 3. 缓存
   277|    entry = {
   278|        "date": bt_date,
   279|        "top3_detail": top3_detail,
   280|        "avg": round(sum(d.get('max5',0) or 0 for d in top3_detail)/len(top3_detail), 1) if top3_detail else 0,
   281|        "hits": sum(1 for d in top3_detail if d.get('max5') and d['max5'] >= 10),
   282|        "total": len(top3_detail)
   283|    }
   284|    history = save_history(entry)
   285|    print(f"  ✅ 缓存: {len(history)}天")
   286|
   287|    # 4. 生成HTML
   288|    html, t3_avg, t3_hits = build_html(bt_date, top10, top3_detail, history)
   289|
   290|    # 5. 发送
   291|    time_str = datetime.now().strftime("%H:%M")
   292|    subject = f"[{bt_date} 回测] 擒龙MAX Top3平均{t3_avg:+.1f}% 命中{t3_hits}/3"
   293|    print(f"  📧 发送: {subject}")
   294|    send_email(RECIPIENTS, subject, html, html=True)
   295|    print(f"  ✅ 完成! {time.time()-t0:.0f}s -> {RECIPIENTS}")
   296|
   297|if __name__ == "__main__":
   298|    main()
   299|