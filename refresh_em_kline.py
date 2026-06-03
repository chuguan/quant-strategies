"""
东方财富全量K线下载 — 替换所有缓存

地址: https://push2his.eastmoney.com/api/qt/stock/kline/get
参数: secid=1.600519 klt=101(日K) fqt=1(前复权) lmt=365
格式: date,open,close,high,low,volume,amount,amplitude,pct,change,turnover

分批慢速下载，防止被封。完成后替换现有缓存。
"""
import json, os, sys, time, requests

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
POOL_FILE = os.path.expanduser('~/AppData/Local/hermes/scripts/活跃股票池_3043.json')

def load_pool():
    with open(POOL_FILE, encoding='utf-8') as f:
        return json.load(f)

def em_kline(code, retries=3):
    """东方财富K线"""
    mkt = '1' if code.startswith(('6','9')) else '0'
    url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={mkt}.{code}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&end=20500101&lmt=365"
    
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            if r.status_code != 200:
                return None
            d = r.json()
            if d.get('rc') != 0 or not d.get('data') or not d['data'].get('klines'):
                return None
            klines = d['data']['klines']
            records = []
            for line in klines:
                parts = line.split(',')
                if len(parts) < 7:
                    continue
                records.append({
                    'date': parts[0],
                    'open': float(parts[1]),
                    'close': float(parts[2]),
                    'high': float(parts[3]),
                    'low': float(parts[4]),
                    'volume': float(parts[5]),
                })
            return records
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
    return None

def main():
    codes = load_pool()
    # 过滤已有缓存中已用东方财富数据的
    todo = []
    for code in codes:
        mkt = 'sh' if code.startswith(('6','9')) else 'sz'
        fp = os.path.join(CACHE_DIR, f'{mkt}{code}.json')
        todo.append((code, mkt, fp))
    
    total = len(todo)
    done = 0
    success = 0
    failed = 0
    skipped = 0
    
    print(f"开始下载 {total} 只股票...")
    start = time.time()
    
    ok = 0
    for code, mkt, fp in todo:
        records = em_kline(code)
        done += 1
        
        if records and len(records) >= 200:
            with open(fp, 'w', encoding='utf-8') as f:
                json.dump(records, f)
            success += 1
        else:
            failed += 1
            print(f"  ❌ {code}: {len(records) if records else 0}条")
        
        # 进度条
        if done % 100 == 0 or done == total:
            elapsed = time.time() - start
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            print(f"  [{done}/{total}] 成功{success} 失败{failed} 跳过{skipped} "
                  f"速率{rate:.1f}只/秒 预计剩余{eta:.0f}秒")
        
        # 限速: 每秒最多5次
        time.sleep(0.25)
    
    elapsed = time.time() - start
    print(f"\n✅ 完成! {total}只, 成功{success} 失败{failed} 跳过{skipped}")
    print(f"耗时 {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)")
    print(f"平均 {total/elapsed:.1f}只/秒")

if __name__ == '__main__':
    main()
