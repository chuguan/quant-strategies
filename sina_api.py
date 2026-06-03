"""
新浪API统一接口（实时行情版）
实时行情 → 新浪 hq.sinajs.cn
K线数据 → 本地缓存（腾讯源）
"""
import subprocess, re, os, json

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

def curl_get(url, timeout=10):
    try:
        r = subprocess.run(['curl', '-s', '--max-time', str(timeout), url, 
                          '-H', 'Referer: https://finance.sina.com.cn'],
                          capture_output=True, timeout=timeout+5)
        return r.stdout
    except:
        return b''

def sina_realtime(codes):
    """
    新浪实时行情 
    codes: ['sh600519', 'sz000001'] 或 ['600519','000001']（自动加前缀）
    返回: {code: {name, price, pct, open, pre_close, high, low, volume, amount}}
    """
    # 标准化代码
    std_codes = []
    for c in codes:
        if c.startswith(('sh','sz')):
            std_codes.append(c)
        else:
            std_codes.append(('sh' if c.startswith(('6','9')) else 'sz') + c)
    
    url = f"https://hq.sinajs.cn/list={','.join(std_codes)}"
    raw = curl_get(url, timeout=10)
    text = raw.decode('gbk', errors='replace')
    
    result = {}
    for line in text.strip().split('\n'):
        m = re.search(r'var hq_str_(\w+)="(.+)"', line)
        if not m:
            continue
        code = m.group(1)
        parts = m.group(2).split(',')
        if len(parts) < 32:
            continue
        pre = float(parts[2]) if parts[2] else 0
        price = float(parts[3]) if parts[3] else 0
        result[code] = {
            'name': parts[0],
            'open': float(parts[1]) if parts[1] else 0,
            'pre_close': pre,
            'price': price,
            'high': float(parts[4]) if parts[4] else 0,
            'low': float(parts[5]) if parts[5] else 0,
            'volume': int(parts[8]) if parts[8] else 0,
            'amount': float(parts[9]) if parts[9] else 0,
            'pct': round((price - pre) / pre * 100, 2) if pre > 0 else 0,
        }
    return result

def get_kline(code, market='sh', days=300):
    """从本地缓存获取K线"""
    fp = os.path.join(CACHE_DIR, f'{market}{code}.json')
    if not os.path.exists(fp):
        return []
    try:
        with open(fp, 'rb') as f:
            return json.loads(f.read().decode('utf-8'))
    except:
        return []

# 测试
if __name__ == '__main__':
    r = sina_realtime(['sh600519', 'sz000001'])
    for code, data in r.items():
        print(f"{code}: {data['name']} {data['price']:.2f} ({data['pct']:+.2f}%)")
