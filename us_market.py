#!/usr/bin/env python3
"""美股数据+新闻获取"""
import json, subprocess, sys

def curl(url):
    r = subprocess.run(['curl','-s','--max-time','12',url], capture_output=True, text=True)
    return r.stdout

# 1. 美股三大指数
indices = {
    '道琼斯': 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=usDJI,day,,,5,qfq',
    '标普500': 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=usSPX,day,,,5,qfq',
    '纳斯达克': 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=usIXIC,day,,,5,qfq',
}
print("=== 美股三大指数 ===")
for name, url in indices.items():
    try:
        d = json.loads(curl(url))
        days = d['data'][list(d['data'].keys())[0]]['day']
        last = days[-1]
        date, op, close = last[0], float(last[1]), float(last[2])
        chg = close - op
        pct = chg/op*100
        print(f"{name}: {close:.2f} ({chg:+.2f}, {pct:+.2f}%) — {date}")
    except Exception as e:
        print(f"{name}: 获取失败")

# 2. 美股板块（用腾讯热点板块API）
print("\n=== 美股热点板块 ===")
try:
    # 使用新浪美股板块
    r = curl("https://vip.stock.finance.sina.com.cn/us/api/sector_hot.php")
    if r:
        print(r[:1000])
    else:
        print("无数据")
except:
    print("获取失败")
