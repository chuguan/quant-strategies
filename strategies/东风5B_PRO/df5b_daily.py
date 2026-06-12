#!/usr/bin/env python3
"""
东风5B — 尾盘14:50每日选股（生产版）
四阶梯：T1-C≥3 → T2-C=2+20日涨幅过滤 → T3-二板N字+扣分 → T4-单阳不破严格+MA20+CL
有信号就推冠军，无信号逐层说明原因
"""
import urllib.request, json, sqlite3, os, sys, time, subprocess
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
PROD_DIR = os.path.normpath(os.path.join(DIR, '..', '..'))
DB = os.path.join(PROD_DIR, 'data', 'df04_prices.db')
POOL = os.path.join(PROD_DIR, 'data', '活跃股票池_3043.json')
SCRIPTS_DIR = PROD_DIR
SEND_MAIL = os.path.join(SCRIPTS_DIR, 'lib', 'send_email.py')

t0 = time.time()
print(f'🚀 东风5B 每日选股 {datetime.now().strftime("%Y-%m-%d %H:%M")}')

# ===== 1. 加载股票池 =====
with open(POOL, encoding='utf-8') as f:
    pool = json.load(f)
codes = pool['codes']
sinfo = pool.get('info', {})

# ===== 2. 加载历史K线 =====
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT date FROM daily_prices WHERE date>='2026-01-01' GROUP BY date ORDER BY date")
dates = [r[0] for r in cur.fetchall()]
dmap = {d: i for i, d in enumerate(dates)}

market = {}
for d in dates:
    cur.execute('SELECT code,open,close,high,low,vol,pct FROM daily_prices WHERE date=?', (d,))
    md = {r[0]: r[1:] for r in cur.fetchall()}
    market[d] = md
conn.close()

def g(code, date):
    dd = market.get(date)
    return dd.get(code) if dd else None

def get_kline(code, dl):
    res = []
    for d in dl:
        r = g(code, d)
        if not r: return None
        res.append(r)
    return res

def calc_ma5(code, di):
    cls = []
    for i in range(di, di-5, -1):
        if i < 0: break
        r = g(code, dates[i])
        if r: cls.append(r[1])
    if len(cls) < 5: return None
    return sum(cls[:5]) / 5

def calc_ma(code):
    cur2 = sqlite3.connect(DB)
    c2 = cur2.cursor()
    c2.execute('SELECT close FROM daily_prices WHERE code=? ORDER BY date DESC LIMIT 25', (code,))
    cl = [r[0] for r in c2.fetchall()][::-1]
    cur2.close()
    if len(cl) < 20: return None, None, None
    return sum(cl[-5:])/5, sum(cl[-10:])/10, sum(cl[-20:])/20

def calc_cl(code, di):
    if di < 20: return None
    closes = []
    for i in range(di-19, di+1):
        r = g(code, dates[i])
        if r: closes.append(r[1])
    if len(closes) < 20: return None
    curr, mn, mx = closes[-1], min(closes), max(closes)
    return 50 if mx == mn else round((curr-mn)/(mx-mn)*100)

# ===== 3. 腾讯API实时行情 =====
def fetch_tx():
    result = {}
    for i in range(0, len(codes), 80):
        batch = codes[i:i+80]
        tx = [('sh' + c if c.startswith(('6', '9')) else 'sz' + c) for c in batch]
        url = 'http://qt.gtimg.cn/q=' + ','.join(tx)
        try:
            req = urllib.request.urlopen(url, timeout=15)
            text = req.read().decode('gbk')
            for line in text.strip().split(';'):
                if '=\"' not in line: continue
                _, val = line.split('=\"', 1)
                val = val.rstrip('\"').rstrip(';')
                p = val.split('~')
                if len(p) < 35: continue
                result[p[2]] = {
                    'name': p[1], 'price': float(p[3] or 0),
                    'prev': float(p[4] or 0), 'open': float(p[5] or 0),
                    'high': float(p[33] or 0), 'low': float(p[34] or 0),
                    'vol': float(p[6] or 0) * 100, 'pct': float(p[32] or 0),
                }
        except: pass
    return result

# ===== 4. 选股 =====
def select_today(tx_data):
    """4阶梯选股，返回(冠军dict or None, 原因说明)"""
    today = datetime.now().strftime('%Y-%m-%d')
    di = len(dates)  # 今天不在dates里，用len作为索引

    reasons = []

    # 先把今天的数据存到market临时位置
    for code, td in tx_data.items():
        if 'ST' in td['name'] or '退' in td['name']: continue
        if td['vol'] <= 0: continue
        if today not in market:
            market[today] = {}
        market[today][code] = (td['open'], td['price'], td['high'], td['low'], td['vol'], td['pct'])

    codes_today = [c for c in codes if c in tx_data and 'ST' not in tx_data[c]['name'] and tx_data[c]['vol'] > 0]

    found = None
    tier = ''

    # ========== T1: C形态评分≥3 ==========
    reasons.append('【T1-C形态】')
    if di >= 3:
        c_count = 0
        for code in codes_today:
            d0, d1, d2 = dates[di-3], dates[di-2], dates[di-1]
            k3 = get_kline(code, [d0, d1, d2])
            if not k3: continue
            t = market.get(today, {}).get(code)
            if not t: continue
            d0k, d1k, d2k = k3
            o3, c3, h3, l3, v3, p3 = t
            d2c = d2k[1]

            if not (d1k[1] > d1k[0] and d2k[1] > d2k[0] and c3 > o3): continue
            if not (d1k[1] < d2k[1] < c3 and d1k[3] < d2k[3] < l3): continue
            r1, r2 = d1k[5], d2k[5]
            r3 = (c3 / d2c - 1) * 100
            if ((1+r1/100)*(1+r2/100)*(1+r3/100)-1)*100 < 10: continue
            if not (6 <= r1 <= 9.8) or not (9.3 <= r2 <= 10.7) or not (2 <= r3 <= 8): continue
            vr = v3 / max(d2k[4], 1)
            sc = (1 if l3 >= d2c*0.99 else 0) + (1 if c3 >= (h3+l3)/2 else 0) + \
                 (1 if (h3-l3)/d2c*100 < 7 else 0) + (1 if 1.05 <= vr <= 2.0 else 0)
            if sc >= 3:
                c_count += 1
                if not found or sc > found['s']:
                    found = {'code': code, 's': sc, 'c3': c3, 'name': sinfo.get(code, {}).get('name', code),
                             'price': tx_data[code]['price'], 'pct': tx_data[code]['pct']}
                    tier = 'T1-C≥3'

        reasons.append(f'  扫描{c_count}只C形态信号')
        if found:
            reasons.append(f'  ✅ 冠军: {found["name"]}({found["code"]}) 评分{found["s"]}')
            found['tier'] = tier
            return found, '\n'.join(reasons)

    # ========== T2: C形态评分=2 + 20日涨幅过滤 ==========
    reasons.append('\n【T2-C形态=2 + 20日涨幅过滤】')
    if not found and di >= 3:
        c2_count = 0
        for code in codes_today:
            d0, d1, d2 = dates[di-3], dates[di-2], dates[di-1]
            k3 = get_kline(code, [d0, d1, d2])
            if not k3: continue
            t = market.get(today, {}).get(code)
            if not t: continue
            d0k, d1k, d2k = k3
            o3, c3, h3, l3, v3, p3 = t
            d2c = d2k[1]

            if not (d1k[1] > d1k[0] and d2k[1] > d2k[0] and c3 > o3): continue
            if not (d1k[1] < d2k[1] < c3 and d1k[3] < d2k[3] < l3): continue
            r1, r2 = d1k[5], d2k[5]
            r3 = (c3 / d2c - 1) * 100
            if ((1+r1/100)*(1+r2/100)*(1+r3/100)-1)*100 < 10: continue
            if not (6 <= r1 <= 9.8) or not (9.3 <= r2 <= 10.7) or not (2 <= r3 <= 8): continue
            vr = v3 / max(d2k[4], 1)
            sc = (1 if l3 >= d2c*0.99 else 0) + (1 if c3 >= (h3+l3)/2 else 0) + \
                 (1 if (h3-l3)/d2c*100 < 7 else 0) + (1 if 1.05 <= vr <= 2.0 else 0)
            if sc == 2:
                # 20日涨幅过滤
                cur2 = sqlite3.connect(DB)
                c2 = cur2.cursor()
                c2.execute('SELECT close FROM daily_prices WHERE code=? AND date<=? ORDER BY date DESC LIMIT 20', (code, dates[-1]))
                cls20 = [r[0] for r in c2.fetchall()][::-1]
                cur2.close()
                if len(cls20) >= 20 and (cls20[-1]/cls20[0]-1)*100 > 40:
                    continue  # 20日涨幅>40%过滤
                c2_count += 1
                if not found or sc > found['s']:
                    found = {'code': code, 's': sc, 'c3': c3, 'name': sinfo.get(code, {}).get('name', code),
                             'price': tx_data[code]['price'], 'pct': tx_data[code]['pct']}
                    tier = 'T2-C=2'

        reasons.append(f'  扫描{c2_count}只C=2信号(20日涨幅过滤后)')
        if found:
            reasons.append(f'  ✅ 冠军: {found["name"]}({found["code"]}) 评分{found["s"]}')
            found['tier'] = tier
            return found, '\n'.join(reasons)

    # ========== T3: 二板N字 + 扣分 ==========
    reasons.append('\n【T3-二板N字 + 涨停扣分】')
    if not found:
        nb_count = 0
        for code in codes_today:
            t = market.get(today, {}).get(code)
            if not t or t[5] < 5.5 or t[5] >= 8: continue  # 涨幅5.5~8%
            lb = dates[max(0, di-8):di]
            cls = get_kline(code, lb)
            if not cls or len(cls) != len(lb): continue
            # 找前8天内的2个涨停
            zts = []
            for i in range(len(cls)-2, -1, -1):
                if cls[i][5] >= 9.5:
                    zts.append(i)
                    if len(zts) >= 2: break
            if len(zts) < 2: continue
            z1, z2 = zts[1], zts[0]
            g_days = z2 - z1
            if g_days < 2 or g_days > 7: continue
            bw = cls[z1+1:z2]
            z1v = cls[z1][4]
            mv = min(c[4] for c in bw) if bw else 999999
            if mv > z1v * 1.5: continue
            z1l = cls[z1][3]
            if any(c[3] < z1l * 0.95 for c in bw): continue
            if cls[z2][4] > z1v * 1.5: continue
            if t[1] < cls[z2][1]: continue
            vr = t[4] / max(cls[z2][4], 1)
            if vr < 0.8 or vr > 2.0: continue
            ma5, ma10, ma20 = calc_ma(code)
            if not (ma5 and ma10 and ma20 and ma5 > ma10 > ma20): continue
            # 20日涨幅过滤
            cur2 = sqlite3.connect(DB)
            c2 = cur2.cursor()
            c2.execute('SELECT close FROM daily_prices WHERE code=? AND date<=? ORDER BY date DESC LIMIT 20', (code, dates[-1]))
            hist = [r[0] for r in c2.fetchall()][::-1]
            cur2.close()
            if len(hist) >= 20 and (hist[-1]/hist[0]-1)*100 > 40: continue

            sc = 5 + (1 if t[5] >= 5 else 0) + (2 if g_days == 3 else (1 if g_days in [2, 4] else 0)) + (1 if vr >= 1.2 else 0)

            # 昨日涨停扣分
            yest = g(code, dates[di-1]) if di > 0 else None
            if yest and yest[5] >= 8: sc -= 3

            # 连阳>5天扣分
            cons_up = 0
            for i in range(1, 8):
                rr = g(code, dates[di-i]) if di-i >= 0 else None
                if not rr or rr[5] <= 0: break
                cons_up += 1
            if cons_up > 5: sc -= 3

            if bw:
                z1_top = max(cls[z1][0], cls[z1][1])
                z1_bot = min(cls[z1][0], cls[z1][1])
                zb = z1_top - z1_bot
                if zb > 0:
                    mid = (max(c[2] for c in bw) + min(c[3] for c in bw)) / 2
                    p = (mid - z1_bot) / zb
                    sc += 2 if p > 0.67 else (1 if p > 0.33 else 0)

            if sc >= 8:
                nb_count += 1
                if not found or sc > found['s']:
                    found = {'code': code, 's': sc, 'c3': t[1], 'name': sinfo.get(code, {}).get('name', code),
                             'price': tx_data[code]['price'], 'pct': tx_data[code]['pct']}
                    tier = 'T3-2B'

        reasons.append(f'  扫描{nb_count}只二板N字信号(涨停扣分+连阳扣分后)')
        if found:
            reasons.append(f'  ✅ 冠军: {found["name"]}({found["code"]}) 评分{found["s"]}')
            found['tier'] = tier
            return found, '\n'.join(reasons)

    # ========== T4: 单阳不破A级严格版 ==========
    reasons.append('\n【T4-单阳不破A级(MA20+CL)】')
    if not found:
        sp_count = 0
        for code in codes_today:
            t = market.get(today, {}).get(code)
            if not t or t[5] < 2 or t[5] >= 8: continue

            # 找过去15天的大阳线
            lookback = []
            for bdi in range(di-15, di):
                if bdi < 0: continue
                r = g(code, dates[bdi])
                if r: lookback.append(r)
            if len(lookback) < 5: continue

            yang_idx = None
            for i in range(len(lookback)-2, -1, -1):
                if lookback[i][1] > lookback[i][0] and lookback[i][5] >= 5:
                    yang_idx = i
                    break
            if yang_idx is None or len(lookback)-yang_idx-1 > 12: continue

            yang = lookback[yang_idx]

            # 大阳线质量A级
            body_pct = abs(yang[1]-yang[0])/yang[0]*100
            shadow = (yang[2]-yang[1])/max(yang[2]-yang[3], 0.01)
            if not (body_pct >= 8 and shadow <= 0.02): continue

            # 不破大阳底部
            if any(lookback[i][3] < yang[3]*0.97 for i in range(yang_idx+1, len(lookback)-1)):
                continue
            # 今日收盘在大阳之上
            if t[1] < yang[1]: continue

            vol_ratio = t[4] / max(yang[4], 1)
            if vol_ratio < 1.0: continue

            ma5, ma10, ma20 = calc_ma(code)
            if not (ma5 and ma10 and ma20 and ma5 > ma10 > ma20): continue  # MA20向下过滤

            # 位置在阳线上部
            yang_body = abs(yang[1]-yang[0]) + 0.001
            pos = ((t[2]+t[3])/2 - min(yang[0], yang[1])) / yang_body
            if pos < 0.67: continue

            cl = calc_cl(code, di-1)
            if cl is None or cl > 70: continue  # CL不能在高位

            sc = 5 + 3 + (2 if pos > 0.8 else 1) + \
                 (2 if vol_ratio >= 1.5 else (1 if vol_ratio >= 1.2 else 0)) + \
                 (2 if cl and cl < 40 else (1 if cl and cl < 60 else 0))

            if sc >= 8:
                sp_count += 1
                if not found or sc > found['s']:
                    found = {'code': code, 's': sc, 'c3': t[1], 'name': sinfo.get(code, {}).get('name', code),
                             'price': tx_data[code]['price'], 'pct': tx_data[code]['pct']}
                    tier = 'T4-SP'

        reasons.append(f'  扫描{sp_count}只单阳不破A级信号(MA20+CL过滤后)')
        if found:
            reasons.append(f'  ✅ 冠军: {found["name"]}({found["code"]}) 评分{found["s"]}')
            found['tier'] = tier
            return found, '\n'.join(reasons)

    return None, '\n'.join(reasons + ['\n❌ 今日无信号，4个梯队全部扫描完毕'])

# ===== 5. 主流程 =====
def main():
    print(f'数据加载: {time.time()-t0:.1f}s')

    tx = fetch_tx()
    now = datetime.now()
    is_trading = now.weekday() < 5 and (9.5 <= now.hour + now.minute/60 <= 15.0)
    print(f'📡 API: {len(tx)}只 | {"交易中" if is_trading else "非交易时间"}')

    if not is_trading:
        print('❌ 非交易时间，跳过选股')
        return

    champion, reason = select_today(tx)
    
    # ===== 东风5B无信号时，涨停回马枪兜底 =====
    source = '东风5B'
    if not champion:
        print(f'⚠️ 东风5B无信号，启动涨停回马枪兜底...')
        try:
            sys.path.insert(0, DIR)
            from zt_ambush_daily import run as run_ambush
            ambush_champ, ambush_reason = run_ambush(tx_data=tx)
            if ambush_champ:
                champion = ambush_champ
                champion['s'] = '回马枪'
                champion['tier'] = 'AMBUSH'
                reason = ambush_reason
                source = '涨停回马枪(兜底)'
                print(f'✅ 回马枪兜底成功！')
            else:
                print(f'❌ 回马枪也无信号')
        except Exception as e:
            print(f'⚠️ 回马枪执行失败: {e}')
    
    total_time = time.time() - t0

    print(f'\n{"="*50}')
    print(f'东风5B PRO 选股结果 | {datetime.now().strftime("%H:%M:%S")}')
    print(f'{"="*50}')

    if champion:
        name = champion['name']
        code = champion['code']
        price = champion['price']
        pct = champion['pct']
        tier_name = champion['tier']
        score = champion.get('s', '—')
        print(f'\n🏆 {name}({code})')
        print(f'   层级: {tier_name} | 评分: {score}')
        print(f'   买入≈{price:.2f} | 当日涨幅: +{pct:.1f}%')
        print(f'   耗时: {total_time:.1f}s')

        # ===== 写入共享DB（供综合榜读取）=====
        try:
            from datetime import datetime as _dt
            now_str = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
            today = _dt.now().strftime('%Y-%m-%d')
            _db_path = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
            _conn = sqlite3.connect(_db_path, timeout=10)
            _conn.execute('''
                INSERT INTO selection_candidates 
                (version, date, run_time, market_type, used_level, pool_size, rank, code, name, price, pct, score)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ''', ('东风5B_PRO', today, now_str, '', tier_name[:2] if tier_name.startswith('T') else tier_name, 0, 1, code, name, price, pct, score if isinstance(score, (int,float)) else 0))
            _conn.commit()
            _conn.close()
            print(f'📝 已写入共享DB(东风5B_PRO)', flush=True)
        except Exception as e:
            print(f'⚠️ 写入共享DB失败: {e}', flush=True)

        # 发邮件到A组
        subject = f'东风5B PRO 今日选股 {datetime.now().strftime("%Y-%m-%d")} - {name}({code})'
        html = f'''<div style="font-family:微软雅黑;padding:20px">
<h2 style="color:#b8860b">🏆 东风5B PRO 尾盘选股</h2>
<p style="color:#666">{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
<div style="background:#fefce8;border-left:4px solid #b8860b;padding:15px;margin:10px 0">
<h3>🥇 {name}({code})</h3>
<table style="font-size:14px">
<tr><td style="padding:4px 10px;color:#888">层级</td><td><b>{tier_name}</b></td></tr>
<tr><td style="padding:4px 10px;color:#888">评分</td><td><b>{score}</b></td></tr>
<tr><td style="padding:4px 10px;color:#888">买入价</td><td><b style="color:#dc2626">¥{price:.2f}</b></td></tr>
<tr><td style="padding:4px 10px;color:#888">当日涨幅</td><td><b style="color:#dc2626">+{pct:.1f}%</b></td></tr>
</table>
</div>
<div style="background:#f9fafb;padding:10px;margin:10px 0;font-size:12px;color:#6b7280">
<pre>{reason}</pre>
</div>
<p style="color:#999;font-size:11px">东风5B PRO | 27笔100%胜率 | 东风5B主选+回马枪兜底</p>
</div>'''
    else:
        print(f'\n❌ 今日无信号')
        print(reason)
        print(f'耗时: {total_time:.1f}s')

        subject = f'东风5B PRO 今日选股 {datetime.now().strftime("%Y-%m-%d")} - 无信号'
        html = f'''<div style="font-family:微软雅黑;padding:20px">
<h2 style="color:#b8860b">🏆 东风5B PRO 尾盘选股</h2>
<p style="color:#666">{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
<div style="background:#fef2f2;border-left:4px solid #dc2626;padding:15px;margin:10px 0">
<h3 style="color:#dc2626">❌ 今日无信号</h3>
<div style="background:#fff;padding:10px;font-size:12px;color:#6b7280;white-space:pre-wrap">{reason}</div>
</div>
<p style="color:#999;font-size:11px">东风5B PRO | 27笔100%胜率 | 东风5B主选+回马枪兜底</p>
</div>'''

    # 发邮件
    try:
        sys.path.insert(0, os.path.join(SCRIPTS_DIR, 'lib')); sys.path.insert(0, SCRIPTS_DIR)
        from send_email import send_email
        send_email(subject=subject, body=html, html=True)
        print(f'📧 邮件已发送(A组3人)')
    except Exception as e:
        print(f'⚠️ 邮件失败: {e}')
        # 备用：subprocess
        try:
            html_bytes = html.encode('utf-8')
            r = subprocess.run([sys.executable, SEND_MAIL, subject, html, '--html', '--to', '1254628314@qq.com,314913203@qq.com,2603672569@qq.com,2318162429@qq.com'],
                               timeout=30, capture_output=True)
            print(f'📧 subprocess邮件: {r.stdout.decode().strip()}')
        except Exception as e2:
            print(f'⚠️ 备用邮件也失败: {e2}')

if __name__ == '__main__':
    main()
