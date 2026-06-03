#!/usr/bin/env python3
"""
V42 胜率监控 — 每天收盘后检查昨日冠军的D+1表现
滚动30天胜率监控，低于阈值自动报警
"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(__file__))
import sqlite3
from datetime import datetime, timedelta

DB = os.path.join(os.path.dirname(__file__), 'v13_quant.db')
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

def curl_get(url, timeout=8):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url], capture_output=True,timeout=timeout+3)
        return r.stdout.decode('gbk',errors='replace')
    except: return ''

def get_today_high(code):
    """通过腾讯API获取今日最高价"""
    sym = f'{PREFIX(code)}{code}'
    text = curl_get(f'https://qt.gtimg.cn/q={sym}', timeout=6)
    if '~' not in text: return None
    parts = text.split('~')
    if len(parts) < 34: return None
    try:
        high = float(parts[33])  # 今日最高
        return high
    except: return None

def check_latest_picks():
    """检查最新V42冠军在D+1的表现（不限日期）"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    if not os.path.exists(DB):
        return {'status': 'no_db'}
    
    conn = sqlite3.connect(DB, timeout=5)
    cur = conn.cursor()
    
    # 找V42中还没有结果的记录（notes IS NULL）
    rows = cur.execute("""
        SELECT id, version, date, c_code, c_name, c_price, market_type
        FROM daily_selection_log
        WHERE version = 'V42' AND (notes IS NULL OR notes = '' OR notes = '{}')
        ORDER BY date DESC
        LIMIT 3
    """).fetchall()
    
    result = {'results': [], 'found': len(rows)}
    
    for row in rows:
        rid, ver, dt, code, name, price, mk = row
        if not price or price <= 0:
            continue
        
        # 获取今日最高价
        high = get_today_high(code)
        if high is None or high <= 0:
            result['results'].append({'id': rid, 'code': code, 'status': 'no_data'})
            continue
        
        # 计算涨幅
        pct = (high / price - 1) * 100
        passed = 1 if pct >= 2.5 else 0
        
        # 记录结果到notes字段
        note = json.dumps({
            'check_date': today,
            'd1_high': round(high, 2),
            'd1_pct': round(pct, 2),
            'passed': passed
        })
        
        cur.execute("UPDATE daily_selection_log SET notes = ? WHERE id = ?", (note, rid))
        
        result['results'].append({
            'id': rid, 'code': code, 'name': name,
            'buy': price, 'd1_high': high, 'd1_pct': round(pct, 2),
            'passed': bool(passed)
        })
    
    conn.commit()
    conn.close()
    return result

def calc_rolling_winrate(days=30):
    """计算滚动30天胜率"""
    if not os.path.exists(DB):
        return None
    
    conn = sqlite3.connect(DB, timeout=5)
    cur = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(days=days*2)).strftime('%Y-%m-%d')
    
    # 找V42有结果记录的
    rows = cur.execute("""
        SELECT date, c_code, c_name, notes
        FROM daily_selection_log
        WHERE version = 'V42' AND date >= ? AND notes IS NOT NULL AND notes != ''
        ORDER BY date DESC
        LIMIT ?
    """, (cutoff, days+5)).fetchall()
    
    conn.close()
    
    results = []
    for r in rows:
        try:
            note = json.loads(r[3])
            if 'passed' in note:
                results.append(note['passed'])
        except: pass
    
    if len(results) < 5:
        return None
    
    wins = sum(results)
    total = len(results)
    rate = wins / total * 100
    
    return {
        'total': total,
        'wins': wins,
        'rate': round(rate, 1),
        'latest': results[-1] if results else None,
    }

def get_recent_picks(n=10):
    """获取最近N天V42的选股和结果"""
    if not os.path.exists(DB):
        return []
    
    conn = sqlite3.connect(DB, timeout=5)
    rows = conn.execute("""
        SELECT date, market_type, c_code, c_name, c_price, notes
        FROM daily_selection_log
        WHERE version = 'V42'
        ORDER BY date DESC
        LIMIT ?
    """, (n,)).fetchall()
    conn.close()
    
    data = []
    for r in rows:
        item = {
            'date': r[0], 'market_type': r[1],
            'code': r[2], 'name': r[3], 'price': r[4],
            'result': None, 'd1_pct': None
        }
        try:
            note = json.loads(r[5]) if r[5] else {}
            item['d1_pct'] = note.get('d1_pct')
            item['passed'] = note.get('passed')
        except: pass
        data.append(item)
    
    return data

if __name__ == '__main__':
    import sys
    if '--check' in sys.argv:
        print('▶ V42 D+1 表现检查...')
        r = check_latest_picks()
        print(f'   找到{r["found"]}条待检查记录')
        for res in r['results']:
            if res.get('passed') is True:
                print(f'   ✅ {res["name"]}({res["code"]}): ¥{res["buy"]}→最高¥{res["d1_high"]} ({res["d1_pct"]:+.2f}%) PASS')
            elif res.get('passed') is False:
                print(f'   ❌ {res["name"]}({res["code"]}): ¥{res["buy"]}→最高¥{res["d1_high"]} ({res["d1_pct"]:+.2f}%) FAIL')
            else:
                print(f'   ⏺ {res.get("code","?")}: 数据未获取')
    
    elif '--winrate' in sys.argv:
        wr = calc_rolling_winrate(30)
        if wr:
            mark = '✅' if wr['rate'] >= 90 else '⚠️' if wr['rate'] >= 80 else '🚨'
            print(f'   {mark} V42 近{wr["total"]}天胜率: {wr["rate"]}% ({wr["wins"]}/{wr["total"]})')
            if wr['rate'] < 90:
                print(f'   ⚠️ 警告：胜率低于90%，请注意！')
            if wr['rate'] < 80:
                print(f'   🚨 严重警告：胜率低于80%，建议检查策略！')
        else:
            print('   ❌ 数据不足（需要至少5次记录）')
        
    elif '--recent' in sys.argv:
        data = get_recent_picks(10)
        print(f'   V42 最近{len(data)}次选股:')
        for d in data:
            mk = d.get('market_type','?')
            if d.get('passed') is True:
                res = f'✅ {d["d1_pct"]:+.2f}%'
            elif d.get('passed') is False:
                res = f'❌ {d["d1_pct"]:+.2f}%'
            else:
                res = '⏺ 待验证'
            print(f'   {d["date"]} [{mk}] {d["name"]}({d["code"]}) ¥{d["price"]} → {res}')
    
    else:
        print('用法: python v42_monitor.py --check    # 检查昨日冠军D+1表现')
        print('      python v42_monitor.py --winrate  # 查看滚动30天胜率')
        print('      python v42_monitor.py --recent   # 查看最近10次选股结果')
