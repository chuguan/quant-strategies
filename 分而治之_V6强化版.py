"""分而治之 V6强化版 — 15000次/行情找回V5水平"""
import pickle, os, sys, copy, random, json, importlib
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
IDX_FILE = os.path.join(SCRIPTS_DIR, '分而治之_日期索引.pkl')
PARAMS_FILE = os.path.join(SCRIPTS_DIR, '分而治之_V5_FINAL_PARAMS.json')
HEARTBEAT = os.path.join(SCRIPTS_DIR, '分而治之_调优心跳.txt')
TARGET = 85.0

sys.path.insert(0, SCRIPTS_DIR)
with open(IDX_FILE, 'rb') as f: di = pickle.load(f)
daily = di['daily']; dates = di['dates']; kline = di['kline']

market_names = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
strat_files = {
    'real_up': '分而治之_真实涨日_评分策略.py',
    'fake_up': '分而治之_虚涨日_评分策略.py',
    'down': '分而治之_跌日_评分策略.py',
    'flat': '分而治之_横盘_评分策略.py',
}

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

mkt_dates={reg:[] for reg in market_names}
for dt in dates:
    ss=[s for s in daily.get(dt,[]) if abs(s.get('p',0))<9.98]
    if ss: mkt_dates[classify(ss)].append(dt)

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
        scored=[(calc_score(s,params),s) for s in cands]
        scored.sort(key=lambda x:-x[0])
        if not scored: continue
        nh=get_nd_high(scored[0][1]['code'],dt,kline)
        if nh is not None and nh>=2.5: wins+=1
        total+=1
    return wins,total,round(wins*100/total,1) if total else 0

def run_search(regime, iters):
    name=market_names[regime]
    print(f"\n📊 {name}: {iters}次搜索", flush=True)
    fp=os.path.join(SCRIPTS_DIR,strat_files[regime])
    spec=importlib.util.spec_from_file_location(f's_{regime}',fp)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    levels=mod.LEVELS
    best_p={}; best_rate=0; best_levels=levels
    for i in range(iters):
        p={
            'use_p':1,'p_w':random.choice([0.01,0.05,0.1,0.3,0.5,1,2,3,5,10,20,50,100]),
            'use_cl':random.choice([0,1]),'cl_w':random.choice([0,0.01,0.05,0.1,0.2,0.5,1]),
            'use_vr':random.choice([0,1]),
            'use_macd':random.choice([0,1]),'macd_w':random.choice([0,0.1,0.3,0.5,1,2,5]),
            'dif_bonus':random.choice([0,2,5,10]),
            'use_a5':random.choice([0,1]),'a5_b':random.choice([0,2,5,10,20]),
            'use_wr':random.choice([0,1]),'wr_lo_b':random.choice([0,2,5,10,20]),
            'use_kdj':random.choice([0,1]),'j_golden_b':random.choice([0,2,5,10]),
            'j_zone_b':random.choice([0,2,5,10]),
            'use_pos':random.choice([0,1]),'pos_hi_pen':random.choice([-20,-10,-5,-2,0]),
            'cl_zones':[],'vr_zones':[],
        }
        if random.random()<0.3: p['cl_zones'].append([65,83,random.choice([1,3,5,10])])
        if random.random()<0.2: p['cl_zones'].append([50,75,random.choice([1,3,5,10])])
        if random.random()<0.15: p['cl_zones'].append([0,20,random.choice([3,5,10,20])])
        if random.random()<0.3: p['vr_zones'].append([1.0,1.5,random.choice([1,3,5,10])])
        if random.random()<0.2: p['vr_zones'].append([0.6,1.0,random.choice([1,3,5,10])])
        this_levels=levels
        if random.random()<0.05 and len(levels)>=3:
            this_levels=copy.deepcopy(levels)
            this_levels[0]['p_min']=random.choice([-3,-2,-1,0,1,2,3,5])
            this_levels[0]['p_max']=random.choice([5,6,7,8])
        _,_,rate=backtest(regime,this_levels,p)
        if rate>best_rate:
            best_p=copy.deepcopy(p); best_rate=rate; best_levels=this_levels
            print(f"  ⬆️ [{i}] {rate}%", flush=True)
            if rate>=TARGET: return best_p,best_levels,best_rate,True
        if i%500==0 and i>0:
            print(f"  ... {i}/{iters} 最佳: {best_rate}%", flush=True)
            with open(HEARTBEAT,'w') as f: f.write(f"{datetime.now().isoformat()}|{regime}|{i}/{iters}|{best_rate}")
    return best_p,best_levels,best_rate,False

def deploy(regime, params, levels, rate):
    name=market_names[regime]
    fn=os.path.join(SCRIPTS_DIR,strat_files[regime])
    p_str=json.dumps(params,indent=4)
    l_str=json.dumps(levels,indent=4)
    backtest_str=f'"v6_15000_{rate}%"'
    content=f'''"""
{name} V5通用评分策略 — 由调优自动生成 v6(15000次)
生成时间: {datetime.now()}
胜率: {rate}%
"""
NAME = "{name}策略 V6"
MARKET = "{regime}"

PARAMS = {p_str}

LEVELS = {l_str}

BACKTEST = {backtest_str}

def score(stock):
    s=stock; p=PARAMS
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
'''
    with open(fn,'w',encoding='utf-8') as f: f.write(content)
    print(f"  ✅ 已部署: {strat_files[regime]} ({rate}%)", flush=True)

# ===== 主 =====
print(f"🚀 分而治之 V6强化版 15000次/行情 {datetime.now()}", flush=True)
with open(HEARTBEAT,'w') as f: f.write(f"{datetime.now().isoformat()}|start")

results={}; all_params={}
# 只跑跌日和横盘（涨日和虚涨日V6已达V5水平）
for regime in ['down', 'flat']:
    if len(mkt_dates[regime])<20:
        print(f"❌ {market_names[regime]}: 数据不足", flush=True); continue
    bp,bl,br,ok=run_search(regime, 15000)
    results[regime]=br
    all_params[regime]={'params':bp,'levels':bl,'rate':br}
    print(f"  → 最终: {br}%{' ✅' if ok else ' ❌'}", flush=True)

# 加载之前V6已保存的涨日和虚涨日参数
existing={}
if os.path.exists(PARAMS_FILE):
    with open(PARAMS_FILE,'r',encoding='utf-8') as f: existing=json.load(f)
for reg in ['real_up','fake_up']:
    if reg in existing:
        all_params[reg]=existing[reg]
        results[reg]=existing[reg]['rate']

# 更新JSON
with open(PARAMS_FILE,'w',encoding='utf-8') as f:
    json.dump(all_params,f,ensure_ascii=False,indent=2)
print(f"\n💾 参数已更新: {PARAMS_FILE}", flush=True)

# 部署所有
print(f"\n🔄 部署全部4个策略文件...", flush=True)
for regime in all_params:
    deploy(regime, all_params[regime]['params'], all_params[regime]['levels'], all_params[regime]['rate'])

print(f"\n{'='*50}")
print(f"V6强化版完成!", flush=True)
for reg,rate in results.items():
    emoji='✅' if rate>=TARGET else '❌'
    print(f"  {emoji} {market_names[reg]}: {rate}%")
print(f"  达标: {sum(1 for r in results.values() if r>=TARGET)}/4", flush=True)
