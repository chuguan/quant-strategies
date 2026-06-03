#!/usr/bin/env python3
"""V13 vs V14 虚涨日详细对比 — 延长到100天"""
import os, sys, importlib, sqlite3

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
V14_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V14')

# 加载评分模块
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

def is_momentum_exhausted(s, code, dt, features):
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

def compute_7day_penalty(code, dt, p_today, data):
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

def score_stock(strats, s, code, dt, mk_cn, stock_info, features, data):
    mod=strats[mk_cn]
    stock={}
    stock['p']=s.get('p',0) or 0; stock['cl']=s.get('cl',50)
    stock['vr']=s.get('vr',1) or s.get('vol_ratio',1)
    stock['dif']=s.get('dif_val',0) or s.get('dif',0)
    stock['mg']=s.get('macd_golden',0) or s.get('mg',0)
    stock['wrv']=s.get('wr_val',0) or s.get('wrv',50)
    stock['jv']=s.get('j_val',0) or s.get('jv',50)
    stock['kv']=s.get('k_val',0) or s.get('kv',50)
    stock['dv']=s.get('d_val',0) or s.get('dv',50)
    stock['a5']=s.get('above_ma5',0); stock['kdj_g']=s.get('kdj_golden',0) or s.get('kdj_g',0)
    stock['pos_in_day']=s.get('pos_in_day',50)
    stock['nm']=s.get('name','') or ''
    si=stock_info.get(code,{}); stock['hsl']=si.get('hsl',0) or 0
    feats=features.get((code,dt),{})
    stock['t4_shadow']=feats.get('t4_shadow',0); stock['slope5']=feats.get('slope5',0)
    stock['cons_up']=feats.get('cons_up',0)
    stock['d1']=feats.get('d1',0); stock['d2']=feats.get('d2',0); stock['d3']=feats.get('d3',0)
    penalty=compute_7day_penalty(code,dt,s.get('p',0) or 0,data)
    return round(mod.score(stock)+penalty,1)

def run_backtest(strats, data, dates, features, stock_info, recent_dates):
    """完整回测，返回逐日记录"""
    results = []
    for dt in dates:
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
                if is_momentum_exhausted(s,s['code'],dt,features): continue
                cand.append(s)
            if len(cand)>=10: pool=cand; break
        if not pool: continue
        scored=[(score_stock(strats,s,s['code'],dt,mk_cn,stock_info,features,data),s) for s in pool]
        scored.sort(key=lambda x:-x[0])
        champ=scored[0][1]; nh=champ.get('n',0) or 0
        t3=[scored[i][1] for i in range(min(3,len(scored)))]
        results.append({
            'dt':dt, 'mk':mk_cn,
            'c_name':champ.get('name','') or champ.get('nm',''),
            'c_code':champ['code'], 'c_p':champ.get('p',0) or 0, 'c_nh':nh,
            's_name':t3[1].get('name','?') if len(t3)>1 else '—',
            's_code':t3[1]['code'] if len(t3)>1 else '',
            's_nh':t3[1].get('n',0) or 0 if len(t3)>1 else 0,
            't_name':t3[2].get('name','?') if len(t3)>2 else '—',
            't_code':t3[2]['code'] if len(t3)>2 else '',
            't_nh':t3[2].get('n',0) or 0 if len(t3)>2 else 0,
            'result':'✅' if nh>=2.5 else '❌',
        })
    return results

# 加载数据
print('▶ 加载数据...')
conn = sqlite3.connect(DB_PATH, timeout=30)
c = conn.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]

# 取最近100天
use_dates = all_dates[-120:]  # 多取20天用于7天扣分计算需要
data = {}
for dt in use_dates:
    c = conn.execute('SELECT * FROM data_cache WHERE date=?', (dt,))
    cols = [d[0] for d in c.description]
    data[dt] = [dict(zip(cols, row)) for row in c.fetchall()]

features = {}
for dt in use_dates:
    c = conn.execute('SELECT * FROM features_cache WHERE date=?', (dt,))
    fcols = [d[0] for d in c.description]
    for row in c.fetchall():
        f = dict(zip(fcols, row))
        features[(f['code'], dt)] = f

c = conn.execute('SELECT code, hsl, shizhi FROM data_stock_info')
stock_info = {r[0]: {'hsl': r[1] or 0, 'shizhi': r[2] or 0} for r in c.fetchall()}
conn.close()

backtest_dates = all_dates[-100:] if len(all_dates) >= 100 else all_dates
print(f'  {len(backtest_dates)}个交易日')

# 跑V13
print('▶ 回测 V13...')
v13_results = run_backtest(V13_STRATS, data, backtest_dates, features, stock_info, all_dates)

# 跑V14
print('▶ 回测 V14...')
v14_results = run_backtest(V14_STRATS, data, backtest_dates, features, stock_info, all_dates)

# 只对比虚涨日
v13_fake = [r for r in v13_results if r['mk'] == '虚涨日']
v14_fake = [r for r in v14_results if r['mk'] == '虚涨日']

print(f'\n=== 虚涨日对比 (共{len(v13_fake)}天) ===')
print(f'{"日期":>10} | {"V13冠军":>10} | {"V13次日高":>8} | {"V14冠军":>10} | {"V14次日高":>8} | 结果')
print('-' * 65)

w13 = sum(1 for r in v13_fake if r['result']=='✅')
w14 = sum(1 for r in v14_fake if r['result']=='✅')
same = sum(1 for i,r in enumerate(v13_fake) if r['c_code']==v14_fake[i]['c_code'])
tot = len(v13_fake)

for v13r, v14r in zip(v13_fake, v14_fake):
    print(f'{v13r["dt"]:>10} | {v13r["c_name"]:>10}({v13r["c_code"]}) | {v13r["c_nh"]:>+7.1f}% | {v14r["c_name"]:>10}({v14r["c_code"]}) | {v14r["c_nh"]:>+7.1f}% | V13:{v13r["result"]} V14:{v14r["result"]}')
    print(f'{"":>10}   V13亚:{v13r["s_name"]}({v13r["s_code"]}){v13r["s_nh"]:+.1f}%  V14亚:{v14r["s_name"]}({v14r["s_code"]}){v14r["s_nh"]:+.1f}%')

print(f'\nV13 虚涨日: {w13}/{tot} = {w13*100//tot}%')
print(f'V14 虚涨日: {w14}/{tot} = {w14*100//tot}%')
print(f'冠军相同: {same}/{tot} = {same*100//tot}%')
print('✅ 完成')
