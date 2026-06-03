"""
龙回头 — 波段策略
思路: 不做超短线
买点: 缩量回踩重要均线(MA20/MA60)
卖点: 放量拉升5-10%获利了结
持有: 3-15天
核心: 不盯盘，不追涨，不杀跌
"""
import pickle, os, sys, numpy as np
from collections import defaultdict

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

d = pickle.load(open(os.path.join(SCRIPTS_DIR, 'tdx_cache.pkl'), 'rb'))
data = d['data']
dates = sorted(data.keys())
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

sc = {}
for dt in dates:
    for s in data[dt]:
        sc[(s['code'], dt)] = {'p': s['p'], 'close': s['close'], 'high': s['high'], 'low': s['low'], 'volume': s['volume']}

def backtest_wave():
    """
    回测波段策略:
    买: 缩量回踩MA20 + MA20向上 + 股价在MA20±1%内
    卖: 持有到涨5%止盈 或 跌5%止损 或 持有10天
    """
    import random; random.seed(42)
    
    trades = []
    bt_dates = [d for d in dates if d >= '2024-01-01']
    
    for di, dt in enumerate(bt_dates):
        di_real = dates.index(dt)
        if di_real < 60 or di_real >= len(dates) - 15: continue
        
        # 每天最多1笔
        for s in data[dt]:
            code = s['code']
            if not IS_MAIN(code): continue
            
            # 跳过ST
            try:
                rec = [sc.get((code, dates[di_real-off])) for off in range(60, -1, -1)]
                if any(r is None for r in rec): continue
            except: continue
            
            close = [r['close'] for r in rec]
            vol = [r['volume'] for r in rec]
            today = rec[-1]
            
            # 均线
            ma20 = sum(close[-20:]) / 20
            ma20_prev = sum(close[-21:-1]) / 20
            ma60 = sum(close[-60:]) / 60
            
            # 条件1: MA20向上
            if ma20 <= ma20_prev: continue
            
            # 条件2: 股价在MA20附近 (±1.5%)
            if abs(today['close'] - ma20) / ma20 > 0.015: continue
            
            # 条件3: 缩量 (量 < 20日均量×0.8)
            avg_v20 = sum(vol[-20:]) / 20
            if avg_v20 > 0 and today['volume'] > avg_v20 * 0.8: continue
            
            # 条件4: 股价在MA60以上 (多头趋势)
            if today['close'] < ma60: continue
            
            # 买入价
            buy_price = today['close']
            buy_date = dt
            
            # 寻找卖出点 (最多持有15天)
            sell_price = buy_price
            sell_date = buy_date
            high_pct = 0
            low_pct = 0
            reason = '持有'
            
            for hold in range(1, 16):
                if di_real + hold >= len(dates): break
                sd = sc.get((code, dates[di_real+hold]))
                if sd is None: break
                
                day_p = (sd['close'] - buy_price) / buy_price * 100
                day_high = (sd['high'] - buy_price) / buy_price * 100
                day_low = (sd['low'] - buy_price) / buy_price * 100
                
                high_pct = max(high_pct, day_high)
                low_pct = min(low_pct, day_low) if low_pct != 0 else day_low
                
                if day_high >= 5:  # 止盈5%
                    sell_price = buy_price * 1.05
                    sell_date = dates[di_real+hold]
                    reason = f'止盈{hold}天'
                    break
                if day_low <= -5:  # 止损5%
                    sell_price = buy_price * 0.95
                    sell_date = dates[di_real+hold]
                    reason = f'止损{hold}天'
                    break
                if hold == 15:  # 到期
                    sell_price = sd['close']
                    sell_date = dates[di_real+hold]
                    reason = f'到期{hold}天'
            
            pnl = (sell_price - buy_price) / buy_price * 100
            trades.append((buy_date, code, buy_price, sell_date, sell_price, round(pnl,1), reason, round(high_pct,1), round(low_pct,1)))
            break  # 每天只做1笔
    
    print(f'波段交易次数: {len(trades)}')
    wins = sum(1 for t in trades if t[5] > 0)
    print(f'盈利次数: {wins}/{len(trades)} = {wins/max(len(trades),1)*100:.1f}%')
    avg_pnl = sum(t[5] for t in trades) / len(trades) if trades else 0
    print(f'平均收益: {avg_pnl:.1f}%')
    total_pnl = sum(t[5] for t in trades)
    print(f'累计收益: {total_pnl:.1f}%')
    
    print(f'\n前20笔:')
    print(f'{"买入日":>10} {"代码":>7} {"买入价":>8} {"卖出日":>10} {"收益":>6} {"原因":>10} {"最高":>6} {"最低":>6}')
    for t in trades[:20]:
        print(f'{t[0]:>10} {t[1]:>7} {t[2]:>8.2f} {t[3]:>10} {t[5]:>+5.1f}% {t[6]:>10} {t[7]:>+5.1f}% {t[8]:>+5.1f}%')

backtest_wave()
