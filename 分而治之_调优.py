"""分而治之 终极调优 v5 — 连LEVEL筛选条件一起调"""
import pickle, os, sys, copy, itertools, time, re, random
from datetime import datetime

SCRIPTS_DIR=os.path.expanduser('~/AppData/Local/hermes/scripts')
IDX_FILE=os.path.join(SCRIPTS_DIR,'分而治之_日期索引.pkl')
HEARTBEAT=os.path.join(SCRIPTS_DIR,'分而治之_调优心跳.txt')
RESULT=os.path.join(SCRIPTS_DIR,'分而治之_调优结果.txt')
TARGET=85.0

sys.path.insert(0, SCRIPTS_DIR)
with open(IDX_FILE,'rb') as f: di=pickle.load(f)

market_names={'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
strat_names={'real_up':'分而治之_真实涨日_评分策略','fake_up':'分而治之_虚涨日_评分策略',
             'down':'分而治之_跌日_评分策略','flat':'分而治之_横盘_评分策略'}

def get_nd_high(code,dt,kline):
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

def classify(stocks):
    if not stocks: return 'flat'
    ps=[s.get('p',0) for s in stocks]; vrs=[s.get('vr',0) for s in stocks if s.get('vr',0)]
    if not ps: return 'flat'
    ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

daily=di['daily']; dates=di['dates']; kline=di['kline']

# 预分类
mkt_dates={reg:[] for reg in market_names}
for dt in dates:
    ss=[s for s in daily.get(dt,[]) if abs(s.get('p',0))<9.98]
    if ss: mkt_dates[classify(ss)].append(dt)

def backtest(regime, levels, score_params):
    """完全灵活的评分+筛选回测"""
    wins=total=0
    targets=mkt_dates[regime][-30:] if len(mkt_dates[regime])>=30 else mkt_dates[regime]
    for dt in targets:
        ss=[s for s in daily.get(dt,[]) if abs(s.get('p',0))<9.98]
        if not ss: continue
        cands=[]
        for lv in levels:
            pool=[s for s in ss if lv.get('p_min',-10)<=s.get('p',0)<=lv.get('p_max',8) and s.get('p',0)<8]
            if len(pool)>=8: cands=pool[:200]; break
        if not cands: cands=[s for s in ss if -10<=s.get('p',0)<8][:200]
        if not cands: continue
        
        scored=[(calc_score_gen(s,regime,score_params),s) for s in cands]
        scored.sort(key=lambda x:-x[0])
        if not scored: continue
        nh=get_nd_high(scored[0][1]['code'],dt,kline)
        if nh is not None and nh>=2.5: wins+=1
        total+=1
    return wins,total,round(wins/total*100,1) if total else 0

def calc_score_gen(s, regime, p):
    """通用评分 — 所有参数在p字典里"""
    score=0
    # 涨幅加分
    if p.get('use_p',1):
        score+=s.get('p',0)*p.get('p_w',1)
    # CL加分
    cl=s.get('cl',50)
    if p.get('use_cl',1):
        score+=cl*p.get('cl_w',0.05)
        for zone in p.get('cl_zones',[]):
            if len(zone)==3 and zone[0]<=cl<=zone[1]: score+=zone[2]
    # 量比加分
    vr=s.get('vr',1)
    if p.get('use_vr',1):
        for zone in p.get('vr_zones',[]):
            if len(zone)==3 and zone[0]<=vr<=zone[1]: score+=zone[2]
    # dif/MACD
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
    # MA5
    if p.get('use_a5',0) and s.get('a5',0):
        score+=p.get('a5_b',0)
    # WR
    wrv=s.get('wrv',50)
    if p.get('use_wr',0):
        if wrv<p.get('wr_lo',25): score+=p.get('wr_lo_b',0)
        if wrv>p.get('wr_hi',75): score+=p.get('wr_hi_b',0)
    # KDJ J值
    jv=s.get('jv',50); kv=s.get('kv',50); dv=s.get('dv',50)
    if p.get('use_kdj',0):
        if jv>kv>dv: score+=p.get('j_golden_b',0)
        if p.get('j_lo',20)<=jv<=p.get('j_hi',40): score+=p.get('j_zone_b',0)
        if jv<p.get('j_super_lo',15): score+=p.get('j_super_b',0)
    # KDJ金叉
    if p.get('use_kdj_g',0) and s.get('kdj_g',0):
        score+=p.get('kdj_g_b',0)
    # pos_in_day
    pos=s.get('pos_in_day',50)
    if p.get('use_pos',0):
        if pos>p.get('pos_hi',85): score+=p.get('pos_hi_pen',-2)
        if pos<p.get('pos_lo',30): score+=p.get('pos_lo_b',0)
    return round(score,1)

def run_search(regime):
    """随机搜索（评分参数+LEVELS联合调优）"""
    name=market_names[regime]
    
    # 加载当前LEVELS
    mod=__import__(strat_names[regime]); __import__('importlib').reload(mod)
    levels=mod.LEVELS
    
    # 随机参数搜索
    print(f"\n📊 {name}: 终极调优", flush=True)
    
    best_p={}; best_rate=0; best_levels=levels
    
    for i in range(15000):
        # 随机生成评分参数
        p = {
            'use_p':1, 'p_w': random.choice([0.01,0.05,0.1,0.3,0.5,1,2,3,5,10,20,50,100]),
            'use_cl': random.choice([0,1]), 'cl_w': random.choice([0,0.01,0.05,0.1,0.2,0.5,1]),
            'use_vr': random.choice([0,1]),
            'use_macd': random.choice([0,1]), 'macd_w': random.choice([0,0.1,0.3,0.5,1,2,5]),
            'dif_bonus': random.choice([0,2,5,10]),
            'use_a5': random.choice([0,1]), 'a5_b': random.choice([0,2,5,10,20]),
            'use_wr': random.choice([0,1]), 'wr_lo_b': random.choice([0,2,5,10,20]),
            'use_kdj': random.choice([0,1]), 'j_golden_b': random.choice([0,2,5,10]),
            'j_zone_b': random.choice([0,2,5,10]),
            'use_pos': random.choice([0,1]), 'pos_hi_pen': random.choice([-20,-10,-5,-2,0]),
        }
        # CL区域加分
        cl_zones=[]
        if random.random()<0.3: cl_zones.append([65,83,random.choice([1,3,5,10])])
        if random.random()<0.2: cl_zones.append([50,75,random.choice([1,3,5,10])])
        if random.random()<0.15: cl_zones.append([0,20,random.choice([3,5,10,20])])
        p['cl_zones']=cl_zones
        
        # VR区域
        vr_zones=[]
        if random.random()<0.3: vr_zones.append([1.0,1.5,random.choice([1,3,5,10])])
        if random.random()<0.2: vr_zones.append([0.6,1.0,random.choice([1,3,5,10])])
        p['vr_zones']=vr_zones
        
        # 偶尔改LEVELS筛选
        this_levels=levels
        if random.random()<0.05 and len(levels)>=3:
            this_levels=copy.deepcopy(levels)
            lv=this_levels[0]  # 改最严格级
            lv['p_min']=random.choice([-3,-2,-1,0,1,2,3,5])
            lv['p_max']=random.choice([5,6,7,8])
        
        _,_,rate=backtest(regime,this_levels,p)
        
        if rate>best_rate:
            best_p=copy.deepcopy(p); best_rate=rate; best_levels=this_levels
            print(f"  ⬆️ [{i}] {rate}%", flush=True)
            if rate>=TARGET:
                return best_p,best_levels,best_rate,True
        
        if i%200==0:
            with open(HEARTBEAT,'w') as f:
                f.write(f"{datetime.now().isoformat()}|{regime}|{i}/5000|{best_rate}")
    
    return best_p,best_levels,best_rate,False

# ===== 主 =====
print(f"🚀 分而治之 终极调优 v5 {datetime.now()}", flush=True)
with open(HEARTBEAT,'w') as f: f.write(f"{datetime.now().isoformat()}|start")

results={}
all_done=True
for regime in ['real_up','fake_up','down','flat']:
    if len(mkt_dates[regime])<20:
        print(f"❌ {market_names[regime]}: 数据不足", flush=True)
        results[regime]=0; continue
    
    best_p,best_levels,best_rate,ok=run_search(regime)
    results[regime]=best_rate
    if not ok: all_done=False
    
    print(f"  → 最佳: {best_rate}%{' ✅' if ok else ' ❌'}", flush=True)

print(f"\n{'='*50}", flush=True)
for k,v in results.items():
    print(f"  {market_names[k]}: {v}%{' ✅' if v>=TARGET else ' ❌'}", flush=True)
print(f"  达标: {sum(1 for v in results.values() if v>=TARGET)}/4", flush=True)

with open(RESULT,'w') as f:
    f.write(f"{datetime.now().isoformat()}\n{sum(1 for v in results.values() if v>=TARGET)}/4\n")
    for k,v in results.items(): f.write(f"{k}: {v}%\n")

if not all_done: sys.exit(1)
