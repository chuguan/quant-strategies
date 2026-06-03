"""
分而治之 V7b 精准调优 — 基于失败日分析，定向优化涨日和横盘

核心发现：
1. 📈涨日: 成功冠军cl更高(88 vs 82)、wrv更低=超买(17 vs 20)、j更高(69 vs 60)
           → 涨日强者恒强，需加CL、WR超买、KDJ J值
2. ➡️横盘: DIF是最大区分因子！成功avg=2.6 vs 失败avg=0.3！
           → 当前use_macd=0，必须加MACD权重
"""
import pickle, os, sys, copy, random, json, importlib
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
IDX_FILE = os.path.join(SCRIPTS_DIR, '分而治之_日期索引.pkl')
PARAMS_FILE = os.path.join(SCRIPTS_DIR, '分而治之_V7b_PARAMS.json')
HEARTBEAT = os.path.join(SCRIPTS_DIR, '分而治之_调优心跳.txt')
TARGET = 80.0

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
    """针对性搜索 - 基于失败日分析结果"""
    name=market_names[regime]
    print(f"\n📊 {name}: {iters}次定向搜索", flush=True)
    fp=os.path.join(SCRIPTS_DIR,strat_files[regime])
    spec=importlib.util.spec_from_file_location(f's_{regime}',fp)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    levels=mod.LEVELS
    best_p={}; best_rate=0; best_levels=levels
    
    for i in range(iters):
        p = {}
        p['use_p'] = 1
        
        if regime == 'real_up':
            # 涨日: 强者恒强! cl高+超买+高J+高pos → 涨日继续涨
            p['p_w'] = random.choice([0.5, 1, 1.5, 2, 3, 4, 5])
            p['use_cl'] = random.choice([0, 1])
            p['cl_w'] = random.choice([0, 0.02, 0.05, 0.1, 0.15, 0.2])
            p['use_vr'] = random.choice([0, 1])
            p['use_macd'] = 1  # 必开
            p['macd_w'] = random.choice([0.1, 0.3, 0.5, 0.8, 1, 2])
            p['dif_bonus'] = random.choice([0, 2, 5, 8, 10, 15])
            p['dif_thresh'] = random.choice([0.3, 0.5, 0.8, 1.0])
            p['use_a5'] = 1
            p['a5_b'] = random.choice([2, 5, 8, 10, 15, 20])
            p['use_wr'] = random.choice([0, 1])
            p['wr_lo'] = random.choice([15, 20, 25])
            p['wr_lo_b'] = random.choice([0, 2, 5, 8, 10, 15])
            p['use_kdj'] = random.choice([0, 1])
            p['j_golden_b'] = random.choice([0, 2, 5, 8, 10])
            # 高J值加分(涨日强者恒强)
            if random.random() < 0.4:
                p['j_hi'] = random.choice([60, 70, 80])
                p['j_zone_b'] = random.choice([2, 5, 8])
            p['use_pos'] = random.choice([0, 1])
            if p['use_pos']:
                p['pos_lo_b'] = random.choice([0, 2, 5])  # 低pos不奖励
            p['pos_hi_pen'] = random.choice([0, -2, -5])   # 高pos不处罚
            p['cl_zones'] = []
            p['vr_zones'] = []
            # CL zone: 高CL加分(强者恒强在涨日)
            if random.random() < 0.5:
                p['cl_zones'].append([75, 95, random.choice([3, 5, 8, 10, 15])])
            if random.random() < 0.3:
                p['cl_zones'].append([55, 75, random.choice([2, 5, 8])])
            # VR zone
            if random.random() < 0.4:
                p['vr_zones'].append([0.8, 1.8, random.choice([2, 5, 8, 10])])
                
        elif regime == 'flat':
            # 横盘: DIF是核心! 加MACD+KDJ金叉+WR超卖
            p['p_w'] = random.choice([0.3, 0.5, 0.8, 1.0, 1.5, 2.0])
            p['use_cl'] = random.choice([0, 1])
            p['cl_w'] = random.choice([0, 0.02, 0.05, 0.1, 0.15])
            p['use_vr'] = random.choice([0, 1])
            p['use_macd'] = 1  # 必开！失败日分析验证DIF是关键
            p['macd_w'] = random.choice([1, 2, 3, 5, 8, 10])  # 高权重
            p['dif_bonus'] = random.choice([5, 8, 10, 15, 20, 30])  # DIF bonus高
            p['dif_thresh'] = random.choice([0.3, 0.5, 0.8, 1.0, 1.5])
            p['use_a5'] = 1
            p['a5_b'] = random.choice([2, 5, 8, 10])
            p['use_wr'] = random.choice([0, 1])
            p['wr_lo'] = random.choice([15, 20, 25])
            p['wr_lo_b'] = random.choice([0, 2, 5, 8, 10])
            p['use_kdj'] = random.choice([0, 1])
            p['j_golden_b'] = random.choice([2, 5, 8, 10])
            p['use_kdj_g'] = random.choice([0, 1])
            if p['use_kdj_g']:
                p['kdj_g_b'] = random.choice([3, 5, 8, 10, 15])
            p['use_pos'] = random.choice([0, 1])
            p['pos_hi_pen'] = random.choice([-10, -5, -2, 0])
            p['cl_zones'] = []
            p['vr_zones'] = []
            # 量比活跃加分
            if random.random() < 0.4:
                p['vr_zones'].append([0.8, 2.0, random.choice([3, 5, 8, 10])])
            if random.random() < 0.2:
                p['vr_zones'].append([0.5, 0.8, random.choice([2, 3, 5])])
            # CL mid range加分(有空间)
            if random.random() < 0.3:
                p['cl_zones'].append([50, 80, random.choice([3, 5, 8])])
        
        this_levels = levels
        if random.random() < 0.03 and len(levels) >= 3:
            this_levels = copy.deepcopy(levels)
            this_levels[0]['p_min'] = random.choice([-3, -2, -1, 0, 1, 2])
            this_levels[0]['p_max'] = random.choice([5, 6, 7, 8])
        
        _,_,rate = backtest(regime, this_levels, p)
        
        if rate > best_rate:
            best_p = copy.deepcopy(p)
            best_rate = rate
            best_levels = this_levels
            print(f"  ⬆️ [{i}] {rate}%", flush=True)
            if rate >= TARGET:
                return best_p, best_levels, best_rate, True
        
        if i % 1000 == 0 and i > 0:
            print(f"  ... {i}/{iters} 最佳: {best_rate}%", flush=True)
            with open(HEARTBEAT,'w') as f:
                f.write(f"{datetime.now().isoformat()}|{regime}|{i}/{iters}|{best_rate}")
    
    return best_p, best_levels, best_rate, False

def deploy(regime, params, levels, rate):
    name=market_names[regime]
    fn=os.path.join(SCRIPTS_DIR,strat_files[regime])
    p_str=json.dumps(params,indent=4)
    l_str=json.dumps(levels,indent=4)
    backtest_str=f'"v7b_{rate}%"'
    content=f'''"""\n{name} V7b精准调优 — 基于失败日分析\n生成时间: {datetime.now()}\n胜率: {rate}%\n"""\nNAME = "{name}策略 V7b"\nMARKET = "{regime}"\n\nPARAMS = {p_str}\n\nLEVELS = {l_str}\n\nBACKTEST = {backtest_str}\n\ndef score(stock):\n    s=stock; p=PARAMS\n    score=0\n    if p.get('use_p',1): score+=s.get('p',0)*p.get('p_w',1)\n    cl=s.get('cl',50)\n    if p.get('use_cl',1):\n        score+=cl*p.get('cl_w',0.05)\n        for z in p.get('cl_zones',[]):\n            if len(z)==3 and z[0]<=cl<=z[1]: score+=z[2]\n    vr=s.get('vr',1)\n    if p.get('use_vr',1):\n        for z in p.get('vr_zones',[]):\n            if len(z)==3 and z[0]<=vr<=z[1]: score+=z[2]\n    dif=s.get('dif',0); mg=s.get('mg',0)\n    if p.get('use_macd',1):\n        ms=0\n        if mg and dif>0.5: ms=10\n        elif mg and dif>0.2: ms=8\n        elif mg: ms=6\n        elif dif>0.5: ms=4\n        elif dif>0: ms=2\n        score+=ms*p.get('macd_w',0.3)\n        if dif>p.get('dif_thresh',0.5): score+=p.get('dif_bonus',0)\n    if p.get('use_a5',0) and s.get('a5',0): score+=p.get('a5_b',0)\n    wrv=s.get('wrv',50)\n    if p.get('use_wr',0):\n        if wrv<p.get('wr_lo',25): score+=p.get('wr_lo_b',0)\n        if wrv>p.get('wr_hi',75): score+=p.get('wr_hi_b',0)\n    jv=s.get('jv',50); kv=s.get('kv',50); dv=s.get('dv',50)\n    if p.get('use_kdj',0):\n        if jv>kv>dv: score+=p.get('j_golden_b',0)\n        if p.get('j_lo',20)<=jv<=p.get('j_hi',40): score+=p.get('j_zone_b',0)\n        if jv<p.get('j_super_lo',15): score+=p.get('j_super_b',0)\n    if p.get('use_kdj_g',0) and s.get('kdj_g',0): score+=p.get('kdj_g_b',0)\n    pos=s.get('pos_in_day',50)\n    if p.get('use_pos',0):\n        if pos>p.get('pos_hi',85): score+=p.get('pos_hi_pen',-2)\n        if pos<p.get('pos_lo',30): score+=p.get('pos_lo_b',0)\n    return round(score,1)\n'''
    with open(fn,'w',encoding='utf-8') as f: f.write(content)
    print(f"  ✅ 已部署: {strat_files[regime]} ({rate}%)", flush=True)

# ===== 主 =====
print(f"🚀 分而治之 V7b精准调优 {datetime.now()}", flush=True)
with open(HEARTBEAT,'w') as f: f.write(f"{datetime.now().isoformat()}|start")

# 先加载已有参数
all_params = {}
results = {}

# 1. 跑涨日(30000次)
regime = 'real_up'
if len(mkt_dates[regime]) >= 15:
    bp, bl, br, ok = run_search(regime, 30000)
    results[regime] = br
    all_params[regime] = {'params': bp, 'levels': bl, 'rate': br}
    deploy(regime, bp, bl, br)

# 2. 跑横盘(30000次)
regime = 'flat'
if len(mkt_dates[regime]) >= 15:
    bp, bl, br, ok = run_search(regime, 30000)
    results[regime] = br
    all_params[regime] = {'params': bp, 'levels': bl, 'rate': br}
    deploy(regime, bp, bl, br)

# 3. 保留跌日和虚涨日
for reg_name, file_name in [('down','分而治之_跌日_评分策略.py'), ('fake_up','分而治之_虚涨日_评分策略.py')]:
    if reg_name not in all_params:
        fp = os.path.join(SCRIPTS_DIR, file_name)
        if os.path.exists(fp):
            spec = importlib.util.spec_from_file_location(f'_{reg_name}', fp)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            rate = 0
            if hasattr(mod, 'BACKTEST'):
                try: rate = float(mod.BACKTEST.split('_')[-1].replace('%',''))
                except: pass
            all_params[reg_name] = {'params': mod.PARAMS, 'levels': mod.LEVELS, 'rate': rate}
            results[reg_name] = rate

# 保存JSON
with open(PARAMS_FILE,'w',encoding='utf-8') as f:
    json.dump(all_params, f, ensure_ascii=False, indent=2)
print(f"\n💾 参数已更新: {PARAMS_FILE}", flush=True)

print(f"\n{'='*50}")
print(f"V7b精准调优完成!", flush=True)
for reg in ['real_up','fake_up','down','flat']:
    if reg in results:
        emoji = '✅' if results[reg] >= TARGET else '❌'
        print(f"  {emoji} {market_names[reg]}: {results[reg]}%")
print(f"  达标: {sum(1 for r in results.values() if r>=TARGET)}/4", flush=True)
