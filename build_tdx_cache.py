"""
构建通达信数据缓存 — 5年日K线
"""
import os, pickle, struct, sys
from collections import defaultdict

TDX_DIR = r'C:\new_tdx_mock\vipdoc'
OUT_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')

def parse_day(filepath):
    """解析通达信日K线.day文件"""
    with open(filepath, 'rb') as f:
        data = f.read()
    records = []
    for i in range(0, len(data), 32):
        if i + 32 > len(data): break
        rec = data[i:i+32]
        d = struct.unpack('<i', rec[0:4])[0]
        o = struct.unpack('<i', rec[4:8])[0] / 100
        h = struct.unpack('<i', rec[8:12])[0] / 100
        l = struct.unpack('<i', rec[12:16])[0] / 100
        c = struct.unpack('<i', rec[16:20])[0] / 100
        a = struct.unpack('<f', rec[20:24])[0]
        v = struct.unpack('<I', rec[24:28])[0]
        dt = f'{d//10000}-{d%10000//100:02d}-{d%100:02d}'
        records.append({'date': dt, 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v, 'amount': a})
    return records

# 主板过滤
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
ALL_MAIN = lambda c: c[:3] in ('600','601','603','605','000','001','002','300','688','900')

# 遍历所有.day文件
data = defaultdict(list)
names = {}
real = {}
count = 0

for mkt in ['sh', 'sz']:
    d = os.path.join(TDX_DIR, mkt, 'lday')
    if not os.path.exists(d): continue
    for fn in os.listdir(d):
        if not fn.endswith('.day'): continue
        code = fn.replace('.day', '').replace(mkt, '')
        # 跳过指数
        if code[:3] in ('000','880','399','139','159'): continue
        # 只保留主板A股
        if not (code.startswith(('600','601','603','605','000','001','002'))): continue
        
        records = parse_day(os.path.join(d, fn))
        if len(records) < 60: continue
        
        # 算涨跌幅
        for j in range(1, len(records)):
            prev = records[j-1]['close']
            records[j]['p'] = round((records[j]['close'] - prev) / prev * 100, 2) if prev > 0 else 0
        records[0]['p'] = 0
        
        for r in records:
            data[r['date']].append({
                'code': code, 'close': r['close'], 'p': r['p'],
                'open': r['open'], 'high': r['high'], 'low': r['low'],
                'volume': r['volume'],
            })
        
        count += 1
        if count % 500 == 0:
            print(f'已处理{count}只...')

print(f'\n处理完成: {count}只股票')
print(f'交易日: {len(data)}天')
print(f'日期范围: {min(data.keys())} ~ {max(data.keys())}')

# 保存
out = os.path.join(OUT_DIR, 'tdx_cache.pkl')
with open(out, 'wb') as f:
    pickle.dump({'data': dict(data), 'names': names, 'real': real}, f)
print(f'已保存: {out}')
print(f'大小: {os.path.getsize(out)/1024/1024:.0f}MB')
