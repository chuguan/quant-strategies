#!/usr/bin/env python3
"""获取美股三大指数和行业ETF数据"""
import urllib.request
import json
import ssl

# 忽略SSL证书验证
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def fetch(code, name):
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,5,qfq'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        resp = urllib.request.urlopen(req, timeout=10, context=ssl_ctx)
        data = json.loads(resp.read())
        if 'data' in data and code in data['data']:
            d = data['data'][code]
            if 'day' in d and d['day']:
                last = d['day'][-1]
                chg = 0.0
                if len(d['day']) >= 2:
                    prev = d['day'][-2]
                    chg = round((float(last[2]) - float(prev[2])) / float(prev[2]) * 100, 2)
                print(f'{name}|{code}|{last[0]}|{last[1]}|{last[2]}|{last[3]}|{last[4]}|{chg}')
            else:
                print(f'{name}|{code}|NODATA|keys={list(d.keys())}')
        else:
            print(f'{name}|{code}|NO_RESP|keys={list(data.keys())}')
    except Exception as e:
        print(f'{name}|{code}|ERROR|{e}')

# 三大指数
fetch('usDJI', '道琼斯')
fetch('usIXIC', '纳斯达克')
fetch('usSPX', '标普500')

# 行业ETF
print('===ETF===')
fetch('usXLE', '能源XLE')
fetch('usXLV', '医疗XLV')
fetch('usSMH', '半导体SMH')
fetch('usXLK', '科技XLK')
fetch('usXLF', '金融XLF')
fetch('usXLP', '消费XLP')
