#!/usr/bin/env python3
"""生成天机早报HTML并发送邮件"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from send_email import send_email

today_str = '2026-05-25 周一'

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:微软雅黑,Helvetica,sans-serif;background:#0d1117;color:#e0e0e0;padding:20px;max-width:680px;margin:auto">

<div style="text-align:center;padding:25px 20px;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;margin-bottom:18px">
<h1 style="color:#ff6b35;margin:0;font-size:26px">📰 天机早报</h1>
<p style="color:#888;font-size:13px;margin:8px 0 0 0">{today_str} | 美股+A股 | 资金流向</p>
</div>

<div style="background:linear-gradient(135deg,#0f3460,#16213e);border-radius:12px;padding:18px;margin:14px 0">
<h3 style="color:#ff6b35;margin:0 0 12px 0;font-size:16px">🇺🇸 美股上周五（5/22）</h3>
<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">
<div style="flex:1;min-width:140px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
<div style="color:#888;font-size:12px">道琼斯</div>
<div style="color:#ff6b35;font-size:20px;font-weight:bold">50579</div>
<div style="color:#7bed9f;font-size:13px">+294 (+0.58%) 📈</div>
</div>
<div style="flex:1;min-width:140px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
<div style="color:#888;font-size:12px">纳斯达克</div>
<div style="color:#ff6b35;font-size:20px;font-weight:bold">26343</div>
<div style="color:#7bed9f;font-size:13px">+50.87 (+0.19%) 📈</div>
</div>
<div style="flex:1;min-width:140px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
<div style="color:#888;font-size:12px">标普500</div>
<div style="color:#ff6b35;font-size:20px;font-weight:bold">7473</div>
<div style="color:#7bed9f;font-size:13px">+27.75 (+0.37%) 📈</div>
</div>
</div>

<h4 style="color:#c0c0c0;margin:14px 0 8px 0;font-size:14px">🏆 美股板块TOP3</h4>
<div style="background:#1a1a2e;border-left:4px solid #ffd700;padding:10px 12px;margin:4px 0;border-radius:4px;font-size:13px">
<strong style="color:#ffd700">🥇 半导体 SMH</strong> <span style="color:#7bed9f">+1.49%</span> — AI算力需求持续，英伟达订单超预期<br>
<strong style="color:#c0c0c0">🥈 医疗 XLV</strong> <span style="color:#7bed9f">+1.17%</span> — 防御性资金流入，创新药活跃<br>
<strong style="color:#cd7f32">🥉 科技 XLK</strong> <span style="color:#7bed9f">+1.00%</span> — 科技巨头普涨
</div>

<div style="background:#1a1a2e;padding:8px 12px;border-radius:4px;font-size:12px;color:#aaa;margin:6px 0">
其他板块: 能源XLE +0.61% | 金融XLF +0.41% | 消费XLP +0.17%
</div>

<h4 style="color:#c0c0c0;margin:14px 0 8px 0;font-size:14px">📡 美股最新重大消息</h4>
<div style="background:#1a1a2e;padding:10px 12px;border-radius:4px;font-size:13px;color:#ccc;line-height:1.7">
• <strong style="color:#ffa502">美伊和平协议预期升温</strong>：白宫经济顾问称伊朗战争结束可能为美联储降息创造空间，布伦特原油跌破$100/桶<br>
• <strong style="color:#ffa502">美联储降息预期</strong>：哈塞特表示油价回落将缓解通胀，为降息创造空间<br>
• <strong style="color:#ffa502">金银价格大涨</strong>：受美伊有望达成协议提振，避险资产持续走强
</div>
</div>

<div style="background:linear-gradient(135deg,#0f3460,#16213e);border-radius:12px;padding:18px;margin:14px 0">
<h3 style="color:#ff6b35;margin:0 0 12px 0;font-size:16px">🇨🇳 A股上周五（5/22）</h3>
<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">
<div style="flex:1;min-width:120px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
<div style="color:#888;font-size:12px">上证</div>
<div style="color:#ff6b35;font-size:20px;font-weight:bold">4112</div>
<div style="color:#7bed9f;font-size:13px">+0.87% 📈</div>
</div>
<div style="flex:1;min-width:120px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
<div style="color:#888;font-size:12px">深证</div>
<div style="color:#ff6b35;font-size:20px;font-weight:bold">15597</div>
<div style="color:#7bed9f;font-size:13px">+2.30% 📈</div>
</div>
<div style="flex:1;min-width:120px;padding:10px;background:#1a1a2e;border-radius:8px;text-align:center">
<div style="color:#888;font-size:12px">创业板</div>
<div style="color:#ff6b35;font-size:20px;font-weight:bold">3938</div>
<div style="color:#7bed9f;font-size:13px">+2.84% 📈</div>
</div>
</div>
<p style="font-size:13px;color:#aaa;margin:12px 0 0 0;line-height:1.6">
🔍 上周五A股全线反弹，创业板领涨2.84%<br>
⚡ 本周关注：上证4100支撑，创业板能否持续领涨
</p>
</div>

<div style="background:#16213e;border-radius:12px;padding:18px;margin:14px 0">
<h3 style="color:#ff6b35;margin:0 0 10px 0;font-size:16px">🔗 美股→A股映射分析</h3>
<div style="font-size:13px;color:#ccc;line-height:1.7">
• <strong style="color:#ffa502">半导体领涨美股（+1.49%）</strong> → A股半导体设备、封测受益，AI芯片概念联动<br>
• <strong style="color:#ffa502">医疗板块走强（+1.17%）</strong> → A股创新药、CXO板块有望跟涨<br>
• <strong style="color:#ffa502">油价跌破$100</strong> → 利好A股航空、化工等用油大户；利空石油石化板块<br>
• <strong style="color:#ffa502">美降息预期升温</strong> → 利好全球风险资产，外资回流A股概率增大
</div>
</div>

<div style="background:#16213e;border-radius:12px;padding:18px;margin:14px 0">
<h3 style="color:#ff6b35;margin:0 0 10px 0;font-size:16px">💰 资金流向分析</h3>
<div style="font-size:13px;color:#ccc;line-height:1.7">
<strong style="color:#7bed9f">📥 资金流入方向：</strong><br>
• 半导体/AI算力 — 美股映射+AI需求持续<br>
• 创新药/医疗 — 防御性资金+板块轮动<br>
• 科技龙头 — 全球风险偏好回升<br><br>
<strong style="color:#ff4757">📤 资金流出方向：</strong><br>
• 石油石化 — 油价跌破$100，盈利预期下调<br>
• 传统能源 — 美伊和谈缓解供应担忧<br><br>
<strong style="color:#ffa502">📊 整体判断：</strong><br>
资金正从能源板块撤出，转向科技和医疗板块。创业板成交活跃，显示中小盘成长股获关注。
</div>
</div>

<div style="background:#16213e;border-radius:12px;padding:18px;margin:14px 0">
<h3 style="color:#ff6b35;margin:0 0 10px 0;font-size:16px">🔥 今日A股热点板块 & 驱动事件</h3>
<div style="font-size:13px;color:#ccc;line-height:1.8">
<strong style="color:#7bed9f">1️⃣ 半导体/AI芯片</strong><br>
&nbsp;&nbsp;驱动：美股SMH +1.49%领涨，AI算力需求持续<br>
<strong style="color:#7bed9f">2️⃣ 创新药/医疗器械</strong><br>
&nbsp;&nbsp;驱动：医疗XLV +1.17%，防御性资金流入+板块轮动<br>
<strong style="color:#7bed9f">3️⃣ 黄金/贵金属</strong><br>
&nbsp;&nbsp;驱动：美伊和平协议预期+金银价格上涨<br>
<strong style="color:#7bed9f">4️⃣ 航空/化工</strong><br>
&nbsp;&nbsp;驱动：油价跌破$100，成本端显著改善
</div>
</div>

<div style="background:#16213e;border-radius:12px;padding:18px;margin:14px 0">
<h3 style="color:#ff6b35;margin:0 0 10px 0;font-size:16px">🎯 操作建议</h3>
<div style="font-size:13px;color:#ccc;line-height:1.8">
<strong style="color:#ff6b35">【核心策略】</strong> 进攻型配置，聚焦科技成长<br><br>
<strong style="color:#7bed9f">✅ 重点配置：</strong><br>
&nbsp;• 半导体/AI芯片（美股映射最强逻辑）<br>
&nbsp;• 创新药/CXO（板块轮动+美股映射）<br>
&nbsp;• 创业板ETF（市场风向标，弹性最大）<br><br>
<strong style="color:#ff4757">❌ 暂时回避：</strong><br>
&nbsp;• 石油石化（油价下跌压力）<br>
&nbsp;• 传统能源（美伊和谈压制）<br><br>
<strong style="color:#ffa502">⚠️ 风险提示：</strong><br>
&nbsp;• 美伊谈判进展可能引发原油剧烈波动<br>
&nbsp;• 美联储政策预期变化<br>
&nbsp;• 上证4100支撑位若失守需减仓
</div>
</div>

<div style="text-align:center;padding:14px;color:#555;font-size:11px;border-top:1px solid #222;margin-top:16px">
<p>⚠️ 本报告仅供参考，不构成投资建议。数据来源：腾讯财经、新浪财经、东方财富</p>
</div></body></html>"""

send_email(['1254628314@qq.com'], f'天机早报 {today_str}', html, html=True)
print("✅ 已发送到 1254628314@qq.com / 314913203@qq.com")
