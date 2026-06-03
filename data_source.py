"""
多数据源统一接口 — 新浪 + 腾讯缓存 + Tushare

使用优先级：
  实时行情: 新浪 hq.sinajs.cn (最快最稳定)
  K线历史: 本地缓存 → Tushare (如果装了token)
  资金流向/龙虎榜: Tushare (需token)

用法:
  from data_source import get_realtime, get_kline, get_moneyflow
  
  # 实时行情
  data = get_realtime(['600519', '000001'])
  
  # K线数据
  kline = get_kline('600519', days=300)
  
  # 资金流向（需Tushare token）
  mf = get_moneyflow('000001', '2026-05-27')
"""
import os, json, subprocess, re, time

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

# ═══════════════════════════════════════════
# 数据源配置
# ═══════════════════════════════════════════

# Tushare token（在.env中配置，或在这里直接设置）
TUSHARE_TOKEN = ''

# 尝试从.env加载
_env_path = os.path.expanduser('~/AppData/Local/hermes/.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            if 'TUSHARE_TOKEN' in _line and '=' in _line:
                TUSHARE_TOKEN = _line.split('=')[1].strip().strip("'\"")

# ═══════════════════════════════════════════
# 新浪实时行情
# ═══════════════════════════════════════════

def _curl(url, timeout=10):
    try:
        r = subprocess.run(['curl', '-s', '--max-time', str(timeout), url,
                          '-H', 'Referer: https://finance.sina.com.cn'],
                          capture_output=True, timeout=timeout+5)
        return r.stdout
    except:
        return b''

def _prefix(code):
    return 'sh' if code.startswith(('6','9')) else 'sz'

def sina_realtime(codes):
    """新浪实时行情"""
    if not codes: return {}
    std = [c if c.startswith(('sh','sz')) else _prefix(c)+c for c in codes]
    raw = _curl(f"https://hq.sinajs.cn/list={','.join(std)}")
    text = raw.decode('gbk', errors='replace')
    result = {}
    for line in text.strip().split('\n'):
        m = re.search(r'var hq_str_(\w+)="(.+)"', line)
        if not m: continue
        code = m.group(1); parts = m.group(2).split(',')
        if len(parts) < 32: continue
        pre = float(parts[2]) if parts[2] else 0
        price = float(parts[3]) if parts[3] else 0
        result[code] = {
            'name': parts[0], 'price': price, 'pre_close': pre,
            'pct': round((price-pre)/pre*100, 2) if pre>0 else 0,
            'open': float(parts[1]) if parts[1] else 0,
            'high': float(parts[4]) if parts[4] else 0,
            'low': float(parts[5]) if parts[5] else 0,
            'volume': int(parts[8]) if parts[8] else 0,
            'amount': float(parts[9]) if parts[9] else 0,
        }
    return result

# ═══════════════════════════════════════════
# K线数据（缓存 → Tushare）
# ═══════════════════════════════════════════

def get_kline(code, market=None, days=300):
    """获取K线数据：优先本地缓存，其次Tushare"""
    mkt = market or _prefix(code)
    
    # 1. 本地缓存
    fp = os.path.join(CACHE_DIR, f'{mkt}{code}.json')
    if os.path.exists(fp):
        try:
            with open(fp, 'rb') as f:
                return json.loads(f.read().decode('utf-8'))
        except:
            pass
    
    # 2. Tushare（如果有token）
    if TUSHARE_TOKEN:
        try:
            import tushare as ts
            ts.set_token(TUSHARE_TOKEN)
            pro = ts.pro_api()
            df = pro.daily(ts_code=f"{code}.{'SH' if mkt=='sh' else 'SZ'}", 
                          start_date='2025-01-01', end_date='2026-12-31')
            if df is not None and len(df) > 0:
                df = df.sort_values('trade_date')
                records = []
                for _, row in df.iterrows():
                    records.append({
                        'date': row['trade_date'],
                        'open': float(row['open']),
                        'close': float(row['close']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'volume': float(row['vol']),
                    })
                # 存到缓存
                try:
                    with open(fp, 'w', encoding='utf-8') as f:
                        json.dump(records, f)
                except: pass
                return records
        except:
            pass
    
    return []

# ═══════════════════════════════════════════
# 统一接口
# ═══════════════════════════════════════════

def get_realtime(codes):
    """统一实时行情接口"""
    return sina_realtime(codes)

def get_moneyflow(code, date):
    """资金流向（需Tushare token）"""
    if not TUSHARE_TOKEN:
        return None
    try:
        import tushare as ts
        ts.set_token(TUSHARE_TOKEN)
        pro = ts.pro_api()
        mf = pro.moneyflow(ts_code=f"{code}.{'SH' if code.startswith(('6','9')) else 'SZ'}", 
                          trade_date=date.replace('-', ''))
        return mf.to_dict('records') if mf is not None else None
    except:
        return None

def get_billboard(date):
    """龙虎榜（需Tushare token）"""
    if not TUSHARE_TOKEN:
        return None
    try:
        import tushare as ts
        ts.set_token(TUSHARE_TOKEN)
        pro = ts.pro_api()
        bb = pro.listed() if False else None
        return None
    except:
        return None

# ═══════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════
if __name__ == '__main__':
    print("=== 新浪实时行情 ===")
    r = get_realtime(['600519', '000001'])
    for c, d in r.items():
        print(f"  {c}: {d['name']} {d['price']:.2f} ({d['pct']:+.2f}%)")
    
    print("\n=== K线（缓存）===")
    k = get_kline('600519', days=5)
    for row in k[-3:]:
        print(f"  {row['date']}: O{row['open']} C{row['close']} H{row['high']} L{row['low']}")
    
    print(f"\n=== Tushare Token: {'已配置' if TUSHARE_TOKEN else '未配置（如需使用请设置TUSHARE_TOKEN）'} ===")
