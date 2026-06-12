#!/usr/bin/env python3
"""
冠军股公告推送 — 每天选股结束后运行
读daily_selection_log → 查巨潮公告 → 分类利好利空 → 推送微信
定时: 交易日 15:00 (选股全部结束后)
"""
import sys, os, json, subprocess, re, sqlite3
from datetime import datetime, timedelta
from pathlib import Path

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/prod')
DB = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
now = datetime.now()
today = now.strftime('%Y-%m-%d')

BULL_KW = ['增持','回购','中标','合同','分红','新高','增长','突破','放量','受益','利好','订单','扭亏','盈喜','产能','投产']
BEAR_KW = ['减持','立案','亏损','下跌','风险','利空','下调','索赔','处罚','监管','降级','预警','ST','*ST','退市','违约','爆雷','调查','违规']

def curl_json(url, data=None):
    cmd = ['curl','-s','--max-time','8','-H','User-Agent: Mozilla/5.0']
    if data:
        cmd += ['-H','Content-Type: application/json','--data-raw', json.dumps(data)]
    r = subprocess.run(cmd, capture_output=True, timeout=12)
    txt = r.stdout.decode('utf-8', errors='replace')
    start = txt.find('{')
    if start < 0: start = txt.find('[')
    if start < 0: return {}
    return json.loads(txt[start:])

def get_today_champions():
    """从数据库读今日各策略冠军"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    strategies = ['V13', 'V42', 'V50', 'CG18']
    champions = []
    
    for ver in strategies:
        c.execute('''SELECT c_code, c_name, c_price, market_type, version
                     FROM daily_selection_log 
                     WHERE date=? AND version=?
                     ORDER BY run_time DESC LIMIT 1''', (today, ver))
        row = c.fetchone()
        if row:
            champions.append({
                'code': row[0], 'name': row[1], 'price': row[2],
                'market': row[3], 'strategy': row[4]
            })
    
    # 也查selection_candidates（二次选股覆盖）
    c.execute('''SELECT DISTINCT code, name, version, market_type
                 FROM selection_candidates 
                 WHERE date=? AND rank=1''', (today,))
    for row in c.fetchall():
        code = row[0]
        if code not in [ch['code'] for ch in champions]:
            champions.append({
                'code': code, 'name': row[1], 'strategy': row[2],
                'market': row[3], 'price': 0
            })
    
    conn.close()
    return champions

def fetch_announcements(codes):
    """从巨潮查这些股票的公告"""
    results = []
    if not codes:
        return results
    
    payload = {"pageNum": 1, "pageSize": 10, "stock": codes,
               "seDate": [(now-timedelta(days=7)).strftime('%Y-%m-%d'), today],
               "isHLtitle": True, "column": "szse_main", "tab": "fulltext",
               "plate": "sz", "searchkey": "", "secid": "", "category": "", "trade": ""}
    
    d = curl_json('https://www.cninfo.com.cn/new/hisAnnouncement/query', data=payload)
    for a in d.get('announcements', []):
        t = a.get('announcementTitle','')
        ts = a.get('announcementTime', 0)
        date = datetime.fromtimestamp(ts/1000).strftime('%m/%d') if isinstance(ts,(int,float)) and ts>0 else ''
        code = str(a.get('secCode','') or '')[-6:]
        name = a.get('secName','')
        
        bs = sum(1 for kw in BULL_KW if kw in t)
        be = sum(1 for kw in BEAR_KW if kw in t)
        
        if bs > be and bs >= 1:
            intens = '⭐⭐⭐' if bs >= 3 else '⭐⭐' if bs >= 2 else '⭐'
            results.append(('bull', code, name, t[:50], date, intens))
        elif be > bs and be >= 1:
            intens = '🔴🔴🔴' if be >= 3 else '🔴🔴' if be >= 2 else '🔴'
            results.append(('bear', code, name, t[:50], date, intens))
    
    return results

def main():
    print(f'=== 冠军股公告推送 {today} ===')
    
    # 1. 读今日冠军
    champs = get_today_champions()
    if not champs:
        print('今日无选股记录')
        return
    print(f'今日选股: {len(champs)}策略')
    for ch in champs:
        print(f'  [{ch["strategy"]}] {ch["name"]}({ch["code"]}) {ch["market"]}')
    
    # 2. 查公告
    codes = list(set(ch['code'] for ch in champs))
    codes_str = ','.join(codes)
    
    # 按策略分组查
    results = []
    for i in range(0, len(codes), 7):
        batch = codes[i:i+7]
        results.extend(fetch_announcements(','.join(batch)))
    
    print(f'公告结果: {len(results)}条')
    
    # 3. 构建消息
    bull_items = [r for r in results if r[0] == 'bull']
    bear_items = [r for r in results if r[0] == 'bear']
    
    msg = f'📋 持仓公告速递 | {today}\n'
    msg += f'今日冠军: {" ".join(ch["name"] for ch in champs[:4])}\n\n'
    
    # 按策略分组显示
    for ch in champs:
        has_ann = False
        for typ, code, name, title, date, intens in results:
            if code == ch['code']:
                if not has_ann:
                    msg += f'[{ch["strategy"]}] {ch["name"]}({code}):\n'
                    has_ann = True
                mark = '🟢' if typ == 'bull' else '🔴'
                msg += f'  {mark} {intens} {title}\n'
        if not has_ann:
            msg += f'[{ch["strategy"]}] {ch["name"]}: 近7日无重大公告\n'
        msg += '\n'
    
    if bear_items:
        msg += '⚠️ 利空预警:\n'
        for typ, code, name, title, date, intens in bear_items[:3]:
            msg += f'  🔴 {name} {title}\n'
    
    print(msg)
    print('=== 推送完成 ===')

if __name__ == '__main__':
    main()
