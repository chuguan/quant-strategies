"""
横盘 V7b 专用优化 — 30000次
"""
import pickle, os, sys, copy, random, json, importlib
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
IDX_FILE = os.path.join(SCRIPTS_DIR, '分而治之_日期索引.pkl')
fp = os.path.join(SCRIPTS_DIR, '分而治之_横盘_评分策略.py')
sys.path.insert(0, SCRIPTS_DIR)

with open(IDX_FILE, 'rb') as f:
    di = pickle.load(f)
daily = di['daily']; dates = di['dates']; kline = di['kline']
market_names = {'flat':'横盘'}

def classify(stocks):
    if not stocks: return 'flat'
    ps=[s.get('p',0) for s in stocks]; vrs=[s.get('vr',0) for s in stocks if s.get('vr',0)]
    if not ps: return 'flat'
    ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

def get_nd_high(code, dt, kline):
    kd=kline.get(code)
    if not kd: return None
    d8=dt.replace('-','')
    ads=sorted([d for d in kd.keys() if len(d)==8 and d.isdigit()])
    try: idx=ads.index(d8)
    except: return None
    if idx+1>=len(ads): return None
    bc=kd.get(d8,{}).get('c',0)
    if bc<=0: return None
    return round((kd[ads[idx+1]]['h']/bc-1)*100,2)

mkt_dates={'flat':[]}
for dt in dates:
    ss=[s for s in daily.get(dt,[]) if abs(s.get('p',0))<9.98]
    if ss and classify(ss)=='flat': mkt_dates['flat'].append(dt)

spec=importlib.util.spec_from_file_location('s_flat',fp)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
levels=mod.LEVELS

def calc_score(s, p):
    score=0
    if p.get('use_p',1): score+=s.get('p',0)*p.get('p_w',1)
    cl=s.get('cl',50)
    if p.get('use_cl',1):
        score+=cl*p.get('cl_w',0.05)
        for z in p.get('cl_zones',[]):
            if len(z)==3 and z[0]<=cl<=z[1]: score+=z[2]
    vr=s.get('vr',1)
    if p.get('use_vr',1):
        for z in p.get('vr_zones',[]):
            if len(z)==3 and z[0]<=vr<=z[1]: score+=z[2]
    dif=s.get('dif',0); mg=s.get('mg',0)
    if p.get('use_macd',1):
        ms=0
        if mg and dif>0.5: ms=10
        elif mg and dif>0.2: ms=8
        elif mg: ms=6
        elif dif>0.5: ms=4
        elif dif>0: ms=2
        score+=ms*p.get('macd_w',0.3)
        if dif>p.get('dif_thresh',0.5): score+=p.get('dif_bonus',0)
    if p.get('use_a5',0) and s.get('a5',0): score+=p.get('a5_b',0)
    wrv=s.get('wrv',50)
    if p.get('use_wr',0):
        if wrv<p.get('wr_lo',25): score+=p.get('wr_lo_b',0)
        if wrv>p.get('wr_hi',75): score+=p.get('wr_hi_b',0)
    jv=s.get('jv',50); kv=s.get('kv',50); dv=s.get('dv',50)
    if p.get('use_kdj',0):
        if jv>kv>dv: score+=p.get('j_golden_b',0)
        if p.get('j_lo',20)<=jv<=p.get('j_hi',40): score+=p.get('j_zone_b',0)
        if jv<p.get('j_super_lo',15): score+=p.get('j_super_b',0)
    if p.get('use_kdj_g',0) and s.get('kdj_g',0): score+=p.get('kdj_g_b',0)
    pos=s.get('pos_in_day',50)
    if p.get('use_pos',0):
        if pos>p.get('pos_hi',85): score+=p.get('pos_hi_pen',-2)
        if pos<p.get('pos_lo',30): score+=p.get('pos_lo_b',0)
    return round(score,1)

def backtest(regime, levels, params):
    wins=total=0
    targets=mkt_dates[regime][-30:] if len(mkt_dates[regime])>=30 else mkt_dates[regime]
    for dt in targets:
        ss=[s for s in daily.get(dt,[]) if abs(s.get('p',0))<9.98]
        if not ss: continue
        cands=[]
        for lv in levels:
            pool=[s for s in ss if lv.get('p_min',-10)<=s.get('p',0)<=lv.get('p_max',8) and s.get('p',0)<8]
            if len(pool)>=8: cands=pool[:200]; break
        if not cands: continue
        scored=[(calc_score(s,params), s) for s in cands]
        scored.sort(key=lambda x:-x[0])
        if not scored: continue
        nh=get_nd_high(scored[0][1]['code'],dt,kline)
        if nh is not None and nh>=2.5: wins+=1
        total+=1
    return wins,total,round(wins*100/total,1) if total else 0

# 预计算池子加速
flat_dates = mkt_dates['flat'][-30:]
flat_pools = {}
for dt in flat_dates:
    ss=[s for s in daily.get(dt,[]) if abs(s.get('p',0))<9.98]
    cands=[]
    for lv in levels:
        pool=[s for s in ss if lv.get('p_min',-10)<=s.get('p',0)<=lv.get('p_max',8) and s.get('p',0)<8]
        if len(pool)>=8: cands=pool[:200]; break
    if cands: flat_pools[dt]=cands

def bt_fast(params, dt_list):
    wins=total=0
    for dt in dt_list:
        pool=flat_pools.get(dt,[])
        if not pool: continue
        scored=[(calc_score(s,params),s) for s in pool]
        scored.sort(key=lambda x:-x[0])
        nh=scored[0][1].get('_nd_high')
        if nh is None:
            nh=get_nd_high(scored[0][1]['code'],dt,kline)
            scored[0][1]['_nd_high']=nh
        if nh is not None:
            total+=1
            if nh>=2.5: wins+=1
    return wins,total,round(wins*100/total,1) if total else 0

print(f"📊 横盘: 30000次 (加速版)")
best_rate=0; best_p=None; best_levels=levels

for i in range(30000):
    p={'use_p':1, 'p_w':random.choice([0.05,0.08,0.1,0.12,0.15,0.2]),
       'use_cl':1, 'cl_w':random.choice([0.03,0.04,0.05,0.06,0.08]),
       'use_vr':random.choice([0,1]),
       'use_macd':0,'macd_w':0.1,'dif_bonus':0,'dif_thresh':0.5,
       'use_a5':1,'a5_b':random.choice([1,2,3,4]),
       'use_wr':random.choice([0,1]),
       'use_kdj':random.choice([0,1]),
       'use_pos':random.choice([0,1]),
       'cl_zones':[],'vr_zones':[],
       'wr_lo':20,'wr_lo_b':0,'wr_hi':80,'wr_hi_b':0,
       'j_golden_b':0,'j_zone_b':0,'j_super_b':0,'j_super_lo':15,
       'use_kdj_g':0,'kdj_g_b':0,
       'pos_hi_pen':0,'pos_lo_b':0}
    if p['use_vr']:
        p['vr_zones']=[[0.8,1.8,random.choice([1,2,3,5])]]
        if random.random()<0.3: p['vr_zones'].append([0.5,0.8,random.choice([1,2])])
    if p['use_wr']:
        p['wr_lo']=random.choice([15,20,25])
        p['wr_lo_b']=random.choice([1,2,3,5])
    if p['use_kdj']:
        p['use_kdj_g']=random.choice([0,1])
        p['kdj_g_b']=random.choice([1,2,3]) if p['use_kdj_g'] else 0
        p['j_golden_b']=random.choice([0,1,2])
    if p['use_pos']:
        p['pos_hi_pen']=random.choice([-5,-3,-2,0])
        p['pos_lo_b']=random.choice([0,1,2])
    if random.random()<0.4:
        p['cl_zones']=[[90,100,random.choice([1,2,3])]]
    
    _,_,rate=bt_fast(p,list(flat_pools.keys()))
    if rate>best_rate:
        best_rate=rate; best_p=copy.deepcopy(p)
        print(f"  [{i}] {rate}%  p_w={p['p_w']} cl_w={p['cl_w']} a5={p['a5_b']} vr={p.get('vr_zones')} wr={p.get('wr_lo_b')} kdj_g={p.get('kdj_g_b')}")
        if rate>=75: break

print(f"\n🏆 最优: {best_rate}%")
if best_p:
    print(json.dumps(best_p,indent=2))
    # 部署
    p_str=json.dumps(best_p,indent=4)
    l_str=json.dumps(best_levels,indent=4)
    content=f'''"""\n横盘 V7b优化 — 自动生成\n胜率: {best_rate}%\n"""\nNAME = "横盘策略 V7b"\nMARKET = "flat"\n\nPARAMS = {p_str}\n\nLEVELS = {l_str}\n\nBACKTEST = "v7b_{best_rate}%"\n\ndef score(stock):\n    s=stock; p=PARAMS\n    score=0\n    if p.get('use_p',1): score+=s.get('p',0)*p.get('p_w',1)\n    cl=s.get('cl',50)\n    if p.get('use_cl',1):\n        score+=cl*p.get('cl_w',0.05)\n        for z in p.get('cl_zones',[]):\n            if len(z)==3 and z[0]<=cl<=z[1]: score+=z[2]\n    vr=s.get('vr',1)\n    if p.get('use_vr',1):\n        for z in p.get('vr_zones',[]):\n            if len(z)==3 and z[0]<=vr<=z[1]: score+=z[2]\n    dif=s.get('dif',0); mg=s.get('mg',0)\n    if p.get('use_macd',1):\n        ms=0\n        if mg and dif>0.5: ms=10\n        elif mg and dif>0.2: ms=8\n        elif mg: ms=6\n        elif dif>0.5: ms=4\n        elif dif>0: ms=2\n        score+=ms*p.get('macd_w',0.3)\n        if dif>p.get('dif_thresh',0.5): score+=p.get('dif_bonus',0)\n    if p.get('use_a5',0) and s.get('a5',0): score+=p.get('a5_b',0)\n    wrv=s.get('wrv',50)\n    if p.get('use_wr',0):\n        if wrv<p.get('wr_lo',25): score+=p.get('wr_lo_b',0)\n        if wrv>p.get('wr_hi',75): score+=p.get('wr_hi_b',0)\n    jv=s.get('jv',50); kv=s.get('kv',50); dv=s.get('dv',50)\n    if p.get('use_kdj',0):\n        if jv>kv>dv: score+=p.get('j_golden_b',0)\n        if p.get('j_lo',20)<=jv<=p.get('j_hi',40): score+=p.get('j_zone_b',0)\n        if jv<p.get('j_super_lo',15): score+=p.get('j_super_b',0)\n    if p.get('use_kdj_g',0) and s.get('kdj_g',0): score+=p.get('kdj_g_b',0)\n    pos=s.get('pos_in_day',50)\n    if p.get('use_pos',0):\n        if pos>p.get('pos_hi',85): score+=p.get('pos_hi_pen',-2)\n        if pos<p.get('pos_lo',30): score+=p.get('pos_lo_b',0)\n    return round(score,1)\n'''
    with open(fp,'w',encoding='utf-8') as f: f.write(content)
    print(f"✅ 已部署到 {fp}")
