#!/usr/bin/env python3
"""获取SPX数据"""
import urllib.request, json, ssl
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=usSPX,day,,,10,qfq'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=10, context=ssl_ctx)
data = json.loads(resp.read())
if 'data' in data and 'usSPX' in data['data']:
    d = data['data']['usSPX']
    print(f"SPX keys: {list(d.keys())}")
    if 'qt' in d:
        qt = d['qt']
        print(f"SPX qt type: {type(qt)}, value (truncated): {str(qt)[:300]}")
    if 'day' in d:
        print(f"SPX day data: {d['day']}")
