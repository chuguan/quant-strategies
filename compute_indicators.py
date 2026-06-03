#!/usr/bin/env python3
"""
技术指标计算 — 收盘采集后执行
读取data_cache的原始数据(p, cl, close)，计算WR/KDJ/DIF并更新
"""
import sqlite3, os, sys
from datetime import datetime

SCRIPTS = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB = os.path.join(SCRIPTS, 'v13_quant.db')

def compute_indicators(date=None):
    """计算指定日期(或最新未计算日期)的技术指标"""
    if not date:
        # 找最近有close数据但指标为默认值的日期
        conn = sqlite3.connect(DB, timeout=30)
        c = conn.cursor()
        c.execute('''SELECT date FROM data_cache 
                     WHERE wr_val=50 AND close>0 
                     GROUP BY date ORDER BY date DESC LIMIT 1''')
        r = c.fetchone()
        if not r:
            print('所有日期指标已计算，无需更新')
            conn.close()
            return
        date = r[0]
        conn.close()
    
    print(f'📊 计算技术指标: {date}')
    
    conn = sqlite3.connect(DB, timeout=30)
    c = conn.cursor()
    
    # 获取当天所有需要计算的股票
    c.execute('SELECT code, close, name FROM data_cache WHERE date=? AND close>0 AND wr_val=50', (date,))
    stocks = c.fetchall()
    if not stocks:
        # 没有wr=50的，就算全部更新DIF/MACD
        c.execute('SELECT code, close, name FROM data_cache WHERE date=? AND close>0', (date,))
        stocks = c.fetchall()
    
    total = len(stocks)
    print(f'  共{total}只')
    
    cache_dir = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
    updated = 0
    missing_kline = 0
    
    for idx, (code, close, name) in enumerate(stocks):
        # 获取该股票过去30天的close数据(从data_cache)
        c.execute('''SELECT date, close FROM data_cache 
                     WHERE code=? AND date<=? AND close>0
                     ORDER BY date DESC LIMIT 30''', (code, date))
        rows = c.fetchall()
        closes = [r[1] for r in reversed(rows)]
        
        if len(closes) < 9:
            continue
        
        # DIF (EMA12-EMA26)
        alpha12, alpha26 = 2/13, 2/27
        ema12 = closes[-1]; ema26 = closes[-1]
        for cv in reversed(closes[:-1]):
            ema12 = cv * alpha12 + ema12 * (1 - alpha12)
            ema26 = cv * alpha26 + ema26 * (1 - alpha26)
        dif = round(ema12 - ema26, 3)
        mg = 1 if len(closes) >= 2 and dif > 0 and closes[-1] > closes[-2] else 0
        a5 = 1 if len(closes) >= 6 and closes[-1] > sum(closes[-6:-1])/5 else 0
        
        # WR/KDJ从K线缓存计算(需要high/low)
        wr, jv, kv, dv = 50, 50, 50, 50
        pref = 'sh' if code.startswith(('6','9')) else 'sz'
        kfile = os.path.join(cache_dir, f'{pref}{code}.json')
        if os.path.exists(kfile):
            try:
                import json
                klines = json.load(open(kfile))
                kh = [k['high'] for k in klines if k['date'] <= date]
                kl = [k['low'] for k in klines if k['date'] <= date]
                kc = [k['close'] for k in klines if k['date'] <= date]
                if len(kh) >= 14 and len(kl) >= 14:
                    # WR 14天
                    h14 = max(kh[-14:]); l14 = min(kl[-14:])
                    wr = round((h14 - close) / (h14 - l14) * 100, 1) if (h14-l14)>0 else 50
                    # KDJ 9天
                    if len(kh) >= 9:
                        h9 = max(kh[-9:]); l9 = min(kl[-9:])
                        rsv = (close - l9) / (h9 - l9) * 100 if (h9-l9)>0 else 50
                        kv = round(50*2/3 + rsv/3, 1)
                        dv = round(50*2/3 + kv/3, 1)
                        jv = round(3*kv - 2*dv, 1)
            except: pass
        
        c.execute('''UPDATE data_cache SET
                     dif_val=?, macd_golden=?, above_ma5=?,
                     wr_val=?, j_val=?, k_val=?, d_val=?
                     WHERE date=? AND code=?''',
                  (round(dif,3), int(mg), int(a5),
                   round(wr,1), round(jv,1), round(kv,1), round(dv,1),
                   date, code))
        updated += 1
        
        if updated % 500 == 0:
            conn.commit()
            print(f'  进度: {updated}/{total}')
    
    conn.commit()
    print(f'✅ {date} 技术指标计算完成: {updated}只')
    print(f'  其中WR/KDJ来自K线缓存' if updated > 0 else '')
    
    conn.close()
    return updated

if __name__ == '__main__':
    # 不传参数自动找最新未计算日期
    import sys as _sys
    target_date = _sys.argv[1] if len(_sys.argv) > 1 else None
    compute_indicators(target_date)
