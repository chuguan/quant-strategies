"""检查big_cache原始数据字段"""
import pickle, os

path = '/c/Users/12546/AppData/Local/hermes/scripts/release/V50/big_cache_full.pkl'
print(f'File size: {os.path.getsize(path)/1e6:.1f} MB')

with open(path, 'rb') as f:
    cache = pickle.load(f)

data = cache['data']
real = cache.get('real', {})
names = cache.get('names', {})

print(f'dates: {len(data)}')
dates = sorted(data.keys())
print(f'Sample dates: {dates[:3]} ... {dates[-3:]}')

# Get first stock entry
first_date = dates[0]
stocks = data[first_date]
print(f'Stocks on {first_date}: {len(stocks)}')

first_stock = stocks[0]
print(f'\\nFirst stock: {first_stock}')
print(f'\\nType: {type(first_stock).__name__}')
if isinstance(first_stock, dict):
    print(f'Fields ({len(first_stock)}):')
    for k, v in sorted(first_stock.items()):
        print(f'  {k}: {v} ({type(v).__name__})')
elif isinstance(first_stock, (list, tuple)):
    print(f'First 3 items: {first_stock[:3]}')

# Also check real data
print(f'\\nReal data: {len(real)} stocks')
if real:
    sample_code = next(iter(real.keys()))
    print(f'Sample real[{sample_code}]: {real[sample_code]}')
