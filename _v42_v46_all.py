#!/usr/bin/env python3
"""V42 VS V46 全量回测 — 优化版"""
import sys, os, importlib
import sqlite3
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)
DB = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4']

def load_strats(d):
    s = {}
    for n in ['真实涨日','虚涨日','跌日','横盘']:
        fp = os.path.join(d, f'分而治之_V10_{n}_评分策略.py')
        spec = importlib.util.spec_from_file_location(n, fp)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        s[n] = m
    return s

v42s = load_strats(os.path.join(SCRIPTS_DIR, 'release', 'V42', '评分策略'))
v46s = load_strats(os.path.join(SCRIPTS_DIR, 'release', 'V46', '评分策略'))

conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

today_str = datetime.now().strftime('%Y-%m-%d')
c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
all_dates_raw = [r[0] for r in c.fetchall()]
all_dates = []
for d in all_dates_raw:
    try:
        wd = datetime.strptime(d, '%Y-%m-%d').weekday()
        if wd < 5 and d != today_str:
            all_dates.append(d)
    except: pass

print(f'总交易日: {len(all_dates)}天 ({all_dates[0]} ~ {all_dates[-1]})')

# 一次性加载所有需要的数据
print('加载数据...', end=' ', flush=True)
extended = all_dates
data = {}
for dt in extended:
    c.execute('SELECT * FROM data_cache WHERE date=?', (dt,))
    cols = [d[0] for d in c.description]
    data[dt] = [dict(zip(cols, row)) for row in c.fetchall()]

features = {}
for dt in all_dates:
    c.execute('SELECT * FROM features_cache WHERE date=?', (dt,))
    fcols = [d[0] for d in c.description]
    for row in c.fetchall():
        f = dict(zip(fcols, row))
        features[(f['code'], dt)] = f

c.execute('SELECT code, hsl, shizhi FROM data_stock_info')
stock_info = {r[0]: {'hsl': r[1] or 0, 'shizhi': r[2] or 0} for r in c.fetchall()}
conn.close()
print(f'完成 ({len(data)}天, {len(features)}特征)')

def is_momentum_exhausted(s,code,dt):
    feats=features.get((code,dt),{})
    if not feats: return False
    sl5=feats.get('slope5',0); t4s=feats.get('t4_shadow',0); cu=feats.get('cons_up',0)
    pk=feats.get('peak_decay',0); pv=s.get('p',0) or 0
    if sl5>8 and t4s>25: return True
    if sl5>10 and t4s>18: return True
    if cu>=5 and sl5>15: return True
    if pk>5 and sl5>5 and pv<6: return True
    if sl5>5 and t4s>30: return True
    if cu>=4 and sl5>10 and pv<7: return True
    return False

def compute_7day_penalty(code,dt,p_today):
    ad=sorted(data.keys())
    try: idx=ad.index(dt)
    except: return 0
    prev=ad[max(0,idx-6):idx]
    gains=[]
    for pd in prev:
        found=False
        for s in data.get(pd,[]):
            if s['code']==code: gains.append(s.get('p',0) or 0); found=True; break
        if not found: gains.append(0)
    gains.append(p_today)
    n=len(gains)
    if n<5: return 0
    d6,d5,d4,d3,d2,d1,p=gains[-7:] if n>=7 else [0]*(7-n)+gains[-n:]
    p_is_max=p>=max(gains[:-1]); avg_7d=sum(gains)/n
    penalty=0; wrv=50
    for s in data.get(dt,[]):
        if s['code']==code: wrv=s.get('wr_val',50) or s.get('wrv',50); break
    if wrv<10 and p_is_max and avg_7d<2.0 and p<6: penalty-=8
    if p_is_max and avg_7d<0.8 and p<8:
        if avg_7d<0: penalty-=15
        elif avg_7d<0.3: penalty-=12
        elif avg_7d<0.7: penalty-=8
        else: penalty-=5
    if d1<-1.5 and d2<-1.0 and p>3 and avg_7d<1.0: penalty-=8
    if max(d4,d3,d2)>5 and d1<0 and d2<0: penalty-=10
    if n>=5 and d5>d1 and d5>d2 and p<=d5:
        recent_sum=(d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
        if recent_sum<=2: penalty-=8
    if n>=5:
        last5=gains[-5:]
        if all(last5[i]>=last5[i+1] for i in range(len(last5)-1)): penalty-=10
    return penalty

def mkt_class(ss):
    if not ss: return 'flat'
    ps=[s.get('p',0) or 0 for s in ss]
    vrs=[s.get('vr',0) or 1 for s in ss if s.get('vr',0)]
    ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

def run(strats, label, pdates):
    wi=0; ta=0
    for dt in pdates:
        ss=data.get(dt,[]); ss=[s for s in ss if (s.get('p',0) or 0)<15]
        if not ss: continue
        mk=mkt_class(ss); mk_cn=MK_MAP.get(mk,'横盘')
        mod=strats[mk_cn]; levels=mod.LEVELS
        lm={l['name']:i for i,l in enumerate(levels)}
        pool=None
        for ln in LO:
            if ln not in lm: continue
            i=lm[ln]; lv=levels[i]; cand=[]
            for s in ss:
                code=s['code']; p_v=s.get('p',0) or 0
                if p_v<lv['p_min'] or p_v>min(lv.get('p_max',10),8): continue
                vr=s.get('vr',0) or s.get('vol_ratio',0) or 0
                if vr<lv['vr_min'] or vr>lv['vr_max']: continue
                si=stock_info.get(code,{}); hsl=si.get('hsl',0) or 0
                if hsl<lv.get('hs_min',0) or hsl>lv.get('hs_max',99): continue
                if (si.get('shizhi',0) or 0)>=lv.get('sz_max',9999): continue
                nm=s.get('name','')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl=s.get('cl',0)
                if cl<lv.get('cl_min',0) or cl>lv.get('cl_max',100): continue
                if is_momentum_exhausted(s,code,dt): continue
                cand.append(s)
            if len(cand)>=10: pool=cand; break
        if not pool: continue
        
        scored=[]
        for s in pool:
            code=s['code']; p_v=s.get('p',0) or 0
            stock={
                'p':p_v,'cl':s.get('cl',50),'vr':s.get('vr',1) or s.get('vol_ratio',1),
                'dif':s.get('dif_val',0) or s.get('dif',0),'mg':s.get('macd_golden',0) or s.get('mg',0),
                'wrv':s.get('wr_val',0) or s.get('wrv',50),
                'jv':s.get('j_val',0) or s.get('jv',50),'kv':s.get('k_val',0) or s.get('kv',50),
                'dv':s.get('d_val',0) or s.get('dv',50),
                'a5':s.get('above_ma5',0),'kdj_g':s.get('kdj_golden',0) or s.get('kdj_g',0),
                'pos_in_day':s.get('pos_in_day',50),'nm':s.get('name','') or ''
            }
            si=stock_info.get(code,{}); stock['hsl']=si.get('hsl',0) or 0
            feats=features.get((code,dt),{})
            stock['t4_shadow']=feats.get('t4_shadow',0); stock['slope5']=feats.get('slope5',0)
            stock['cons_up']=feats.get('cons_up',0)
            stock['d1']=feats.get('d1',0); stock['d2']=feats.get('d2',0); stock['d3']=feats.get('d3',0)
            penalty=compute_7day_penalty(code,dt,p_v)
            score=round(mod.score(stock)+penalty,1)
            if score>0: scored.append((code,score,s))
        
        scored.sort(key=lambda x:-x[1])
        if not scored: continue
        champ=scored[0][2]; nh=champ.get('n',0) or 0
        has_next=nh!=0 or any((s.get('n',0) or 0)!=0 for s in ss)
        if has_next: ta+=1
        if has_next and nh>=2.5: wi+=1
    return wi, ta

# 分段跑
periods = [
    ('近30天', all_dates[-30:]),
    ('近60天', all_dates[-60:]),
    ('近90天', all_dates[-90:]),
    ('近120天', all_dates[-120:]),
    ('近180天', all_dates[-180:]),
]

results = []
for pname, pdates in periods:
    print(f'跑{pname}...', end=' ', flush=True)
    v42_wi, v42_ta = run(v42s, 'V42', pdates)
    v46_wi, v46_ta = run(v46s, 'V46', pdates)
    results.append((pname, v42_ta, v42_wi, v42_wi*100/v42_ta, v46_wi, v46_wi*100/v46_ta))
    print(f'{v42_wi}/{v42_ta}={v42_wi*100/v42_ta:.1f}% vs {v46_wi}/{v46_ta}={v46_wi*100/v46_ta:.1f}%')

print()
print(f'===== V42 vs V46 多周期对比 =====')
print(f'{"周期":<10} {"天数":>4} {"V42 #1":>14} {"V46 #1":>14} {"差异":>10}')
print('-'*55)
for pname, ta, v42w, v42p, v46w, v46p in results:
    diff = v46p - v42p
    print(f'{pname:<10} {ta:>4}  {v42w:>3}/{ta:<3}={v42p:>5.1f}%  {v46w:>3}/{ta:<3}={v46p:>5.1f}%  {diff:+>+5.1f}%')
