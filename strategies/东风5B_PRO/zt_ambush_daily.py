#!/usr/bin/env python3
"""
涨停回马枪 — 尾盘14:50每日选股（兜底策略）
条件：涨停量比≥3.0 + 缩量≤0.8 + 盘中跌破涨停价 + 低损>-3% + 超跌<2
无未来函数，用最低价判断"跌"
"""
import urllib.request, json, sqlite3, os, sys, time
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(DIR, '..', '东风5A', 'df04_prices.db')
POOL = os.path.join(DIR, '..', '..', '活跃股票池_3043.json')
SCRIPTS_DIR = os.path.normpath(os.path.join(DIR, '..', '..'))

def run(tx_data=None):
    """运行涨停回马枪选股，返回(冠军dict或None, 原因文字)"""
    t0 = time.time()
    
    # 加载股票池
    with open(POOL, encoding='utf-8') as f:
        pool = json.load(f)
    codes = pool['codes']
    sinfo = pool.get('info', {})
    
    # 加载历史K线
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT date FROM daily_prices WHERE date>='2026-01-01' GROUP BY date ORDER BY date")
    dates = [r[0] for r in cur.fetchall()]
    dmap = {d: i for i, d in enumerate(dates)}
    
    market = {}
    for d in dates:
        cur.execute('SELECT code,open,close,high,low,vol FROM daily_prices WHERE date=?', (d,))
        for r in cur.fetchall():
            market.setdefault(r[0], {})[d] = {'o':r[1],'c':r[2],'h':r[3],'l':r[4],'v':r[5]}
    conn.close()
    
    def g(code, date):
        return market.get(code, {}).get(date)
    
    def get_ma(code, date, n):
        di = dmap.get(date)
        if di is None or di < n-1: return None
        cls = [g(code, dates[i])['c'] for i in range(di-n+1, di+1) if g(code, dates[i])]
        return sum(cls)/len(cls) if len(cls) >= n else None
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # 如果没传实时数据，去拿
    if tx_data is None:
        tx_data = fetch_tx()
    
    reasons = []
    sp_count = 0
    found = None
    
    for code in codes:
        r1 = g(code, today_str)
        if not r1: continue
        
        # 拿到历史前一日和涨停日数据
        di = dmap.get(today_str)
        if di is None or di < 2: continue
        
        # 涨停日 = 昨日（T-1）
        yang_date = dates[di-1]
        yc_data = g(code, yang_date)
        if not yc_data: continue
        
        yc = yc_data['c']
        yv = yc_data['v']
        yh = yc_data['h']
        yo = yc_data['o']
        
        # 昨日前一日（T-2）
        prev_yang = g(code, dates[di-2])
        if not prev_yang: continue
        
        # === 条件1：昨日是完美涨停 ===
        pct = round((yc/prev_yang['c']-1)*100, 1)
        if pct < 9.5: continue
        
        vol_r = yv / max(prev_yang['v'], 1)
        if vol_r < 3.0: continue  # 量比≥3.0
        
        if yh/yc > 1.05: continue  # 上影<5%
        if yc_data['l']>0 and yo/yc_data['l'] > 1.05: continue  # 下影<5%
        
        # 20日涨幅
        c20_data = g(code, dates[max(0, di-22)])
        if c20_data and (yc/c20_data['c']-1)*100 >= 50: continue
        
        # === 条件2：超跌反弹排除 ===
        crash_days = 0
        for off in range(-5, 0):
            pr = g(code, dates[di+off-2])
            cr = g(code, dates[di+off-1])
            if pr and cr and (cr['c']/pr['c']-1)*100 < -3:
                crash_days += 1
        if crash_days >= 2: continue
        
        # === 条件3：今日买入条件 ===
        # 盘中最低跌破涨停价（无未来函数）
        if r1['l'] >= yc: continue
        
        low_pct = (r1['l']/yc-1)*100
        if low_pct < -3.0: continue  # 低损>-3%
        
        vr1 = r1['v'] / yv if yv else 1
        if vr1 > 0.8: continue  # 缩量≤0.8
        
        # MA30存在
        m30 = get_ma(code, today_str, 30)
        if m30 is None or m30 == 0: continue
        
        sp_count += 1
        
        # 当前实时价格
        price = r1['c']
        today_pct = round((r1['c']/yc-1)*100, 1)
        
        candidate = {
            'name': sinfo.get(code, {}).get('name', code),
            'code': code,
            'price': price,
            'pct': today_pct,
            'vol_r': round(vol_r, 1),
            'vr1': round(vr1, 2),
            'low_pct': low_pct,
            'yang_date': yang_date,
        }
        
        # 取评分最高的（这里按量比排序即可，量比越高信号越强）
        if not found or vol_r > found.get('vol_r', 0):
            found = candidate
    
    reason = f'涨停回马枪 | 扫描{sp_count}只涨停候选'
    if found:
        reason += f'\n✅ 冠军: {found["name"]}({found["code"]}) 量比{found["vol_r"]} 缩量{found["vr1"]}'
        reason += f'\n   涨停日{found["yang_date"]} → 今日跌{found["low_pct"]:.1f}%'
    else:
        if sp_count == 0:
            reason += '\n❌ 今日无涨停符合基础条件'
        else:
            reason += '\n❌ 今日无信号（候选均未通过买入条件）'
    
    print(f'回马枪扫描: {sp_count}只  耗时: {time.time()-t0:.1f}s')
    return found, reason


def fetch_tx():
    """腾讯API实时行情"""
    import urllib.request
    url = 'https://qt.gtimg.cn/q=sh600000,sz000001,s_sh600000,s_sz000001'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.read().decode('gbk')
    except:
        return ''


if __name__ == '__main__':
    champ, reason = run()
    if champ:
        print(f'\n🏆 {champ["name"]}({champ["code"]})')
        print(f'   买入≈{champ["price"]:.2f}  今日跌{champ["pct"]:+.1f}%')
    else:
        print(f'\n❌ 无信号')
    print(reason)
