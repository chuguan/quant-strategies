"""
开盘强势股策略 — 9:30-10:00 强则全强
基于AkShare 30分钟K线
"""
import os, pickle, json, time, sys, random
import numpy as np

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
sys.path.insert(0, SCRIPTS_DIR)

# 加载股票列表
pool = json.load(open(os.path.join(SCRIPTS_DIR, '活跃股票池_3043.json'), encoding='utf-8'))
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
codes = sorted(set(c for c in pool['codes'] if IS_MAIN(c)))
random.seed(42)
random.shuffle(codes)
print(f'主板: {len(codes)}只')

# 加载名称
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    names = pickle.load(f)['names']

# ===== 下载30分钟数据 =====
import akshare as ak
PREFIX = lambda c: 'sh' if c.startswith('6') else 'sz'

SAMPLE_N = 200  # 扫200只
morn_cache = {}  # {code: df_30min}

for i, code in enumerate(codes[:SAMPLE_N]):
    sym = f'{PREFIX(code)}{code}'
    try:
        df = ak.stock_zh_a_minute(symbol=sym, period='30')
        morn_cache[code] = df
    except:
        pass
    if (i+1) % 50 == 0:
        print(f'[{i+1}/{SAMPLE_N}] 已缓存{len(morn_cache)}只')
    time.sleep(0.1)

print(f'缓存: {len(morn_cache)}只')

# ===== 扫描开盘强势信号 =====
print('\n扫描开盘强势信号...')
hits = []
total_days_set = set()

for code, df in morn_cache.items():
    nm = names.get(code, '?')
    if 'ST' in nm or '*ST' in nm or '退' in nm: continue
    
    # 取每天10:00 bar (9:30-10:00)
    m10 = df[df['day'].str.contains('10:00', na=False)].copy()
    
    for idx in range(len(m10)):
        row = m10.iloc[idx]
        dt = str(row['day'])[:10]
        total_days_set.add(dt)
        
        o = float(row['open'])
        c = float(row['close'])
        h = float(row['high'])
        v = float(row['volume'])
        
        # 开盘30分钟涨幅
        pct = round((c - o) / o * 100, 2) if o > 0 else 0
        if pct < 3: continue  # 不够强
        
        # 量比: 对比前5天同时间段的量
        if idx >= 5:
            prev_vols = [float(m10.iloc[idx-k]['volume']) for k in range(1,6)]
            avg_vol = sum(prev_vols)/len(prev_vols) if prev_vols else 1
            vr = v / avg_vol if avg_vol > 0 else 1
        else:
            vr = 1
        
        if vr < 1.2: continue  # 量不够
        
        # 当天后续走势
        day_bars = df[df['day'].str.startswith(dt)]
        if len(day_bars) == 0: continue
        
        # 后续最高（到收盘）
        later_bars = day_bars[day_bars['day'] > row['day']]
        if len(later_bars) == 0: continue
        later_max = max(float(b) for b in later_bars['high'])
        high_pct = round((later_max - o) / o * 100, 2)
        
        close_bar = day_bars.iloc[-1]
        close_pct = round((float(close_bar['close']) - o) / o * 100, 2)
        
        hits.append({
            'date': dt, 'code': code, 'name': nm,
            'open': o, 'morn_pct': pct, 'vr': round(vr, 1),
            'high_pct': high_pct, 'close_pct': close_pct,
        })

# 统计
print(f'总交易日: {len(total_days_set)}')
print(f'开盘强势信号: {len(hits)}个')

if hits:
    pct2 = sum(1 for h in hits if h['high_pct'] >= 2.5)
    pct5 = sum(1 for h in hits if h['high_pct'] >= 5.0)
    close_ok = sum(1 for h in hits if h['close_pct'] >= 2.5)
    print(f'\n胜率（盘中最高≥2.5%）: {pct2}/{len(hits)} = {pct2/len(hits)*100:.0f}%')
    print(f'胜率（盘中最高≥5.0%）: {pct5}/{len(hits)} = {pct5/len(hits)*100:.0f}%')
    print(f'收盘≥2.5%: {close_ok}/{len(hits)} = {close_ok/len(hits)*100:.0f}%')
    
    print(f'\n逐日明细（前30）:')
    print(f'{"日期":>10} {"代码":>7} {"名称":>8} {"开盘":>8} {"涨幅%":>6} {"量比":>5} {"最高%":>6} {"收盘%":>6}')
    hits.sort(key=lambda x: x['date'])
    for h in hits[:30]:
        d, c, n = h['date'], h['code'], h['name'][:6]
        o, mp, vr = h['open'], h['morn_pct'], h['vr']
        hp, cp = h['high_pct'], h['close_pct']
        print(f'{d:>10} {c:>7} {n:>8} {o:>8.2f} {mp:>+5.1f}% {vr:>5.1f} {hp:>+5.1f}% {cp:>+5.1f}%')
