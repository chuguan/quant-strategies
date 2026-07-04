#!/usr/bin/env python3
"""
每日14:55 择优V4推送（CL≥20 + VR∈[0.8,2] 回测95.2%）
含：买入价、买入涨幅、今日最低跌
"""
import sqlite3, os, sys, json
import numpy as np
import xgboost as xgb
from datetime import datetime, date
from collections import defaultdict

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
MODEL_PATH = os.path.join(SCRIPTS_DIR, 'meta_ranker_model.json')
SNAPSHOT_PATH = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/unified_snapshot.json')

model = xgb.XGBClassifier()
model.load_model(MODEL_PATH)

conn = sqlite3.connect(DB_PATH, timeout=10)
conn.row_factory = sqlite3.Row
c = conn.cursor()

today = date.today().strftime('%Y-%m-%d')
if len(sys.argv) > 1:
    today = sys.argv[1]


# 读今日实时快照（取最低价）
snap_low = {}
if os.path.exists(SNAPSHOT_PATH):
    try:
        with open(SNAPSHOT_PATH, 'r', encoding='utf-8') as f:
            snap = json.load(f)
        ss = snap.get('stocks', {})
        for code, data in ss.items():
            raw = data.get('raw', [])
            if len(raw) >= 35:
                # raw[33]=最高价 raw[34]=最低价
                low = float(raw[34]) if raw[34] else 0
                if low > 0:
                    snap_low[code] = low
    except:
        pass

c.execute('''SELECT sc.*, dr.win_2_5 FROM selection_candidates sc
             LEFT JOIN daily_records dr ON sc.date=dr.date AND sc.code=dr.code
             WHERE sc.date=? AND sc.run_time IS NOT NULL
               AND sc.run_time >= ? || ' 14:00' AND sc.run_time <= ? || ' 15:00'
               AND sc.version != '东风31AG' ''', (today, today, today))
rows = c.fetchall()

# 14-15窗口不足30条时放宽至全天
if len(rows) < 30:
    c.execute('''SELECT sc.*, dr.win_2_5 FROM selection_candidates sc
                 LEFT JOIN daily_records dr ON sc.date=dr.date AND sc.code=dr.code
                 WHERE sc.date=? AND sc.run_time IS NOT NULL
                   AND sc.version != '东风31AG' ''', (today,))
    rows = c.fetchall()

if not rows:
    print(f"⚠️ {today} 无选股数据")
    conn.close()
    sys.exit(0)

# 各策略来源统计
src_count = {}
for r in rows:
    v = r['version']
    src_count[v] = src_count.get(v, 0) + 1
src_str = ' | '.join(f"{v}{n}" for v, n in sorted(src_count.items()))
print(f"📊 数据来源: {src_str}", flush=True)

c.execute('SELECT market FROM market_days WHERE date=?', (today,))
mkt_row = c.fetchone()
mkt = mkt_row['market'] if mkt_row else 'flat'
mkt_enc = {'real_up':0, 'fake_up':1, 'flat':2, 'down':3}.get(mkt, 2)

vers_all = ['V13','V42','V50','V88','V89','1180','CG18']
ver_enc = {v:i for i,v in enumerate(vers_all)}

picks = []
for r in rows:
    feats = np.array([[
        r['score'] or 0, r['cl'] or 50, r['vr'] or 1.0, r['hsl'] or 3,
        r['wr'] or 50, r['dif'] or 0,
        r['rank'] or 99, ver_enc.get(r['version'], 0), mkt_enc,
        r['pct'] or 0,
        1.0 / (max(r['rank'],1) + 1),
        (r['score'] or 0) * (r['cl'] or 50) / 100.0,
        int((r['dif'] or 0) > 0), int((r['vr'] or 1.0) < 2.0),
        int((r['cl'] or 50) > 60), int((r['hsl'] or 3) > 3),
    ]])
    prob = model.predict_proba(feats)[0, 1]
    price = r['price'] or r['close'] or 0
    
    # 当天最低
    low_price = snap_low.get(r['code'], 0)
    low_pct = (low_price - price) / price * 100 if low_price > 0 and price > 0 else 0
    
    picks.append({
        'prob': float(prob),
        'version': r['version'], 'rank': r['rank'],
        'code': r['code'], 'name': r['name'], 'price': price,
        'cl': r['cl'] or 50, 'vr': r['vr'] or 1.0,
        'hsl': r['hsl'] or 3, 'dif': r['dif'] or 0,
        'score': r['score'] or 0, 'pct': r['pct'] or 0,
        'low_pct': round(low_pct, 2),
        'run_time': r['run_time'] or '',
    })

# 去重（按version排，保留首个策略的条目）
seen = set()
deduped = []
for p in picks:
    if p['code'] not in seen and p['score'] > 0:
        seen.add(p['code'])
        deduped.append(p)

# 择优V4 — CL≥20 + VR∈[0.8,2] 4档回退
tier1 = [p for p in deduped if (p['cl'] or 0) >= 20 and 0.8 <= (p['vr'] or 1.0) <= 2.0]
tier1.sort(key=lambda x: -x['prob'])
# 同prob±4%内选score高的，避免低分冒尖
if tier1:
    best = tier1[0]
    for p in tier1[1:]:
        if (best['prob'] - p['prob']) * 100 <= 4 and p['score'] > best['score']:
            best = p
    tier1 = [best] + [p for p in tier1 if p != best]
if tier1:
    deduped = tier1
else:
    tier2 = [p for p in deduped if (p['cl'] or 0) > 60]
    if tier2:
        deduped = tier2
    else:
        tier3 = [p for p in deduped if (p['score'] or 0) > 20 and (p['vr'] or 1.0) > 0.8]
        if tier3:
            deduped = tier3
        # tier4: 全量

picks_top3 = deduped[:3]

# 查买入时间 = selection_candidates的记录创建时间（用#1）
pick = picks_top3[0]
c.execute('SELECT run_time FROM selection_candidates WHERE date=? AND code=? ORDER BY run_time LIMIT 1',
    (today, pick['code']))
rt = c.fetchone()
buy_time = rt[0] if rt else None

# 查当日收盘价（从bt_data），库存price存收盘而非快照价
c.execute('SELECT close FROM bt_data WHERE date=? AND code=?', (today, pick['code']))
bt_row = c.fetchone()
close_price = bt_row['close'] if bt_row else pick['price']

# 查下一交易日收盘价+最低价（用于次日收盘涨幅+最低跌幅）
c.execute('''
    SELECT close, high, low, date FROM bt_data 
    WHERE date > ? AND code = ? 
      AND date GLOB '????-??-??'
    ORDER BY date LIMIT 1
''', (today, pick['code']))
next_bt = c.fetchone()
next_close = next_bt['close'] if next_bt else None
next_high = next_bt['high'] if next_bt and next_bt['high'] and next_bt['high'] > (next_bt['close'] or 0) else None
next_low = next_bt['low'] if next_bt and next_bt['low'] and next_bt['low'] > 0 and next_bt['low'] < (next_bt['close'] or 99999) else None

# bt_data的高/低不可靠时，用腾讯K线API补真实值
if (not next_high or not next_low) and next_bt:
    import urllib.request, json, time
    next_date = next_bt['date']
    sh = 'sh' if pick['code'].startswith(('6','9')) else 'sz'
    for attempt in range(2):
        try:
            req = urllib.request.Request(
                f'http://ifzq.gtimg.cn/appstock/app/fqkline/get?param={sh}{pick["code"]},day,,,320,bfq',
                headers={'User-Agent': 'Mozilla/5.0'})
            kd = json.loads(urllib.request.urlopen(req, timeout=15).read().decode('utf-8'))
            klines = None
            for p in [f'{sh}{pick["code"]}', pick['code']]:
                if 'data' in kd and p in kd['data']:
                    dd = kd['data'][p]
                    if 'bfq' in dd and 'day' in dd['bfq']: klines = dd['bfq']['day']; break
                    if 'day' in dd: klines = dd['day']; break
            if klines:
                for kl in klines:
                    if isinstance(kl, list) and len(kl) >= 5 and str(kl[0]) == next_date:
                        if not next_high or next_high <= 0: next_high = float(kl[3])
                        if not next_low or next_low <= 0: next_low = float(kl[4])
                        break
            break
        except:
            time.sleep(0.3)
        pass

next_close_n = round((next_close - close_price) / close_price * 100, 2) if next_close and close_price > 0 else None
next_day_n = round((next_high - close_price) / close_price * 100, 2) if next_high and next_high > 0 and close_price > 0 else None
next_low_n = round((next_low - close_price) / close_price * 100, 2) if next_low and next_low > 0 and close_price > 0 else None
next_high_price = next_high if next_high and next_high > 0 else None
next_low_price = next_low if next_low and next_low > 0 else None

# 评分描述
def rating_desc(p):
    if p['prob'] >= 0.8: return '🟢强', '确定性高'
    if p['prob'] >= 0.65: return '🟡中', '有把握'
    if p['prob'] >= 0.5: return '🟠弱', '中性'
    return '🔴低', '风险偏高'

# 输出前三
print(f"📌 择优V4 {today}")
print(f"")
for rank_i, pick in enumerate(picks_top3, 1):
    emoji, desc = rating_desc(pick)
    print(f"{'🥇🥈🥉'[rank_i-1]} #{rank_i} {pick['code']} {pick['name']}")
    print(f"   买入价: {pick['price']:.2f}  当日: {pick['pct']:+.2f}%  评分: {pick['prob']*100:.0f}%")
    print(f"   来源: {pick['version']}(rank#{pick['rank']})  CL={pick['cl']:.0f} VR={pick['vr']:.2f} DIF={pick['dif']:.2f}")
    low_str = f"{pick['low_pct']:+.2f}%" if pick['low_pct'] < 0 else "未触及最低"
    print(f"   今日最低跌: {low_str}")
    advice = "可买入" if pick['prob'] >= 0.65 else "信号偏弱"
    print(f"   {'⚡' if pick['prob'] >= 0.65 else '⚠️'} 建议: {advice}")
    print(f"")

# 恢复#1为冠军（循环后pick是最后一只）
pick = picks_top3[0]

# 各策略冠军评分

# 各策略冠军评分
c.execute('''SELECT * FROM selection_candidates WHERE date=? AND rank=1 AND version != '东风31AG' ORDER BY version''', (today,))
seen_champ = set()
print(f"\n各策略冠军评分:")
for r in c.fetchall():
    k = (r['version'], r['code'])
    if k in seen_champ: continue
    seen_champ.add(k)
    feats = np.array([[
        r['score'] or 0, r['cl'] or 50, r['vr'] or 1.0, r['hsl'] or 3,
        r['wr'] or 50, r['dif'] or 0,
        1, ver_enc.get(r['version'], 0), mkt_enc,
        r['pct'] or 0,
        0.5,
        (r['score'] or 0) * (r['cl'] or 50) / 100.0,
        int((r['dif'] or 0) > 0), int((r['vr'] or 1.0) < 2.0),
        int((r['cl'] or 50) > 60), int((r['hsl'] or 3) > 3),
    ]])
    prob = model.predict_proba(feats)[0, 1]
    mark = '▲' if prob >= 0.5 else '▼'
    print(f"  {mark} {r['version']:<8} {r['code']} {r['name']:<6} → {prob*100:.0f}%")

# 保存到数据库追踪
c.execute('''INSERT OR REPLACE INTO meta_pick_records 
    (date, code, name, price, pct, model_prob, source_version, next_close_n, next_day_n, next_low_n, next_high_price, next_low_price, buy_time, source_rank, ver)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
    (today, pick['code'], pick['name'], close_price,
     pick['pct'], pick['prob'], pick['version'], next_close_n, next_day_n, next_low_n,
     next_high_price, next_low_price, buy_time, pick['rank'], '4'))
conn.commit()

# 保存JSON
OUT = os.path.join(SCRIPTS_DIR, f'meta_pick_v4_{today}.json')
json.dump({
    'date': today, 'market': mkt,
    'pick': {k: pick[k] for k in ['code','name','pct','low_pct',
                                   'prob','version','rank','cl','vr','dif','score','run_time']},
    'price': close_price,
    'next_close_n': next_close_n, 'next_day_n': next_day_n, 'next_low_n': next_low_n
}, open(OUT, 'w'), ensure_ascii=False)
print(f"\n✅ 已保存")
conn.close()
