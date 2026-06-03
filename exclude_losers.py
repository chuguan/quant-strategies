#!/usr/bin/env python3
"""量比TOP20 失败票剔除 + XGBoost评分
每天开盘15分钟后运行，从量比最高的票中剔除失败概率高的，
输出最可能达标的TOP5

用法: python exclude_losers.py
"""

import sys, os, json, subprocess
import numpy as np

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

DB = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

def curl_get(url, timeout=10):
    try:
        r = subprocess.run(['curl', '-s', '--max-time', str(timeout), url],
                          capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except:
        return ''

def get_market_data():
    """获取全市场实时行情（按代码段批量拉取）"""
    stocks = {}
    
    # 批量获取 - 主要是600xxx和000xxx/002xxx
    all_codes = []
    for prefix in ['sh600','sh601','sh603','sh605','sz000','sz001','sz002']:
        for i in range(0, 1000, 80):
            codes = [f'{prefix}{str(j).zfill(3)}' for j in range(i, min(i+80, 1000))]
            all_codes.append(','.join(codes))
    
    for batch in all_codes:
        text = curl_get(f'https://qt.gtimg.cn/q={batch}', timeout=8)
        for line in text.split('
'):
            if '~' not in line: continue
            parts = line.split('~')
            if len(parts) < 40: continue
            try:
                nm = parts[1]
                code = parts[2]
                if not nm or 'ST' in nm or '*ST' in nm or '退' in nm: continue
                if not code.startswith(('600','601','603','605','000','001','002')): continue
                
                price = float(parts[3])
                prev_close = float(parts[4])
                pct = round((price/prev_close-1)*100, 2) if prev_close else 0
                vol_ratio = float(parts[38]) if parts[38] else 0
                high = float(parts[33]) if parts[33] else price
                low = float(parts[34]) if parts[34] else price
                
                # 过滤条件：非涨停、正常量比
                if pct >= 9: continue
                if vol_ratio <= 0: continue
                
                stocks[code] = {
                    'name': nm, 'price': price, 'p': pct, 'vr': vol_ratio,
                    'high': high, 'low': low, 'prev_close': prev_close
                }
            except:
                pass
    
    return stocks

def get_indicator(code, name):
    """获取技术指标（CL, WR, DIF等）- 从K线数据计算"""
    prefix = 'sh' if code.startswith(('6','9')) else 'sz'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,200,qfq'
    text = curl_get(url, timeout=8)
    if not text.strip().startswith('{'):
        return None
    
    try:
        data = json.loads(text)
        klines = data.get('data', {}).get(f'{prefix}{code}', {}).get('qfqday', [])
        if not klines:
            for key in data.get('data', {}).get(f'{prefix}{code}', {}):
                if isinstance(data['data'][f'{prefix}{code}'][key], list) and len(data['data'][f'{prefix}{code}'][key]) > 0:
                    klines = data['data'][f'{prefix}{code}'][key]
                    break
        if not klines or len(klines) < 60:
            return None
        
        closes = [float(k[2]) for k in klines]
        highs = [float(k[3]) for k in klines]
        lows = [float(k[4]) for k in klines]
        volumes = [float(k[5]) for k in klines]
        n = len(closes)
        
        # CL（收盘位置）
        h20 = max(highs[-20:])
        l20 = min(lows[-20:])
        cl = (closes[-1] - l20) / (h20 - l20 + 1e-10) * 100 if h20 != l20 else 50
        
        # WR（威廉指标）
        h21 = max(highs[-21:])
        l21 = min(lows[-21:])
        wr = 100 * (h21 - closes[-1]) / (h21 - l21 + 1e-10) if h21 != l21 else 50
        
        # DIF（MACD）
        ema12 = closes[-1]
        ema26 = closes[-1]
        for i in range(n-2, max(n-27, -1), -1):
            ema12 = closes[i] * 2/13 + ema12 * 11/13
            ema26 = closes[i] * 2/27 + ema26 * 25/27
        dif = ema12 - ema26
        
        # KDJ
        k_val = d_val = j_val = 50
        if n >= 9:
            h9 = max(highs[-9:])
            l9 = min(lows[-9:])
            rsv = (closes[-1] - l9) / (h9 - l9 + 1e-10) * 100
            k_val = rsv * 2/3 + 50/3
            d_val = k_val * 2/3 + 50/3
            j_val = 3 * k_val - 2 * d_val
        
        macd_golden = 1 if dif > 0 else 0
        kdj_golden = 1 if k_val > d_val else 0
        above_ma5 = 1 if closes[-1] > np.mean(closes[-5:]) else 0
        
        return {
            'cl': min(max(cl, 0), 100),
            'wr': min(max(wr, 0), 100),
            'dif': round(dif, 3),
            'macd_g': macd_golden,
            'k': round(k_val, 1),
            'd': round(d_val, 1),
            'j': round(j_val, 1),
            'kdj_g': kdj_golden,
            'ma5': above_ma5,
            'close': closes[-1],
            'vol': volumes[-1] if volumes else 0
        }
    except:
        return None

def predict(p, vr, cl, wr, dif, macd_g, kdj_g, j, k, d, ma5, close, vol):
    """XGBoost预测达标概率（模拟规则版本）"""
    # 一票否决：失败率>90%的条件
    if cl < 30: return 0.05, 'CL<30低位一票否决'
    if wr > 70 and cl < 50: return 0.05, 'WR超卖+CL低位'
    if p < 0 and cl < 40: return 0.05, '下跌+低位'
    if dif < 0 and wr > 50: return 0.05, 'MACD死叉+弱势'
    if vr < 1.0: return 0.05, '量比不足'
    if ma5 == 0 and cl < 40: return 0.05, '未站上5日线+低位'
    
    # 评分 - 多因子加权
    score = 0
    # vr: 量比越高越好
    if vr > 3: score += 35
    elif vr > 2.5: score += 30
    elif vr > 2: score += 25
    elif vr > 1.5: score += 15
    else: score += 5
    
    # p: 当日涨幅
    if p > 4: score += 25
    elif p > 2: score += 20
    elif p > 0: score += 10
    else: score -= 5
    
    # cl: 收盘位置
    if cl > 80: score += 20
    elif cl > 60: score += 15
    elif cl > 40: score += 5
    else: score -= 10
    
    # wr: 威廉(低=强)
    if wr < 20: score += 15
    elif wr < 40: score += 10
    elif wr < 60: score += 5
    else: score -= 5
    
    # dif: MACD动量
    if dif > 0.1: score += 10
    elif dif > 0: score += 5
    else: score -= 5
    
    # ma5 + kdj金叉
    if ma5: score += 10
    if kdj_g: score += 8
    
    prob = min(max(score / 130, 0.05), 0.85)
    return prob, f'评分{score}/130'

def main():
    print('🚀 量比TOP20 失败票剔除分析')
    
    # 1. 获取实时数据
    print('📡 拉取全市场行情...', end=' ', flush=True)
    stocks = get_market_data()
    print(f'{len(stocks)}只')
    
    # 2. 按量比排序取前50
    sorted_stocks = sorted(stocks.values(), key=lambda s: s['vr'], reverse=True)
    top50 = sorted_stocks[:50]
    
    # 3. 获取技术指标
    print('📊 计算技术指标...', flush=True)
    candidates = []
    for s in top50:
        code = [k for k, v in stocks.items() if v == s][0] if len(stocks) > 0 else ''
        # find code for this stock
        for c, v in stocks.items():
            if v['p'] == s['p'] and v['vr'] == s['vr'] and v['name'] == s['name']:
                code = c
                break
        if not code:
            continue
        
        ind = get_indicator(code, s['name'])
        if not ind:
            continue
        
        prob, reason = predict(
            s['p'], s['vr'], ind['cl'], ind['wr'], ind['dif'],
            ind['macd_g'], ind['kdj_g'], ind['j'], ind['k'], ind['d'],
            ind['ma5'], ind['close'], ind['vol']
        )
        
        candidates.append({
            'code': code,
            'name': s['name'],
            'price': s['price'],
            'p': s['p'],
            'vr': s['vr'],
            'cl': ind['cl'],
            'wr': ind['wr'],
            'macd': ind['dif'],
            'prob': prob,
            'reason': reason
        })
    
    # 4. 按达标概率排序
    candidates.sort(key=lambda c: c['prob'], reverse=True)
    
    # 5. 输出
    print(f'
📊 开盘15分钟 量比TOP50 → 失败票剔除分析')
    print(f'{"#":>3} {"名称":>8} {"代码":>7} {"量比":>5} {"涨幅%":>6} {"CL":>5} {"WR":>5} {"达标概率":>8} {"备注":>20}')
    print('-' * 70)
    for i, c in enumerate(candidates[:20]):
        bar = '█' * int(c['prob'] * 20)
        print(f'{i+1:>3} {c["name"][:6]:>8} {c["code"]:>7} {c["vr"]:>5.1f} {c["p"]:>+5.1f}% {c["cl"]:>4.0f} {c["wr"]:>4.0f} {c["prob"]:>7.0%} {bar:<20}')
    
    # 6. 推荐TOP3（排除失败票后）
    print(f'
🎯 剔除失败票后推荐TOP3:')
    top3 = [c for c in candidates if c['prob'] >= 0.20][:3]
    for i, c in enumerate(top3):
        print(f'  {i+1}. {c["name"]}({c["code"]}) ¥{c["price"]} 达标概率{c["prob"]:.0%} | vr:{c["vr"]:.1f} p:{c["p"]:+.1f}%')
    
    # 7. 被剔除的（失败概率高）
    excluded = [c for c in candidates if c['prob'] < 0.20][:5]
    if excluded:
        print(f'
🛑 已剔除（失败概率高）:')
        for c in excluded[:3]:
            print(f'  {c["name"]}({c["code"]}) vr:{c["vr"]:.1f} p:{c["p"]:+.1f}% -> {c["reason"]}')
    
    return top3

if __name__ == '__main__':
    main()
