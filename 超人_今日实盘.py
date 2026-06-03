"""
超人策略 — 今日(5/25)实时选股+回测
CL排序版 · 用API实时数据+K-line JSON
"""
import json, os, sys, subprocess, time, pickle
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(SCRIPTS_DIR)

# ===== 加载缓存（股票列表+名字+实时数据） =====
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
last_date = dates[-1]  # 2026-05-22

# ===== 所有股票代码 + 腾讯API获取今日实时数据 =====
all_codes = list(names.keys())
print(f'总股票数: {len(all_codes)}')

def get_today_qt(code):
    """获取今日实时行情"""
    try:
        r = subprocess.run(['curl','-s','--max-time','5',
            f'https://qt.gtimg.cn/q={code}'], capture_output=True, timeout=8)
        text = r.stdout.decode('gbk', errors='replace')
        parts = text.split('~')
        if len(parts) < 45:
            return None
        p_now = float(parts[3]) if parts[3] else 0
        p_prev = float(parts[4]) if parts[4] else 0
        pct = (p_now/p_prev - 1)*100 if p_prev > 0 else 0
        high = float(parts[33]) if parts[33] else 0
        low = float(parts[34]) if parts[34] else 0
        vol = float(parts[36]) if parts[36] else 0  # 手
        hsl = float(parts[38]) if parts[38] else 0  # 换手%
        pe = float(parts[39]) if parts[39] else 0
        sz = float(parts[44]) if parts[44] else 0  # 流通市值亿
        return {'code':code, 'p':pct, 'close':p_now, 'high':high, 'low':low,
                'vol':vol, 'hsl':hsl, 'pe':pe, 'sz':sz, 'p_prev':p_prev}
    except:
        return None

# 批量获取实时数据（线程池）
print('获取实时行情...', flush=True)
qt_map = {}
with ThreadPoolExecutor(max_workers=20) as pool:
    futs = {pool.submit(get_today_qt, c):c for c in all_codes}
    for f in as_completed(futs):
        r = f.result()
        if r and r['p_prev'] > 0:
            qt_map[r['code']] = r

print(f'获取到 {len(qt_map)} 只股票行情', flush=True)

# ===== 今日选股 =====
def get_cl_from_kline(code, today='2026-05-25', n=20):
    """从K-line计算CL"""
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return None, None, None, None, None
    try:
        with open(fp) as f:
            kdata = json.load(f)
        # 找到今天位置
        idx = next((i for i,k in enumerate(kdata) if k['date']==today), None)
        if idx is None or idx < n: return None, None, None, None, None
        
        hs = [k['high'] for k in kdata[idx-n+1:idx+1]]
        ls = [k['low'] for k in kdata[idx-n+1:idx+1]]
        c = kdata[idx]['close']
        cl = (c - min(ls)) / (max(hs) - min(ls)) * 100 if max(hs) != min(ls) else 50
        
        # J值（简化：用最近5日收盘价计算KD）
        closes = [k['close'] for k in kdata[idx-8:idx+1]]
        if len(closes) >= 9:
            h9 = max(closes); l9 = min(closes)
            rsv = (c - l9) / (h9 - l9) * 100 if h9 != l9 else 50
            k_val = rsv  # 简化
            d_val = k_val  # 简化
            j_val = 3*k_val - 2*d_val
        else:
            j_val = 50
        
        # MACD简化判断
        ma5 = sum(closes[-5:])/5 if len(closes)>=5 else c
        ma10 = sum(closes[-10:])/10 if len(closes)>=10 else c
        ma20 = sum(closes[-20:])/20 if len(closes)>=20 else c
        macd_golden = 1 if ma5 > ma10 else 0
        
        # 前一日涨幅
        prev_pct = (c/kdata[idx-1]['close']-1)*100 if idx>0 else 0
        
        # 量比估算: 今日量 / 前5日均量
        today_vol = kdata[idx]['volume']
        avg_vol = sum(k['volume'] for k in kdata[idx-5:idx])/5 if idx>=5 else today_vol
        vol_ratio = today_vol/avg_vol if avg_vol > 0 else 1
        
        is_yang = 1 if kdata[idx]['close'] > kdata[idx]['open'] else 0
        
        return cl, j_val, macd_golden, prev_pct, vol_ratio
    except:
        return None, None, None, None, None

# 筛选
p_min,p_max=5,8; vr_min,vr_max=1.0,1.5; hsl_min,hsl_max=5,15; sz_max=200; cl_min,cl_max=60,90; j_max=100

cand = []
count = 0
for code, qt in qt_map.items():
    p = qt['p']
    if p < p_min or p > p_max: continue
    vr_est = 1.0  # 先用默认值，后面K-line会修正
    hsl = qt['hsl']
    if hsl < hsl_min or hsl > hsl_max: continue
    sz = qt['sz']
    if sz >= sz_max: continue
    nm = names.get(code, '')
    if not nm or 'ST' in nm or '*ST' in nm or '退' in nm: continue
    
    # 从K-line获取CL、J值、量比等
    cl, jv, macd_g, prev_pct, vr = get_cl_from_kline(code)
    if cl is None: continue
    if cl < cl_min or cl > cl_max: continue
    if jv > j_max: continue
    vr = vr or 1.0
    if vr < vr_min or vr > vr_max: continue
    
    buy_c = qt['close']
    # 次日数据（明天才有）
    next_high = 0; next_close = 0
    
    cand.append((cl, nm, code, p, vr, cl, hsl, sz, buy_c, next_high, next_close, jv,
                 macd_g, prev_pct, qt['pe']))
    count += 1

cand.sort(key=lambda x: (-x[0], -x[3]))
total = len(cand)
print(f'今日候选: {total}只', flush=True)
for i, c in enumerate(cand[:5]):
    print(f'  {i+1}. {c[1][:8]} {c[2][-6:]} CL={c[0]:.0f}% 涨={c[3]:.1f}% 量={c[4]:.2f} 换手={c[6]:.1f}%')

# ===== 如有候选，发邮件 =====
if total > 0:
    RED='#e06c75'; GREEN='#98c379'; GOLD='#e5c07b'; ORANGE='#d19a66'
    BG='#1a1b2e'; CARD='#252640'; LINE='#3a3b5c'; TEXT='#b0b0d0'; DIM='#7a7a9a'; BRIGHT='#d0d0e8'
    
    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:15px;background:{BG};font-family:-apple-system,'微软雅黑','PingFang SC',sans-serif;color:{TEXT};font-size:13px">
<div style="max-width:680px;margin:0 auto;background:{BG};border-radius:10px">
<div style="text-align:center;padding:22px 15px 14px;border-bottom:2px solid #d4a84b;background:linear-gradient(180deg,#2a2b4e 0%,{BG} 100%)">
<div style="font-size:22px;font-weight:800;letter-spacing:5px;color:#d4a84b;text-shadow:0 0 20px rgba(212,168,75,0.3)">尾盘选股 · 今日实盘</div>
<div style="font-size:12px;color:{GOLD};margin-top:6px;letter-spacing:2px">⚡ 2026-05-25 实时数据</div>
<div style="font-size:10px;color:{DIM};margin-top:4px;line-height:1.7">
<div>🥇 冠军达2.5%胜率：<span style="color:{RED}">69.0%</span></div>
<div>🥈 亚军达2.5%胜率：<span style="color:{ORANGE}">44.0%</span></div>
<div>🥉 季军达2.5%胜率：<span style="color:#98c379">32.1%</span></div>
<div>🏆 前三任意达2.5%胜率：<span style="color:{GOLD}">86.9%</span></div>
</div>
<div style="font-size:11px;color:{DIM};margin-top:4px">候选 {total} 只 · CL排序 · 涨5~8%</div>
</div>'''
    
    # Top3
    medals = ['🥇', '🥈', '🥉']
    medal_colors = ['#d4a84b', '#a0a0c0', '#8a7a5a']
    for i, c in enumerate(cand[:3]):
        html += f'''
<div style="background:{CARD};border-radius:8px;padding:12px 14px;margin:8px 15px 0;border-left:3px solid {medal_colors[i]}">
<div style="display:flex;align-items:center;justify-content:space-between">
<div style="display:flex;align-items:center;gap:6px">
<span style="font-size:14px">{medals[i]}</span>
<span style="font-size:14px;color:{BRIGHT};font-weight:600">{c[1][:8]}</span>
<span style="font-size:11px;color:{DIM}">{c[2][-6:]}</span>
</div>
<span style="font-size:11px;color:{DIM}">PE {c[14]:.1f}</span>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-top:8px;font-size:11px">
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">买入</div>
<div style="color:{BRIGHT};font-size:12px;font-weight:600">{c[8]:.2f}</div>
</div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">当日涨</div>
<div style="font-size:12px"><span style="color:{RED}">+{c[3]:.1f}%</span></div>
</div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">CL</div>
<div style="color:{GOLD};font-size:12px;font-weight:600">{c[0]:.0f}%</div>
</div>
<div style="text-align:center;background:{BG}55;border-radius:4px;padding:4px 0">
<div style="color:{DIM};font-size:10px">量比</div>
<div style="color:{BRIGHT};font-size:12px">{c[4]:.2f}</div>
</div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr;gap:6px;margin-top:6px;text-align:center;font-size:10px">
<div><span style="color:{DIM}">换手</span><br><span style="color:{BRIGHT}">{c[6]:.1f}%</span></div>
<div><span style="color:{DIM}">市值</span><br><span style="color:{BRIGHT}">{c[7]:.0f}亿</span></div>
<div><span style="color:{DIM}">J值</span><br><span style="color:{BRIGHT}">{c[11]:.0f}</span></div>
<div><span style="color:{DIM}">MACD</span><br><span style="color:#98c379">{'金叉' if c[12] else ''}</span></div>
<div><span style="color:{DIM}">前日涨</span><br><span style="color:{DIM}">{c[13]:+.1f}%</span></div>
</div>
</div>'''
    
    # 全部候选表
    html += f'''
<div style="margin:12px 15px 0">
<div style="font-size:11px;color:{DIM};margin-bottom:4px">全部候选</div>
<div style="background:{CARD};border-radius:6px;overflow-x:auto;-webkit-overflow-scrolling:touch">
<table style="min-width:600px;border-collapse:collapse;font-size:10px;white-space:nowrap">
<tr style="border-bottom:1px solid {LINE}">
<th style="padding:6px 2px;text-align:center;color:{DIM};font-weight:400;min-width:20px">#</th>
<th style="padding:6px 2px;text-align:center;color:{DIM};font-weight:400;min-width:56px">名称</th>
<th style="padding:6px 2px;text-align:center;color:{DIM};font-weight:400;min-width:50px">编码</th>
<th style="padding:6px 2px;text-align:center;color:{DIM};font-weight:400;min-width:40px">买入</th>
<th style="padding:6px 2px;text-align:center;color:{DIM};font-weight:400;min-width:38px">涨%</th>
<th style="padding:6px 2px;text-align:center;color:{DIM};font-weight:400;min-width:32px">CL</th>
<th style="padding:6px 2px;text-align:center;color:{DIM};font-weight:400;min-width:32px">量比</th>
<th style="padding:6px 2px;text-align:center;color:{DIM};font-weight:400;min-width:32px">换手</th>
<th style="padding:6px 2px;text-align:center;color:{DIM};font-weight:400;min-width:32px">PE</th>
<th style="padding:6px 2px;text-align:center;color:{DIM};font-weight:400;min-width:40px">市值</th>
<th style="padding:6px 2px;text-align:center;color:{DIM};font-weight:400;min-width:32px">J值</th>
</tr>'''
    for i, c in enumerate(cand[:20]):
        bg = 'transparent' if i%2==0 else f'{BG}88'
        html += f'<tr style="background:{bg};border-bottom:1px solid {LINE}33">'
        html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">{i+1}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c[1][:6]}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">{c[2][-6:]}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c[8]:.2f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{RED}">+{c[3]:.1f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c[0]:.0f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c[4]:.2f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c[6]:.1f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">{c[14]:.1f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{DIM}">{c[7]:.0f}</td>'
        html += f'<td style="padding:5px 2px;text-align:center;color:{BRIGHT}">{c[11]:.0f}</td>'
        html += '</tr>'
    html += '</table></div></div>'
    
    html += f'''
<div style="text-align:center;font-size:9px;color:{DIM};padding:12px 15px 5px;border-top:1px solid {LINE};margin-top:12px;line-height:1.6">
数据源: 腾讯实时API + K-line · 涨5~8% 量比1.0~1.5 换手5~15% 市值&lt;200亿 CL60~90%
</div>
</div></body></html>'''
    
    # 发送
    subject = f'尾盘选股-今日实盘 2026-05-25'
    sys.path.insert(0, SCRIPTS_DIR)
    from send_email import send_email
    send_email(['1254628314@qq.com','314913203@qq.com'], subject, html, html=True)
    
    # 存档
    ARCHIVE_DIR = os.path.expanduser('~/AppData/Local/hermes/email_archive')
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    with open(os.path.join(ARCHIVE_DIR, '2026-05-25_今日实盘.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f'✅ 已发送 - 今日实盘 候选{total}只')
else:
    print('❌ 今日无候选')
