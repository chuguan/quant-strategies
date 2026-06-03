#!/usr/bin/env python
"""
从data_cache计算特征 → 写入features_cache
特征：d1~d5, slope5, t4_shadow, cons_up, peak_decay

交易日收盘后(15:30)执行，增量补充缺失日期的特征
"""
import sqlite3, os, sys, time, numpy as np
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

def compute_features():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('PRAGMA journal_mode=WAL')
    c = conn.cursor()
    
    # 获取所有交易日（按顺序）
    c.execute('SELECT DISTINCT date FROM data_cache WHERE close > 0 ORDER BY date')
    all_dates = [r[0] for r in c.fetchall()]
    print(f'交易日范围: {all_dates[0]} ~ {all_dates[-1]} ({len(all_dates)}天)')
    
    # 获取features_cache已有日期
    c.execute('SELECT DISTINCT date FROM features_cache')
    feat_dates = set(r[0] for r in c.fetchall())
    
    # 需要计算的日期（已有data_cache但无features的）
    # 以及最新3天（确保覆盖最新）
    need_compute = set(all_dates[-3:]) | (set(all_dates) - feat_dates)
    need_compute = sorted(d for d in need_compute if d in all_dates)
    
    if not need_compute:
        print('✅ 所有日期特征已齐全')
        conn.close(); return 0
    
    print(f'需计算特征: {len(need_compute)}天 ({need_compute[0]}~{need_compute[-1]})')
    
    # 获取所有股票代码
    c.execute('SELECT DISTINCT code FROM data_cache WHERE close > 0')
    all_codes = [r[0] for r in c.fetchall()]
    print(f'股票数: {len(all_codes)}')
    
    # 预加载所有股票的日涨跌幅（p字段），避免反复查库
    print('预加载p字段...')
    p_data = {}  # code -> {date: p}
    batch_size = 500
    for i in range(0, len(all_codes), batch_size):
        batch_codes = all_codes[i:i+batch_size]
        placeholders = ','.join(['?'] * len(batch_codes))
        c.execute(f'''
            SELECT code, date, p, close, high, low 
            FROM data_cache 
            WHERE code IN ({placeholders}) AND close > 0
            ORDER BY code, date
        ''', batch_codes)
        for row in c.fetchall():
            code, dt, p, close, high, low = row
            if code not in p_data:
                p_data[code] = {}
            p_data[code][dt] = {
                'p': p or 0,
                'close': close or 0,
                'high': high or 0,
                'low': low or 0
            }
    print(f'  加载 {sum(len(v) for v in p_data.values())} 条')
    
    # 确保features_cache表结构完整
    c.execute('''
        CREATE TABLE IF NOT EXISTS features_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            code TEXT NOT NULL,
            d1 REAL DEFAULT 0, d2 REAL DEFAULT 0, d3 REAL DEFAULT 0,
            d4 REAL DEFAULT 0, d5 REAL DEFAULT 0,
            slope5 REAL DEFAULT 0,
            t4_shadow REAL DEFAULT 0,
            cons_up REAL DEFAULT 0,
            peak_decay REAL DEFAULT 0,
            computed_from TEXT DEFAULT 'auto_compute',
            UNIQUE(date, code)
        )
    ''')
    
    total = 0
    t0 = time.time()
    
    for dt in need_compute:
        # 获取该日期在all_dates中的索引
        date_idx = all_dates.index(dt)
        
        # 前5个交易日的日期
        prev_dates = {}
        for offset in range(1, 6):
            idx = date_idx - offset
            if idx >= 0:
                prev_dates[f'd{offset}'] = all_dates[idx]
            else:
                prev_dates[f'd{offset}'] = None
        
        # 前14个交易日用于计算
        prev_20_dates = []
        for offset in range(1, 21):
            idx = date_idx - offset
            if idx >= 0:
                prev_20_dates.append(all_dates[idx])
        
        # 遍历该日的所有股票
        for code in all_codes:
            cd = p_data.get(code, {})
            today = cd.get(dt)
            if not today or today['close'] <= 0:
                continue
            
            today_p = today['p']
            
            # --- d1~d5：前1~5天涨跌幅 ---
            d = {}
            for name, prev_dt in prev_dates.items():
                if prev_dt and prev_dt in cd:
                    d[name] = cd[prev_dt]['p']
                else:
                    d[name] = 0.0
            
            d1, d2, d3, d4, d5 = d['d1'], d['d2'], d['d3'], d['d4'], d['d5']
            
            # --- slope5：5日动量斜率 ---
            # 用d1~d5对时间(0,1,2,3,4)做线性回归的斜率
            p_vals = [d5, d4, d3, d2, d1]  # 时间顺序：d5(最远) → d1(最近)
            if len(set(p_vals)) > 1:
                x = np.array([0, 1, 2, 3, 4])
                y = np.array(p_vals)
                slope5 = round(np.polyfit(x, y, 1)[0], 2)
            else:
                slope5 = 0.0
            
            # --- t4_shadow：T-4日影线率 ---
            # = (high - low) / close * 100 在T-4日
            t4_dt = prev_dates.get('d4')
            if t4_dt and t4_dt in cd:
                t4 = cd[t4_dt]
                t4_shadow = round((t4['high'] - t4['low']) / t4['close'] * 100, 1) if t4['close'] > 0 else 0.0
            else:
                t4_shadow = 0.0
            
            # --- cons_up：连续上涨天数 ---
            cons_up = 0
            for p_name in ['d1', 'd2', 'd3', 'd4', 'd5']:
                pd_val = d.get(p_name, 0)
                if pd_val >= 0:  # 不跌就算连续（包含平盘）
                    cons_up += 1
                else:
                    break
            
            # --- peak_decay：峰值衰减 ---
            # 最近5天中最高涨幅 / 最近1天涨幅 - 1 的绝对值
            # 表示"最近5天最高涨了很多，但今天只涨了一点点"的衰减
            p_max = max(p_vals) if p_vals else 0
            p_min = min(p_vals) if p_vals else 0
            peak_decay = 0.0
            if p_max > 3 and abs(today_p) < p_max * 0.3:
                # 最高涨幅>3%且今日涨幅<最高值的30% = 显著衰减
                peak_decay = round(p_max - abs(today_p), 2)
            
            # 写入数据库
            c.execute('''
                INSERT OR REPLACE INTO features_cache
                (date, code, d1, d2, d3, d4, d5,
                 slope5, t4_shadow, cons_up, peak_decay,
                 computed_from)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (dt, code,
                  round(d1, 2), round(d2, 2), round(d3, 2),
                  round(d4, 2), round(d5, 2),
                  slope5, t4_shadow, cons_up, peak_decay,
                  'auto_compute'))
            total += 1
        
        conn.commit()
        print(f'  {dt}: 计算完成', end='\r')
    
    elapsed = time.time() - t0
    print(f'\n✅ 特征计算完成: {total}条, {elapsed:.0f}s')
    
    # 验证
    c.execute('SELECT date, COUNT(*) FROM features_cache GROUP BY date ORDER BY date DESC LIMIT 5')
    print('最新5天特征量:')
    for dt, cnt in c.fetchall():
        print(f'  {dt}: {cnt}条')
    
    conn.close()
    return total

if __name__ == '__main__':
    print(f'📊 特征计算 {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*50}')
    compute_features()
