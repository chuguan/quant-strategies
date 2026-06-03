"""对比新旧缓存的行情分类差异"""
import pickle, os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 加载新缓存（2976只）
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, names = d['data'], d['names']
dates = sorted([x for x in data.keys() if '2026-01-01' <= x < '2026-06-01'])

def classify_market(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p',0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

# 统计2026年各行情天数
mkt_counts = {'real_up':0, 'fake_up':0, 'down':0, 'flat':0}
for dt in dates:
    stocks = data.get(dt, [])
    if len(stocks) < 2000: continue  # 只统计数据完整的日期
    mkt = classify_market(stocks)
    mkt_counts[mkt] += 1

print(f'2026年（数据完整期）行情分布:')
print(f'  真实涨日: {mkt_counts["real_up"]}天')
print(f'  虚涨日: {mkt_counts["fake_up"]}天')
print(f'  跌日: {mkt_counts["down"]}天')
print(f'  横盘: {mkt_counts["flat"]}天')

# 逐日输出近30天的分类和关键数据
print(f'\n{"="*70}')
print(f'近30天逐日行情分类')
print(f'{"="*70}')
print(f'{"日期":>12s} | {"总数":>5s} | {"均涨":>7s} | {"涨5-8%":>7s} | {"行情":>8s} | {"n≥2.5%":>7s}')
print(f'{"-"*70}')

last_dates = [dt for dt in dates if dt >= '2026-04-20'][-30:]
for dt in last_dates:
    stocks = data.get(dt, [])
    if len(stocks) < 2000: continue
    ps = [s.get('p',0) or 0 for s in stocks]
    avg_p = sum(ps)/len(ps)
    hot = sum(1 for p in ps if 5 <= p <= 8)
    mkt = classify_market(stocks)
    ns = [s.get('n',0) or 0 for s in stocks if (s.get('n',0) or 0) > 0]
    n25 = sum(1 for n in ns if n >= 2.5)
    avg_n25_pct = n25*100/len(ps) if ps else 0
    print(f'{dt:>12s} | {len(stocks):>5d} | {avg_p:>+6.2f}% | {hot:>5d}只 | {mkt:>8s} | {avg_n25_pct:>5.1f}%')
