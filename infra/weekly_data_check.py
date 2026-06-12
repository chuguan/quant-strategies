#!/usr/bin/env python
"""
每周数据源完整性检查 — 看看各数据源有没有缺口
跑法：python weekly_data_check.py
"""
import sqlite3, os, sys, json
from datetime import datetime, timedelta

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/prod')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
sys.path.insert(0, os.path.join(SCRIPTS_DIR, 'lib'))
sys.path.insert(0, SCRIPTS_DIR)
from db_config import get_config

def check_data_gaps():
    """检查数据天数的连续性"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    report = []
    report.append(f'\n{"="*55}')
    report.append(f'  📊 数据完整性周报 {datetime.now().strftime("%Y-%m-%d")}')
    report.append(f'{"="*55}')
    
    # 1. 检查各表数据量
    tables = ['data_cache', 'data_sina', 'selection_pool', 'strategy_files', 'strategy_snapshot']
    report.append(f'\n📋 各表数据量：')
    for tbl in tables:
        try:
            cnt = c.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]
            c.execute(f'SELECT MIN(date), MAX(date) FROM {tbl}')
            dr = c.fetchone()
            if dr and dr[0]:
                report.append(f'  {tbl:>20}: {cnt:>8,}行  {dr[0]} ~ {dr[1]}')
            else:
                report.append(f'  {tbl:>20}: {cnt:>8,}行')
        except:
            pass
    
    # 2. 检查 data_cache 的日期连续性
    report.append(f'\n📅 数据连续性(data_cache)：')
    c.execute('SELECT DISTINCT date FROM data_cache ORDER BY date')
    dates = [r[0] for r in c.fetchall()]
    
    if len(dates) >= 2:
        # 找缺口
        gaps = []
        for i in range(len(dates) - 1):
            d1 = datetime.strptime(dates[i], '%Y-%m-%d')
            d2 = datetime.strptime(dates[i+1], '%Y-%m-%d')
            diff = (d2 - d1).days
            if diff > 3:  # 周末最多隔2天，超过3天说明缺了
                gaps.append((dates[i], dates[i+1], diff - 1))
        
        report.append(f'  连续天数: {len(dates)}天')
        report.append(f'  起止: {dates[0]} ~ {dates[-1]}')
        
        if gaps:
            report.append(f'  ⚠️ 发现 {len(gaps)} 个数据缺口：')
            for g in gaps:
                report.append(f'    {g[0]} → {g[1]}: 缺 {g[2]} 天')
        else:
            report.append(f'  ✅ 数据连续，无缺口')
    
    # 3. 检查选股记录
    report.append(f'\n🏆 本周选股记录(selection_pool)：')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    c.execute('''
        SELECT date, strategy_version, COUNT(DISTINCT date) 
        FROM selection_pool 
        WHERE date >= ? 
        GROUP BY strategy_version
    ''', (week_ago,))
    for r in c.fetchall():
        report.append(f'  {r[0]:>10} ~ {r[1]}: {r[2]}天有记录')
    
    week_dates = c.execute('''
        SELECT DISTINCT date FROM selection_pool 
        WHERE date >= ? ORDER BY date
    ''', (week_ago,)).fetchall()
    
    if len(week_dates) < 5:
        report.append(f'  ⚠️ 最近7天仅有{len(week_dates)}天有选股记录')
    else:
        report.append(f'  ✅ 最近7天选股正常')
    
    # 4. 配置检查
    report.append(f'\n⚙️ 关键配置：')
    for key in ['active_version', 'data_cache_version', 'target_nh']:
        val = get_config('strategy', key, '?')
        report.append(f'  {key:>20}: {val}')
    
    # 5. 数据库文件大小
    if os.path.exists(DB_PATH):
        size_mb = os.path.getsize(DB_PATH) / 1024 / 1024
        report.append(f'\n💾 数据库大小: {size_mb:.1f}MB')
    
    report.append(f'\n{"="*55}')
    report.append(f'  📋 检查完成')
    report.append(f'{"="*55}')
    
    conn.close()
    return '\n'.join(report)

if __name__ == '__main__':
    report = check_data_gaps()
    print(report)
    
    # 如果有缺口，发告警邮件
    if '⚠️' in report:
        print('\n⚠️ 发现数据问题，需关注')
