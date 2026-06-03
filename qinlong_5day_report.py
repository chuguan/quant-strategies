#!/usr/bin/env python3
"""
擒龙MAX 近5日回测HTML报告生成器
生成美观的HTML文件，分5个卡片展示最近5个交易日的回测详情
"""
import json, os, sys
from datetime import datetime

CACHE_FILE = os.path.join(os.path.dirname(__file__), "qinlong_history.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "qinlong_5day_report.html")

def load_history():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return []

def generate():
    history = load_history()
    if not history:
        print("❌ 无历史数据")
        return

    # 取最近5天
    recent5 = history[-5:]
    now = datetime.now()

    # 总统计
    all_avgs, all_hits, all_tot = [], 0, 0
    for e in history:
        t3 = e.get('top3_detail', [])
        vals = [s.get('max5',0) or 0 for s in t3[:3]]
        vals = [v for v in vals if v]
        if vals: all_avgs.append(sum(vals)/len(vals))
        all_hits += sum(1 for v in vals if v >= 10)
        all_tot += len(vals)
    ov_avg = sum(all_avgs)/len(all_avgs) if all_avgs else 0
    ov_hit = f"{all_hits}/{all_tot}={all_hits*100//all_tot}%" if all_tot else "—"

    # 构建每一天的卡片HTML
    day_cards = ""
    for entry in reversed(recent5):
        d = entry['date']
        avg = entry.get('avg', 0)
        hits = entry.get('hits', 0)
        t3 = entry.get('top3_detail', [])

        # Top3 表格行
        t3_rows = ""
        for i, s in enumerate(t3[:3], 1):
            m5 = s.get('max5')
            m5s = f"{m5:+.1f}%" if m5 is not None else "—"
            m5c = "up" if m5 and m5 >= 10 else ("warn" if m5 and m5 >= 5 else "down")
            daily = s.get('daily', [])

            # 一个小走势条（用色块表示5天涨跌）
            bars = ""
            for di in range(5):
                if di < len(daily):
                    v = daily[di]["high"]
                    arr = daily[di]["arrow"]
                    if v >= 5: bc, bi = "#3fb950", "🔥"
                    elif v >= 2: bc, bi = "#58a6ff", "↑"
                    elif v >= 0: bc, bi = "#d29922", "→"
                    else: bc, bi = "#f85149", "↓"
                    bars += f'<div class="bar" style="background:{bc};height:{max(4,min(24,abs(v)*2))}px" title="D+{di+1}:{v:+.1f}%{arr}">{bi}</div>'
                else:
                    bars += '<div class="bar" style="background:#21262d;height:4px" title="—">—</div>'

            # 每日数值
            daily_vals = ""
            for di in range(5):
                if di < len(daily):
                    v = daily[di]["high"]
                    arr = daily[di]["arrow"]
                    vc = "up" if v >= 5 else ("warn" if v >= 2 else "down")
                    daily_vals += f'<td class="num {vc}">{v:+.1f}%{arr}</td>'
                else:
                    daily_vals += '<td class="num" style="color:#484f58">—</td>'

            rank_badge = "🥇" if i == 1 else ("🥈" if i == 2 else "🥉")
            t3_rows += f"""
            <tr>
                <td class="rank">{rank_badge}</td>
                <td><strong>{s['name']}</strong><span class="code">{s['code']}</span></td>
                <td class="num">{s['price']:.2f}</td>
                <td class="num {m5c}"><strong>{m5s}</strong></td>
                {daily_vals}
                <td class="bars-cell"><div class="bars">{bars}</div></td>
            </tr>"""

        # 命中率进度条
        hit_pct = int(hits / 3 * 100) if hits else 0
        avg_cls = "up" if avg >= 10 else ("warn" if avg >= 5 else "down")

        day_cards += f"""
        <div class="day-card">
            <div class="day-header">
                <div class="day-title">
                    <span class="day-date">📅 {d}</span>
                    <span class="day-badge {avg_cls}">Top3平均 <strong>{avg:+.1f}%</strong></span>
                    <span class="day-badge blue">命中 <strong>{hits}/3</strong></span>
                </div>
                <div class="hit-bar">
                    <div class="hit-fill" style="width:{hit_pct}%"></div>
                </div>
            </div>
            <table>
                <thead>
                    <tr><th>#</th><th>名称</th><th>买入</th><th>↗最高</th><th>D+1</th><th>D+2</th><th>D+3</th><th>D+4</th><th>D+5</th><th>走势</th></tr>
                </thead>
                <tbody>{t3_rows}</tbody>
            </table>
        </div>"""

    # 总表（全部历史）
    all_rows = ""
    for entry in reversed(history):
        d = entry['date']
        avg = entry.get('avg', 0)
        hits = entry.get('hits', 0)
        t3 = entry.get('top3_detail', [])
        names = "、".join(f"{s['name']}({s.get('max5','—')})" for s in t3[:3]) if t3 else "—"
        avg_cls = "up" if avg >= 10 else ("warn" if avg >= 5 else "down")
        all_rows += f"""
        <tr>
            <td class="num">{d}</td>
            <td style="font-size:11px">{names}</td>
            <td class="num {avg_cls}">{avg:+.1f}%</td>
            <td class="num">{hits}/3</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>擒龙MAX 近5日回测报告</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif; background:#0d1117; color:#e6edf3; padding:20px; }}
.container {{ max-width:960px; margin:0 auto; }}
.header {{ background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460); border-radius:12px; padding:24px 28px; margin-bottom:20px; border:1px solid #30363d; }}
.header h1 {{ font-size:24px; color:#58a6ff; }}
.header .sub {{ font-size:12px; color:#8b949e; margin-top:4px; }}
.stats-row {{ display:flex; gap:14px; margin-bottom:20px; }}
.stat-card {{ flex:1; background:#161b22; border:1px solid #30363d; border-radius:10px; padding:16px; text-align:center; }}
.stat-card .val {{ font-size:28px; font-weight:700; }}
.stat-card .lbl {{ font-size:11px; color:#8b949e; margin-top:4px; }}
.stat-card.green .val {{ color:#3fb950; }} .stat-card.blue .val {{ color:#58a6ff; }}
.stat-card.orange .val {{ color:#d29922; }} .stat-card.purple .val {{ color:#a371f7; }}

.day-card {{ background:#161b22; border:1px solid #30363d; border-radius:10px; margin-bottom:16px; overflow:hidden; }}
.day-header {{ background:#1c2128; padding:14px 18px; border-bottom:1px solid #30363d; }}
.day-title {{ display:flex; align-items:center; gap:12px; flex-wrap:wrap; }}
.day-date {{ font-size:16px; font-weight:700; color:#e6edf3; }}
.day-badge {{ font-size:12px; padding:2px 10px; border-radius:12px; background:#21262d; color:#8b949e; }}
.day-badge.up {{ background:#3fb95022; color:#3fb950; border:1px solid #3fb95044; }}
.day-badge.warn {{ background:#d2992222; color:#d29922; border:1px solid #d2992244; }}
.day-badge.down {{ background:#f8514922; color:#f85149; border:1px solid #f8514944; }}
.day-badge.blue {{ background:#58a6ff22; color:#58a6ff; border:1px solid #58a6ff44; }}
.hit-bar {{ margin-top:8px; height:4px; background:#21262d; border-radius:2px; overflow:hidden; }}
.hit-fill {{ height:100%; background:linear-gradient(90deg,#3fb950,#58a6ff); border-radius:2px; transition:width 0.5s; }}

table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ background:#161b22; padding:8px 6px; text-align:left; font-weight:500; color:#8b949e; font-size:10px; text-transform:uppercase; letter-spacing:0.3px; border-bottom:1px solid #30363d; white-space:nowrap; }}
td {{ padding:8px 6px; border-bottom:1px solid #21262d; white-space:nowrap; }}
tr:last-child td {{ border-bottom:none; }}
tr:hover td {{ background:#1c212844; }}
.num {{ font-family:'JetBrains Mono','Consolas','Courier New',monospace; text-align:right; }}
.up {{ color:#3fb950; }} .down {{ color:#f85149; }} .warn {{ color:#d29922; }}
.rank {{ text-align:center; width:30px; font-size:14px; }}
.code {{ color:#8b949e; font-size:10px; margin-left:3px; }}

.bars-cell {{ width:100px; }}
.bars {{ display:flex; gap:3px; align-items:flex-end; justify-content:center; height:28px; }}
.bar {{ width:16px; border-radius:2px; font-size:8px; text-align:center; line-height:28px; color:#fff; min-height:4px; transition:all 0.2s; }}
.bar:hover {{ transform:scale(1.2); }}

.summary-section {{ background:#161b22; border:1px solid #30363d; border-radius:10px; margin-bottom:16px; overflow:hidden; }}
.section-title {{ background:#1c2128; padding:12px 18px; font-size:14px; font-weight:600; color:#e6edf3; border-bottom:1px solid #30363d; }}
.section-title span {{ color:#8b949e; font-weight:400; font-size:11px; margin-left:8px; }}

.footer {{ text-align:center; color:#484f58; font-size:10px; padding:20px 0; }}

@media (max-width:600px) {{
    .stats-row {{ flex-wrap:wrap; }}
    .stat-card {{ min-width:45%; }}
    .day-title {{ flex-direction:column; align-items:flex-start; }}
    .bars-cell {{ display:none; }}
}}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🐉 擒龙MAX <span style="font-size:14px;color:#8b949e">v9.0 六重风控</span></h1>
        <div class="sub">回测报告 · 生成时间 {now.strftime('%Y-%m-%d %H:%M')} · 共{len(history)}天数据</div>
    </div>

    <div class="stats-row">
        <div class="stat-card green"><div class="val">{ov_avg:+.1f}%</div><div class="lbl">累计Top3平均</div></div>
        <div class="stat-card blue"><div class="val">{ov_hit}</div><div class="lbl">累计命中率</div></div>
        <div class="stat-card orange"><div class="val">{len(recent5)}天</div><div class="lbl">本次展示</div></div>
        <div class="stat-card purple"><div class="val">{len(history)}天</div><div class="lbl">总数据量</div></div>
    </div>

    {day_cards}

    <div class="summary-section">
        <div class="section-title">📊 全部历史数据汇总 <span>{len(history)}天</span></div>
        <table>
            <thead><tr><th>日期</th><th>Top3</th><th>平均</th><th>命中</th></tr></thead>
            <tbody>{all_rows}</tbody>
        </table>
        <div style="padding:10px 18px;border-top:1px solid #21262d;font-size:12px;color:#8b949e;">
            累计 {len(history)}天 · Top3平均 <strong style="color:#3fb950">{ov_avg:+.1f}%</strong> · 命中率 <strong style="color:#58a6ff">{ov_hit}</strong> · 六重风控规则
        </div>
    </div>

    <div class="footer">
        擒龙MAX v9.0 · 六重风控 · ①放量>2.5x二板排除 ②连板≥5排除 ③20日>50%+5日<20%排除<br>
        ④首板放量>3x排除 ⑤连板扣10分 ⑥7天重复入选排除 · 数据:腾讯财经+新浪财经
    </div>
</div>
</body>
</html>"""

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ 报告已生成: {OUTPUT_FILE}")
    print(f"   文件大小: {len(html)} 字节")
    print(f"   展示 {len(recent5)} 天卡片 + 总数 {len(history)} 天")

if __name__ == "__main__":
    generate()
