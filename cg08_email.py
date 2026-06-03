"""
尾盘选股日报 — CG08数据+极简淡色HTML邮件
运行cg08_final.py获取数据，直接生成HTML，不走AI
"""
import subprocess, json, os, sys, re
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)

# 运行cg08选股
print('运行cg08_final.py...', flush=True)
r = subprocess.run([sys.executable, 'cg08_final.py'], capture_output=True, text=True, timeout=120)
output = r.stdout
print(f'完成 ({len(output)} chars)', flush=True)

# 解析结果：找Top10
today = datetime.now().strftime('%Y-%m-%d')
lines = output.split('\n')

# 提取股票数据行（格式：名 代码 涨% 量比 CL% ...）
stocks = []
for line in lines:
    # 匹配形如 "  1 贵州茅台 sh600519 +3.2 1.05 75.0"
    m = re.search(r'^\s*\d+\s+(\S+)\s+(\w+)\s+([+-]?\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)', line)
    if m:
        stocks.append({
            'rank': len(stocks)+1,
            'name': m.group(1),
            'code': m.group(2),
            'pct': float(m.group(3)),
            'vr': float(m.group(4)),
            'cl': float(m.group(5))
        })

# 颜色
RED = '#e06c75'
GREEN = '#98c379'
GOLD = '#e5c07b'
BG = '#1e1e2e'
CARD = '#282840'
LINE = '#3b3b5c'
TEXT = '#a0a0c0'
DIM = '#6c6c8a'
BRIGHT = '#cdd6f4'

html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{BG};font-family:-apple-system,'微软雅黑','PingFang SC',sans-serif;color:{TEXT}">
<div style="max-width:580px;margin:0 auto;padding:20px 15px">
<div style="text-align:center;padding:15px 0 12px;border-bottom:1px solid {LINE}">
<div style="font-size:13px;letter-spacing:2px;color:{DIM}">尾 盘 选 股</div>
<div style="font-size:11px;color:{DIM};margin-top:4px">{today} · 候选 {len(stocks)} 只 · CG08评分</div>
</div>'''

if not stocks:
    html += f'<div style="margin-top:20px;padding:25px;text-align:center;border:1px solid {LINE};border-radius:6px;color:{DIM}">❌ 今日无候选</div>'
else:
    medals = ['①', '②', '③']
    for i, s in enumerate(stocks[:3]):
        pct_str = f'+{s["pct"]:.1f}%' if s['pct'] > 0 else f'{s["pct"]:.1f}%'
        html += f'''
<div style="background:{CARD};border-radius:6px;padding:12px 14px;margin-top:8px">
<div style="display:flex;align-items:center;gap:6px">
<span style="font-size:11px;color:{DIM}">{medals[i]}</span>
<span style="font-size:12px;color:{BRIGHT}">{s['name'][:8]}</span>
<span style="font-size:10px;color:{DIM}">{s['code'][-6:]}</span>
</div>
<div style="display:flex;gap:10px;margin-top:6px;font-size:11px;color:{TEXT}">
<div><span style="color:{DIM}">涨幅</span> <span style="color:{RED}">{pct_str}</span></div>
<div><span style="color:{DIM}">量比</span> {s['vr']:.2f}</div>
<div><span style="color:{DIM}">CL</span> {s['cl']:.0f}%</div>
</div>
</div>'''
    
    # 全部候选表
    html += f'''
<div style="margin-top:16px;font-size:11px;color:{DIM}">全部候选</div>
<div style="background:{CARD};border-radius:6px;overflow:hidden;margin-top:4px">
<table style="width:100%;border-collapse:collapse;font-size:10px">
<tr style="border-bottom:1px solid {LINE}">
<th style="padding:7px 3px;text-align:center;color:{DIM};font-weight:400">#</th>
<th style="padding:7px 3px;text-align:center;color:{DIM};font-weight:400">名称</th>
<th style="padding:7px 3px;text-align:center;color:{DIM};font-weight:400">涨%</th>
<th style="padding:7px 3px;text-align:center;color:{DIM};font-weight:400">量比</th>
<th style="padding:7px 3px;text-align:center;color:{DIM};font-weight:400">CL%</th>
</tr>'''
    
    for i, s in enumerate(stocks[:20]):
        bg = 'transparent' if i % 2 == 0 else f'{BG}66'
        pct_str = f'+{s["pct"]:.1f}' if s['pct'] > 0 else f'{s["pct"]:.1f}'
        html += f'<tr style="background:{bg};border-bottom:1px solid {LINE}33">'
        html += f'<td style="padding:5px 3px;text-align:center;color:{DIM}">{i+1}</td>'
        html += f'<td style="padding:5px 3px;text-align:center;color:{BRIGHT}">{s["name"][:6]}</td>'
        html += f'<td style="padding:5px 3px;text-align:center;color:{RED}">{pct_str}</td>'
        html += f'<td style="padding:5px 3px;text-align:center;color:{DIM}">{s["vr"]:.2f}</td>'
        html += f'<td style="padding:5px 3px;text-align:center">{s["cl"]:.0f}</td>'
        html += '</tr>'
    
    html += '</table></div>'

html += f'''
<div style="text-align:center;font-size:9px;color:{DIM};padding:15px 0 5px;border-top:1px solid {LINE};margin-top:15px">
CG08评分 · 涨跌幅×1 + ATR×1.5 + DIF×0.5 + 收盘位×0.02
</div>
</div>
</body>
</html>'''

# 发邮件
from send_email import send_email
send_email(['1254628314@qq.com'], f'尾盘选股-每日推荐 {today}', html, html=True)
print(f'✅ 已发送 - {today} 候选{len(stocks)}只')
