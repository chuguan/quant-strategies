"""
补 data_sina 表 — 从腾讯5分钟K线提取每天14:50价格
遍历沪深主板3043只股票，取5分钟K线→14:50价格→存入data_sina
"""
import sqlite3, json, os, subprocess, time, sys
from datetime import datetime

DB = os.path.expanduser(r'~/AppData/Local/hermes/scripts/v13_quant.db')
CACHE_DIR = os.path.expanduser(r'~/AppData/Local/hermes/hermes-agent/cache')
BATCH_SIZE = 500

def get_stock_codes():
    """从缓存文件获取所有主板代码"""
    codes = []
    if os.path.exists(CACHE_DIR):
        for fn in sorted(os.listdir(CACHE_DIR)):
            if not fn.endswith('.json'): continue
            code = fn.replace('.json', '')
            raw = code.lstrip('sh').lstrip('sz')
            if raw.startswith('300') or raw.startswith('688'): continue
            if raw.startswith('000') or raw.startswith('001') or raw.startswith('002') \
               or raw.startswith('600') or raw.startswith('601') or raw.startswith('603') \
               or raw.startswith('605'):
                codes.append((code, raw))
    return codes

def get_market_prefix(raw_code):
    """sh: 600/601/603/605, sz: 000/001/002"""
    if raw_code.startswith(('600','601','603','605')):
        return 'sh'
    return 'sz'

def fetch_5min(code_key, raw_code):
    """取5分钟K线，返回{date: 14:50_close}，自动尝试sh/sz"""
    for prefix in [code_key[:2], get_market_prefix(raw_code)]:
        if prefix not in ('sh','sz'): continue
        full_key = prefix + raw_code
        url = f'https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={full_key},m5,,320'
        try:
            r = subprocess.run(['curl', '-s', '--max-time', '10', url,
                               '-H', 'User-Agent: Mozilla/5.0'],
                              capture_output=True, timeout=15)
            raw = r.stdout.decode('utf-8', errors='replace')
            if not raw or raw.startswith('<!'): continue
            if raw.startswith('_'):
                idx = raw.index('(')
                raw = raw[idx+1:-1]
            d = json.loads(raw)
            data_set = d.get('data',{})
            mk = data_set.get(full_key,{}).get('m5',[])
            if not mk:
                # 可能key不同
                for k in data_set:
                    if isinstance(data_set[k], dict) and 'm5' in data_set[k]:
                        mk = data_set[k]['m5']
                        break
            if not mk: continue
            result = {}
            for k in mk:
                dt_str = k[0]
                if '1450' in dt_str:
                    date = f'{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:8]}'
                    close_1450 = float(k[2])
                    result[date] = {'price': close_1450, 'close': float(k[2]), 'high': float(k[3])}
            if result:
                return result
        except:
            continue
    return {}

def main():
    codes = get_stock_codes()
    print(f'沪深主板: {len(codes)}只')
    
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    # 建索引
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sina_date ON data_sina(date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sina_code ON data_sina(code)')
    
    stored = 0
    failed = 0
    batch = []
    
    for i, (code_key, raw_code) in enumerate(codes):
        if i % 100 == 0 and i > 0:
            print(f'  {i}/{len(codes)}  已存{stored}  失败{failed}')
        
        # 跳过已经有的
        cur.execute('SELECT COUNT(*) FROM data_sina WHERE code=?', (raw_code,))
        if cur.fetchone()[0] > 0:
            continue
        
        data = fetch_5min(code_key, raw_code)
        if not data:
            failed += 1
            continue
        
        yesterday_close = None
        for date, info in sorted(data.items()):
            price_1450 = info['price']
            batch.append((date, '14:50', raw_code, '', price_1450, 0, 0, 0, 0, 0, 0, 'tencent:5min', i))
            stored += 1
        
        # 分批写入
        if len(batch) >= BATCH_SIZE:
            cur.executemany(
                'INSERT OR IGNORE INTO data_sina(date,time,code,name,price,pre_close,pct,high,low,volume,amount,api_endpoint,fetch_batch) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                batch
            )
            conn.commit()
            batch = []
        
        time.sleep(0.3)  # 300ms间隔防封
    
    # 写入剩余
    if batch:
        cur.executemany(
            'INSERT OR IGNORE INTO data_sina(date,time,code,name,price,pre_close,pct,high,low,volume,amount,api_endpoint,fetch_batch) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
            batch
        )
        conn.commit()
    
    conn.close()
    print(f'\n完成! 共存储{stored}条, 失败{failed}只')

if __name__ == '__main__':
    main()
