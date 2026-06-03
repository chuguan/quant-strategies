"""一次性修复所有日期的VR — 从volume计算"""
import sqlite3, os
DB = os.path.expanduser('~/AppData/Local/hermes/scripts/v13_quant.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
dates = [r[0] for r in c.fetchall()]
print(f'共{len(dates)}个交易日')

total_fixed = 0
for dt in dates:
    # 对每个日期，逐只股票从成交量算VR
    c.execute('SELECT code, volume FROM data_cache WHERE date=? AND volume>0', (dt,))
    stocks = c.fetchall()
    
    fixed = 0
    for code, vol in stocks:
        if not vol or vol <= 0: continue
        # 前5日均量
        c.execute('SELECT volume FROM data_cache WHERE code=? AND date<? AND volume>0 ORDER BY date DESC LIMIT 5', (code, dt))
        vols = [r[0] for r in c.fetchall()]
        if len(vols) < 3: continue
        avg_vol = sum(vols)/len(vols)
        if avg_vol <= 0: continue
        calc_vr = round(vol/avg_vol, 2)
        calc_vr = max(0.01, min(calc_vr, 10.0))
        c.execute('UPDATE data_cache SET vr=? WHERE date=? AND code=?', (calc_vr, dt, code))
        fixed += 1
    
    if fixed > 0:
        conn.commit()
        total_fixed += fixed
        if len(dates) > 50:
            pass  # 静默执行
        print(f'  {dt}: 补{fixed}只', end='\r')

print(f'\n✅ 完成! 共补{total_fixed}条VR记录')

# 验证
c.execute('SELECT date, COUNT(*), ROUND(MIN(vr),2), ROUND(AVG(vr),2), ROUND(MAX(vr),2) FROM data_cache WHERE vr>0 GROUP BY date ORDER BY date')
print('\nVR范围:')
for dt, cnt, mn, avg, mx in c.fetchall():
    print(f'  {dt}: {cnt}只, VR[{mn}~{mx}], 均值{avg}')

conn.close()
