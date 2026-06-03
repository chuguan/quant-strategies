#!/usr/bin/env python3
"""完整获取美股数据"""
import urllib.request, json, ssl
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def fetch_qt(code, name, spx=False):
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,5,qfq'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10, context=ssl_ctx)
        data = json.loads(resp.read())
        key = code
        if 'data' in data and key in data['data']:
            d = data['data'][key]
            if 'qt' in d and key in d['qt']:
                qt = d['qt'][key]
                close = float(qt[3])
                prev = float(qt[4])
                chg_pts = round(close - prev, 2)
                chg_pct = round(chg_pts/prev*100, 2)
                print(f'{name}|{close}|{chg_pts}|{chg_pct}')
            else:
                print(f'{name}|NO_QT')
        else:
            print(f'{name}|NO_DATA')
    except Exception as e:
        print(f'{name}|ERROR|{e}')

# 指数
fetch_qt('usDJI', '道琼斯')
fetch_qt('usIXIC', '纳斯达克')
fetch_qt('usINX', '标普500')

print('===ETF===')
fetch_qt('usXLE', '能源XLE')
fetch_qt('usXLV', '医疗XLV')
fetch_qt('usSMH', '半导体SMH')
fetch_qt('usXLK', '科技XLK')
fetch_qt('usXLF', '金融XLF')
fetch_qt('usXLP', '消费XLP')
