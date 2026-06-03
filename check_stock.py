import json, os

cache = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

# sh603867 - 冠军股
fn = os.path.join(cache, "sh603867.json")
with open(fn, 'rb') as f:
    d = json.loads(f.read().decode('utf-8'))
r = d[-1]
print(f"🏆 sh603867 最新数据:")
print(f"   日期: {r['date']}")
print(f"   收盘(买入价): {r['close']}元")
print(f"   开盘: {r['open']}元")
print(f"   最高: {r['high']}元")
print(f"   最低: {r['low']}元")

# 前几条
for r2 in d[-3:]:
    print(f"   {r2['date']}: 收{r2['close']} 高{r2['high']} 低{r2['low']}")

print(f"\n数据范围: {d[0]['date']} ~ {d[-1]['date']} (共{len(d)}条)")

# 检查是否有5/25数据
if d[-1]['date'] >= '2026-05-25':
    print(f"\n✅ 有次日数据! 次日最高: {d[-1]['high']}元")
else:
    print(f"\n⚠️ 最新数据到 {d[-1]['date']}，下周一(5/25)数据还未缓存")

# 再查一下股票名称
# 试试从文件名推断市场
code = "603867"
if fn.split(os.sep)[-1].startswith('sh'):
    market = "上海"
else:
    market = "深圳"
print(f"   主板: {market}主板")
print(f"   代码: 603867 (沪市主板)")
