#!/usr/bin/env python3
"""完整补全SQLite数据"""
import pickle, sqlite3, os, json, sys

SCRIPTS = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB = os.path.join(SCRIPTS, 'v13_quant.db')

print('加载原版数据...')
pkl = pickle.load(open(os.path.join(SCRIPTS, 'release/V13/big_cache_full.pkl'), 'rb'))
pkl_data = pkl['data']
pkl_names = pkl.get('names', {})
feat_pkl = pickle.load(open(os.path.join(SCRIPTS, 'release/V13/features_30d.pkl'), 'rb'))

print('加载股票池...')
with open(os.path.join(SCRIPTS, '活跃股票池_3043.json'), 'r') as f:
    pool = json.load(f)
all_codes = pool['codes']
all_codes = [c for c in all_codes if c.startswith(('600','601','603','605','000','001','002'))]
ref = len(all_codes)
print(f'参考池: {ref}只')

conn = sqlite3.connect(DB)
c = conn.cursor()

# 1. data_cache补缺 - 逐日遍历
print('\n=== 阶段1: data_cache补缺 ===')
c.execute('SELECT DISTINCT date FROM data_cache ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]
inserted = 0
fixed_dates = 0

for dt in all_dates:
    c.execute('SELECT code FROM data_cache WHERE date=?', (dt,))
    existing = {r[0] for r in c.fetchall()}
    missing = [code for code in all_codes if code not in existing]
    if not missing:
        continue
    
    # 从big_cache找
    pkl_map = {s.get('code'): s for s in pkl_data.get(dt, [])}
    batch = 0
    for code in missing:
        s = pkl_map.get(code)
        if not s:
            continue
        nm = s.get('name','') or pkl_names.get(code,'')
        c.execute('''INSERT OR IGNORE INTO data_cache(date,code,name,p,cl,vr,n,
            dif_val,macd_golden,wr_val,j_val,k_val,d_val,
            pos_in_day,above_ma5,kdj_golden,
            close,volume,original_source,cache_version)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (dt, code, nm,
             round(s.get('p',0) or 0,2), round(s.get('cl',50),2),
             round(s.get('vol_ratio',1) or s.get('vr',1) or 1,2),
             round(s.get('n',0) or 0,2),
             round(s.get('dif_val',0) or s.get('dif',0),3),
             int(s.get('macd_golden',0) or s.get('mg',0) or 0),
             round(s.get('wr_val',0) or s.get('wrv',50),1),
             round(s.get('j_val',0) or s.get('jv',50),1),
             round(s.get('k_val',0) or s.get('kv',50),1),
             round(s.get('d_val',0) or s.get('dv',50),1),
             round(s.get('pos_in_day',50),1),
             int(s.get('above_ma5',0) or 0),
             int(s.get('kdj_golden',0) or s.get('kdj_g',0) or 0),
             round(s.get('close',0) or 0,2),
             round(s.get('volume',0) or s.get('vol',0) or 0,0),
             'big_cache','big_cache_full'))
        batch += 1
        inserted += 1
    
    conn.commit()
    fixed_dates += 1
    if fixed_dates <= 5 or dt >= '2026-05-20':
        print(f'  {dt}: 补了{batch}只')

print(f'data_cache补全: 新增{inserted}条, 涉及{fixed_dates}天')

# 2. features_cache补缺
print('\n=== 阶段2: features_cache补缺 ===')
c.execute('SELECT DISTINCT date FROM data_cache WHERE date > "2026-05-22" ORDER BY date')
post_dates = [r[0] for r in c.fetchall()]

# 先补05-22及之前的数据（从原版features_30d.pkl）
c.execute('SELECT DISTINCT date FROM data_cache WHERE date <= "2026-05-22"')
for dr in c.fetchall():
    dt = dr[0]
    c.execute('SELECT code FROM data_cache WHERE date=?', (dt,))
    codes = [r[0] for r in c.fetchall()]
    for code in codes:
        feats = feat_pkl.get((code, dt), {})
        if not feats:
            continue
        c.execute('''INSERT OR IGNORE INTO features_cache
            (date,code,d1,d2,d3,d4,d5,slope5,t4_shadow,cons_up,peak_decay,computed_from,cache_version)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (dt, code,
             feats.get('d1',0), feats.get('d2',0), feats.get('d3',0),
             0, 0, feats.get('slope5',0),
             feats.get('t4_shadow',0), feats.get('cons_up',0), feats.get('peak_decay',0),
             'features_30d.pkl', dt))
    conn.commit()

print(f'原版特征已补 (到2026-05-22)')

# 05-22之后：从data_cache计算
feat_ins = 0
for dt in post_dates:
    c.execute('SELECT code FROM data_cache WHERE date=?', (dt,))
    codes = [r[0] for r in c.fetchall()]
    
    for code in codes:
        # 前7天p值
        c.execute('''SELECT p FROM data_cache WHERE date IN (
            SELECT DISTINCT date FROM data_cache 
            WHERE date <= ? ORDER BY date DESC LIMIT 8
        ) AND code=? ORDER BY date DESC''', (dt, code))
        rows = c.fetchall()
        gains = [(r[0] or 0) for r in rows]
        if gains and len(gains) > 1:
            # 去掉当天
            gains = gains[1:]  # 剩下的就是前N天
        gains = gains[:7]
        gains.reverse()
        
        d1 = gains[-1] if len(gains) >= 1 else 0
        d2 = gains[-2] if len(gains) >= 2 else 0
        d3 = gains[-3] if len(gains) >= 3 else 0
        d4 = gains[-4] if len(gains) >= 4 else 0
        d5 = gains[-5] if len(gains) >= 5 else 0
        s5 = round((sum(gains[-5:]) - gains[-1]) / 5, 2) if len(gains) >= 5 else 0
        cu = sum(1 for g in gains[-5:] if g > 0)
        pd_val = round(max(0, max(gains[-5:-2]) - (gains[-1]+gains[-2])), 1) if len(gains) >= 5 else 0
        
        c.execute('''INSERT OR IGNORE INTO features_cache
            (date,code,d1,d2,d3,d4,d5,slope5,t4_shadow,cons_up,peak_decay,computed_from,cache_version)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (dt, code, round(d1,2), round(d2,2), round(d3,2),
             round(d4,2), round(d5,2), round(s5,2),
             0, cu, round(pd_val,1),
             'computed', 'full-fix'))
        feat_ins += 1
    conn.commit()
    print(f'  {dt}: 特征{len(codes)}只')

print(f'features_cache补全: 新增约{feat_ins}条')

# 3. 最终检查
print('\n=== 最终检查 ===')
for dt in ['2026-05-25','2026-05-26','2026-05-27','2026-05-28']:
    dc = conn.execute('SELECT COUNT(*) FROM data_cache WHERE date=?', (dt,)).fetchone()[0]
    fc = conn.execute('SELECT COUNT(*) FROM features_cache WHERE date=?', (dt,)).fetchone()[0]
    pct = round(dc/ref*100, 1)
    flag = 'OK' if dc >= ref * 0.98 else 'LOW'
    print(f'  {dt}: data={dc}/{ref}({pct}%) [{flag}] | feature={fc}')

# 全库检查
print('\n=== 全库完整性 ===')
c.execute('SELECT date, COUNT(DISTINCT code) FROM data_cache GROUP BY date ORDER BY date')
bad = 0
total_days = 0
for dt, cnt in c.fetchall():
    total_days += 1
    if cnt < ref * 0.95 and dt >= '2026-04-01':
        bad += 1
        print(f'  LOW: {dt}: {cnt}只')
print(f'总计: {total_days}天, 近期不完整: {bad}天')

conn.close()
print('\nDone!')
