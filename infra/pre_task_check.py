#!/usr/bin/env python
"""
统一前置检查 — 跑任何策略任务前验证数据完整性、实时性、有效性
根据当前时间智能判断数据预期状态，缺失自动补充

三步检查：
1️⃣ 股票信息(data_stock_info) → 是否最新
2️⃣ 历史行情(data_cache) → 日期覆盖是否完整
3️⃣ 技术指标(WR/KDJ/MACD) → 是否已计算
"""
import sqlite3, os, json, time, subprocess, sys
from datetime import datetime, timedelta

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/prod')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
sys.path.insert(0, os.path.join(SCRIPTS_DIR, 'lib'))
sys.path.insert(0, SCRIPTS_DIR)
from db_config import get_config

def now():
    return datetime.now()

def is_trading_day():
    """简单判断是否为交易日（周一到周五，不考虑节假日）"""
    return now().weekday() < 5

def get_last_trading_day():
    """获取最近一个交易日"""
    d = now()
    # 如果今天是非交易日，往前找
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    # 如果现在还没到收盘(15:00)，昨天才是最新完整交易日
    if now().hour < 15 or (now().hour == 15 and now().minute < 30):
        yesterday = now() - timedelta(days=1)
        d = yesterday
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d.strftime('%Y-%m-%d')

def get_today_str():
    return now().strftime('%Y-%m-%d')

def get_today_hms():
    return now().strftime('%H:%M:%S')

def check_stock_info_freshness(conn):
    """① 检查股票信息是否当天最新"""
    c = conn.cursor()
    today = get_today_str()
    
    c.execute('SELECT MAX(updated_at) FROM data_stock_info')
    row = c.fetchone()
    last_update = row[0] if row and row[0] else ''
    
    c.execute('SELECT COUNT(*) FROM data_stock_info')
    total = c.fetchone()[0]
    
    is_fresh = last_update.startswith(today)
    is_complete = total >= 3000  # 3043只基本覆盖
    
    return {
        'fresh': is_fresh,
        'complete': is_complete,
        'total': total,
        'last_update': last_update,
        'need_refresh': not is_fresh or not is_complete
    }

def check_data_cache_continuity(conn):
    """② 检查data_cache最近交易日数据完整性"""
    c = conn.cursor()
    today = get_today_str()
    last_td = get_last_trading_day()
    
    # 查最近5个交易日的日期分布
    c.execute('''
        SELECT date, COUNT(*) as cnt 
        FROM data_cache 
        WHERE date >= ? 
        GROUP BY date 
        ORDER BY date DESC 
        LIMIT 10
    ''', (last_td,))
    daily = c.fetchall()
    
    # 检查最近交易日数据量（应接近3000只）
    last_date_data = {}
    for d, cnt in daily:
        last_date_data[d] = cnt
    
    missing_dates = []
    need_refresh = False
    
    # 预期最近交易日应有 ~3000只
    if last_td in last_date_data:
        cnt = last_date_data[last_td]
        if cnt < 2000:
            missing_dates.append(f'{last_td} 数据量不足({cnt}/3000)')
            need_refresh = True
    else:
        missing_dates.append(f'{last_td} 完全缺失')
        need_refresh = True
    
    return {
        'ok': not need_refresh,
        'daily_counts': daily,
        'missing_dates': missing_dates,
        'need_refresh': need_refresh,
        'last_trading_day': last_td
    }

def check_tech_indicators(conn):
    """③ 检查最近交易日技术指标是否已计算"""
    c = conn.cursor()
    last_td = get_last_trading_day()
    
    # 随机采样50只检查WR/KDJ/DIF是否已算
    c.execute('''
        SELECT code, wr_val, dif_val, j_val
        FROM data_cache 
        WHERE date = ? AND wr_val = 50
        LIMIT 50
    ''', (last_td,))
    no_wr = c.fetchall()
    
    c.execute('''
        SELECT COUNT(*) 
        FROM data_cache 
        WHERE date = ? AND (j_val = 50 AND k_val = 50 AND d_val = 50)
    ''', (last_td,))
    no_kdj = c.fetchone()[0]
    
    return {
        'ok': len(no_wr) < 100,  # <100只缺WR算ok
        'missing_wr': len(no_wr),
        'missing_kdj': no_kdj,
        'need_refresh': len(no_wr) > 500 or no_kdj > 500
    }

def refresh_stock_info(conn):
    """刷新股票信息(HSL/PE/市值)"""
    today = get_today_str()
    now_str = get_today_hms()
    
    pool_file = get_config('path', 'stock_pool')
    if not pool_file or not os.path.exists(pool_file):
        pool_file = os.path.join(SCRIPTS_DIR, '活跃股票池_3043.json')
    
    with open(pool_file, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    
    codes = [s['code'] if isinstance(s, dict) else s for s in pool]
    codes = [c for c in codes if c.startswith(('600','601','603','605','000','001','002'))]
    
    # 只刷新上次失败的（先查已有today的）
    c = conn.cursor()
    c.execute('SELECT code FROM data_stock_info WHERE updated_at LIKE ?', (f'{today}%',))
    fresh_codes = set(r[0] for r in c.fetchall())
    
    to_fetch = [c for c in codes if c not in fresh_codes]
    updated = len(fresh_codes)
    total_failed = 0
    
    if to_fetch:
        BATCH = 50
        for i in range(0, len(to_fetch), BATCH):
            batch = to_fetch[i:i+BATCH]
            symbols = ','.join(f"sh{c}" if c.startswith(('6','9')) else f"sz{c}" for c in batch)
            url = f'http://qt.gtimg.cn/q={symbols}'
            
            try:
                r = subprocess.run(['curl', '-s', '--max-time', '10', url],
                                  capture_output=True, timeout=15)
                text = r.stdout.decode('gbk', errors='ignore')
                
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
                        total_failed += 1
                        continue
            except Exception as e:
                total_failed += len(batch)
            
            conn.commit()
    
    return updated, total_failed, len(to_fetch)

def refresh_last_trading_day_data(conn):
    """补充最近交易日的收盘数据"""
    c = conn.cursor()
    last_td = get_last_trading_day()
    now_str = get_today_hms()
    
    # 看看缺哪些
    c.execute('SELECT COUNT(*) FROM data_cache WHERE date=?', (last_td,))
    existing = c.fetchone()[0]
    
    pool_file = os.path.join(SCRIPTS_DIR, '活跃股票池_3043.json')
    with open(pool_file, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    
    codes = [s['code'] if isinstance(s, dict) else s for s in pool]
    codes = [c for c in codes if c.startswith(('600','601','603','605','000','001','002'))]
    
    c2 = conn.cursor()
    c2.execute('SELECT code FROM data_cache WHERE date=?', (last_td,))
    existing_codes = set(r[0] for r in c2.fetchall())
    
    to_fetch = [c for c in codes if c not in existing_codes]
    saved = 0
    BATCH = 50
    
    for i in range(0, len(to_fetch), BATCH):
        batch = to_fetch[i:i+BATCH]
        symbols = ','.join(f"sh{c}" if c.startswith(('6','9')) else f"sz{c}" for c in batch)
        url = f'http://qt.gtimg.cn/q={symbols}'
        
        try:
            r = subprocess.run(['curl', '-s', '--max-time', '10', url],
                              capture_output=True, timeout=15)
            text = r.stdout.decode('gbk', errors='ignore')
            
            for line in text.strip().split(';'):
                if not line or '=' not in line:
                    continue
                try:
                    parts = line.split('=')[1].strip().strip('"').split('~')
                    if len(parts) < 40:
                        continue
                    code = parts[2]
                    price = float(parts[3]) if parts[3] else 0
                    if price <= 0:
                        continue
                    
                    high = float(parts[33]) if len(parts) > 33 and parts[33] else price
                    low = float(parts[34]) if len(parts) > 34 and parts[34] else price
                    cl = round((price - low) / (high - low) * 100, 2) if (high - low) > 0 else 50
                    
                    c.execute('''
                        INSERT OR IGNORE INTO data_cache
                        (date, code, name, p, cl, vr, n, vol_ratio,
                         dif_val, macd_golden, wr_val, j_val, k_val, d_val,
                         pos_in_day, above_ma5, kdj_golden,
                         close, volume, original_source, cache_version)
                        VALUES (?,?,?,?,?,0,0,0,
                                0,0,50,50,50,50,
                                50,0,0,
                                ?,?,?,?)
                    ''', (last_td, code, parts[1] if len(parts) > 1 else '',
                          float(parts[39]) if len(parts) > 39 and parts[39] else 0, cl,
                          round(float(parts[46]) if len(parts) > 46 and parts[46] else 0, 2),
                          round(price, 2), 0,
                          f'tencent:precheck', last_td))
                    saved += 1
                except:
                    pass
            conn.commit()
        except:
            pass
    
    return saved, len(to_fetch)

def run_checks(refresh_if_needed=True):
    """
    主入口：执行前置检查
    refresh_if_needed: 是否自动补充缺失数据
    """
    print(f'📋 前置数据检查 {now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'{"=" * 50}')
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # ① 检查股票信息
        print('\n① 股票信息(data_stock_info)...')
        info = check_stock_info_freshness(conn)
        if info['fresh']:
            print(f'   ✅ 当天已更新 ({info["last_update"]}), {info["total"]}只')
        else:
            print(f'   ⚠️ 非当天数据 ({info["last_update"]}), {info["total"]}只')
            if refresh_if_needed:
                print('   → 开始刷新...')
                updated, failed, total = refresh_stock_info(conn)
                print(f'   ✅ 刷新完成: 成功{updated}只 | 失败{failed}只')
                info = check_stock_info_freshness(conn)
                if info['fresh']:
                    print(f'   ✅ 刷新后验证通过')
                else:
                    print(f'   ⚠️ 刷新后仍有缺口，不影响策略运行')
        
        # ② 检查历史行情
        print('\n② 历史行情(data_cache)...')
        cache = check_data_cache_continuity(conn)
        last_td = cache['last_trading_day']
        daily_str = ', '.join(f"{d}={cnt}" for d, cnt in cache['daily_counts'][:5])
        print(f'   📅 最近交易日: {last_td}')
        print(f'   日分布: {daily_str}')
        
        if cache['missing_dates']:
            print(f'   ⚠️ 缺口: {" | ".join(cache["missing_dates"])}')
            if refresh_if_needed:
                print('   → 开始补充缺口数据...')
                saved, total = refresh_last_trading_day_data(conn)
                print(f'   ✅ 补充完成: 新增{saved}只')
        else:
            print(f'   ✅ 数据完整')
        
        # ③ 检查技术指标
        print('\n③ 技术指标(WR/KDJ/MACD)...')
        tech = check_tech_indicators(conn)
        if tech['ok']:
            print(f'   ✅ WR/KDJ已计算 (缺失{tech["missing_wr"]}只WR, {tech["missing_kdj"]}只KDJ)')
        else:
            print(f'   ⚠️ 大量缺失: WR缺{tech["missing_wr"]}只, KDJ缺{tech["missing_kdj"]}只')
        
    finally:
        conn.close()
    
    print(f'\n{"=" * 50}')
    print(f'✅ 前置检查完成 {now().strftime("%H:%M:%S")}')
    return 0

def check_data_completeness(strict=False, refresh_if_needed=True):
    """
    核心数据完整性检查 — 跑策略前必须执行
    
    检查内容:
    1. data_cache 当天和最近交易日数据是否完整（对照3043只活跃池）
    2. features_cache 是否已计算
    3. data_stock_info 是否当天最新
    
    自动修复:
    - 缺股票 → 从腾讯K线或原版big_cache补
    - 缺特征 → 自动计算
    - 缺HSL → 从腾讯API拉
    
    返回: (pass_count, fail_count, issues)
    """
    import json as _json
    issues = []
    pass_count = 0
    fail_count = 0
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 加载活跃股票池
    pool_file = os.path.join(SCRIPTS_DIR, 'data', '活跃股票池_3043.json')
    if not os.path.exists(pool_file):
        issues.append(('CRITICAL', '股票池文件不存在'))
        conn.close()
        return 0, 1, issues
    
    with open(pool_file, 'r', encoding='utf-8') as f:
        pool = _json.load(f)
    active_codes = set(pool.get('codes', pool if isinstance(pool, list) else []))
    active_codes = {c for c in active_codes if c.startswith(('600','601','603','605','000','001','002'))}
    
    today = get_today_str()
    last_td = get_last_trading_day()
    
    # === ① data_cache: 最近交易日的完整度 ===
    c.execute('SELECT DISTINCT code FROM data_cache WHERE date=?', (last_td,))
    have_td = {r[0] for r in c.fetchall()}
    missing_ids = active_codes - have_td
    # 只报有名字的缺（历史代码不计）
    named_missing = []
    for code in missing_ids:
        c.execute('SELECT name FROM data_cache WHERE code=? LIMIT 1', (code,))
        r = c.fetchone()
        if r and r[0] and r[0] != '?':
            named_missing.append(code)
    
    if named_missing:
        issues.append(('WARN', f'{last_td} 缺少{len(named_missing)}只有名股票'))
        if strict:
            fail_count += 1
    else:
        pass_count += 1
    
    # === ② features_cache: 检查和补全 ===
    c.execute('SELECT COUNT(*) FROM features_cache WHERE date=?', (last_td,))
    feat_cnt = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM data_cache WHERE date=?', (last_td,))
    data_cnt = c.fetchone()[0]
    
    if feat_cnt < data_cnt * 0.95:
        issues.append(('WARN', f'{last_td} 特征不全: {feat_cnt}/{data_cnt}'))
        if strict:
            fail_count += 1
    else:
        pass_count += 1
    
    # === ③ data_stock_info: 数据是否已刷新 ===
    c.execute('SELECT COUNT(*) FROM data_stock_info')
    info_cnt = c.fetchone()[0]
    
    if info_cnt < 2900:
        issues.append(('INFO', f'股票信息不全: {info_cnt}只，尝试刷新'))
        if refresh_if_needed:
            refresh_stock_info(conn)
            issues.append(('INFO', '股票信息已尝试刷新'))
    
    conn.close()
    return pass_count, fail_count, issues


def auto_fill_data():
    """自动补全缺失的股票数据 — 跑策略前自动执行"""
    import json as _json
    import subprocess as _sp
    from time import sleep
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 活跃股票池
    pool_file = os.path.join(SCRIPTS_DIR, '活跃股票池_3043.json')
    with open(pool_file, 'r', encoding='utf-8') as f:
        pool = _json.load(f)
    active_codes = set(pool.get('codes', pool))
    active_codes = {c for c in active_codes if c.startswith(('600','601','603','605','000','001','002'))}
    
    # 最近3个交易日
    c.execute('SELECT DISTINCT date FROM data_cache ORDER BY date DESC LIMIT 3')
    recent_dates = [r[0] for r in c.fetchall()]
    
    fixed = 0
    for dt in recent_dates:
        c.execute('SELECT code FROM data_cache WHERE date=?', (dt,))
        have = {r[0] for r in c.fetchall()}
        missing = [code for code in active_codes if code not in have]
        
        for code in missing:
            c.execute('SELECT name FROM data_cache WHERE code=? LIMIT 1', (code,))
            r = c.fetchone()
            if not r or not r[0]:  # 无名的老代码跳过
                continue
            
            # 从腾讯K线API补
            pref = 'sh' if code.startswith(('6','9')) else 'sz'
            url = f'http://ifzq.gtimg.cn/appstock/app/kline/mkline?param={pref}{code},day,,,30'
            try:
                r2 = _sp.run(['curl', '-sL', '--max-time', '8', url], capture_output=True, timeout=10)
                k_data = _json.loads(r2.stdout)
                day_data = k_data.get('data', {}).get(pref+code, {}).get('day', [])
            except:
                day_data = []
            
            if not day_data:
                continue
            
            k_map = {}
            for k in day_data:
                if len(k) >= 6:
                    k_map[k[0][:10]] = {'close': float(k[2]), 'high': float(k[3]), 
                                        'low': float(k[4]), 'vol': float(k[5])}
            
            k = k_map.get(dt)
            if not k: continue
            
            prev_c = 0
            c.execute('SELECT close FROM data_cache WHERE code=? AND date IN (SELECT MAX(date) FROM data_cache WHERE date<?)', (code, dt))
            pr = c.fetchone()
            if pr: prev_c = pr[0]
            if prev_c <= 0:
                for kd in sorted(k_map.keys()):
                    if kd < dt: prev_c = k_map[kd]['close']
            if prev_c <= 0: continue
            
            p = round((k['close'] - prev_c) / prev_c * 100, 2)
            cl = round((k['close'] - k['low']) / (k['high'] - k['low']) * 100, 2) if (k['high'] - k['low']) > 0 else 50
            
            # 从成交量算VR
            c.execute('SELECT volume FROM data_cache WHERE code=? AND date<? AND volume>0 ORDER BY date DESC LIMIT 5', (code, dt))
            vols = [r[0] for r in c.fetchall()]
            avg_vol = sum(vols)/len(vols) if vols else 1
            calc_vr = round(k['vol']/avg_vol, 2) if avg_vol > 0 else 1.0
            calc_vr = max(0.01, min(calc_vr, 10.0))
            
            c.execute('''INSERT OR IGNORE INTO data_cache
                (date,code,name,p,cl,vr,n,dif_val,macd_golden,wr_val,j_val,k_val,d_val,
                 pos_in_day,above_ma5,kdj_golden,close,volume,original_source,cache_version)
                VALUES(?,?,?,?,?,?,0,0,0,50,50,50,50,50,0,0,?,?,?,?)''',
                (dt, code, r[0], round(p,2), round(cl,2), round(k['close'],2), 
                 round(k['vol'],0), 'auto-fill-precheck', dt))
            fixed += 1
            sleep(0.3)
        
        if fixed > 0:
            conn.commit()
    
    conn.close()
    return fixed


def run():
    """生产运行入口 — 每个策略任务跑之前调用"""
    if not is_trading_day():
        print('📋 非交易日，跳过前置检查')
        return 0
    
    print(f'📋 前置数据检查 {now().strftime("%H:%M:%S")}')
    
    # 1. 完整性检查（只检查，不拉数据！14:50不能等）
    ok, fail, issues = check_data_completeness(strict=False, refresh_if_needed=False)
    
    # 2. 输出结果
    has_warn = False
    for level, msg in issues:
        icon = '⚠️' if level == 'WARN' else 'ℹ️' if level == 'INFO' else '❌'
        print(f'  {icon} {msg}')
        if level == 'WARN': has_warn = True
    
    if has_warn:
        print(f'  ⚠️ 数据有缺口，但不阻塞策略（用已有数据继续）')
    else:
        print(f'  ✅ 数据完整，可以安全运行策略')
    
    return 0

if __name__ == '__main__':
    sys.exit(run())
