#!/usr/bin/env python3
"""
V43 安全监控 — 滚动胜率检查 + 自动级别建议
每天早上计算最近20天胜率，决定用L0-L4哪一级
"""
import sys, os, sqlite3, json
from datetime import datetime, timedelta

DB = os.path.join(os.path.dirname(__file__), 'v13_quant.db')

def check_rolling_winrate(days=20):
    """
    检查最近N天的V43选股胜率
    返回: {total_days, win_days, win_rate, suggested_level}
    """
    if not os.path.exists(DB):
        return {'status': 'no_db', 'suggested_level': 'L0', 'message': '数据库不存在，默认L0'}
    
    try:
        conn = sqlite3.connect(DB, timeout=5)
        cur = conn.cursor()
        
        # 检查是否有selection_log表
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if 'selection_log' not in tables:
            conn.close()
            return {'status': 'no_table', 'suggested_level': 'L0', 'message': '无日志表'}
        
        # 查最近N天的选股记录
        cutoff = (datetime.now() - timedelta(days=days*2)).strftime('%Y-%m-%d')
        
        rows = cur.execute("""
            SELECT date, version, code, name, score, price, next_high_pct, passed
            FROM selection_log 
            WHERE date >= ? AND version LIKE 'V43%'
            ORDER BY date DESC
            LIMIT 50
        """, (cutoff,)).fetchall()
        
        conn.close()
        
        if not rows:
            return {'status': 'no_data', 'suggested_level': 'L0', 'message': '无V43选股记录，默认L0'}
        
        # 按天去重，取每天的冠军
        daily = {}
        for r in rows:
            date = r[0]
            if date not in daily and r[7] is not None:  # passed != None
                daily[date] = {'passed': r[7], 'code': r[3], 'next_high': r[6]}
        
        recent = list(daily.values())[:days]
        total = len(recent)
        wins = sum(1 for r in recent if r['passed'] == 1)
        
        if total == 0:
            return {'status': 'no_recent', 'suggested_level': 'L0', 'message': '最近无数据'}
        
        win_rate = wins / total * 100
        
        # 自动降级逻辑
        if win_rate >= 90:
            level = 'L0'
            msg = f'胜率{win_rate:.0f}% 稳定，维持L0'
        elif win_rate >= 80:
            level = 'L1'
            msg = f'胜率{win_rate:.0f}% 偏高但OK，降一级L1保平安'
        elif win_rate >= 70:
            level = 'L2'
            msg = f'胜率{win_rate:.0f}% 下滑，降到L2放宽候选'
        elif win_rate >= 60:
            level = 'L3'
            msg = f'胜率{win_rate:.0f}% 偏低，降到L3'
        else:
            level = 'BREAK'
            msg = f'胜率{win_rate:.0f}% ❌ 建议空仓一天'
        
        return {
            'status': 'ok',
            'total': total,
            'wins': wins,
            'win_rate': round(win_rate, 1),
            'suggested_level': level,
            'message': msg,
        }
    
    except Exception as e:
        return {'status': 'error', 'suggested_level': 'L0', 'message': str(e)}

def record_selection(version, code, name, score, price, market_type, level):
    """记录选股结果到数据库"""
    try:
        conn = sqlite3.connect(DB, timeout=5)
        today = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn.execute("""
            INSERT INTO selection_log (date, datetime, version, code, name, score, price, rank, market_type, level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (today, now, version, code, name, score, price, 1, market_type, level))
        
        conn.commit()
        conn.close()
        return True
    except:
        return False

if __name__ == '__main__':
    print('V43 安全监控')
    print('=' * 40)
    
    result = check_rolling_winrate()
    print(f'状态: {result.get("status")}')
    print(f'近{result.get("total",0)}天: {result.get("wins",0)}胜 / {result.get("total",0)}次')
    print(f'胜率: {result.get("win_rate","?")}%')
    print(f'建议级别: {result.get("suggested_level","L0")}')
    print(f'建议: {result.get("message","")}')
