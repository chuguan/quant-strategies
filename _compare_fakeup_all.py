#!/usr/bin/env python3
"""V13 vs V14 虚涨日全面对比 — 全部33天"""
import os, sys, importlib, sqlite3

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
V14_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V14')

def load_strats(base_dir):
    strats = {}
    for n in ['真实涨日','虚涨日','跌日','横盘']:
        fp = os.path.join(base_dir, '评分策略', f'分而治之_V10_{n}_评分策略.py')
        spec = importlib.util.spec_from_file_location(n, fp)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        strats[n] = m
    return strats

V13_STRATS = load_strats(V13_DIR)
V14_STRATS = load_strats(V14_DIR)
MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4']

def mkt_class(ss):
    if not ss: return 'flat'
    ps=[s.get('p',0) or 0 for s in ss]
    vrs=[s.get('vr',0) or 1 for s in ss if s.get('vr',0)]
    ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

# 加载数据
DB = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
conn = sqlite3.connect(DB, timeout=30)
c = conn.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]

# 判断每天的行情
fake_dates = []
for dt in all_dates:
    c = conn.execute('SELECT p, vr FROM data_cache WHERE date=?', (dt,))
    rows = c.fetchall()
    ps = [r[0] or 0 for r in rows if abs(r[0] or 0) < 15]
    vrs = [r[1] or 0 for r in rows if (r[1] or 0) > 0]
    if not ps: continue
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if ap>0.5 and (hot<15 or av<0.9):
        fake_dates.append(dt)

print(f'虚涨日: {len(fake_dates)}天')

# 加载全量数据（包括前7天用于7天扣分）
earliest = all_dates.index(fake_dates[0]) - 7
pre_dates = all_dates[max(0,earliest):all_dates.index(fake_dates[-1])+1]
data = {}
for dt in pre_dates:
    c = conn.execute('SELECT * FROM data_cache WHERE date=?', (dt,))
    cols = [d[0] for d in c.description]
    data[dt] = [dict(zip(cols, row)) for row in c.fetchall()]

# 加载特征
features = {}
for dt in fake_dates + pre_dates:
    c = conn.execute('SELECT * FROM features_cache WHERE date=?', (dt,))
    fcols = [d[0] for d in c.description]
    for row in c.fetchall():
        f = dict(zip(fcols, row))
        features[(f['code'], dt)] = f

c = conn.execute('SELECT code, hsl, shizhi FROM data_stock_info')
stock_info = {r[0]: {'hsl': r[1] or 0, 'shizhi': r[2] or 0} for r in c.fetchall()}
conn.close()

# 7天扣分
def compute_7day_penalty(code, dt, p_today):
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
    n=len(gains); penalty=0
    if n<5: return 0
    d6,d5,d4,d3,d2,d1,p=gains[-7:] if n>=7 else [0]*(7-n)+gains[-n:]
    p_is_max=p>=max(gains[:-1]); avg_7d=sum(gains)/n
    wrv=50
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
        rs=(d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
        if rs<=2: penalty-=8
    if n>=5:
        l5=gains[-5:]
        if all(l5[i]>=l5[i+1] for i in range(len(l5)-1)): penalty-=10
    return penalty

# 动量衰竭
def is_exhausted(s,code,dt):
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

def score_v(strats, s, code, dt, mk_cn):
    mod=strats[mk_cn]
    stock={'p':s.get('p',0) or 0,'cl':s.get('cl',50),'vr':s.get('vr',1) or s.get('vol_ratio',1),
           'dif':s.get('dif_val',0) or s.get('dif',0),'mg':s.get('macd_golden',0) or s.get('mg',0),
           'wrv':s.get('wr_val',0) or s.get('wrv',50),'jv':s.get('j_val',0) or s.get('jv',50),
           'kv':s.get('k_val',0) or s.get('kv',50),'dv':s.get('d_val',0) or s.get('dv',50),
           'a5':s.get('above_ma5',0),'kdj_g':s.get('kdj_golden',0) or s.get('kdj_g',0),
           'pos_in_day':s.get('pos_in_day',50),'nm':s.get('name','') or '',
           'hsl':stock_info.get(code,{}).get('hsl',0) or 0}
    feats=features.get((code,dt),{})
    stock['t4_shadow']=feats.get('t4_shadow',0); stock['slope5']=feats.get('slope5',0)
    stock['cons_up']=feats.get('cons_up',0)
    stock['d1']=feats.get('d1',0); stock['d2']=feats.get('d2',0); stock['d3']=feats.get('d3',0)
    pn=compute_7day_penalty(code,dt,s.get('p',0) or 0)
    return round(mod.score(stock)+pn,1)

def run(strats, dates):
    results=[]
    for dt in dates:
        ss=data.get(dt,[]); ss=[s for s in ss if (s.get('p',0) or 0)<15]
        if not ss: continue
        mod=strats['虚涨日']; levels=mod.LEVELS
        lm={l['name']:i for i,l in enumerate(levels)}
        pool=None
        for ln in LO:
            if ln not in lm: continue
            i=lm[ln]; lv=levels[i]; cand=[]
            for s in ss:
                p=s.get('p',0) or 0
                if p<lv['p_min'] or p>min(lv.get('p_max',10),8): continue
                vr=s.get('vr',0) or s.get('vol_ratio',0) or 0
                if vr<lv['vr_min'] or vr>lv['vr_max']: continue
                si=stock_info.get(s['code'],{}); hsl=si.get('hsl',0) or 0
                if hsl<lv.get('hs_min',0) or hsl>lv.get('hs_max',99): continue
                if (si.get('shizhi',0) or 0)>=lv.get('sz_max',9999): continue
                nm=s.get('name','')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl=s.get('cl',0)
                if cl<lv.get('cl_min',0) or cl>lv.get('cl_max',100): continue
                if is_exhausted(s,s['code'],dt): continue
                cand.append(s)
            if len(cand)>=10: pool=cand; break
        if not pool: continue
        scored=[(score_v(strats,s,s['code'],dt,'虚涨日'),s) for s in pool]
        scored.sort(key=lambda x:-x[0])
        champ=scored[0][1]; nh=champ.get('n',0) or 0
        second=scored[1][1] if len(scored)>1 else None
        third=scored[2][1] if len(scored)>2 else None
        results.append({
            'dt':dt,
            'c_name':champ.get('name','') or champ.get('nm',''),'c_code':champ['code'],
            'c_p':champ.get('p',0) or 0,'c_nh':nh,
            's_name':second.get('name','?') if second else '—','s_code':second['code'] if second else '',
            's_nh':second.get('n',0) or 0 if second else 0,
            't_name':third.get('name','?') if third else '—','t_code':third['code'] if third else '',
            't_nh':third.get('n',0) or 0 if third else 0,
            'result':'✅' if nh>=2.5 else '❌',
        })
    return results

print('▶ 跑V13虚涨日回测...')
v13r = run(V13_STRATS, fake_dates)
print('▶ 跑V14虚涨日回测...')
v14r = run(V14_STRATS, fake_dates)

w13=sum(1 for r in v13r if r['result']=='✅')
w14=sum(1 for r in v14r if r['result']=='✅')
same=sum(1 for i,r in enumerate(v13r) if r['c_code']==v14r[i]['c_code'])
tot=len(v13r)

print(f'\n=== 虚涨日 全部{tot}天 ===')
print(f'{"V13":>5}: {w13}/{tot} = {w13*100//tot}%')
print(f'{"V14":>5}: {w14}/{tot} = {w14*100//tot}%')
print(f'冠军相同: {same}/{tot} = {same*100//tot}%')
print()

print(f'{"日期":>10} {"V13冠军":>14} {"V13次日高":>8} {"V14冠军":>14} {"V14次日高":>8} 结果')
print('-' * 75)
for i in range(tot):
    a=v13r[i]; b=v14r[i]
    sig='*' if a['result']!=b['result'] or a['c_code']!=b['c_code'] else ''
    print(f'{a["dt"]:>10} {a["c_name"]:>10}({a["c_code"]}) {a["c_nh"]:>+7.1f}% {b["c_name"]:>10}({b["c_code"]}) {b["c_nh"]:>+7.1f}%  V13:{a["result"]} V14:{b["result"]}{sig}')

print(f'\n✅ 完成')
