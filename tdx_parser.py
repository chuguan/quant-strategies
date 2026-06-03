"""
通达信.day文件解析器
格式: 32字节/条, 大端
  int date     YYYYMMDD
  int open     * 1000
  int high     * 1000
  int low      * 1000
  int close    * 1000
  float amount  成交额
  int volume    成交量(股)
  int reserve   保留
"""
import os, struct
from datetime import datetime

TDX_DIR = '/c/new_tdx_mock/vipdoc'

def parse_day(code):
    """解析单只股票日K线"""
    mkt = 'sh' if code.startswith(('6','9')) or code.startswith(('0','3')) else 'sz'
    # 上证: sh, 深证: sz
    if code.startswith(('0','3')):
        mkt = 'sz'
    elif code.startswith(('6','9')):
        mkt = 'sh'
    
    fp = os.path.join(TDX_DIR, mkt, 'lday', f'{mkt}{code}.day')
    if not os.path.exists(fp):
        return None
    
    with open(fp, 'rb') as f:
        data = f.read()
    
    records = []
    for i in range(0, len(data), 32):
        if i + 32 > len(data): break
        rec = data[i:i+32]
        date_int = struct.unpack('<i', rec[0:4])[0]
        open_p = struct.unpack('<i', rec[4:8])[0] / 100
        high = struct.unpack('<i', rec[8:12])[0] / 100
        low = struct.unpack('<i', rec[12:16])[0] / 100
        close = struct.unpack('<i', rec[16:20])[0] / 100
        amount = struct.unpack('<f', rec[20:24])[0]
        volume = struct.unpack('<I', rec[24:28])[0]
        
        dt_str = str(date_int)
        dt = f'{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:8]}'
        
        records.append({
            'date': dt, 'open': open_p, 'high': high,
            'low': low, 'close': close,
            'volume': volume, 'amount': amount,
        })
    
    # 算涨跌幅
    for i in range(len(records)):
        if i > 0:
            prev = records[i-1]['close']
            records[i]['p'] = round((records[i]['close'] - prev) / prev * 100, 2) if prev > 0 else 0
        else:
            records[i]['p'] = 0
    
    return records

def tdx_to_big_cache():
    """把通达信数据转成big_cache格式"""
    import pickle, json
    from collections import defaultdict
    
    # 获取股票列表
    import re
    sh_files = [f for f in os.listdir(os.path.join(TDX_DIR, 'sh', 'lday')) if f.endswith('.day')]
    sz_files = [f for f in os.listdir(os.path.join(TDX_DIR, 'sz', 'lday')) if f.endswith('.day')]
    
    print(f'SH: {len(sh_files)}, SZ: {len(sz_files)}')
    
    data = defaultdict(list)
    names = {}
    real = {}
    
    for files, mkt in [(sh_files, 'sh'), (sz_files, 'sz')]:
        for fn in files:
            code = fn.replace('.day', '').replace(mkt, '')
            # 跳过指数 (000开头是上证指数等)
            if code.startswith('000') or code.startswith('880') or code.startswith('399'):
                continue
            # 只保留主板A股
            if not (code.startswith(('600','601','603','605','000','001','002'))):
                continue
            
            records = parse_day(code)
            if not records or len(records) < 60: continue
            
            for r in records:
                dt = r['date']
                data[dt].append({
                    'code': code,
                    'close': r['close'],
                    'p': r['p'],
                    'open': r['open'],
                    'high': r['high'],
                    'low': r['low'],
                    'volume': r['volume'],
                })
    
    print(f'交易日: {len(data)}')
    print(f'总记录: {sum(len(v) for v in data.values())}')
    
    out_path = os.path.join(os.path.expanduser('~/AppData/Local/hermes/scripts'), 'tdx_big_cache.pkl')
    with open(out_path, 'wb') as f:
        pickle.dump({'data': dict(data), 'names': names, 'real': real}, f)
    print(f'已保存: {out_path}')

if __name__ == '__main__':
    # 测试
    r = parse_day('600519')
    if r:
        print(f'600519: {len(r)}条, {r[0]["date"]}~{r[-1]["date"]}')
        print(f'  最近: {r[-1]}')
    r = parse_day('000001')
    if r:
        print(f'000001: {len(r)}条, {r[0]["date"]}~{r[-1]["date"]}')
        print(f'  最近: {r[-1]}')
