#!/usr/bin/env python3
"""擒龙MAX 5日回测邮件推送 — 板块信息版"""
import sys, os, time, subprocess, re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))
from send_email import send_email
from qinlong_max import run_qinlong_max, fetch_kline
RECIPIENTS = ["1254628314@qq.com", "314913203@qq.com", "2603672569@qq.com", "2318162429@qq.com"]

# ===== 板块信息缓存 =====
_industry_cache = {}
_sector_cache = {}

def get_industry(code):
    """从新浪获取所属行业（申万行业分类）"""
    if code in _industry_cache:
        return _industry_cache[code]
    try:
        url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpOtherInfo/stockid/{code}/menu_num/2.phtml"
        r = subprocess.run(['curl', '-s', '--max-time', '6', url], capture_output=True)
        html = r.stdout.decode('gbk', errors='replace')
        m = re.search(r'所属行业板块.*?</tr>.*?<tr>.*?<td[^>]*>([^<]+)</td>', html, re.DOTALL)
        if m:
            ind = m.group(1).strip()
            _industry_cache[code] = ind
            return ind
    except:
        pass
    _industry_cache[code] = "—"
    return "—"

def get_sector_change(sector_name):
    """获取板块涨跌幅（占位，后续可接板块指数API）"""
    return "—"

def get_prev_trading_days(target, count=4):
    d = datetime.strptime(target, "%Y-%m-%d")
    r = []
    while len(r) < count:
        d -= timedelta(days=1)
        if d.weekday() < 5: r.append(d.strftime("%Y-%m-%d"))
    return list(reversed(r))

def get_daily_breakdown(code, market, buy_date, buy_price):
    recs = fetch_kline(code, market)
    if not recs: return None
    bi = None
    for i, r in enumerate(recs):
        if r["date"] == buy_date: bi = i; break
    if bi is None: return None
    after = recs[bi+1:bi+6]
    if not after: return None
    result = []
    prev_close = buy_price
    for r in after:
        dh = round((r["high"] / buy_price - 1) * 100, 1)
        chg = r["close"] - prev_close
        arr = "↑" if chg > 0 else ("↓" if chg < 0 else "→")
        result.append({"high": dh, "arrow": arr, "date": r["date"]})
        prev_close = r["close"]
    max5 = max(d["high"] for d in result) if result else None
    return {"max5": max5, "daily": result}

def build_html(target_date, prev_dates, all_data):
    now = datetime.now()
    all_avgs, all_hits, all_tot = [], 0, 0
    for d in [target_date] + prev_dates:
        data = all_data.get(d)
        if not data: continue
        t3 = data.get('top3_detail', [])
        vals = [s.get('max5',0) or 0 for s in t3[:5]]
        vals = [v for v in vals if v]
        if vals: all_avgs.append(sum(vals)/len(vals))
        all_hits += sum(1 for v in vals if v >= 10)
        all_tot += len(vals)
    ov_avg = sum(all_avgs)/len(all_avgs) if all_avgs else 0
    ov_hit_pct = all_hits*100//all_tot if all_tot else 0

    def get_d_labels(t3):
        first = t3[0].get('daily', []) if t3 else []
        return [first[di]['date'][5:] if di < len(first) else f"D+{di+1}" for di in range(5)]

    def star_rating(s):
        if s >= 80: return "⭐⭐⭐⭐⭐"
        elif s >= 70: return "⭐⭐⭐⭐"
        elif s >= 60: return "⭐⭐⭐"
        elif s >= 50: return "⭐⭐"
        return "⭐"

    all_cards = ""
    for date in [target_date] + list(reversed(prev_dates)):
        data = all_data.get(date)
        if not data:
            all_cards += f'<div class="day-card"><div class="day-header" style="text-align:center"><span class="day-date">📅 {date}</span><span class="day-badge">无数据</span></div></div>'
            continue
        top10 = data.get('top10', [])
        t3 = data.get('top3_detail', [])
        avg = data.get('avg', 0)
        hits = data.get('hits', 0)
        d_labels = get_d_labels(t3)

        # Top10 — 买入价、所属板块、⭐强度
        t10_rows = ""
        for i, r in enumerate(top10[:10], 1):
            cls = "gold" if i == 1 else ("silver" if i == 2 else ("bronze" if i == 3 else ""))
            pc = "up" if r['pct'] > 0 else "down"
            sc = "score-high" if r['score'] >= 110 else ("score-mid" if r['score'] >= 90 else "")
            ind = r.get('industry', '—')
            stars = star_rating(r['score'])
            t10_rows += f'<tr class="{cls}">' \
                f'<td class="rank">{i}</td>' \
                f'<td><strong>{r["name"]}</strong><span class="code">{r["code"]}</span></td>' \
                f'<td class="num">{r["price"]:.2f}</td>' \
                f'<td class="num">{ind}</td>' \
                f'<td class="num {sc}">{r["score"]}<span class="stars">{stars}</span></td>' \
                f'<td class="num {pc}">{r["pct"]:+.2f}%</td></tr>'

        # Top5
        show_n = min(5, len(t3))
        t5_rows = ""
        for i, s in enumerate(t3[:show_n], 1):
            m5 = s.get('max5')
            m5s = f"{m5:+.1f}%" if m5 is not None else "—"
            m5c = "up" if m5 and m5 >= 10 else ("warn" if m5 and m5 >= 5 else "down")
            score = s.get('score', 0)
            stars = star_rating(score)
            daily = s.get('daily', [])
            cols = ""
            for di in range(5):
                if di < len(daily):
                    v = daily[di]["high"]
                    arr = daily[di]["arrow"]
                    vc = "up" if v >= 5 else ("warn" if v >= 2 else "down")
                    # 实时决策：只用当天及以前的数据，不用未来
                    # 找当天之前的最佳值
                    prev_best = max(d["high"] for d in daily[:di]) if di > 0 else v
                    is_dead = v < -3
                    if is_dead:
                        icon = "💀"
                    elif di == 0:
                        icon = "🚀"  # 首日上涨
                    elif v >= prev_best - 1.5:
                        icon = "🚀"  # 还在创新高
                    elif v <= prev_best - 3:
                        icon = "💀"  # 从最高跌了3%+
                    elif v < daily[di-1]["high"]:
                        icon = "🏃"  # 比前一天低了，到顶跑路
                    else:
                        icon = "🔥"
                    cols += f'<td class="num {vc}">{v:+.1f}%{arr}{icon}</td>'
                else:
                    cols += '<td class="num" style="color:#484f58">—</td>'
            rank = "🥇" if i==1 else ("🥈" if i==2 else ("🥉" if i==3 else (f"{i}️⃣" if i<=5 else str(i))))
            t5_rows += f'<tr><td class="rank">{rank}</td><td><strong>{s["name"]}</strong><span class="code">{s["code"]}</span></td><td class="num">{s["price"]:.2f}</td><td class="num {m5c}"><strong>{m5s}</strong></td><td class="num" style="color:#58a6ff">{score} {stars}</td>{cols}</tr>'

        hit_pct = int(hits/show_n*100) if show_n else 0
        avg_cls = "up" if avg >= 10 else ("warn" if avg >= 5 else "down")
        d_cols = "".join(f'<th>{dl}</th>' for dl in d_labels)

        all_cards += f'''
        <div class="day-card">
            <div class="day-header" style="text-align:center">
                <div class="day-title" style="justify-content:center">
                    <span class="day-date">📅 {date}</span>
                    <span class="day-badge {avg_cls}">Top5均 <strong>{avg:+.1f}%</strong></span>
                    <span class="day-badge blue">胜率 <strong>{hit_pct}%</strong></span>
                </div>
                <div class="hit-bar"><div class="hit-fill" style="width:{hit_pct}%"></div></div>
            </div>
            <div style="padding:0">
                <details open>
                    <summary style="padding:8px 16px;font-size:12px;color:#8b949e;text-align:left;border-bottom:1px solid #21262d;cursor:pointer">🏆 Top10</summary>
                    <div class="scroll-wrap"><table><thead><tr><th style="width:24px">#</th><th>名称</th><th>买入价</th><th>所属板块</th><th>⭐强度</th><th>涨幅</th></tr></thead>
                    <tbody>{t10_rows}</tbody></table></div>
                </details>
                <details open>
                    <summary style="padding:8px 16px;font-size:12px;color:#8b949e;text-align:left;border-bottom:1px solid #21262d;cursor:pointer">📈 Top5 D+1~D+5</summary>
                    <div class="scroll-wrap"><table><thead><tr><th style="width:24px">#</th><th>名称</th><th>买入</th><th>↗最高</th><th>强度</th>{d_cols}</tr></thead>
                    <tbody>{t5_rows}</tbody></table></div>
                </details>
            </div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#ffffff;color:#2c3e50;padding:10px}}
.container{{max-width:100%;margin:0 auto;overflow-x:hidden}}
.scroll-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -4px;padding:0 4px}}
.scroll-wrap::-webkit-scrollbar{{height:6px}}
.scroll-wrap::-webkit-scrollbar-thumb{{background:#dfe6e9;border-radius:3px}}
.header{{background:linear-gradient(135deg,#667eea,#764ba2);border-radius:12px;padding:16px 20px;margin-bottom:12px;text-align:center}}
.header h1{{font-size:20px;color:#ffffff}}
.header .sub{{font-size:11px;color:#e0e0e0;margin-top:2px}}
.stats{{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;justify-content:center}}
.stat-box{{flex:1;min-width:80px;max-width:160px;background:#f5f6fa;border:1px solid #dfe6e9;border-radius:8px;padding:10px;text-align:center}}
.stat-box .num{{font-size:22px;font-weight:700}}
.stat-box .lbl{{font-size:9px;color:#95a5a6;margin-top:2px}}
.stat-box.green .num{{color:#e74c3c}} .stat-box.blue .num{{color:#3498db}} .stat-box.orange .num{{color:#f39c12}}
.legend{{text-align:center;padding:6px;font-size:10px;color:#7f8c8d;margin-bottom:10px;background:#f5f6fa;border:1px solid #dfe6e9;border-radius:8px;white-space:nowrap;overflow-x:auto}}
.day-card{{background:#ffffff;border:1px solid #dfe6e9;border-radius:10px;margin-bottom:12px;overflow:hidden}}
.day-header{{background:#f8f9fb;padding:10px 12px;border-bottom:1px solid #dfe6e9}}
.day-title{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.day-date{{font-size:15px;font-weight:700;color:#2c3e50}}
.day-badge{{font-size:10px;padding:2px 6px;border-radius:10px;background:#f0f1f5;color:#7f8c8d;white-space:nowrap}}
.day-badge.up{{background:#ffeaea;color:#e74c3c;border:1px solid #f5c6c6}}
.day-badge.warn{{background:#fef3e0;color:#e67e22;border:1px solid #faddb5}}
.day-badge.blue{{background:#e8f4fd;color:#3498db;border:1px solid #b8dff5}}
.hit-bar{{margin:6px 12px 0;height:3px;background:#dfe6e9;border-radius:2px;overflow:hidden}}
.hit-fill{{height:100%;background:linear-gradient(90deg,#e74c3c,#3498db);border-radius:2px}}
table{{width:100%;border-collapse:collapse;font-size:11px;min-width:720px}}
th{{background:#f5f6fa;padding:6px 3px;text-align:center;font-weight:600;color:#636e72;font-size:9px;letter-spacing:0.2px;border-bottom:1px solid #dfe6e9;white-space:nowrap}}
td{{padding:6px 3px;text-align:center;border-bottom:1px solid #f0f1f5;white-space:nowrap}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#f8f9fb}}
tr.gold td:first-child{{border-left:3px solid #f39c12}}
tr.silver td:first-child{{border-left:3px solid #bdc3c7}}
tr.bronze td:first-child{{border-left:3px solid #9b59b6}}
.rank{{text-align:center;width:24px;font-size:12px}}
.num{{font-family:"JetBrains Mono","Consolas","Courier New",monospace;text-align:center}}
.stars{{font-size:8px;margin-left:2px}}
.up{{color:#e74c3c}} .down{{color:#27ae60}} .warn{{color:#e67e22}}
.score-high{{color:#3498db;font-weight:700}} .score-mid{{color:#e67e22}}
.code{{color:#95a5a6;font-size:9px;margin-left:2px}}
details summary{{list-style:none;user-select:none}}
details summary::-webkit-details-marker{{display:none}}
details summary:hover{{background:#f0f1f5}}
.footer{{text-align:center;color:#bdc3c7;font-size:9px;padding:12px 0}}
@media screen and (max-width:480px){{
  body{{padding:6px}}
  .header h1{{font-size:17px}}
  table{{font-size:10px;min-width:620px}}
  td,th{{padding:4px 2px}}
  .stat-box .num{{font-size:18px}}
  .day-date{{font-size:13px}}
}}
</style></head><body>
<div class="container">
    <div class="header">
        <h1>🐉 擒龙MAX <span style="font-size:14px;color:#e0e0e0">v9.0 六重风控</span></h1>
        <div class="sub">5日回测 · {now.strftime("%Y-%m-%d %H:%M")} 推送 · {target_date} 及前4个交易日</div>
    </div>
    <div class="stats">
        <div class="stat-box green"><div class="num">{ov_avg:+.1f}%</div><div class="lbl">5日平均</div></div>
        <div class="stat-box blue"><div class="num">{ov_hit_pct}%</div><div class="lbl">累计胜率</div></div>
        <div class="stat-box orange"><div class="num">{len(prev_dates)+1}天</div><div class="lbl">回测天数</div></div>
    </div>
    <div class="legend">🔥上涨持有  🏃到顶快跑  💀跌3%+  🚀全程无忧  ↑↓→收盘方向</div>
    {all_cards}
    <div class="footer">擒龙MAX v9.0 · 六重风控 · 数据:腾讯财经+新浪财经</div>
</div></body></html>'''
    return html, ov_avg, ov_hit_pct

def get_last_trading_day():
    d = datetime.now()
    for offset in range(0, 5):
        day = d - timedelta(days=offset)
        if day.weekday() < 5: return day.strftime("%Y-%m-%d")
    return d.strftime("%Y-%m-%d")

def main():
    target_date = sys.argv[1] if len(sys.argv) > 1 else get_last_trading_day()
    prev_dates = get_prev_trading_days(target_date, 4)
    all_dates = prev_dates + [target_date]
    print(f"🐉 5日回测 — {target_date} +前4天")
    t0 = time.time()
    all_data = {}
    for i, date in enumerate(all_dates, 1):
        print(f"  [{i}/{len(all_dates)}] {date}...", end=" ", flush=True)
        res = run_qinlong_max(test_date=date)
        if not res:
            print("无候选，跳过这一天")
            continue
        top10, top_codes = res
        top3 = top10[:5] if top10 else []
        t3_detail = []
        for r in top3:
            dd = get_daily_breakdown(r['code'], r['market'], date, r['price'])
            t3_detail.append({"name":r['name'],"code":r['code'],"price":round(r['price'],2),"score":r['score'],
                              "max5":dd['max5'] if dd else None,"daily":dd['daily'] if dd else []})
        avg = sum(d.get('max5',0) or 0 for d in t3_detail)/len(t3_detail) if t3_detail else 0
        hits = sum(1 for d in t3_detail if d.get('max5') and d['max5'] >= 10)

        # 获取Top10的行业信息（并行）
        t10 = []
        codes_to_fetch = [r['code'] for r in top10]
        with ThreadPoolExecutor(max_workers=10) as ex:
            fm = {ex.submit(get_industry, c): c for c in codes_to_fetch}
            ind_results = {}
            for f in as_completed(fm):
                ind_results[fm[f]] = f.result()
        for r in top10:
            ind = ind_results.get(r['code'], '—')
            t10.append({"name":r['name'],"code":r['code'],"price":r['price'],"pct":r['pct'],
                        "score":r['score'],"industry":ind})

        all_data[date] = {"top10":t10,"top3_detail":t3_detail,"avg":round(avg,1),"hits":hits}
        print(f"均{avg:+.1f}% 胜{hits}/{len(t3_detail)}")
    html, ov_avg, ov_hit_pct = build_html(target_date, prev_dates, all_data)
    print(f"  📧 ...")
    send_email(RECIPIENTS, f"[{target_date} 5日回测] 擒龙MAX 均{ov_avg:+.1f}% 胜率{ov_hit_pct}%", html, html=True)
    print(f"✅ 完成! {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
