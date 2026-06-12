#!/usr/bin/env python3
"""多源实时数据采集器 — 通达信→腾讯API→其他，全部缓存

优先级：
  1. 通达信 get_security_quotes (盘中实时)
  2. 通达信 get_security_bars (盘中/盘后)
  3. 腾讯API qt.gtimg.cn (全天可用，最稳定)
  4. 本地缓存备份

输出：industry_snapshot.json + 历史回测可用格式
"""
import os, json, subprocess, pickle, sys, time
from collections import defaultdict
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/prod')
CACHE_DIR = os.path.normpath(os.path.expanduser(
    '~/AppData/Local/hermes/hermes-agent/cache'
))
SNAP_PATH = os.path.normpath(os.path.join(CACHE_DIR, '..', 'industry_snapshot.json'))
RICH_CACHE = os.path.join(CACHE_DIR, 'rich_cache.json')

# 自动检测版本目录
VERSION_DIR = None
for d in ['1180', '1170', '1150', '11041142', '1103']:
    p = os.path.join(SCRIPTS_DIR, 'strategies', d)
    if os.path.exists(p):
        # 用最新版本
        VERSION_DIR = p
IND_PATH = os.path.join(VERSION_DIR or SCRIPTS_DIR, 'industry_map.pkl')
ACTIVE_PATH = os.path.join(VERSION_DIR or SCRIPTS_DIR, '活跃股票池_3043.json')

# 加载行业映射
INDUSTRY_MAP = {}
if os.path.exists(IND_PATH):
    with open(IND_PATH, 'rb') as f:
        INDUSTRY_MAP = pickle.load(f)

# 加载股票池
codes = []
if os.path.exists(ACTIVE_PATH):
    with open(ACTIVE_PATH) as f:
        pool = json.load(f)
    codes = pool.get('codes', [])
else:
    codes = [f'{i:06d}' for i in range(600000, 606000)] + [f'{i:06d}' for i in range(3000)]
    codes = [c for c in codes if c.startswith(('600','601','603','605','000','001','002'))]

print(f'📋 股票池: {len(codes)}只 | 🏭 行业: {len(INDUSTRY_MAP)}只', flush=True)

PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

# ===== 数据源1: 通达信 (最快，但盘中才能用) =====
def fetch_tdx_quotes(codes_batch):
    """通达信实时行情 — 返回 {code: {数据}}"""
    try:
        from pytdx.hq import TdxHq_API
        api = TdxHq_API()
        api.connect('110.41.147.114', 7709)
        
        # 分批取，每次30只
        all_data = {}
        for i in range(0, len(codes_batch), 30):
            chunk = codes_batch[i:i+30]
            # 判断市场：600=上海(1), 000=深圳(0)
            fmt_codes = [(1 if c.startswith(('6','9')) else 0, c) for c in chunk]
            q = api.get_security_quotes(fmt_codes)
            if q:
                for row in q:
                    code = str(row.get('code', ''))
                    if not code: continue
                    # 通达信quote字段
                    all_data[code] = {
                        'price': row.get('price', 0),
                        'prev_close': row.get('last_close', 0) or row.get('yest_close', 0),
                        'open': row.get('open', 0),
                        'high': row.get('high', 0),
                        'low': row.get('low', 0),
                        'volume': row.get('vol', 0),
                        'amount': row.get('amount', 0),
                        'source': 'tdx'
                    }
        api.disconnect()
        if all_data:
            print(f'  📡 通达信: {len(all_data)}只', flush=True)
        return all_data
    except Exception as e:
        print(f'  ⚠️ 通达信失败: {e}', flush=True)
        return {}

# ===== 数据源2: 腾讯API (全天可用，字段最全) =====
def curl_get(url, timeout=10):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url],
                          capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except:
        return ''

def fetch_tencent_quotes(codes_batch):
    """腾讯API实时行情 — 返回 {code: {丰富数据}}"""
    all_data = {}
    for i in range(0, len(codes_batch), 80):
        chunk = codes_batch[i:i+80]
        symbols = [f'{PREFIX(c)}{c}' for c in chunk]
        text = curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}', timeout=8)
        for line in text.split('\n'):
            if '~' not in line: continue
            parts = line.split('~')
            if len(parts) < 47: continue
            try:
                nm = parts[1]; code = parts[2]
                if not nm or 'ST' in nm or '*ST' in nm or '退' in nm: continue
                price = float(parts[3])
                prev_c = float(parts[4])
                pct = round((price/prev_c-1)*100, 2) if prev_c else 0
                if abs(pct) > 20: continue
                
                # 全量字段提取
                vol_str = parts[6] if parts[6] else '0'
                amt_str = parts[7] if parts[7] else '0'
                
                # 内盘/外盘（资金流向关键）
                inner_vol = float(parts[39]) if len(parts) > 39 and parts[39] else 0  # 内盘
                outer_vol = float(parts[40]) if len(parts) > 40 and parts[40] else 0  # 外盘
                
                # 换手率
                hsl = 0
                try: hsl = float(parts[38]) if parts[38] else 0
                except: pass
                
                # 量比
                vol_ratio = 0
                try: vol_ratio = float(parts[36]) if parts[36] else 0
                except: pass
                
                # 振幅
                amp = 0
                try: amp = float(parts[43]) if len(parts) > 43 and parts[43] else 0
                except: pass
                
                # 5日涨幅 / 60日涨幅
                p5 = 0; p60 = 0
                try: p5 = float(parts[49]) if len(parts) > 49 and parts[49] else 0
                except: pass
                try: p60 = float(parts[48]) if len(parts) > 48 and parts[48] else 0
                except: pass
                
                # 市盈率/总市值
                pe = 0; mkt_cap = 0
                try: pe = float(parts[41]) if len(parts) > 41 and parts[41] else 0
                except: pass
                try: mkt_cap = float(parts[44]) if len(parts) > 44 and parts[44] else 0
                except: pass
                
                # 净流入 = 外盘 - 内盘
                net_inflow = outer_vol - inner_vol
                inflow_ratio = outer_vol / max(inner_vol, 1)  # 外盘/内盘比
                
                all_data[code] = {
                    'name': nm, 'price': price, 'pct': pct,
                    'volume': int(float(vol_str)),
                    'amount': float(amt_str),
                    'inner': inner_vol,
                    'outer': outer_vol,
                    'net_inflow': net_inflow,
                    'inflow_ratio': round(inflow_ratio, 2),
                    'hsl': hsl,
                    'vol_ratio': vol_ratio,
                    'amp': amp,
                    'p5': p5,
                    'p60': p60,
                    'pe': pe,
                    'mkt_cap': mkt_cap,
                    'source': 'tencent'
                }
            except:
                pass
    if all_data:
        print(f'  📡  腾讯: {len(all_data)}只', flush=True)
    return all_data

# ===== 主流程 =====
print('🚀 多源实时数据采集...', flush=True)
t0 = time.time()

# 第一步：尝试通达信
now_hour = datetime.now().hour
stocks = {}
if 9 <= now_hour <= 15:  # 交易时段
    print('🟢 交易时段 → 先通达信', flush=True)
    stocks = fetch_tdx_quotes(codes)
else:
    print('🔴 非交易时段 → 直接腾讯API', flush=True)

# 第二步：腾讯API补充/覆盖（有更全字段）
print('📡 腾讯API补充...', flush=True)
tencent_data = fetch_tencent_quotes(codes)

# 合并：腾讯数据覆盖（因为有内盘/外盘等字段）
for code, td in tencent_data.items():
    if code in stocks:
        stocks[code].update(td)
        stocks[code]['source'] = 'tencent+tdx'
    else:
        stocks[code] = td

print(f'📡 合并后: {len(stocks)}只 ({time.time()-t0:.0f}s)', flush=True)

# ===== 计算行业统计 =====
ind_prices = defaultdict(list)
ind_inflow = defaultdict(list)
ind_amount = defaultdict(list)

for code, s in stocks.items():
    ind = INDUSTRY_MAP.get(code, '')
    if ind:
        if 'pct' in s:
            ind_prices[ind].append(s['pct'])
        if 'net_inflow' in s:
            ind_inflow[ind].append(s['net_inflow'])
        if 'amount' in s:
            ind_amount[ind].append(s['amount'])

live_ind_avg = {k: round(sum(v)/len(v), 2) for k, v in ind_prices.items() if v}
ind_net_inflow = {k: sum(v) for k, v in ind_inflow.items() if len(v) > 5}
ind_amount_sum = {k: sum(v) for k, v in ind_amount.items() if len(v) > 5}

now_str = datetime.now().strftime('%H:%M')

# ===== 存快照（丰富格式）=====
snap_data = {
    'time': now_str,
    'date': datetime.now().strftime('%Y-%m-%d'),
    'stocks': stocks,
    'ind_avg': live_ind_avg,
    'ind_inflow': ind_net_inflow,
    'ind_amount': ind_amount_sum,
    'stats': {
        'total': len(stocks),
        'industries': len(live_ind_avg),
        'with_inflow': sum(1 for s in stocks.values() if 'net_inflow' in s),
        'with_hsl': sum(1 for s in stocks.values() if s.get('hsl', 0) > 0),
    }
}
os.makedirs(os.path.dirname(SNAP_PATH), exist_ok=True)
with open(SNAP_PATH, 'w', encoding='utf-8') as f:
    json.dump(snap_data, f, ensure_ascii=False)

# 同时存一份可历史回溯的格式（按日期追加）
rich_cache = {}
if os.path.exists(RICH_CACHE):
    try:
        with open(RICH_CACHE, encoding='utf-8') as f:
            rich_cache = json.load(f)
    except:
        pass
rich_cache[now_str] = {
    'stocks': {c: {k: s[k] for k in ['price','pct','hsl','vol_ratio','amp','p5','net_inflow','inflow_ratio','amount','inner','outer']
                   if k in s} for c, s in stocks.items()},
    'ind_avg': live_ind_avg,
}
with open(RICH_CACHE, 'w', encoding='utf-8') as f:
    json.dump(rich_cache, f, ensure_ascii=False)

print(f'💾 快照: {SNAP_PATH} | 丰富缓存: {RICH_CACHE}', flush=True)
print(f'📊 {len(stocks)}只 | {len(live_ind_avg)}行业 | {len(ind_net_inflow)}有净流入', flush=True)

# ===== 展示价值数据 =====
print(f'\n🏆 行业热点 (基于价格涨幅):')
sorted_inds = sorted(live_ind_avg.items(), key=lambda x: -x[1])
for ind, avg in sorted_inds[:8]:
    tag = '🔥' if avg > 0.5 else ('↑' if avg > 0 else ('❄️' if avg < -1 else '↓'))
    inf = ind_net_inflow.get(ind, 0)
    print(f'  {tag} {ind.split()[-1][:12]}: {avg:+.2f}% | 净流入{inf:+.0f}手')

print(f'\n⚡ 行业资金流向TOP5 (基于净流入):')
sorted_inflow = sorted(ind_net_inflow.items(), key=lambda x: -x[1])
for ind, inf in sorted_inflow[:5]:
    ind_short = ind.split()[-1][:12] if ' ' in ind else ind[:12]
    avg = live_ind_avg.get(ind, 0)
    print(f'  💰 {ind_short}: 净流入{inf:+.0f}手 | 涨跌幅{avg:+.2f}%')

print(f'\n🔻 行业资金流出TOP5:')
for ind, inf in sorted_inflow[-5:]:
    ind_short2 = ind.split()[-1][:12] if ' ' in ind else ind[:12]
    avg = live_ind_avg.get(ind, 0)
    print(f'  💸 {ind_short2}: 净流出{abs(inf):.0f}手 | 涨跌幅{avg:+.2f}%')

# 统计全市场资金流向
total_inner = sum(s.get('inner', 0) for s in stocks.values())
total_outer = sum(s.get('outer', 0) for s in stocks.values())
if total_inner + total_outer > 0:
    ratio = total_outer / max(total_inner, 1)
    print(f'\n📊 全市场: 内盘{total_inner:.0f}手 | 外盘{total_outer:.0f}手 | 内外比{ratio:.2f}')
    if ratio > 1.15:
        print('  🟢 主动买入 > 主动卖出 → 资金整体流入')
    elif ratio < 0.85:
        print(f'  🔴 主动卖出 > 主动买入 → 资金整体流出')

# 选top5净流入股票
top_inflow = sorted(stocks.items(), key=lambda x: x[1].get('net_inflow', 0), reverse=True)[:5]
print(f'\n🥇 个股净流入TOP5:')
for code, s in top_inflow:
    ind = INDUSTRY_MAP.get(code, '')
    ind_name = ind.split()[-1][:8] if ind else '—'
    nm = s.get('name', '?')
    ni = s.get('net_inflow', 0)
    pc = s.get('pct', 0)
    print(f'  {nm}({code}): 净流入{ni:+.0f}手 | {pc:+.2f}% | {ind_name}')

print(f'\n✅ 采集完成 ⏱ {time.time()-t0:.1f}s')
