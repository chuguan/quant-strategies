#!/usr/bin/env python3
"""补全05-29数据 + 完整技术指标"""
import sqlite3, os, json, subprocess, time, sys

SCRIPTS = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB = os.path.join(SCRIPTS, 'v13_quant.db')
CACHE = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

# 查缺多少
c.execute('SELECT code, name FROM data_cache WHERE date="2026-05-28"')
codes28 = {r[0]: r[1] for r in c.fetchall()}
c.execute('SELECT code FROM data_cache WHERE date="2026-05-29"')
have = {r[0] for r in c.fetchall()}
missing = [code for code in codes28 if code not in have]
print(f'05-29: 需补{len(missing)}只')

# ① 腾讯API批量拿收盘价
BATCH = 50
prices = {}
for i in range(0, len(missing), BATCH):
    batch = missing[i:i+BATCH]
    sym = ','.join(f'sh{c}' if c.startswith(('6','9')) else f'sz{c}' for c in batch)
    try:
        r = subprocess.run(['curl','-sL','--max-time','8',f'http://qt.gtimg.cn/q={sym}'], capture_output=True, timeout=12)
        for line in r.stdout.decode('gbk',errors='ignore').strip().split(';'):
            if '=' not in line: continue
            parts = line.split('=')[1].strip('"').split('~')
            if len(parts)<40: continue
            code = parts[2]
            close = float(parts[3]) if parts[3] else 0
            pre = float(parts[4]) if parts[4] else 0
            if close > 0:
                prices[code] = {'close': close, 'pre': pre, 'name': parts[1]}
    except: pass
print(f'收盘价: {len(prices)}只')

# ② 从K线缓存算指标 + 写入
fixed = 0
for code in missing:
    p = prices.get(code)
    if not p: continue
    close = p['close']
    pre = p['pre']
    name = p['name']
    pct = round((close-pre)/pre*100, 2) if pre>0 else 0
    
    wr, jv, kv, dv, dif, mg, a5 = 50, 50, 50, 50, 0, 0, 0
    cl_val = 50.0
    
    # 读K线缓存
    pref = 'sh' if code.startswith(('6','9')) else 'sz'
    kf = os.path.join(CACHE, f'{pref}{code}.json')
    if os.path.exists(kf):
        try:
            klines = json.load(open(kf))
            kh = [k['high'] for k in klines if k['date'] <= '2026-05-29']
            kl = [k['low'] for k in klines if k['date'] <= '2026-05-29']
            kc = [k['close'] for k in klines if k['date'] <= '2026-05-29']
            
            if len(kh) >= 14:
                h14 = max(kh[-14:]); l14 = min(kl[-14:])
                wr = round((h14-close)/(h14-l14)*100, 1) if (h14-l14)>0 else 50
            if len(kh) >= 9:
                h9 = max(kh[-9:]); l9 = min(kl[-9:])
                rsv = (close-l9)/(h9-l9)*100 if (h9-l9)>0 else 50
                kv = round(50*2/3 + rsv/3, 1)
                dv = round(50*2/3 + kv/3, 1)
                jv = round(3*kv-2*dv, 1)
            if len(kc) >= 26:
                a12, a26 = 2/13, 2/27
                e12, e26 = kc[-1], kc[-1]
                for cv in reversed(kc[:-1]):
                    e12 = cv*a12 + e12*(1-a12)
                    e26 = cv*a26 + e26*(1-a26)
                dif = round(e12-e26, 3)
                mg = 1 if len(kc)>=2 and dif>0 and kc[-1]>kc[-2] else 0
                a5 = 1 if len(kc)>=6 and close>sum(kc[-6:-1])/5 else 0
            # cl
            hi, lo = kh[-1], kl[-1]
            cl_val = round((close-lo)/(hi-lo)*100, 2) if (hi-lo)>0 else 50
        except: pass
    
    c.execute('''INSERT OR REPLACE INTO data_cache
        (date,code,name,p,cl,vr,n,dif_val,macd_golden,wr_val,j_val,k_val,d_val,
         pos_in_day,above_ma5,kdj_golden,close,volume,original_source,cache_version)
        VALUES(?,?,?,?,?,1.0,0,?,?,?,?,?,?,?,?,0,?,?,?,?)''',
        ('2026-05-29', code, name, round(pct,2), round(cl_val,2),
         round(dif,3), int(mg), round(wr,1), round(jv,1), round(kv,1), round(dv,1),
         round(cl_val,1), int(a5), round(close,2), 0,
         'tencent+kline-cache', '0529-fix-final'))
    fixed += 1
    
    if fixed % 200 == 0:
        conn.commit()
        print(f'  进度: {fixed}/{len(missing)}')

conn.commit()

print(f'\n写入: {fixed}只')

# 最终检查
print('\n=== 最终检查 ===')
for dt in ['2026-05-27','2026-05-28','2026-05-29']:
    cnt = conn.execute('SELECT COUNT(*) FROM data_cache WHERE date=?', (dt,)).fetchone()[0]
    no_wr = conn.execute('SELECT COUNT(*) FROM data_cache WHERE date=? AND wr_val=50', (dt,)).fetchone()[0]
    no_dif = conn.execute('SELECT COUNT(*) FROM data_cache WHERE date=? AND dif_val=0 AND close>0', (dt,)).fetchone()[0]
    print(f'  {dt}: {cnt}只 | WR缺失:{no_wr} | DIF缺失:{no_dif}')
conn.close()
