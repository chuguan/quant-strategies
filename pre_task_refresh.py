#!/usr/bin/env python
"""
统一前置任务 — 跑任何定时任务之前先刷新基础数据
每天09:00运行，更新HSL/PE/市值等股票信息
后续所有任务（竞价、选股）都读到最新数据
"""
import sqlite3, os, sys, json, time, subprocess
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

def refresh_stock_info():
    """
    从腾讯API批量刷新股票基本信息：
    - hsl (换手率)
    - pe (市盈率)
    - shizhi (总市值)
    - liangbi (量比)
    """
    today = datetime.now().strftime('%Y-%m-%d')
    now_str = datetime.now().strftime('%H:%M:%S')
    
    # 加载股票池
    pool_file = os.path.join(SCRIPTS_DIR, '活跃股票池_3043.json')
    if not os.path.exists(pool_file):
        print(f'⚠️ 未找到股票池文件')
        return 0
    
    with open(pool_file, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    
    codes = [s['code'] if isinstance(s, dict) else s for s in pool]
    codes = [c for c in codes if c.startswith(('600','601','603','605','000','001','002'))]
    
    print(f'🔄 刷新 {len(codes)} 只股票信息...')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 确保表存在
    c.execute('''
        CREATE TABLE IF NOT EXISTS data_stock_info (
            code TEXT PRIMARY KEY,
            name TEXT DEFAULT '',
            hsl REAL DEFAULT 0,
            pe REAL DEFAULT 0,
            shizhi REAL DEFAULT 0,
            liangbi REAL DEFAULT 0,
            price REAL DEFAULT 0,
            updated_at TEXT DEFAULT ''
        )
    ''')
    
    updated = 0
    failed = 0
    t0 = time.time()
    
    # 腾讯API单次查多只（最多50只一批）
    BATCH = 50
    for i in range(0, len(codes), BATCH):
        batch = codes[i:i+BATCH]
        # 构造腾讯API请求
        symbols = ','.join(f"sh{c}" if c.startswith(('6','9')) else f"sz{c}" for c in batch)
        url = f'http://qt.gtimg.cn/q={symbols}'
        
        try:
            r = subprocess.run(['curl', '-s', '--max-time', '10', url],
                              capture_output=True, timeout=15)
            text = r.stdout.decode('gbk', errors='ignore')
            
            # 解析每只股票
            for line in text.strip().split(';'):
                if not line or '=' not in line:
                    continue
                try:
                    parts = line.split('=')[1].strip().strip('"').split('~')
                    if len(parts) < 45:
                        continue
                    
                    code = parts[2]
                    hsl = float(parts[38]) if len(parts) > 38 and parts[38] else 0
                    pe = float(parts[39]) if len(parts) > 39 and parts[39] else 0
                    shizhi = float(parts[44]) if len(parts) > 44 and parts[44] else 0
                    liangbi = float(parts[46]) if len(parts) > 46 and parts[46] else 0
                    price = float(parts[3]) if parts[3] else 0
                    name = parts[1]
                    
                    c.execute('''
                        INSERT OR REPLACE INTO data_stock_info
                        (code, name, hsl, pe, shizhi, liangbi, price, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (code, name, hsl, pe, shizhi, liangbi, price, f'{today} {now_str}'))
                    updated += 1
                    
                except (ValueError, IndexError):
                    failed += 1
                    continue
        
        except Exception as e:
            failed += len(batch)
            print(f'  批次{i//BATCH}失败: {str(e)[:50]}')
        
        # 进度
        pct = min(100, (i + BATCH) * 100 // len(codes))
        elapsed = time.time() - t0
        print(f'  {pct:>3}% | 已刷新{updated}只 | {elapsed:.0f}s')
    
    conn.commit()
    conn.close()
    
    elapsed = time.time() - t0
    print(f'\n✅ 股票信息刷新完成')
    print(f'  成功: {updated}只 | 失败: {failed}只 | 耗时: {elapsed:.0f}s')
    return updated

if __name__ == '__main__':
    print(f'📡 统一前置任务 {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*50}')
    refresh_stock_info()
