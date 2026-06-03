#!/usr/bin/env python
"""
收盘后刷新技术指标 — 正确版
交易日15:31运行，只刷新最近3天
"""
import sqlite3, os, sys, time
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

def refresh_technical_indicators():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('PRAGMA journal_mode=WAL')
    c = conn.cursor()
    
    # 找到最近的日期
    c.execute('SELECT MAX(date) FROM data_cache WHERE close > 0')
    max_date = c.fetchone()[0]
    if not max_date:
        print('❌ data_cache无数据')
        conn.close(); return
    
    # 只刷新最近3天（增量）
    c.execute('SELECT DISTINCT date FROM data_cache WHERE close > 0 ORDER BY date DESC LIMIT 3')
    refresh_dates = [r[0] for r in c.fetchall()]
    print(f'刷新日期: {refresh_dates}')
    
    # 获取所有股票代码
    c.execute('SELECT DISTINCT code FROM data_cache WHERE close > 0')
    codes = [r[0] for r in c.fetchall()]
    print(f'股票数: {len(codes)}')
    
    updated = 0
    skipped_no_hl = 0
    t0 = time.time()
    
    for idx, code in enumerate(codes):
        # 读该股票所有历史数据
        c.execute('''
            SELECT date, close, high, low FROM data_cache 
            WHERE code=? AND close > 0 ORDER BY date
        ''', (code,))
        rows = c.fetchall()
        
        if len(rows) < 20:
            continue  # 数据不足
        
        dates = [r[0] for r in rows]
        closes = [r[1] for r in rows]
        highs = [r[2] if r[2] else r[1] for r in rows]  # high为0时用close替代
        lows = [r[3] if r[3] else r[1] for r in rows]    # low为0时用close替代
        
        for dt in refresh_dates:
            if dt not in dates:
                continue
            i = dates.index(dt)
            if i < 14:
                continue  # 数据不足14天无法算WR
            
            # === KDJ (标准算法) ===
            h9 = max(highs[i-8:i+1])
            l9 = min(lows[i-8:i+1])
            rsv = (closes[i] - l9) / (h9 - l9) * 100 if (h9 - l9) > 0 else 50
            
            # 前一天的K/D值
            if i >= 1:
                # 从数据库读前一天的k_val和d_val
                prev_k = 50
                prev_d = 50
                c.execute('SELECT k_val, d_val FROM data_cache WHERE code=? AND date=?', (code, dates[i-1]))
                pk_row = c.fetchone()
                if pk_row and pk_row[0] is not None and pk_row[0] != 50:
                    prev_k = pk_row[0]
                    prev_d = pk_row[1] if pk_row[1] and pk_row[1] != 50 else 50
            else:
                prev_k = 50
                prev_d = 50
            
            k_val = round(2/3 * prev_k + 1/3 * rsv, 2)
            d_val = round(2/3 * prev_d + 1/3 * k_val, 2)
            j_val = round(3 * k_val - 2 * d_val, 2)
            
            # KDJ金叉：当日K上穿D
            if i >= 1:
                c.execute('SELECT k_val, d_val FROM data_cache WHERE code=? AND date=?', (code, dates[i-1]))
                prev_kd = c.fetchone()
                if prev_kd and prev_kd[0] is not None:
                    kdj_golden = 1 if (k_val > d_val and prev_kd[0] <= prev_kd[1]) else 0
                else:
                    kdj_golden = 0
            else:
                kdj_golden = 0
            
            # === WR (14日威廉指标) ===
            h14 = max(highs[i-13:i+1])
            l14 = min(lows[i-13:i+1])
            wr_val = round((h14 - closes[i]) / (h14 - l14) * 100, 2) if (h14 - l14) > 0 else 50
            
            # === MACD DIF ===
            if i >= 25:
                # EMA12
                ema12 = closes[i-11]
                for k in range(i-10, i+1):
                    ema12 = ema12 * 11/13 + closes[k] * 2/13
                # EMA26
                ema26 = closes[i-25]
                for k in range(i-24, i+1):
                    ema26 = ema26 * 25/27 + closes[k] * 2/27
                dif_val = round(ema12 - ema26, 3)
                
                # MACD金叉：DIF上穿DEA(9日EMA of DIF)
                # 简化：DIF > 0视为金叉状态
                macd_golden = 1 if dif_val > 0 else 0
                
                # 如果前一天也有dif，比较金叉变化
                if i >= 1:
                    c.execute('SELECT dif_val, macd_golden FROM data_cache WHERE code=? AND date=?', (code, dates[i-1]))
                    prev_macd = c.fetchone()
                    if prev_macd and prev_macd[0] is not None:
                        prev_dif = prev_macd[0] or 0
                        # DIF从负转正 = 金叉
                        if prev_dif <= 0 and dif_val > 0:
                            macd_golden = 1
                        # DIF从正转负 = 死叉
                        if prev_dif > 0 and dif_val <= 0:
                            macd_golden = 0
            else:
                dif_val = 0
                macd_golden = 0
            
            # === 5日线位置 ===
            if i >= 4:
                ma5 = sum(closes[i-4:i+1]) / 5
                above_ma5 = 1 if closes[i] > ma5 else 0
            else:
                above_ma5 = 0
            
            # === 日内位置 ===
            pos_in_day = round((closes[i] - lows[i]) / (highs[i] - lows[i]) * 100, 2) if (highs[i] - lows[i]) > 0 else 50
            
            # ⚠️ 正确的参数顺序！
            c.execute('''
                UPDATE data_cache SET
                wr_val=?, k_val=?, d_val=?, j_val=?,
                dif_val=?, macd_golden=?,
                kdj_golden=?, above_ma5=?, pos_in_day=?
                WHERE date=? AND code=?
            ''', (wr_val, k_val, d_val, j_val,
                  dif_val, macd_golden,
                  kdj_golden, above_ma5, pos_in_day,
                  dt, code))
            updated += 1
        
        if (idx + 1) % 500 == 0:
            conn.commit()
            pct = (idx + 1) * 100 // len(codes)
            print(f'  进度: {pct}% | {idx+1}/{len(codes)} | 已更新{updated}条')
    
    conn.commit()
    elapsed = time.time() - t0
    
    # 验证
    print(f'\n✅ 技术指标刷新完成: {updated}条, {elapsed:.0f}s')
    for dt in refresh_dates:
        c.execute('SELECT COUNT(*) FROM data_cache WHERE date=? AND wr_val IS NOT NULL AND wr_val != 50', (dt,))
        ok_wr = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM data_cache WHERE date=?', (dt,))
        total = c.fetchone()[0]
        print(f'  {dt}: {ok_wr}/{total}只有WR指标')
    
    conn.close()
    return updated

if __name__ == '__main__':
    print(f'📊 技术指标刷新 {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*50}')
    refresh_technical_indicators()
