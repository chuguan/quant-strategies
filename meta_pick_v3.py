#!/usr/bin/env python3
"""V3择优 — 纯CL>60 + prob排序，无额外价格修正，与外部验证一致"""
import sqlite3, numpy as np, xgboost as xgb, os, sys, json, urllib.request, time
from datetime import datetime

S=os.path.expanduser('~/AppData/Local/hermes/scripts')
DB=f'{S}/v13_quant.db'
conn=sqlite3.connect(DB)
conn.row_factory=sqlite3.Row
c=conn.cursor()

today=sys.argv[1] if len(sys.argv)>1 else datetime.now().strftime('%Y-%m-%d')
print(f'📌 择优V3 {today}')

model=xgb.XGBClassifier()
model.load_model(f'{S}/meta_ranker_model.json')
va='V13 V42 V50 V88 V89 1180 CG18'.split()
ve={v:i for i,v in enumerate(va)}

c.execute('SELECT market FROM market_days WHERE date=?',(today,))
mr=c.fetchone()
me={'real_up':0,'fake_up':1,'flat':2,'down':3}.get(mr['market']if mr else'flat',2)

# 读14-15窗口数据
c.execute('''SELECT * FROM selection_candidates WHERE date=?
    AND run_time >= ?||' 14:00' AND run_time <= ?||' 15:00'
    AND version NOT IN ("东风31AG") ORDER BY version,rank''',(today,today,today))
rows=c.fetchall()
if not rows:
    # fallback: 放宽时间窗口
    c.execute('''SELECT * FROM selection_candidates WHERE date=?
        AND version NOT IN ("东风31AG") ORDER BY version,rank''',(today,))
    rows=c.fetchall()
    if not rows:
        print('⚠️ 无选股数据');sys.exit(0)

# prob计算+去重
seen=set();picks=[]
for r in rows:
    if r['code'] in seen:continue
    seen.add(r['code'])
    sc_v=r['score']or 0;cl_v=r['cl']or 0;vr_v=r['vr']or 1.0;dif_v=r['dif']or 0
    f=np.array([[sc_v,cl_v,vr_v,r['hsl']or 3,r['wr']or 50,dif_v,r['rank']or 99,ve.get(r['version'],0),me,r['pct']or 0,1.0/(max(r['rank'],1)+1),sc_v*cl_v/100.0,int(dif_v>0),int(vr_v<2.0),int(cl_v>60),int((r['hsl']or 3)>3)]])
    prob=float(model.predict_proba(f)[0,1])
    picks.append({'prob':prob,'code':r['code'],'name':r['name'],'cl':cl_v,'score':sc_v,'version':r['version'],'rank':r['rank'],'price':r['price']or r['close']or 0,'pct':r['pct']or 0})

# V3: CL>60优先，不足5只则纯prob排序
t1=[p for p in picks if p['cl']>60]
t1.sort(key=lambda p:-p['prob'])
if len(t1)>=5:
    deduped=t1
else:
    deduped=sorted(picks,key=lambda p:-p['prob'])

pick=deduped[0]
print(f'🥇 {pick["code"]} {pick["name"]}  CL={pick["cl"]:.0f} 评分={pick["prob"]*100:.0f}%')
print(f'   来源: {pick["version"]}(rank#{pick["rank"]})')

# T+1数据
c.execute('SELECT date FROM market_days ORDER BY date')
md=[r[0]for r in c.fetchall()]
nd={}
for i,d in enumerate(md):
    if i+1<len(md):nd[d]=md[i+1]

nxt=nd.get(today)
next_high=next_low=next_close=None
if nxt:
    sh='sh' if pick['code'].startswith(('6','9')) else 'sz'
    for _ in range(2):
        try:
            d=json.loads(urllib.request.urlopen(urllib.request.Request(f'http://ifzq.gtimg.cn/appstock/app/fqkline/get?param={sh}{pick["code"]},day,,,320,bfq',headers={'User-Agent':'Mozilla/5.0'}),timeout=15).read().decode())
            kl=None
            for kk in[f'{sh}{pick["code"]}',pick['code']]:
                if'data'in d and kk in d['data']:
                    dd=d['data'][kk]
                    if'day'in dd:kl=dd['day'][-20:]
                    elif'bfq'in dd and'day'in dd['bfq']:kl=dd['bfq']['day'][-20:]
                    break
            if kl:
                for k in kl:
                    if isinstance(k,list) and len(k)>=5 and str(k[0])==nxt:
                        next_high=float(k[3]);next_low=float(k[4]);next_close=float(k[2])
                        break
            time.sleep(0.05);break
        except:time.sleep(0.3)

next_day_n=round((next_high/pick['price']-1)*100,2)if next_high and pick['price']>0 else None
next_low_n=round((next_low/pick['price']-1)*100,2)if next_low and pick['price']>0 else None
next_close_n=round((next_close/pick['price']-1)*100,2)if next_close and pick['price']>0 else None
win=1 if next_day_n is not None and next_day_n>=2.5 else(0 if next_day_n is not None else None)
print(f'   次日最高: {next_day_n}% {"✅" if win==1 else "❌" if win==0 else "?"} 最低: {next_low_n}% 收盘: {next_close_n}%')

# 保存到meta_pick_records
c2=sqlite3.connect(DB)
c2.execute('''INSERT OR REPLACE INTO meta_pick_records
    (date,code,name,price,pct,model_prob,source_version,next_close_n,next_day_n,next_low_n,next_high_price,next_low_price,buy_time,source_rank,ver)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
    (today,pick['code'],pick['name'],pick['price'],pick['pct'],pick['prob'],pick['version'],next_close_n,next_day_n,next_low_n,next_high,next_low,datetime.now().strftime('%Y-%m-%d %H:%M:%S'),pick['rank'],'3'))
c2.execute('UPDATE meta_pick_records SET win_2_5=? WHERE date=? AND code=? AND ver="3"',(win,today,pick['code']))
c2.commit()
c2.close()

print(f'✅ 已保存')
