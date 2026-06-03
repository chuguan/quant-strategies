"""策略库构建：逐月最优策略 + 市场特征"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

def get_best_params(mdates):
    """搜当月最优选股+评分"""
    best_w=0; best_p=None
    for p_min,p_max in [(4,9),(5,8)]:
     for vr_min,vr_max in [(0.6,2.5),(0.8,2.0)]:
      for hsl_min,hsl_max in [(3,20),(5,15)]:
       for sz_max in [200,300]:
        for cl_min,cl_max in [(50,95),(60,90)]:
         for j_max in [100,120]:
            wins=0; nd=0
            for dt in mdates:
                cand=[]
                for s in data.get(dt,[]):
                    code=s['code'];p=s['p']
                    if p<p_min or p>p_max: continue
                    vr=s.get('vol_ratio',0) or 0
                    if vr<vr_min or vr>vr_max: continue
                    ri=real.get(code)
                    if not ri: continue
                    hsl=(ri.get('hsl',0) or 0)
                    if hsl<hsl_min or hsl>hsl_max: continue
                    sz=(ri.get('shizhi',0) or 0)
                    if sz>=sz_max: continue
                    nm=names.get(code,'')
                    if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                    jv=s.get('j_val',0) or 0
                    if jv>j_max: continue
                    cl=s.get('cl',0)
                    if cl<cl_min or cl>cl_max: continue
                    nh=s.get('n',0) or 0
                    if nh<=0: continue
                    buy=s.get('close',0); dif=s.get('dif_val',0) or 0
                    macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
                    is_yang=s.get('is_yang',0); close=s.get('close',0)
                    ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
                    
                    macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                    ps2=min(10,max(1,11-buy/10))
                    hsl_b=2*0.3 if 5<=hsl<=7 else 0
                    duotou_b=3*0.3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
                    
                    # 评分公式
                    score=p*2.5+cl*0.1+ps2*0.3+macd_s*0.3+3*above5+hsl_b+duotou_b
                    
                    cand.append((score,nh,p))
                if not cand: continue
                cand.sort(key=lambda x:(-x[0], -x[2]))
                nd+=1
                if cand[0][1]>=2.5: wins+=1
            rate=wins*100/nd if nd else 0
            if rate>best_w:
                best_w=rate; best_p=(p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max,j_max,wins,nd)
    return best_p

# 构建策略库
print("构建逐月策略库...", flush=True)
strategy_lib={}

for month in sorted(set(d[:7] for d in dates)):
    mdates=[d for d in dates if d.startswith(month)]
    bp=get_best_params(mdates)
    if bp:
        # 当月市场特征
        avg_p=[]; avg_vr=[]; avg_hsl=[]; cand_cnt=[]
        for dt in mdates:
            cn=0
            for s in data.get(dt,[]):
                cn+=1
                avg_p.append(s.get('p',0) or 0)
                avg_vr.append(s.get('vol_ratio',0) or 0)
                ri=real.get(s['code'])
                if ri: avg_hsl.append(ri.get('hsl',0) or 0)
            cand_cnt.append(cn)
        
        features={
            'avg_p': sum(avg_p)/len(avg_p) if avg_p else 0,
            'avg_vr': sum(avg_vr)/len(avg_vr) if avg_vr else 0,
            'avg_hsl': sum(avg_hsl)/len(avg_hsl) if avg_hsl else 0,
            'active_stocks': sum(cand_cnt)/len(cand_cnt) if cand_cnt else 0,
            'days': len(mdates)
        }
        
        strategy_lib[month]={
            'params': {'p_min':bp[0],'p_max':bp[1],'vr_min':bp[2],'vr_max':bp[3],
                      'hsl_min':bp[4],'hsl_max':bp[5],'sz_max':bp[6],'cl_min':bp[7],
                      'cl_max':bp[8],'j_max':bp[9]},
            'win_rate': bp[10]*100/bp[11] if bp[11] else 0,
            'wins': bp[10], 'days': bp[11],
            'features': features
        }

# 输出策略库
print(f"\n{'='*80}", flush=True)
print(f"{'月份':<10} {'胜率':>6} {'选股条件':<40} {'市均涨':>6} {'均量比':>6} {'均换手':>6}", flush=True)
print('-'*80, flush=True)

for m in sorted(strategy_lib.keys()):
    sl=strategy_lib[m]
    p=sl['params']
    desc=f"涨{p['p_min']}~{p['p_max']}量{p['vr_min']}~{p['vr_max']}换{p['hsl_min']}~{p['hsl_max']}"
    f=sl['features']
    print(f"{m:<10} {sl['win_rate']:>5.1f}% {desc:<40} {f['avg_p']:>+5.1f}% {f['avg_vr']:>5.2f} {f['avg_hsl']:>5.1f}%", flush=True)

# 策略选择器
print(f"\n{'='*80}", flush=True)
print("策略选择器演示：给定市场特征，选最优策略", flush=True)
print('-'*80, flush=True)

def select_strategy(curr_avg_p, curr_avg_vr, curr_active_stocks):
    """给定当前市场特征，找出最匹配的历史月份策略"""
    best_score=99999; best_month=None
    for m,sl in strategy_lib.items():
        f=sl['features']
        # 计算相似度（简单欧氏距离）
        score=abs(curr_avg_p-f['avg_p'])*2+abs(curr_avg_vr-f['avg_vr'])*5+abs(curr_active_stocks-f['active_stocks'])*0.1
        if score<best_score and sl['win_rate']>=50:
            best_score=score; best_month=m
    return best_month, strategy_lib[best_month] if best_month else None

# 演示：不同行情选什么策略
for label, ap, avr, act in [("📈大涨日",2.5,1.5,1800),("📉大跌日",-2.0,1.2,1500),("➡横盘",0.2,1.0,1700)]:
    m,sl=select_strategy(ap,avr,act)
    if sl:
        p=sl['params']
        print(f"{label:<12} → 选{m}策略(胜率{sl['win_rate']:.0f}%) 选股:涨{p['p_min']}~{p['p_max']}量{p['vr_min']}~{p['vr_max']}", flush=True)
