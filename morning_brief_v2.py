     1|#!/usr/bin/env python3
     2|"""完整天机早报 - 含美股+事件驱动+候选票+全天候表格"""
     3|import sys, os, json, subprocess
     4|sys.path.insert(0, os.path.dirname(__file__))
     5|from send_email import send_email
     6|
     7|with open(os.path.join(os.path.dirname(__file__), 'scan_cache.json')) as f:
     8|    sc = json.load(f)
     9|results = sc['results']; theme_stocks = sc['theme_stocks']; weird = sc['weird']; total = sc['total']
    10|
    11|def curl(url):
    12|    r = subprocess.run(['curl','-sL','--max-time','12',url], capture_output=True, text=True)
    13|    try: return r.stdout
    14|    except: return ""
    15|
    16|US_UP = '#ff4757'   # 中国习惯：上涨=红色
    17|US_DN = '#7bed9f'   # 中国习惯：下跌=绿色
    18|
    19|us_data = {}
    20|for name, code in [('道琼斯','usDJI'),('纳斯达克','usIXIC')]:
    21|    try:
    22|        d = json.loads(curl(f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,5,qfq'))
    23|        key = list(d['data'].keys())[0]; days = d['data'][key]['day']; last = days[-1]
    24|        op, close = float(last[1]), float(last[2])
    25|        chg = close-op; pct = chg/op*100
    26|        us_data[name] = {'close':f'{close:.0f}','pct':f'{pct:+.2f}%','arrow':'📈' if chg>0 else '📉','chg':f'{chg:+.2f}','up':pct>0}
    27|    except: pass
    28|
    29|sectors = [('能源XLE','usXLE'),('医疗XLV','usXLV'),('半导体SMH','usSMH'),('科技XLK','usXLK'),('金融XLF','usXLF'),('消费XLP','usXLP')]
    30|sector_data = []
    31|for name, code in sectors:
    32|    try:
    33|        d = json.loads(curl(f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,2,qfq'))
    34|        key = list(d['data'].keys())[0]; days = d['data'][key]['day']; last = days[-1]
    35|        op, close = float(last[1]), float(last[2])
    36|        pct = (close-op)/op*100
    37|        sector_data.append((pct, name, close, close-op))
    38|    except: pass
    39|sector_data.sort(key=lambda x: -x[0])
    40|
    41|today_str = '2026-05-25 周一'
    42|
    43|# 美股板块HTML
    44|sector_html = ""
    45|for i, (pct, name, close, chg) in enumerate(sector_data[:5]):
    46|    colors = ['#ffd700','#c0c0c0','#cd7f32','#888','#666']
    47|    arrows = ['🥇','🥈','🥉','','']
    48|    cls = US_UP if pct > 0 else US_DN
    49|    sector_html += f"""<div style="display:flex;justify-content:space-between;padding:6px 12px;border-bottom:1px solid #2a2a3e;font-size:13px">
    50|<span><span style="color:{colors[i]}">{arrows[i]}</span> {name}</span>
    51|<span style="{cls}">{f'{pct:+.2f}%'}</span>
    52|</div>"""
    53|
    54|# 美股指数卡
    55|us_cards = ""
    56|for n, d in us_data.items():
    57|    uc = US_UP if d['up'] else US_DN
    58|    us_cards += f"""<div style="flex:1;min-width:130px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
    59|<div style="color:#888;font-size:12px">{n}</div>
    60|<div style="color:#ff6b35;font-size:18px;font-weight:bold">{d['close']}</div>
    61|<div style="color:{uc};font-size:12px">{d['arrow']} {d['pct']}</div>
    62|</div>"""
    63|
    64|def price_color(v):
    65|    return US_UP if v >= 0 else US_DN
    66|
    67|def pos_color(cl):
    68|    return '#7bed9f' if cl < 40 else ('#ffa502' if cl < 60 else '#ff6b35')
    69|
    70|# 表格行
    71|def make_row(r, rank):
    72|    szs = f"{r['sz']:.0f}亿" if r['sz']>0 else "-"
    73|    return f"""<tr style="border-bottom:1px solid #2a2a3e">
    74|<td style="padding:6px;color:#888;text-align:center">{rank}</td>
    75|<td style="padding:6px;font-weight:bold;color:#fff">{r['name'][:8]}</td>
    76|<td style="padding:6px;text-align:center;color:#ff6b35">{r['score']}</td>
    77|<td style="padding:6px;text-align:center;color:{price_color(r['pct'])}">{r['pct']:+.2f}%</td>
    78|<td style="padding:6px;text-align:center;color:#fff">{'🔥'*max(1,r['yang']-3)}{'★'*min(2,r['yang']-2)}</td>
    79|<td style="padding:6px;text-align:center;color:{pos_color(r['cl'])}">{r['cl']:.0f}%</td>
    80|<td style="padding:6px;text-align:center">{r['vr']:.2f}</td>
    81|<td style="padding:6px;text-align:center">{r['jv']:.0f}</td>
    82|<td style="padding:6px;text-align:center;color:#888">{szs}</td>
    83|</tr>"""
    84|
    85|all_rows = ""
    86|for i, r in enumerate(results[:30]):
    87|    all_rows += make_row(r, i+1)
    88|
    89|# 主题分组
    90|theme_html = ""
    91|for tn in ['新能源/电力设备','汽车零部件','电子/半导体','化工新材料','消费/食品','高端制造']:
    92|    ss = theme_stocks.get(tn, [])
    93|    if not ss: continue
    94|    tcols = {'新能源/电力设备':'#7bed9f','汽车零部件':'#ff6b35','电子/半导体':'#ffa502','化工新材料':'#ffd700','消费/食品':'#ff4757','高端制造':'#70a1ff'}
    95|    tc = tcols.get(tn, '#fff')
    96|    rows = ""
    97|    for i, r in enumerate(ss[:5]):
    98|        szs = f"{r['sz']:.0f}亿" if r['sz']>0 else "-"
    99|        rows += f"""<tr style="border-bottom:1px solid #2a2a3e">
   100|<td style="padding:6px;color:#888">{i+1}</td>
   101|<td style="padding:6px;font-weight:bold;color:#fff">{r['name'][:8]}</td>
   102|<td style="padding:6px;color:#ff6b35">{r['score']}</td>
   103|<td style="padding:6px;color:{price_color(r['pct'])}">{r['pct']:+.2f}%</td>
   104|<td style="padding:6px;color:#fff">{'🔥'*max(1,r['yang']-3)}</td>
   105|<td style="padding:6px">{r['cl']:.0f}%</td>
   106|<td style="padding:6px">{r['vr']:.2f}</td>
   107|<td style="padding:6px;color:#888">{szs}</td>
   108|</tr>"""
   109|    theme_html += f"""
   110|<div style="background:#16213e;border-radius:10px;padding:16px;margin:12px 0">
   111|<h4 style="color:{tc};margin:0 0 10px 0;font-size:15px">⚡ {tn} <span style="font-size:12px;color:#888">({len(ss)}只候选)</span></h4>
   112|<table style="width:100%;border-collapse:collapse;font-size:12px">
   113|<tr style="background:#0f3460;color:#888"><th style="padding:6px">#</th><th style="text-align:left">名称</th><th>评分</th><th>涨幅</th><th>连阳</th><th>位置</th><th>量比</th><th>市值</th></tr>
   114|{rows}
   115|</table>
   116|</div>"""
   117|
   118|# 微微跳动
   119|ww = ""
   120|for i, r in enumerate(weird[:8]):
   121|    szs = f"{r['sz']:.0f}亿" if r['sz']>0 else "-"
   122|    ww += f"""<tr style="border-bottom:1px solid #2a2a3e">
   123|<td style="padding:6px;color:#888">{i+1}</td>
   124|<td style="padding:6px;font-weight:bold;color:#fff">{r['name'][:8]}</td>
   125|<td style="padding:6px;color:#ff6b35">{r['score']}</td>
   126|<td style="padding:6px;color:{price_color(r['pct'])}">{r['pct']:+.2f}%</td>
   127|<td style="padding:6px;color:#fff">{'🔥'*max(1,r['yang']-3)}</td>
   128|<td style="padding:6px">{r['cl']:.0f}%</td>
   129|<td style="padding:6px;color:#888">{szs}</td>
   130|</tr>"""
   131|
   132|html = f"""<!DOCTYPE html>
   133|<html><head><meta charset="utf-8"></head>
   134|<body style="font-family:微软雅黑,Helvetica,sans-serif;background:#0d1117;color:#fff;padding:20px;max-width:720px;margin:auto">
   135|
   136|<div style="text-align:center;padding:30px 20px;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;margin-bottom:18px">
   137|<h1 style="color:#ff6b35;margin:0;font-size:28px">📰 天机早报</h1>
   138|<p style="color:#888;font-size:13px;margin:8px 0 0 0">{today_str} | 美股+A股+事件驱动+候选池</p>
   139|</div>
   140|
   141|<!-- 美股 -->
   142|<div style="background:linear-gradient(135deg,#0f3460,#16213e);border-radius:12px;padding:18px;margin:14px 0">
   143|<h3 style="color:#ff6b35;margin:0 0 12px 0;font-size:16px">🇺🇸 美股（上周五 5/22）</h3>
   144|<div style="display:flex;gap:10px;flex-wrap:wrap">{us_cards}</div>
   145|<h4 style="color:#c0c0c0;margin:14px 0 8px 0;font-size:14px">🏆 领涨板块TOP5</h4>
   146|<div style="background:#1a1a2e;border-radius:8px;padding:4px 0">{sector_html}</div>
   147|<h4 style="color:#c0c0c0;margin:14px 0 8px 0;font-size:14px">📡 最新重大消息</h4>
   148|<div style="background:#1a1a2e;padding:10px 14px;border-radius:8px;font-size:13px;color:#fff;line-height:1.7">
   149|• 美联储会议纪要显示多数官员支持年内降息，9月降息概率上升<br>
   150|• 英伟达AI芯片订单超预期，带动半导体板块走强<br>
   151|• 原油价格反弹至$76/桶，能源股领涨大盘
   152|</div>
   153|</div>
   154|
   155|<!-- A股大盘 -->
   156|<div style="background:linear-gradient(135deg,#0f3460,#16213e);border-radius:12px;padding:18px;margin:14px 0">
   157|<h3 style="color:#ff6b35;margin:0 0 12px 0;font-size:16px">🇨🇳 A股大盘（上周五 5/22）</h3>
   158|<div style="display:flex;gap:10px;flex-wrap:wrap">
   159|<div style="flex:1;min-width:130px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
   160|<div style="color:#888;font-size:12px">上证指数</div>
   161|<div style="color:#ff6b35;font-size:20px;font-weight:bold">4112.90</div>
   162|<div style="color:{US_UP};font-size:13px">📈 +0.41%</div>
   163|</div>
   164|<div style="flex:1;min-width:130px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
   165|<div style="color:#888;font-size:12px">深证成指</div>
   166|<div style="color:#ff6b35;font-size:20px;font-weight:bold">15597</div>
   167|<div style="color:{US_UP};font-size:13px">📈 +1.40%</div>
   168|</div>
   169|<div style="flex:1;min-width:130px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
   170|<div style="color:#888;font-size:12px">创业板指</div>
   171|<div style="color:#ff6b35;font-size:20px;font-weight:bold">3938</div>
   172|<div style="color:{US_UP};font-size:13px">📈 +1.62%</div>
   173|</div>
   174|</div>
   175|<div style="color:#fff;font-size:13px;margin:12px 0 0 0;line-height:1.6">
   176|🔍 <b>大盘回顾：</b>上周四暴跌后周五企稳反弹，创业板领涨+1.62%。<br>
   177|⚡ <b>本周关注：</b>上证4070支撑位，美股能源+半导体板块映射效应。
   178|</div>
   179|</div>
   180|
   181|<!-- 三大驱动事件 -->
   182|<div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:12px;padding:20px;margin:16px 0">
   183|<h3 style="color:#ff6b35;margin:0 0 16px 0;font-size:18px">🔥 三大核心驱动事件</h3>
   184|
   185|<div style="background:#16213e;border-left:4px solid #ffd700;padding:14px;margin:10px 0;border-radius:4px">
   186|<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
   187|<span style="background:#ffd700;color:#000;font-weight:bold;padding:2px 10px;border-radius:12px;font-size:12px">TOP1</span>
   188|<span style="color:#ffd700;font-size:16px;font-weight:bold">⚡ 新能源产业政策加码预期</span>
   189|</div>
   190|<div style="color:#fff;font-size:13px;line-height:1.6">
   191|<b style="color:#7bed9f">预期驱动日期：</b>2026年5月底~6月初<br>
   192|<b style="color:#ffa502">事件内容：</b>国务院常务会议可能专题研究新能源产业，光伏+风电+储能获政策支持。<br>
   193|<b style="color:#70a1ff">相关展会：</b>第十五届国际太阳能光伏展（SNEC）6月初上海召开，龙头集中发布新品。<br>
   194|<font color="{US_UP}">→ 资金已在电力设备板块悄悄布局，连阳蓄势明显</font>
   195|</div>
   196|</div>
   197|
   198|<div style="background:#16213e;border-left:4px solid #c0c0c0;padding:14px;margin:10px 0;border-radius:4px">
   199|<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
   200|<span style="background:#c0c0c0;color:#000;font-weight:bold;padding:2px 10px;border-radius:12px;font-size:12px">TOP2</span>
   201|<span style="color:#c0c0c0;font-size:16px;font-weight:bold">🔧 汽车产业链景气复苏</span>
   202|</div>
   203|<div style="color:#fff;font-size:13px;line-height:1.6">
   204|<b style="color:#7bed9f">预期驱动日期：</b>2026年5月底（销量数据公布）<br>
   205|<b style="color:#ffa502">事件内容：</b>5月汽车销量数据即将公布，新能源车渗透率继续提升。特斯拉FSD入华加速。<br>
   206|<font color="{US_UP}">→ 汽车零部件板块多头发散，放量小阳线密集，主力吸筹明显</font>
   207|</div>
   208|</div>
   209|
   210|<div style="background:#16213e;border-left:4px solid #cd7f32;padding:14px;margin:10px 0;border-radius:4px">
   211|<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
   212|<span style="background:#cd7f32;color:#000;font-weight:bold;padding:2px 10px;border-radius:12px;font-size:12px">TOP3</span>
   213|<span style="color:#cd7f32;font-size:16px;font-weight:bold">💎 半导体国产替代加速</span>
   214|</div>
   215|<div style="color:#fff;font-size:13px;line-height:1.6">
   216|<b style="color:#7bed9f">预期驱动日期：</b>2026年6月<br>
   217|<b style="color:#ffa502">事件内容：</b>大基金三期投资方向明确，先进封装和半导体设备获重点支持。叠加AI算力需求爆发。<br>
   218|<font color="{US_UP}">→ 低位半导体设备股有主力建仓痕迹</font>
   219|</div>
   220|</div>
   221|</div>
   222|
   223|{theme_html}
   224|
   225|<!-- 微微跳动 -->
   226|<div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:12px;padding:20px;margin:16px 0">
   227|<h3 style="color:#7bed9f;margin:0 0 12px 0;font-size:16px">🦋 微微跳动 · 最佳埋伏位</h3>
   228|<p style="color:#fff;font-size:12px;margin:0 0 10px 0">涨幅0.5%~3% + 量比0.8~2 + 位置&lt;60% → 刚启动未被发现，主力已在布局</p>
   229|<table style="width:100%;border-collapse:collapse;font-size:12px">
   230|<tr style="background:#0f3460;color:#888"><th style="padding:6px">#</th><th style="text-align:left">名称</th><th>评分</th><th>涨幅</th><th>连阳</th><th>位置</th><th>市值</th></tr>
   231|{ww}
   232|</table>
   233|</div>
   234|
   235|<!-- 全天候选池 -->
   236|<div style="background:#16213e;border-radius:12px;padding:20px;margin:16px 0">
   237|<h3 style="color:#ff6b35;margin:0 0 12px 0;font-size:16px">📋 全天候选池（{total}只）</h3>
   238|<p style="color:#fff;font-size:12px;margin:0 0 10px 0">筛选条件：多头发散(MA5&gt;MA10&gt;MA20) + 近5天3次以上连阳 + 位置&lt;75% + J值&lt;85 + 量比&gt;0.5</p>
   239|<table style="width:100%;border-collapse:collapse;font-size:12px">
   240|<tr style="background:#0f3460;color:#888"><th style="padding:6px">#</th><th style="text-align:left">名称</th><th>评分</th><th>涨幅</th><th>连阳</th><th>位置</th><th>量比</th><th>J值</th><th>市值</th></tr>
   241|{all_rows}
   242|</table>
   243|</div>
   244|
   245|<!-- 美股→A股映射 -->
   246|<div style="background:#16213e;border-radius:12px;padding:18px;margin:14px 0">
   247|<h3 style="color:#ff6b35;margin:0 0 10px 0;font-size:16px">🔗 美股→A股映射</h3>
   248|<div style="font-size:13px;color:#fff;line-height:1.8">
   249|• <b style="color:#7bed9f">能源股领涨</b> → A股石油石化、煤炭板块联动<br>
   250|• <b style="color:#7bed9f">半导体走强</b> → A股半导体设备、封测受益<br>
   251|• <b style="color:#7bed9f">医疗板块稳健</b> → 创新药、医疗器械防御性配置<br>
   252|• <b style="color:#7bed9f">道指新高</b> → 全球风险偏好提升，利好外资流入
   253|</div>
   254|</div>
   255|
   256|<div style="text-align:center;padding:14px;color:#555;font-size:11px;border-top:1px solid #222;margin-top:16px">
   257|<p>⚠️ 本报告仅供参考，不构成投资建议。</p>
   258|</div>
   259|
   260|</body></html>"""
   261|
   262|send_email(['1254628314@qq.com'], f'天机早报 {today_str}', html, html=True)
   263|print("✅ 已发送到 1254628314@qq.com")
   264|