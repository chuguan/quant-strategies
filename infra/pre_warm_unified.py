#!/usr/bin/env python3
"""统一缓存预热 — 14:30 运行
一次性预热所有策略所需的数据：
1. K线缓存 (sh{code}.json, 1h TTL) → V13/V42/V50 的 fetch_kline() 直接读本地
2. 实时行情快照 (unified_snapshot.json) → V13/V42/V50 的 get_live_stocks() 直接读本地
3. 行业快照 (industry_snapshot.json) → 兼容历史格式

所有策略从此只需要读本地，0网络请求。
"""
import os, json, subprocess, time, sys, sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ===== 路径 =====
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/prod')
CACHE_DIR = os.path.normpath(os.path.expanduser(
    '~/AppData/Local/hermes/hermes-agent/cache'))
os.makedirs(CACHE_DIR, exist_ok=True)

SNAPSHOT_PATH = os.path.join(CACHE_DIR, '..', 'unified_snapshot.json')
SNAPSHOT_PATH = os.path.normpath(SNAPSHOT_PATH)
IND_PATH = os.path.normpath(os.path.join(CACHE_DIR, '..', 'industry_snapshot.json'))

PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

# ===== 股票池 =====
# 优先从活跃股票池_3043.json加载
active_codes = []
pool_file = os.path.join(SCRIPTS_DIR, 'data', '活跃股票池_3043.json')
if os.path.exists(pool_file):
    try:
        pool = json.load(open(pool_file, encoding='utf-8'))
        active_codes = pool.get('codes', [])
    except:
        pass
if not active_codes:
    active_codes = [str(i) for i in range(600000, 606000)] + \
                   [f'{i:06d}' for i in range(3000)]

# 排除ST等
try:
    db = sqlite3.connect(os.path.join(SCRIPTS_DIR, 'v13_quant.db'), timeout=3)
    excluded = set(r[0] for r in db.execute(
        'SELECT code FROM excluded_stocks WHERE active=1'))
    db.close()
except:
    excluded = set()

# 加载行业映射（如果有）
industry_map = {}
ind_map_file = os.path.join(SCRIPTS_DIR, 'data', 'industry_map.pkl')
if not os.path.exists(ind_map_file):
    ind_map_file = os.path.join(SCRIPTS_DIR, 'industry_map.pkl')
if os.path.exists(ind_map_file):
    try:
        import pickle
        industry_map = pickle.load(open(ind_map_file, 'rb'))
    except:
        pass
# 从DB补充（主数据源）
if not industry_map:
    try:
        _db = sqlite3.connect(os.path.join(SCRIPTS_DIR, 'v13_quant.db'), timeout=3)
        for r in _db.execute('SELECT code, industry FROM stock_industry'):
            industry_map[r[0]] = r[1]
        _db.close()
    except:
        pass

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))


def curl_get(url, timeout=8):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url],
                          capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except:
        return ''


# ═══════════════════════════════════════════════════════════════
# 第一步：K线缓存预热（同原pre_warm_cache.py）
# ═══════════════════════════════════════════════════════════════
def fetch_kline(code):
    """拉取300天日K线并缓存到本地"""
    if code in excluded:
        return None
    mkt = PREFIX(code)
    kf = os.path.join(CACHE_DIR, f'{mkt}{code}.json')
    if os.path.exists(kf) and time.time() - os.path.getmtime(kf) < 3600 * 2:
        return None  # 缓存有效
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt}{code},day,,,300,qfq'
    text = curl_get(url, timeout=6)
    if text and text.strip().startswith('{'):
        try:
            d = json.loads(text)
            sd = d.get('data', {}).get(f'{mkt}{code}', {})
            k = sd.get('qfqday', [])
            if not k:
                for key in sd:
                    if isinstance(sd[key], list) and sd[key] and isinstance(sd[key][0], list):
                        k = sd[key]
                        break
            if k and len(k) >= 80:
                recs = [{'date': x[0], 'open': float(x[1]), 'close': float(x[2]),
                         'high': float(x[3]), 'low': float(x[4]), 'volume': float(x[5])}
                        for x in k]
                with open(kf, 'w') as f:
                    json.dump(recs, f)
                return 1  # 成功
        except:
            pass
    return None


def warm_kline_cache():
    """多线程预热K线缓存"""
    print('🚀 K线缓存预热...', flush=True)
    t0 = time.time()
    fetched = 0
    errors = 0
    total = len(active_codes)

    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(fetch_kline, c): c for c in active_codes}
        for f in as_completed(futures):
            try:
                r = f.result()
                if r == 1:
                    fetched += 1
            except:
                errors += 1
            done = fetched + errors
            if done % 500 == 0 and done > 0:
                print(f'  ⏳ {done}/{total} ({done*100//total}%) 新拉{fetched}条',
                      flush=True)

    elapsed = time.time() - t0
    print(f'✅ K线预热: 新拉{fetched}条, 失败{errors}条, 耗时{elapsed:.0f}s',
          flush=True)
    return fetched, errors


# ═══════════════════════════════════════════════════════════════
# 第二步：实时行情快照（腾讯API，跟V13/V42/V50完全一样的字段）
# ═══════════════════════════════════════════════════════════════
def fetch_realtime_snapshot():
    """拉取全市场3043只实时行情，保存为unified_snapshot.json
    格式跟V13/V42/V50的get_live_stocks()完全一致"""
    print('📡 实时行情快照...', flush=True)
    t0 = time.time()

    # 预加载量比（从SQLite取上交易日VR，跟V13保持一致）
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

    # 同V13/V42: 600000~606000 + 000~002
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

    print(f'💾 快照: {SNAPSHOT_PATH} ({len(stocks)}只, {time.time()-t0:.0f}s)',
          flush=True)

    # 同时更新industry_snapshot.json（兼容旧格式）
    try:
        # 计算行业均值
        from collections import defaultdict
        ind_prices = defaultdict(list)
        for code, s in stocks.items():
            ind = industry_map.get(code, '')
            if ind:
                ind_prices[ind].append(s['p'])
        live_ind_avg = {k: round(sum(v) / len(v), 2)
                        for k, v in ind_prices.items() if v}

        ind_data = {
            'time': snap['time'],
            'date': snap['date'],
            'stocks': {c: {'price': s['price'], 'pct': s['p']}
                       for c, s in stocks.items()},
            'ind_avg': live_ind_avg,
            'stats': {'total': len(stocks), 'industries': len(live_ind_avg)},
        }
        with open(IND_PATH, 'w', encoding='utf-8') as f:
            json.dump(ind_data, f, ensure_ascii=False)
        print(f'💾 行业快照: {IND_PATH} ({len(live_ind_avg)}行业)', flush=True)
    except Exception as e:
        print(f'⚠️ 行业快照保存失败: {e}', flush=True)

    return stocks


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('=' * 50, flush=True)
    print(f'🔋 统一缓存预热启动 {datetime.now().strftime("%H:%M:%S")}', flush=True)
    print('=' * 50, flush=True)
    t_all = time.time()

    # 1. K线缓存预热
    warm_kline_cache()

    # 2. 实时行情快照
    fetch_realtime_snapshot()

    elapsed = time.time() - t_all
    print(f'\n✅ 统一预热完成! 总耗时{elapsed:.0f}s', flush=True)
    print(f'   各策略在14:44~14:48运行时将直接读本地缓存，无需网络请求',
          flush=True)
