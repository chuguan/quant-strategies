"""大道至简 时间点回测"""
import sqlite3, os, sys, importlib
from datetime import datetime

TIME_LABEL = sys.argv[1] if len(sys.argv) > 1 else '14:30'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 30
tl_clean = TIME_LABEL.replace(':', '')
VER = f'大道至简_{tl_clean}_{N}d'

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
sys.path.insert(0, os.path.join(SCRIPTS_DIR, 'dev', 'current'))

STRATS = {}
FUNC_NAMES = {'真实涨日':'真实涨日_评分','虚涨日':'虚涨日_评分','跌日':'跌日_评分','横盘':'横盘_评分'}
for n, fn in FUNC_NAMES.items():
    mod = importlib.import_module(f'大道至简_{n}_评分策略')
    STRATS[n] = mod

TIME_PROGRESS = {'14:30': 0.85, '14:40': 0.90, '14:50': 0.95}
progress = TIME_PROGRESS.get(TIME_LABEL, 0.85)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]
dates_n = all_dates[-N:]
extended = all_dates[all_dates.index(dates_n[0])-6:all_dates.index(dates_n[-1])+1]

data = {}
for dt in extended:
    c.execute('SELECT code,name,p,cl,vr,n,dif_val,macd_golden,wr_val,j_val,k_val,d_val,pos_in_day,above_ma5,kdj_golden,close,volume,high,low FROM data_cache WHERE date=?', (dt,))
    cols = ['code','name','p','cl','vr','n','dif_val','macd_golden','wr_val','j_val','k_val','d_val','pos_in_day','above_ma5','kdj_golden','close','volume','high','low']
    data[dt] = [dict(zip(cols, row)) for row in c.fetchall()]

c.execute('SELECT code, close FROM data_cache WHERE date=?', (all_dates[all_dates.index(dates_n[0])-1],))
prev_closes = {r[0]: r[1] or 0 for r in c.fetchall()}
for dt in dates_n:
    idx = all_dates.index(dt)
    if idx > 0:
        c.execute('SELECT code, close FROM data_cache WHERE date=?', (all_dates[idx-1],))
        for r in c.fetchall():
            if r[0] not in prev_closes: prev_closes[r[0]] = r[1] or 0

features = {}
for dt in dates_n:
    c.execute('SELECT * FROM features_cache WHERE date=?', (dt,))
    fcols = [desc[0] for desc in c.description]
    for row in c.fetchall():
        f = dict(zip(fcols, row))
        features[(f['code'], dt)] = f

c.execute('SELECT code, hsl, shizhi FROM data_stock_info')
stock_info = {r[0]: {'hsl': r[1] or 0, 'shizhi': r[2] or 0} for r in c.fetchall()}

MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4','L5']

def est_p(s):
    cp = s.get('p',0) or 0
    pc = prev_closes.get(s['code'],0)
    cl = s.get('close',0) or 0
    if pc<=0 or cl<=0: return cp
    return round((pc*(1+cp/100*progress)-pc)/pc*100,2)

def est_vr(s): return round((s.get('vr',1) or 1)*progress,2)

def mkt_class(ss):
    ps=[s.get('_p',0) for s in ss if abs(s.get('_p',0))<15]
    vrs=[s.get('_vr',1) for s in ss if s.get('_vr',0)]
    if not ps: return 'flat'
    ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0
    return 'fake_up' if (ap>0.5 and (sum(1 for p in ps if 5<=p<=8)<15 or av<0.9)) else ('real_up' if ap>0.5 else ('down' if ap<-0.5 else 'flat'))

def exhausted(s,code,dt):
    ft=features.get((code,dt),{}); sl5=ft.get('slope5',0); t4=ft.get('t4_shadow',0); cu=ft.get('cons_up',0); pk=ft.get('peak_decay',0); pv=s.get('_p',0)
    for c in [(sl5>8 and t4>25),(sl5>10 and t4>18),(cu>=5 and sl5>15),(pk>5 and sl5>5 and pv<6),(sl5>5 and t4>30),(cu>=4 and sl5>10 and pv<7)]:
        if c: return True
    return False

def penalty(code,dt,p_today):
    ad=sorted(data.keys())
    try: idx=ad.index(dt)
    except: return 0
    prev=ad[max(0,idx-6):idx]
    g=[]
    for pd in prev:
        f=False
        for s in data.get(pd,[]):
            if s['code']==code: g.append(s.get('p',0) or 0); f=True; break
        if not f: g.append(0)
    g.append(p_today); n=len(g)
    if n<5: return 0
    d6,d5,d4,d3,d2,d1,p_=g[-7:] if n>=7 else [0]*(7-n)+g[-n:]
    pm=p_>=max(g[:-1]); a7=sum(g)/n; pen=0; w=50
    for s in data.get(dt,[]):
        if s['code']==code: w=s.get('wr_val',50) or s.get('wrv',50); break
    if w<10 and pm and a7<2.0 and p_<6: pen-=8
    if pm and a7<0.8 and p_<8:
        pen-=15 if a7<0 else (-12 if a7<0.3 else (-8 if a7<0.7 else -5))
    if n>=6 and d1<-1.5 and d2<-1.0 and p_>3 and a7<1.0: pen-=8
    if len(g)>=7 and max(d4,d3,d2)>5 and d1<0 and d2<0: pen-=10
    if n>=5 and d5>d1 and d5>d2 and p_<=d5:
        rs=(d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
        if rs<=2: pen-=8
    if n>=5 and all(g[-5+i]>=g[-4+i] for i in range(4)): pen-=10
    return pen

def score_stock(s,code,dt,mk_cn):
    mod=STRATS[mk_cn]
    fn=getattr(mod, FUNC_NAMES[mk_cn])
    stock={'p':s.get('_p',0),'cl':s.get('cl',50),'vr':s.get('_vr',1),'dif':s.get('dif_val',0) or 0,'mg':s.get('macd_golden',0) or 0,'wrv':s.get('wr_val',0) or 50,'jv':s.get('j_val',0) or 50,'kv':s.get('k_val',0) or 50,'dv':s.get('d_val',0) or 50,'a5':s.get('above_ma5',0),'kdj_g':s.get('kdj_golden',0) or 0,'pos_in_day':s.get('pos_in_day',50),'nm':s.get('name','') or ''}
    si=stock_info.get(code,{}); stock['hsl']=si.get('hsl',0) or 0
    ft=features.get((code,dt),{})
    for k in ['t4_shadow','slope5','cons_up','d1','d2','d3']: stock[k]=ft.get(k,0) if ft else 0
    stock['buy_c']=s.get('close',0) or 0
    stock['close']=s.get('close',0) or 0
    return round(fn(stock)+penalty(code,dt,s.get('_p',0)),1)

wi=ta=cta=0
mk_s={k:[0,0] for k in ['real_up','fake_up','down','flat']}

print(f'⏰ {TIME_LABEL} 大道至简 {N}天')
for dt in reversed(dates_n):
    ss=data.get(dt,[])
    for s in ss: s['_p']=est_p(s); s['_vr']=est_vr(s)
    ss=[s for s in ss if abs(s.get('_p',0))<15]
    if not ss: continue
    mk=mkt_class(ss); mk_cn=MK_MAP.get(mk,'横盘')
    mod=STRATS[mk_cn]
    levels=mod.LEVELS if hasattr(mod,'LEVELS') else []
    lm={l['name']:i for i,l in enumerate(levels)} if levels else {}
    pool=None
    for ln in LO:
        if ln not in lm: continue
        lv=levels[lm[ln]]; cand=[]
        for s in ss:
            p=s['_p']; vr=s['_vr']
            if p<lv.get('p_min',-10) or p>min(lv.get('p_max',10),8): continue
            if vr<lv.get('vr_min',0) or vr>lv.get('vr_max',10): continue
            si=stock_info.get(s['code'],{}); hsl=si.get('hsl',0) or 0
            if hsl<lv.get('hs_min',0) or hsl>lv.get('hs_max',100): continue
            if (si.get('shizhi',0) or 0)>=lv.get('sz_max',9999): continue
            nm=s.get('name','')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl=s.get('cl',0)
            if cl<lv.get('cl_min',0) or cl>lv.get('cl_max',100): continue
            if exhausted(s,s['code'],dt): continue
            cand.append(s)
        if len(cand)>=10: pool=cand; break
    if not pool: continue
    scored=[(score_stock(s,s['code'],dt,mk_cn),s) for s in pool]
    scored.sort(key=lambda x:-x[0])
    champ=scored[0][1]; nh=champ.get('n',0) or 0
    hn=(dt!=dates_n[-1]); mk_s[mk][1]+=1
    if hn:
        win='✅' if nh>=2.5 else '❌'
        if win=='✅': wi+=1; mk_s[mk][0]+=1
        cta+=1
    else: win='⏳'
    ta+=1

print(f'{TIME_LABEL} {N}天: {wi}/{cta}={wi*100/cta:.1f}%' if cta else '无数据')
for mk in ['real_up','fake_up','down','flat']:
    w,t=mk_s[mk]
    if t: print(f'  {MK_MAP[mk]}: {w}/{t}={w*100/t:.1f}%')
conn.close()
