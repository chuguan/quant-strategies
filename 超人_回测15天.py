"""
超人策略 v6 — 最近15个交易日回测报告
CL排序版 · 每日详情 · 发送3人
"""
import pickle, json, os, sys
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(SCRIPTS_DIR)

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())

p_min,p_max=5,8; vr_min,vr_max=1.0,1.5; hsl_min,hsl_max=5,15; sz_max=200; cl_min,cl_max=60,90; j_max=100

target_dates = [d for d in dates if d >= '2026-04-29'][-15:]
print(f'回测: {target_dates[0]} ~ {target_dates[-1]} ({len(target_dates)}天)')

# ===== 回测 =====
results = []
for dt in target_dates:
    stocks = data[dt]
    cand = []
    for s in stocks:
        code, p = s['code'], s['p']
        if p < p_min or p > p_max: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < vr_min or vr > vr_max: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < hsl_min or hsl > hsl_max: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= sz_max: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > j_max: continue
        cl = s.get('cl',0)
        if cl < cl_min or cl > cl_max: continue
        buy_c = s.get('close', 0)
        n_val = s.get('n',0) or 0
        
        next_high = 0; next_close = 0; d1_d5 = ['—']*5
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    kdata = json.load(f)
                idx = next((i for i,k in enumerate(kdata) if k['date']==dt), None)
                if idx is not None:
                    if idx+1 < len(kdata):
                        next_high = (kdata[idx+1]['high']/buy_c-1)*100
                        next_close = (kdata[idx+1]['close']/buy_c-1)*100
                    for d in range(5):
                        if idx+1+d < len(kdata):
                            hv = kdata[idx+1+d]["high"]
                            d1_d5[d] = f'{(hv/buy_c-1)*100:.1f}'
            except: pass
        
        macd_g = '金' if s.get('macd_golden',0) else ''
        kdj_g = '金' if s.get('kdj_golden',0) else ''
        trend = f'{macd_g}{kdj_g}'
        
        cand.append((cl, nm, code, p, vr, cl, hsl, sz, buy_c, next_high, next_close, jv, trend, d1_d5))
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[3]))
    results.append({'dt':dt, 'cand':cand, 'total':len(cand)})

# ===== 颜色 =====
RED='#e06c75'; GREEN='#98c379'; GOLD='#e5c07b'; ORANGE='#d19a66'
BG='#1a1b2e'; CARD='#252640'; LINE='#3a3b5c'; TEXT='#b0b0d0'; DIM='#7a7a9a'; BRIGHT='#d0d0e8'

def pct(v):
    try:
        v = float(v)
        if v > 0: return f'<span style="color:{RED}">+{v:.1f}%</span>'
        if v < 0: return f'<span style="color:{GREEN}">{v:.1f}%</span>'
        return f'<span style="color:{DIM}">0.0%</span>'
    except: return f'<span style="color:{DIM}">{v}</span>'

# ===== 构建HTML =====
html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:15px;background:{BG};font-family:-apple-system,'微软雅黑','PingFang SC',sans-serif;color:{TEXT};font-size:13px">
<div style="max-width:800px;margin:0 auto;background:{BG};border-radius:10px">

<div style="text-align:center;padding:22px 15px 14px;border-bottom:2px solid #d4a84b;background:linear-gradient(180deg,#2a2b4e 0%,{BG} 100%)">
<div style="font-size:22px;font-weight:800;letter-spacing:5px;color:#d4a84b;text-shadow:0 0 20px rgba(212,168,75,0.3)">超 人 战 略 · 近15日回测</div>
<div style="font-size:11px;color:{DIM};margin-top:6px;letter-spacing:1px">{target_dates[0]} ~ {target_dates[-1]} · {len(target_dates)}个交易日 · CL排序版</div>
</div>'''

# ===== 汇总卡片 =====
champ_highs = []; champ_closes = []; second_highs = []; third_highs = []
for r in results:
    c = r['cand']
    ch = c[0][9]; cc = c[0][10]
    sh = c[1][9] if len(c)>1 else 0
    th = c[2][9] if len(c)>2 else 0
    champ_highs.append(ch); champ_closes.append(cc); second_highs.append(sh); third_highs.append(th)

n = len(results)
c25 = sum(1 for v in champ_highs if v>=2.5)
c5 = sum(1 for v in champ_highs if v>=5)
s25 = sum(1 for v in second_highs if v>=2.5)
t25 = sum(1 for v in third_highs if v>=2.5)
any25 = sum(1 for i in range(n) if champ_highs[i]>=2.5 or second_highs[i]>=2.5 or third_highs[i]>=2.5)
avg_ch = sum(champ_highs)/n
avg_cc = sum(champ_closes)/n

html += f'''
<div style="padding:12px 15px">
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;text-align:center;font-size:11px">
<div style="background:{CARD};border-radius:6px;padding:8px 4px">
<div style="color:{DIM}">🥇 冠军2.5%</div>
<div style="color:{RED};font-size:16px;font-weight:700;margin-top:2px">{c25*100/n:.1f}%</div>
<div style="color:{DIM};font-size:9px">{c25}/{n}天</div>
</div>
<div style="background:{CARD};border-radius:6px;padding:8px 4px">
<div style="color:{DIM}">🥈 亚军2.5%</div>
<div style="color:{ORANGE};font-size:16px;font-weight:700;margin-top:2px">{s25*100/n:.1f}%</div>
<div style="color:{DIM};font-size:9px">{s25}/{n}天</div>
</div>
<div style="background:{CARD};border-radius:6px;padding:8px 4px">
<div style="color:{DIM}">🥉 季军2.5%</div>
<div style="color:{GREEN};font-size:16px;font-weight:700;margin-top:2px">{t25*100/n:.1f}%</div>
<div style="color:{DIM};font-size:9px">{t25}/{n}天</div>
</div>
<div style="background:{CARD};border-radius:6px;padding:8px 4px">
<div style="color:{DIM}">🏆 前三任意</div>
<div style="color:{GOLD};font-size:16px;font-weight:700;margin-top:2px">{any25*100/n:.1f}%</div>
<div style="color:{DIM};font-size:9px">{any25}/{n}天</div>
</div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px;text-align:center;font-size:11px">
<div style="background:{CARD};border-radius:6px;padding:6px 4px">
<span style="color:{DIM}">冠军均最高涨幅</span>
<span style="color:{BRIGHT};font-size:14px;font-weight:600;margin-left:4px">+{avg_ch:.2f}%</span>
</div>
<div style="background:{CARD};border-radius:6px;padding:6px 4px">
<span style="color:{DIM}">冠军均收盘涨幅</span>
<span style="color:{BRIGHT};font-size:14px;font-weight:600;margin-left:4px">{avg_cc:+.2f}%</span>
</div>
</div>'''

# ===== 每日详情 =====
html += f'''
<div style="margin-top:8px;padding:0 15px">
<div style="background:{CARD};border-radius:6px;overflow-x:auto;-webkit-overflow-scrolling:touch">
<table style="min-width:700px;border-collapse:collapse;font-size:10px;white-space:nowrap">
<tr style="border-bottom:1px solid {LINE}">
<th style="padding:6px 3px;text-align:center;color:{DIM};font-weight:400;min-width:70px">日期</th>
<th style="padding:6px 3px;text-align:center;color:{DIM};font-weight:400;min-width:80px">冠军</th>
<th style="padding:6px 3px;text-align:center;color:{DIM};font-weight:400;min-width:40px">候选</th>
<th style="padding:6px 3px;text-align:center;color:{DIM};font-weight:400;min-width:44px">买入</th>
<th style="padding:6px 3px;text-align:center;color:{DIM};font-weight:400;min-width:40px">涨%</th>
<th style="padding:6px 3px;text-align:center;color:{DIM};font-weight:400;min-width:40px">CL%</th>
<th style="padding:6px 3px;text-align:center;color:{DIM};font-weight:400;min-width:44px">次日高%</th>
<th style="padding:6px 3px;text-align:center;color:{DIM};font-weight:400;min-width:44px">次日收%</th>
<th style="padding:6px 3px;text-align:center;color:{DIM};font-weight:400;min-width:36px">趋势</th>
<th style="padding:6px 3px;text-align:center;color:{DIM};font-weight:400;min-width:36px">达标</th>
</tr>'''

for r in results:
    c = r['cand'][0]
    nm, code = c[1], c[2][-6:]
    ch_str = f'+{c[9]:.1f}%' if c[9]>0 else (f'{c[9]:.1f}%' if c[9]!=0 or c[9]==0 else 'N/A')
    cc_str = f'+{c[10]:.1f}%' if c[10]>0 else (f'{c[10]:.1f}%' if c[10]!=0 else 'N/A')
    ok_mark = '🔥' if c[9]>=5 else ('✅' if c[9]>=2.5 else '❌')
    bg_r = 'transparent'
    html += f'<tr style="background:{bg_r};border-bottom:1px solid {LINE}33">'
    html += f'<td style="padding:5px 3px;text-align:center;color:{DIM}">{r["dt"][5:]}</td>'
    html += f'<td style="padding:5px 3px;text-align:center;color:{BRIGHT}">{nm[:6]}</td>'
    html += f'<td style="padding:5px 3px;text-align:center;color:{DIM}">{r["total"]}</td>'
    html += f'<td style="padding:5px 3px;text-align:center;color:{BRIGHT}">{c[8]:.2f}</td>'
    html += f'<td style="padding:5px 3px;text-align:center;color:{RED}">+{c[3]:.1f}</td>'
    html += f'<td style="padding:5px 3px;text-align:center;color:{BRIGHT}">{c[0]:.0f}</td>'
    html += f'<td style="padding:5px 3px;text-align:center">{"<span style=color:RED>"+ch_str+"</span>" if c[9]>0 else ("<span style=color:GREEN>"+ch_str+"</span>" if c[9]<0 else "<span style=color:DIM>"+ch_str+"</span>")}</td>'
    html += f'<td style="padding:5px 3px;text-align:center">{cc_str}</td>'
    html += f'<td style="padding:5px 3px;text-align:center;color:{GOLD};font-size:9px">{c[12]}</td>'
    html += f'<td style="padding:5px 3px;text-align:center;font-size:12px">{ok_mark}</td>'
    html += '</tr>'

html += '</table></div></div>'

# ===== 近5天Top3详情 =====
html += f'<div style="margin-top:12px;padding:0 15px">'
recent5 = results[-5:] if len(results)>=5 else results
for r in reversed(recent5):
    html += f'<div style="background:{CARD};border-radius:6px;padding:8px 10px;margin-top:6px">'
    html += f'<div style="font-size:10px;color:{GOLD};font-weight:600;margin-bottom:4px">{r["dt"]} · {r["total"]}只候选</div>'
    for i, c in enumerate(r['cand'][:3]):
        h_str = f'+{c[9]:.1f}%' if c[9]>0 else (f'{c[9]:.1f}%' if c[9]!=0 else 'N/A')
        ok2 = '🔥' if c[9]>=5 else ('✅' if c[9]>=2.5 else '')
        html += f'<div style="font-size:9px;color:{TEXT}">'
        html += f'{"🥇" if i==0 else ("🥈" if i==1 else "🥉")} {c[1][:8]} 买{c[8]:.2f} 涨+{c[3]:.1f}% CL{c[0]:.0f}% → 高{h_str} {ok2}'
        html += '</div>'
    html += '</div>'
html += '</div>'

# 底部
html += f'''
<div style="text-align:center;font-size:9px;color:{DIM};padding:12px 15px 5px;border-top:1px solid {LINE};margin-top:12px;line-height:1.6">
涨5~8% · 量比1.0~1.5 · 换手5~15% · 市值&lt;200亿 · CL 60~90% · CL降序<br>
<span style="color:{RED}">红涨</span> · <span style="color:{GREEN}">绿跌</span> · 数据源: big_cache_full.pkl
</div>
</div>
</body></html>'''

# ===== 发送 =====
subject = f'超人策略近15日回测 {target_dates[0]}~{target_dates[-1]}'
sys.path.insert(0, SCRIPTS_DIR)
from send_email import send_email
send_email(['1254628314@qq.com','314913203@qq.com'], subject, html, html=True)

# 存档
ARCHIVE_DIR = os.path.expanduser('~/AppData/Local/hermes/email_archive')
os.makedirs(ARCHIVE_DIR, exist_ok=True)
with open(os.path.join(ARCHIVE_DIR, f'{target_dates[-1]}_回测15天.html'), 'w', encoding='utf-8') as f:
    f.write(html)

print(f'✅ 已发送 - 15日回测 {target_dates[0]}~{target_dates[-1]} | 冠军2.5%:{c25*100/n:.1f}% 前三:{any25*100/n:.1f}%')
