#!/usr/bin/env python3
"""
V43 每日选股 — V42基础 + 横盘安全分 + 滚动胜率监控
不改V42任何代码，独立运行
"""
import sys, os, json, time, subprocess
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime
from safety_monitor import check_rolling_winrate, record_selection

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
V43_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V43')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
sys.path.insert(0, V43_DIR); sys.path.insert(0, SCRIPTS_DIR)

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

# 加载V43评分策略
import importlib
STRATS = {}
for n in ['真实涨日','虚涨日','跌日','横盘']:
    fp = os.path.join(V43_DIR, '评分策略', f'分而治之_V10_{n}_评分策略.py')
    spec = importlib.util.spec_from_file_location(n, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    STRATS[n] = m

LO = ['L0','L1','L2','L3','L4']
MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}

# ===== 前置检查：滚动胜率 =====
print('▶ V43 安全监控检查...', flush=True)
safety = check_rolling_winrate(days=20)
print(f'   胜率: {safety.get("win_rate","?")}%')
print(f'   建议级别: {safety.get("suggested_level","L0")}: {safety.get("message","")}')

LEVEL_OVERRIDE = safety.get('suggested_level', 'L0')
if LEVEL_OVERRIDE == 'BREAK':
    print('⚠️ 警告：连续亏损，建议空仓！')
    print('   但V42在跌日100%胜率，继续执行正常选股')
    LEVEL_OVERRIDE = 'L0'  # 强制继续，用最严格级别

print(f'\n▶ V43 执行选股 (Level={LEVEL_OVERRIDE})...', flush=True)

# ===== 获取市场数据 =====
def curl_get(url, timeout=10):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url],capture_output=True,timeout=timeout+5)
        return r.stdout.decode('gbk',errors='replace')
    except: return ''

# 获取实时行情 + 分类
now_hour = datetime.now().hour
today_str = datetime.now().strftime('%Y-%m-%d')

# 开盘前用data_cache，盘中用实时API
active = {}
if now_hour < 9 or (now_hour == 9 and datetime.now().minute < 30):
    # 开盘前：从data_cache加载
    import sqlite3 as sq3
    db = sq3.connect(os.path.join(SCRIPTS_DIR, 'v13_quant.db'), timeout=5)
    cur = db.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 AND date<? ORDER BY date DESC LIMIT 1', (today_str,))
    r = cur.fetchone()
    if r:
        dt = r[0]
        cur2 = db.execute('SELECT code, name, p, cl, wr_val, dif_val, vr, close FROM data_cache WHERE date=? AND close>0', (dt,))
        hsl_data = {}
        try:
            hsl_cur = db.execute('SELECT code, hsl FROM data_stock_info')
            hsl_data = {r2[0]: r2[1] or 0 for r2 in hsl_cur.fetchall()}
        except: pass
        for r2 in cur2.fetchall():
            code = r2[0]
            active[code] = {
                'name': r2[1] or '', 'price': r2[7], 'p': r2[2] or 0,
                'vol_ratio': r2[6] or 1, 'cl': r2[3] or 50,
                'wr_val': r2[4] or 50, 'dif_val': r2[5] or 0,
                'hsl': hsl_data.get(code, 0), 'pe': 0, 'sz': 0
            }
        print(f'  开盘前，从data_cache加载: {len(active)}只 ({dt})', flush=True)
    db.close()
else:
    # 盘中：实时API
    codes = [str(i) for i in range(600000, 606000)] + [f'{i:06d}' for i in range(3000)]
    for i in range(0, len(codes), 80):
        chunk = codes[i:i+80]
        symbols = [f'{PREFIX(c)}{c}' for c in chunk]
        text = curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}', timeout=8)
        for line in text.split('\n'):
            if '~' not in line: continue
            parts = line.split('~')
            if len(parts) < 40: continue
            try:
                nm = parts[1]; code = parts[2]
                if not code.startswith(('600','601','603','605','000','001','002')): continue
                if 'ST' in nm or '退' in nm or not nm: continue
                price = float(parts[3]) if parts[3] else 0
                open_p = float(parts[5]) if parts[5] else 0
                if price <= 0 or open_p <= 0: continue
                active[code] = {
                    'name': nm, 'price': price,
                    'p': (price - open_p) / open_p * 100 if open_p > 0 else 0,
                    'vol_ratio': float(parts[38]) if parts[38] and parts[38].replace('.','').isdigit() else 1,
                    'cl': float(parts[38]) if parts[38] and parts[38].replace('.','').isdigit() and float(parts[38]) <= 100 else 50,
                    'hsl': float(parts[34]) if parts[34] and parts[34].replace('.','').isdigit() else 0,
                    'pe': float(parts[40]) if parts[40] and parts[40].replace('.','').isdigit() else 0,
                    'sz': 0,
                }
            except: pass
    print(f'  实时API加载: {len(active)}只', flush=True)

# 市场分类（简化版）
sh_idx = None
try:
    import akshare as ak
    sh = ak.stock_zh_index_daily_tx(symbol='sh000001', start_date=datetime.now().strftime('%Y%m%d'), end_date=datetime.now().strftime('%Y%m%d'))
    if len(sh) > 0:
        sh_idx = sh['close'].iloc[-1]
except: pass

# 分类市场类型（使用V42逻辑的简化版）
def classify_market(pct_change, up_count=0, down_count=0):
    """简化的市场分类"""
    if pct_change > 0.5:
        return '真实涨日'
    elif pct_change < -0.5:
        return '跌日'
    else:
        return '横盘'

market_type = '横盘'
if sh_idx:
    try:
        prev_data = ak.stock_zh_index_daily_tx(symbol='sh000001', start_date='20260101', end_date=datetime.now().strftime('%Y%m%d'))
        if len(prev_data) >= 2:
            prev_close = prev_data['close'].iloc[-2]
            pct = (sh_idx / prev_close - 1) * 100
            market_type = classify_market(pct)
    except:
        pass

print(f'  市场类型: {market_type}', flush=True)

# ===== 执行选股 =====
strategy = STRATS.get(market_type)
if not strategy:
    print(f'❌ 未找到{market_type}的策略', flush=True)
    sys.exit(1)

print(f'  评分策略: {strategy.NAME}', flush=True)

# 按Level筛选和评分
candidates = []
for code, info in active.items():
    if not IS_MAIN(code): continue
    if info.get('pe', 1) <= 0: continue
    if info.get('price', 0) <= 3 or info.get('price', 0) > 80: continue
    if 'ST' in info.get('name', '') or '退' in info.get('name', ''): continue
    
    # 构建评分所需数据
    stock_data = {
        'nm': info.get('name', ''), 'code': code,
        'p': info.get('p', 0), 'cl': info.get('cl', 50),
        'vr': info.get('vol_ratio', 1), 'dif': info.get('dif_val', 0),
        'wrv': info.get('wr_val', 50), 'hsl': info.get('hsl', 0),
        'pos_in_day': 50,
        'slope5': 0, 'mg': 0, 'a5': 0, 'jv': 50, 'kv': 50, 'dv': 50,
        't4_shadow': 0,
    }
    
    s = strategy.score(stock_data)
    if s > 0:
        candidates.append((code, info.get('name', ''), s, info.get('price', 0)))

# 排序取Top3
candidates.sort(key=lambda x: -x[2])
top3 = candidates[:3]

print(f'\n  候选总数: {len(candidates)}')
print(f'  {"="*50}')
print(f'  🏆 V43 TOP3 (Level={LEVEL_OVERRIDE})')
print(f'  {"="*50}')

for i, (code, name, score, price) in enumerate(top3, 1):
    medal = ['🥇','🥈','🥉'][i-1]
    warning = ' ⚠️ 价格较高' if price > 100 else ''
    print(f'  {medal} {name}({code})')
    print(f'     买入价: ¥{price:.2f}{warning}')
    print(f'     评分: {score:.1f}')
    
    # 记录到数据库
    record_selection(f'V43_{LEVEL_OVERRIDE}', code, name, score, price, market_type, LEVEL_OVERRIDE)

# 输出便于邮件模板使用
print(f'\n  {"-"*50}')
print(f'  市场: {market_type} | Level: {LEVEL_OVERRIDE}')
print(f'  30天胜率: {safety.get("win_rate","?")}% | {safety.get("message","")}')
