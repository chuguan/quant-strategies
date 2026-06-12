#!/usr/bin/env python3
"""实时行情快照刷新 — 14:50 运行
轻量版：只拉实时行情（不拉K线，14:30预热的还在），刷新 unified_snapshot.json + industry_snapshot.json
V13/V42/V50 的二次选股自动读到最新数据。
"""
import os, json, subprocess, time, sqlite3
from collections import defaultdict
from datetime import datetime

# ===== 路径 =====
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/prod')
CACHE_DIR = os.path.normpath(os.path.expanduser(
    '~/AppData/Local/hermes/hermes-agent/cache'))
SNAPSHOT_PATH = os.path.normpath(os.path.join(CACHE_DIR, '..', 'unified_snapshot.json'))
IND_PATH = os.path.normpath(os.path.join(CACHE_DIR, '..', 'industry_snapshot.json'))

PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))


def curl_get(url, timeout=8):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url],
                          capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except:
        return ''


# 预加载量比（从SQLite取上交易日VR）
cache_vr = {}
try:
    _db = sqlite3.connect(os.path.join(SCRIPTS_DIR, 'v13_quant.db'), timeout=3)
    _today = datetime.now().strftime('%Y-%m-%d')
    _cur = _db.execute(
        'SELECT DISTINCT date FROM data_cache WHERE vr>0 AND date<? ORDER BY date DESC LIMIT 1',
        (_today,))
    _last = _cur.fetchone()
    if _last:
        _last_date = _last[0]
        _cur2 = _db.execute(
            'SELECT code, vr FROM data_cache WHERE date=? AND vr>0', (_last_date,))
        cache_vr = {r[0]: r[1] for r in _cur2.fetchall()}
    _db.close()
except:
    pass

# 加载行业映射
industry_map = {}
for p in [os.path.join(SCRIPTS_DIR, 'data', 'industry_map.pkl'),
          os.path.join(SCRIPTS_DIR, 'industry_map.pkl')]:
    if os.path.exists(p):
        try:
            import pickle
            industry_map = pickle.load(open(p, 'rb'))
        except:
            pass
        if industry_map:
            break

print('🔄 实时行情快照刷新...', flush=True)
t0 = time.time()

codes = [str(i) for i in range(600000, 606000)] + [f'{i:06d}' for i in range(3000)]
stocks = {}
for i in range(0, len(codes), 80):
    chunk = codes[i:i + 80]
    symbols = [f'{PREFIX(c)}{c}' for c in chunk]
    text = curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}', timeout=8)
    for line in text.split('\n'):
        if '~' not in line:
            continue
        parts = line.split('~')
        if len(parts) < 40:
            continue
        try:
            nm = parts[1]
            code = parts[2]
            if not nm or 'ST' in nm or '*ST' in nm or '退' in nm:
                continue
            if not IS_MAIN(code):
                continue
            price = float(parts[3])
            prev_c = float(parts[4])
            pct = round((price / prev_c - 1) * 100, 2) if prev_c else 0
            vol_r = cache_vr.get(code, float(parts[38])) if parts[38] else 0
            hsl = 0
            try:
                hsl = float(parts[46]) if parts[46] and float(parts[46]) < 100 else 0
            except:
                pass
            pe = float(parts[39]) if parts[39] else 0
            sz = 0
            try:
                sz = float(parts[44]) / 1e8 if parts[44] else 0
            except:
                pass
            stocks[code] = {
                'name': nm, 'price': price, 'p': pct,
                'vol_ratio': vol_r, 'hsl': hsl, 'pe': pe, 'sz': sz
            }
        except:
            pass

# 写入快照
snap = {
    'time': datetime.now().strftime('%H:%M'),
    'date': datetime.now().strftime('%Y-%m-%d'),
    'ts': time.time(),
    'stocks': stocks,
    'stats': {
        'total': len(stocks),
        'with_hsl': sum(1 for s in stocks.values() if s['hsl'] > 0),
    }
}
os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
with open(SNAPSHOT_PATH, 'w', encoding='utf-8') as f:
    json.dump(snap, f, ensure_ascii=False)

# 更新行业快照
try:
    ind_prices = defaultdict(list)
    for code, s in stocks.items():
        ind = industry_map.get(code, '')
        if ind:
            ind_prices[ind].append(s['p'])
    live_ind_avg = {k: round(sum(v) / len(v), 2) for k, v in ind_prices.items() if v}
    ind_data = {
        'time': snap['time'],
        'date': snap['date'],
        'stocks': {c: {'price': s['price'], 'pct': s['p']} for c, s in stocks.items()},
        'ind_avg': live_ind_avg,
        'stats': {'total': len(stocks), 'industries': len(live_ind_avg)},
    }
    with open(IND_PATH, 'w', encoding='utf-8') as f:
        json.dump(ind_data, f, ensure_ascii=False)
except Exception as e:
    print(f'⚠️ 行业快照: {e}', flush=True)

elapsed = time.time() - t0
print(f'✅ 快照刷新完成: {len(stocks)}只, 耗时{elapsed:.0f}s', flush=True)
print(f'   V13/V42/V50二次选股将自动读取最新数据', flush=True)
