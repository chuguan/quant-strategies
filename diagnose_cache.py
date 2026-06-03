"""诊断缓存数据问题"""
import pickle, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))

d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, real, names = d['data'], d['real'], d['names']
dates = sorted(data.keys())

print(f'日期: {dates[0]} ~ {dates[-1]} ({len(dates)}天)')

# 检查几个日期点
for dt in [dates[0], dates[50], dates[100], dates[200], dates[-1]]:
    if dt in data:
        print(f'  {dt}: {len(data[dt])}只, codes: {data[dt][0]["code"]}...{data[dt][-1]["code"]}')

# 检查最近30天n>=2.5比例
last30 = dates[-30:]
good = 0; total = 0
for dt in last30:
    for s in data[dt]:
        n = s.get('n', 0) or 0
        if n >= 2.5: good += 1
        total += 1
print(f'\n最近30天: n>=2.5比例 = {good}/{total} = {good*100/total:.1f}%')

# 检查几个具体股票的n字段
sample_stocks = ['600000', '600519', '000001']
for code in sample_stocks:
    for dt in dates[-10:]:
        stocks = data.get(dt, [])
        for s in stocks:
            if s['code'] == code:
                n = s.get('n', 0)
                p = s.get('p', 0)
                cl = s.get('cl', 0)
                print(f'{dt} {code}: p={p:.2f}% n={n:.1f}% cl={cl:.0f}%')
                break

# 检查2026-05-25具体数据（威龙股份赢的那天）
dt = '2026-05-25'
stocks = data.get(dt, [])
print(f'\n=== {dt} 详细 ===')
# 按n排序
by_n = sorted(stocks, key=lambda s: -(s.get('n',0) or 0))
for s in by_n[:10]:
    code = s.get('code', '')
    nm = names.get(code, '?')
    print(f'  {nm}({code[-4:]}) n={s.get("n",0):.1f}% p={s.get("p",0):.1f}% cl={s.get("cl",0):.0f}%')

# 检查2026-05-08（天顺股份赢的那天）
dt = '2026-05-08'
stocks = data.get(dt, [])
print(f'\n=== {dt} 详细 ===')
by_n = sorted(stocks, key=lambda s: -(s.get('n',0) or 0))
for s in by_n[:10]:
    code = s.get('code', '')
    nm = names.get(code, '?')
    print(f'  {nm}({code[-4:]}) n={s.get("n",0):.1f}% p={s.get("p",0):.1f}% cl={s.get("cl",0):.0f}%')
