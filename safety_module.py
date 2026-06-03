#!/usr/bin/env python
"""每日安全模块：备份 + 健康检查 + 版本校验"""
import sqlite3, os, shutil, hashlib, json
from datetime import datetime, timedelta

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
BACKUP_DIR = os.path.join(SCRIPTS_DIR, 'backup')
os.makedirs(BACKUP_DIR, exist_ok=True)

def daily_backup():
    """① 每日自动备份数据库（保留30天）"""
    today = datetime.now().strftime('%Y%m%d')
    backup_file = os.path.join(BACKUP_DIR, f'v13_quant_{today}.db')
    
    if os.path.exists(backup_file):
        print(f'⏭ 今日已备份: {backup_file}')
        return
    
    if not os.path.exists(DB_PATH):
        print(f'❌ 数据库不存在: {DB_PATH}')
        return
    
    shutil.copy2(DB_PATH, backup_file)
    size_mb = os.path.getsize(backup_file) / 1024 / 1024
    print(f'✅ 备份完成: {backup_file} ({size_mb:.1f}MB)')
    
    # 清理30天前的备份
    cutoff = datetime.now() - timedelta(days=30)
    for f in os.listdir(BACKUP_DIR):
        if not f.endswith('.db'):
            continue
        fpath = os.path.join(BACKUP_DIR, f)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime < cutoff:
            os.remove(fpath)
            print(f'🗑 清理旧备份: {f}')

def health_check():
    """② 每日健康检查：昨天是否有选股记录"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    if not os.path.exists(DB_PATH):
        print(f'❌ 健康检查失败: 数据库不存在')
        return False
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 检查昨天是否有选股记录
    c.execute('''
        SELECT COUNT(*) FROM selection_pool 
        WHERE date=? AND strategy_version=(SELECT value FROM config WHERE key='active_version')
    ''', (yesterday,))
    cnt = c.fetchone()[0]
    
    if cnt == 0:
        print(f'⚠️ 健康检查告警: {yesterday} 无选股记录！')
        conn.close()
        return False
    
    # 检查昨日冠军
    c.execute('''
        SELECT name, total_score FROM selection_pool
        WHERE date=? AND strategy_version=(SELECT value FROM config WHERE key='active_version')
        ORDER BY total_score DESC LIMIT 1
    ''', (yesterday,))
    champ = c.fetchone()
    if champ:
        print(f'✅ 健康检查通过: {yesterday} 冠军={champ[0]} 总分={champ[1]}')
    
    conn.close()
    return True

def verify_strategy_hash(version=None):
    """③ 运行时校验：当前策略文件hash vs 数据库归档hash"""
    if not os.path.exists(DB_PATH):
        print('❌ 数据库不存在，无法校验')
        return False
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 读取当前active_version
    if version is None:
        c.execute("SELECT value FROM config WHERE key='active_version'")
        r = c.fetchone()
        version = r[0] if r else 'V13'
    
    # 找到该版本的归档文件
    c.execute('''
        SELECT file_name, file_hash, file_content 
        FROM strategy_files 
        WHERE strategy_version=? AND file_type='scoring_strategy'
    ''', (version,))
    
    all_ok = True
    for fname, db_hash, content in c.fetchall():
        # 在磁盘上找这个文件
        disk_path = os.path.join(SCRIPTS_DIR, 'release', version, '评分策略', f'分而治之_V10_{fname.split("_")[0]}_评分策略.py')
        # 模糊查找
        found = False
        for root, dirs, files in os.walk(os.path.join(SCRIPTS_DIR, 'release')):
            for f in files:
                if f.endswith('.py') and version in root and fname.split('_')[0] in f:
                    disk_path = os.path.join(root, f)
                    found = True
                    break
            if found:
                break
        
        if found and os.path.exists(disk_path):
            with open(disk_path, 'r', encoding='utf-8') as f:
                disk_content = f.read()
            disk_hash = hashlib.sha256(disk_content.encode()).hexdigest()[:16]
            
            if disk_hash == db_hash:
                print(f'  ✅ {fname:>35} hash一致')
            else:
                print(f'  ❌ {fname:>35} hash不匹配！磁盘={disk_hash} 归档={db_hash}')
                all_ok = False
        else:
            # 磁盘文件不存在，用归档恢复
            print(f'  ⚠️ {fname:>35} 磁盘文件丢失，将从数据库恢复')
            recovery_path = os.path.join(SCRIPTS_DIR, 'release', version, '评分策略', f'分而治之_V10_{fname.split("_")[0]}_评分策略.py')
            os.makedirs(os.path.dirname(recovery_path), exist_ok=True)
            with open(recovery_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f'  ✅ 已恢复: {recovery_path}')
    
    conn.close()
    return all_ok

def check_rolling_winrate(days=30):
    """④ 滚动胜率监控"""
    if not os.path.exists(DB_PATH):
        return None
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key='active_version'")
    ver = c.fetchone()
    version = ver[0] if ver else 'V13'
    c.execute("SELECT value FROM config WHERE key='target_nh'")
    t = c.fetchone()
    target = float(t[0]) if t else 2.5
    
    # 从champion_daily视图获取最近N天的冠军及其涨幅
    c.execute('''
        SELECT p.date, p.name, p.total_score, dp.n
        FROM champion_daily p
        LEFT JOIN data_cache dp ON p.date=dp.date AND p.code=dp.code
        WHERE p.strategy_version=?
        ORDER BY p.date DESC LIMIT ?
    ''', (version, days))
    
    results = c.fetchall()
    conn.close()
    
    if len(results) < 5:
        print(f'⏳ 数据不足，无法计算滚动胜率')
        return None
    
    wins = sum(1 for r in results if r[3] is not None and r[3] >= target)
    total = len(results)
    rate = wins / total * 100
    
    print(f'📊 滚动胜率（最近{total}天）: {wins}/{total} = {rate:.1f}% (目标≥{target}%)')
    
    if rate < 70:
        print(f'  ❌ 告警：胜率低于70%！')
    elif rate < 80:
        print(f'  ⚠️ 警告：胜率低于80%，需关注')
    else:
        print(f'  ✅ 正常')
    
    return rate

if __name__ == '__main__':
    print(f'{"="*60}')
    print(f'  🛡️ 安全模块自检 {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*60}')
    
    print(f'\n① 数据库备份')
    daily_backup()
    
    print(f'\n② 策略文件hash校验')
    verify_strategy_hash()
    
    print(f'\n③ 滚动胜率监控')
    check_rolling_winrate(30)
    
    print(f'\n④ 健康检查')
    health_check()
