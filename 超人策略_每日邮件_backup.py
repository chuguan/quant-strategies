"""
超人策略 v6 — 每日尾盘选股邮件推送（CL排序版）
全新模板：名称/编码/当前价/当前涨幅/次日涨幅/次日最高涨幅/所属板块/未来趋势/资金情况/AI综合打分/D+1~D+5每日最高价涨幅
淡色字体 · 红涨绿跌 · 深色背景
"""
import pickle, os, sys, json, re, time
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(SCRIPTS_DIR)

# ========== 加载缓存 ==========
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())

today = datetime.now().strftime('%Y-%m-%d')
# 使用最新可用日期
sel_date = today if today in data else dates[-1]

# ========== 参数（最新高胜率v6 - CL排序版） ==========
PARAMS = {
    'p_min': 5, 'p_max': 8,          # 涨幅5~8%
    'vr_min': 1.0, 'vr_max': 1.5,    # 量比1.0~1.5
    'hsl_min': 5, 'hsl_max': 15,     # 换手5~15%
    'sz_max': 200,                    # 市值<200亿
    'cl_min': 60, 'cl_max': 90,       # CL 60~90%
    'j_max': 100,                     # J<100
}

# ========== 选股 ==========
stocks = data.get(sel_date, [])
cand = []
for s in stocks:
    code, p = s['code'], s['p']
    if p < PARAMS['p_min'] or p > PARAMS['p_max']: continue
    vr = s.get('vol_ratio', 0) or 0
    if vr < PARAMS['vr_min'] or vr > PARAMS['vr_max']: continue
    ri = real.get(code)
    if not ri: continue
    hsl = (ri.get('hsl', 0) or 0)
    if hsl < PARAMS['hsl_min'] or hsl > PARAMS['hsl_max']: continue
    sz = (ri.get('shizhi', 0) or 0)
    if sz >= PARAMS['sz_max']: continue
    nm = names.get(code, '')
    if 'ST' in nm or '*ST' in nm or '退' in nm: continue
    jv = s.get('j_val', 0) or 0
    if jv > PARAMS['j_max']: continue
    cl = s.get('cl', 0)
    if cl < PARAMS['cl_min'] or cl > PARAMS['cl_max']: continue

    buy_c = s.get('close', 0)
    n_val = s.get('n', 0) or 0        # 次日最高涨幅%
    
    # MACD/KDJ 趋势判断
    macd_golden = s.get('macd_golden', 0)   # MACD金叉
    kdj_golden = s.get('kdj_golden', 0)     # KDJ金叉
    dif_val = s.get('dif_val', 0) or 0
    is_yang = s.get('is_yang', 0)           # 收阳?
    above_ma5 = s.get('above_ma5', 0)       # 站上5日线?
    
    # 未来趋势标签
    trend_signals = []
    score_bonus = 0
    if macd_golden:
        trend_signals.append('MACD金叉')
        score_bonus += 10
    if kdj_golden:
        trend_signals.append('KDJ金叉')
        score_bonus += 8
    if dif_val > 0:
        trend_signals.append('DIF>0')
        score_bonus += 5
    if is_yang:
        trend_signals.append('收阳')
        score_bonus += 3
    if above_ma5:
        trend_signals.append('站上5日线')
        score_bonus += 5
    if cl >= 75:
        trend_signals.append('近高位')
        score_bonus += 3
    elif cl <= 65:
        trend_signals.append('近低位')
    trend_label = '↑' + ' '.join(trend_signals) if trend_signals else '→ 横盘'
    
    # 资金情况（从缓存估算）
    liangbi = ri.get('liangbi', 0) or 0
    if vr > 1.2 and liangbi > 1.0:
        fund_label = '🔥 放量流入'
    elif vr > 1.0:
        fund_label = '📈 温和放量'
    elif vr > 0.8:
        fund_label = '➡ 量能正常'
    else:
        fund_label = '📉 缩量'
    
    # AI综合打分（基于技术指标）
    score = 0
    # 涨幅分：5~6.5%最佳
    if 5.5 <= p <= 6.5:
        score += 30
    elif 5 <= p <= 7:
        score += 25
    elif p <= 7.5:
        score += 20
    else:
        score += 10
    # 收盘位分：70~85%最佳
    if 70 <= cl <= 85:
        score += 25
    elif 65 <= cl <= 90:
        score += 20
    else:
        score += 10
    # 量比分：1.0~1.2最佳
    if 1.0 <= vr <= 1.2:
        score += 20
    elif 1.0 <= vr <= 1.5:
        score += 15
    else:
        score += 5
    # 换手分
    if 5 <= hsl <= 10:
        score += 10
    elif hsl <= 15:
        score += 5
    # MACD/KDJ加分
    score += score_bonus
    # J值扣分
    if jv > 80:
        score -= 5
    if jv > 90:
        score -= 10
    
    # D+1~D+5 每日最高价相对买入价涨幅
    d1_h5 = ['—'] * 5
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if os.path.exists(fp):
        try:
            with open(fp, 'r') as f:
                kdata = json.load(f)
            idx = next((i for i, k in enumerate(kdata) if k['date'] == sel_date), None)
            if idx is not None:
                for d in range(1, 6):
                    if idx + d < len(kdata):
                        kd = kdata[idx + d]
                        high_pct = (kd['high'] / buy_c - 1) * 100 if buy_c > 0 else 0
                        d1_h5[d-1] = f'{high_pct:.1f}'
        except:
            pass
    
    cand.append({
        'rank': 0, 'nm': nm, 'code': code, 'buy_c': buy_c,
        'p': p, 'vr': vr, 'cl': cl, 'hsl': hsl, 'sz': sz,
        'jv': jv, 'n_val': n_val, 'score': score,
        'trend': trend_label, 'fund': fund_label,
        'd1': d1_h5[0], 'd2': d1_h5[1], 'd3': d1_h5[2], 'd4': d1_h5[3], 'd5': d1_h5[4],
        'next_close_pct': '—',  # 次日收盘涨幅
        'pe': ri.get('pe', 0) or 0,
    })

# CL降序排序（最优参数）
cand.sort(key=lambda x: (-x['cl'], -x['p']))

# 次日涨幅（收盘涨幅）— 从K-line计算
for c in cand:
    if c['d1'] != '—':
        # D+1最高已经拿到了，但要计算收盘涨幅
        fp = os.path.join(CACHE_DIR, f'{c["code"]}.json')
        if os.path.exists(fp):
            try:
                with open(fp, 'r') as f:
                    kdata = json.load(f)
                idx = next((i for i, k in enumerate(kdata) if k['date'] == sel_date), None)
                if idx is not None and idx + 1 < len(kdata):
                    next_close = kdata[idx+1]['close']
                    c['next_close_pct'] = f'{(next_close/c["buy_c"]-1)*100:.1f}'
            except:
                pass

total = len(cand)

# ========== 颜色调色板（淡色系） ==========
RED = '#e06c75'       # 涨（柔和红）
GREEN = '#98c379'     # 跌（柔和绿）
GOLD = '#e5c07b'      # 金色
ORANGE = '#d19a66'    # 橙色
BG = '#1a1b2e'        # 深色背景
CARD = '#252640'      # 卡片底
LINE = '#3a3b5c'      # 分割线
TEXT = '#b0b0d0'      # 淡灰紫主色
DIM = '#7a7a9a'       # 更淡
BRIGHT = '#d0d0e8'    # 亮白
HEAD = '#8a8aba'      # 表头

def pct_color(val_str):
    """返回涨幅颜色，红涨绿跌（中国习惯）"""
    try:
        v = float(val_str)
        if v > 0: return RED
        if v < 0: return GREEN
    except:
        pass
    return DIM

def pct_format(val_str, suffix='%'):
    """格式化为带颜色的涨幅"""
    try:
        v = float(val_str)
        if v > 0: return f'<span style="color:{RED}">+{v:.1f}{suffix}</span>'
        if v < 0: return f'<span style="color:{GREEN}">{v:.1f}{suffix}</span>'
        return f'<span style="color:{DIM}">0.0{suffix}</span>'
    except:
        return f'<span style="color:{DIM}">{val_str}</span>'

# ========== 构建HTML ==========
def build_html():
    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:15px;background:{BG};font-family:-apple-system,'微软雅黑','PingFang SC',sans-serif;color:{TEXT};font-size:13px">

<div style="max-width:680px;margin:0 auto;background:{BG};border-radius:10px">

<!-- 头部 — 霸气大标题 -->
<div style="text-align:center;padding:22px 15px 14px;border-bottom:2px solid #d4a84b;background:linear-gradient(180deg,#2a2b4e 0%,{BG} 100%)">
<div style="font-size:22px;font-weight:800;letter-spacing:5px;color:#d4a84b;text-shadow:0 0 20px rgba(212,168,75,0.3)">尾盘选股 · 每日推荐</div>
<div style="font-size:12px;color:{GOLD};margin-top:6px;letter-spacing:2px">⚡ 主推荐前三</div>
<div style="font-size:10px;color:{DIM};margin-top:4px;line-height:1.7">
<div>🥇 冠军达2.5%胜率：<span style="color:{RED}">69.0%</span></div>
<div>🥈 亚军达2.5%胜率：<span style="color:{ORANGE}">44.0%</span></div>
<div>🥉 季军达2.5%胜率：<span style="color:#98c379">32.1%</span></div>
<div>🏆 前三任意达2.5%胜率：<span style="color:{GOLD}">86.9%</span></div>
</div>
<div style="font-size:11px;color:{DIM};margin-top:4px;letter-spacing:1px">{sel_date} · 候选 {total} 只 · CL排序 · 涨5~8%</div>
</div>'''
    if not cand:
        html += f'<div style="padding:30px;text-align:center;color:{DIM}">❌ 今日无候选</div>'
        html += '</div></body></html>'
        return html
    
    # ========== Top3 卡片 ==========
    medals = ['🥇', '🥈', '🥉']
    medal_colors = ['#d4a84b', '#a0a0c0', '#8a7a5a']
    
    html += '<div style="padding:10px 0">'
    
    for i, c in enumerate(cand[:3]):
        d1_str = c['d1'] if c['d1'] != '—' else '待确认'
        nc_str = c['next_close_pct'] if c['next_close_pct'] != '—' else '待确认'
        
        html += f'''
<div style="background:{CARD};border-radius:8px;padding:12px 14px;margin-top:8px;border-left:3px solid {medal_colors[i]}">
<div style="display:flex;align-items:center;justify-content:space-between">
<div style="display:flex;align-items:center;gap:6px">
<span style="font-size:14px">{medals[i]}</span>
<span style="font-size:14px;color:{BRIGHT};font-weight:600">{c['nm'][:8]}</span>
<span style="font-size:11px;color:{DIM}">{c['code'][-6:]}</span>
</div>
<span style="font-size:11px;color:{DIM}">综合分 {c['score']}</span>
</div>
<!-- 数据网格：4列 -->
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-top:8px;font-size:11px">
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">买入</div>
<div style="color:{BRIGHT};font-size:12px;font-weight:600">{c['buy_c']:.2f}</div>
</div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">当日涨</div>
<div style="font-size:12px">{pct_format(str(c['p']).replace("+",""))}</div>
</div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">次日涨幅</div>
<div style="font-size:12px">{pct_format(nc_str.replace("+",""))}</div>
</div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">次日最高价涨幅</div>
<div style="font-size:12px">{pct_format(d1_str.replace("+",""))}</div>
</div>
</div>
<!-- 网格：5列 -->
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr;gap:6px;margin-top:6px;font-size:11px">
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">CL</span><br><span style="color:{GOLD}">{c['cl']:.0f}%</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">量比</span><br><span style="color:{BRIGHT}">{c['vr']:.2f}</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">换手</span><br><span style="color:{BRIGHT}">{c['hsl']:.1f}%</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">市值</span><br><span style="color:{BRIGHT}">{c['sz']:.0f}亿</span></div>
<div style="text-align:center;padding:2px 0"><span style="color:{DIM}">PE</span><br><span style="color:{BRIGHT}">{c['pe']:.1f}</span></div>
</div>
<!-- 趋势 & 资金 -->
<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:4px;font-size:10px">
<div style="text-align:center;background:{BG}33;border-radius:4px;padding:3px 0">
<span style="color:{DIM}">趋势</span> <span style="color:{GOLD}">{c['trend']}</span>
</div>
<div style="text-align:center;background:{BG}33;border-radius:4px;padding:3px 0">
<span style="color:{DIM}">资金</span> <span style="color:{ORANGE}">{c['fund']}</span>
</div>
</div>
<!-- D+1~D+5 每日最高 -->
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr;gap:4px;margin-top:5px;font-size:10px">'''
        d_labels = ['D+1', 'D+2', 'D+3', 'D+4', 'D+5']
        for d in range(5):
            val = c[f'd{d+1}']
            if val == '—':
                html += f'<div style="text-align:center;border-radius:3px;padding:2px 0;background:{BG}44"><span style="color:{DIM}">{d_labels[d]}</span><br><span style="color:{DIM}">—</span></div>'
            else:
                html += f'<div style="text-align:center;border-radius:3px;padding:2px 0;background:{BG}44"><span style="color:{DIM};font-size:9px">{d_labels[d]}</span><br>{pct_format(val)}</div>'
        html += '</div></div>'
    
    # ========== 全部候选完整表格 ==========
    html += f'''
<div style="margin-top:16px;font-size:11px;color:{DIM}">全部候选（{total}只）</div>
<div style="background:{CARD};border-radius:6px;overflow-x:auto;-webkit-overflow-scrolling:touch;margin-top:4px">
<table style="min-width:860px;border-collapse:collapse;font-size:10px;white-space:nowrap">'''
    
    # 表头
    cols = ['#', '名称', '编码', '买入价', '当日涨幅%', '次日涨幅%', '次日最高价涨幅%', 'CL%', '量比', '换手%', 'PE', '市值', '趋势', '资金', '评分', 'D+1', 'D+2', 'D+3', 'D+4', 'D+5']
    html += f'<tr style="border-bottom:1px solid {LINE}">'
    w = ['24', '64', '56', '44', '38', '38', '38', '34', '34', '34', '34', '46', '80', '60', '32', '34', '34', '34', '34', '34']
    for j, col in enumerate(cols):
        html += f'<th style="padding:6px 2px;text-align:center;color:{HEAD};font-weight:400;min-width:{w[j]}px">{col}</th>'
    html += '</tr>'
    
    # 数据行
    for i, c in enumerate(cand[:30]):
        bg = 'transparent' if i % 2 == 0 else f'{BG}88'
        html += f'<tr style="background:{bg};border-bottom:1px solid {LINE}33">'
        html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">{i+1}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT};font-size:10px">{c["nm"][:6]}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{DIM};font-size:9px">{c["code"][-6:]}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c["buy_c"]:.2f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center">{pct_format(str(c["p"]), "")}</td>'
        html += f'<td style="padding:5px 2px;text-align:center">{pct_format(c["next_close_pct"], "")}</td>'
        nc_val = c['d1'] if c['d1'] != '—' else '—'
        if nc_val != '—':
            html += f'<td style="padding:5px 2px;text-align:center">{pct_format(nc_val, "")}</td>'
        else:
            html += f'<td style="padding:5px 2px;text-align:center"><span style="color:{DIM}">—</span></td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c["cl"]:.0f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c["vr"]:.2f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c["hsl"]:.1f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">{c["pe"]:.1f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">{c["sz"]:.0f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{GOLD};font-size:9px">{c["trend"][:12]}</td>'
        # 资金简化
        fund_s = '🔥' if '放量' in c['fund'] else ('➡' if '正常' in c['fund'] else '📉')
        html += f'<td style="padding:5px 2px;text-align:center;color:{ORANGE};font-size:9px">{fund_s}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT};font-weight:600">{c["score"]}</td>'
        # D+1~D+5
        for d in range(5):
            val = c[f'd{d+1}']
            if val == '—':
                html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">—</td>'
            else:
                html += f'<td style="padding:5px 2px;text-align:center">{pct_format(val, "")}</td>'
        html += '</tr>'
    
    html += '</table></div>'
    
    # 底部说明
    html += f'''
<div style="text-align:center;font-size:9px;color:{DIM};padding:12px 0 5px;border-top:1px solid {LINE};margin-top:12px;line-height:1.6">
涨5~8% · 量比1.0~1.5 · 换手5~15% · 市值&lt;200亿 · CL 60~90% · CL降序排名<br>
<span style="color:{RED}">红涨</span> · <span style="color:{GREEN}">绿跌</span> · 综合评分:涨幅+收盘位+量比+换手+MACD/KDJ金叉
</div>
</div>
</body>
</html>'''
    return html

# ========== 发送 + 归档 ==========
html_content = build_html()
subject = f'尾盘选股-每日推荐 {sel_date}'

# 存档到本地
ARCHIVE_DIR = os.path.expanduser('~/AppData/Local/hermes/email_archive')
os.makedirs(ARCHIVE_DIR, exist_ok=True)
archive_name = f'{sel_date}_尾盘选股.html'
archive_path = os.path.join(ARCHIVE_DIR, archive_name)
with open(archive_path, 'w', encoding='utf-8') as f:
    f.write(html_content)
print(f'📁 已归档: {archive_path}')

# 发邮件
sys.path.insert(0, SCRIPTS_DIR)
from send_email import send_email
send_email(['1254628314@qq.com','314913203@qq.com'], subject, html_content, html=True)
print(f'✅ 已发送 - {sel_date} 候选{total}只')
