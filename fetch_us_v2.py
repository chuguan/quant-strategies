#!/usr/bin/env python3
"""获取美股三大指数和行业ETF数据 - 含涨跌幅"""
import urllib.request
import json
import ssl

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
            # qt field has current price and change info
            if 'qt' in d and code in d['qt']:
                qt = d['qt'][code]
                # qt[0]=market_status, qt[1]=name, qt[2]=code, qt[3]=current_price, qt[4]=prev_close
                # qt[5]=open, qt[31]=change%, qt[32]=change_pts, qt[33]=high, qt[34]=low
                close_price = qt[3]
                prev_close = qt[4]
                change_pct = qt[31] if len(qt) > 31 else 'N/A'
                change_pts = qt[32] if len(qt) > 32 else 'N/A'
                print(f'{name}|{code}|收盘:{close_price}|昨收:{prev_close}|涨跌额:{change_pts}|涨跌幅:{change_pct}%')
            
            # day data
            if 'day' in d and d['day']:
                days = d['day']
                print(f'  K线数据: {len(days)}条, 最新: {days[-1]}')
                if len(days) >= 2:
                    prev = days[-2]
                    chg = round((float(days[-1][2]) - float(prev[2])) / float(prev[2]) * 100, 2)
                    print(f'  K线涨跌幅: {chg}%')
                elif len(days) == 1:
                    print(f'  仅1条K线({days[-1][0]}), 无法计算涨跌幅')
        else:
            print(f'{name}|{code}|NO_DATA')
    except Exception as e:
        print(f'{name}|{code}|ERROR|{e}')

# 三大指数
fetch('usDJI', '道琼斯')
fetch('usIXIC', '纳斯达克')
fetch('usSPX', '标普500')

print('\n=== 行业ETF ===')
fetch('usXLE', '能源XLE')
fetch('usXLV', '医疗XLV')
fetch('usSMH', '半导体SMH')
fetch('usXLK', '科技XLK')
fetch('usXLF', '金融XLF')
fetch('usXLP', '消费XLP')
