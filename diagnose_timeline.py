"""检查数据完整性的时间线"""
import pickle, os, sys
sys.path.insert(0, os.path.dirname(__file__))

d = pickle.load(open('big_cache_full.pkl', 'rb'))
data = d['data']
dates = sorted(data.keys())

# 找哪天开始超过100只、500只、2000只、2900只
print('数据完整性时间线:')
for dt in dates:
    n = len(data[dt])
    if n in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] or n % 500 < 50 or n >= 2900:
        if n >= 2900 and n % 100 != 0:
            # Only show first time reaching 2900
            pass
        else:
            print(f'  {dt}: {len(data[dt])}只')

# 重点：看2025年的数据增长
print('\n2025年关键节点:')
for dt in dates:
    if dt.startswith('2025'):
        n = len(data[dt])
        if n < 100:
            print(f'  {dt}: {n}只')
# 找到第一个超过500只的
for dt in dates:
    if len(data[dt]) >= 500:
        print(f'\n首次≥500只: {dt} ({len(data[dt])}只)')
        break
for dt in dates:
    if len(data[dt]) >= 2000:
        print(f'首次≥2000只: {dt} ({len(data[dt])}只)')
        break
for dt in dates:
    if len(data[dt]) >= 2900:
        print(f'首次≥2900只: {dt} ({len(data[dt])}只)')
        break

# 查最近30天的股票数
print('\n最近30天股票数:')
last30 = [dt for dt in dates if dt >= '2026-04-20'][-30:]
for dt in last30:
    print(f'  {dt}: {len(data[dt])}只')
