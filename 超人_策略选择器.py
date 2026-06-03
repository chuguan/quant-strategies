"""精细化策略选择器：丰富市场特征+动态匹配"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

# ===== 1. 构建逐月最优策略 =====
def get_best(mdates):
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
                    macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                    ps2=min(10,max(1,11-buy/10))
                    score=p*2.5+cl*0.1+ps2*0.3+macd_s*0.3+3*above5
                    cand.append((score,nh,p))
                if not cand: continue
                cand.sort(key=lambda x:(-x[0], -x[2]))
                nd+=1
                if cand[0][1]>=2.5: wins+=1
            rate=wins*100/nd if nd else 0
            if rate>best_w:
                best_w=rate; best_p=(p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max,j_max,wins,nd)
    return best_p

# ===== 2. 计算每月丰富特征 =====
def get_market_features(mdates):
    """返回丰富的市场特征"""
    avg_p=[]; up_ratio=[]; big_rise=[]; stock_cnt=[]
    for dt in mdates:
        st=data.get(dt,[]); n=len(st)
        stock_cnt.append(n)
        ps=[s.get('p',0) or 0 for s in st]
        avg_p.append(sum(ps)/n if n else 0)
        up_ratio.append(sum(1 for x in ps if x>0)/n if n else 0)
        big_rise.append(sum(1 for x in ps if x>3)/n if n else 0)
    return {
        'avg_p': sum(avg_p)/len(avg_p),
        'avg_p_std': (sum((x-sum(avg_p)/len(avg_p))**2 for x in avg_p)/len(avg_p))**0.5 if len(avg_p)>1 else 0,
        'up_ratio': sum(up_ratio)/len(up_ratio),
        'big_rise_ratio': sum(big_rise)/len(big_rise),
        'active_stocks': sum(stock_cnt)/len(stock_cnt),
    }

print("构建精细化策略库...", flush=True)
strategy_lib={}
for month in sorted(set(d[:7] for d in dates)):
    mdates=[d for d in dates if d.startswith(month)]
    bp=get_best(mdates)
    if bp and bp[11]>=5:  # 至少5天
        feats=get_market_features(mdates)
        strategy_lib[month]={
            'params': (bp[0],bp[1],bp[2],bp[3],bp[4],bp[5],bp[6],bp[7],bp[8],bp[9]),
            'win_rate': bp[10]*100/bp[11],
            'wins':bp[10],'days':bp[11],
            'features':feats
        }

print(f"共{len(strategy_lib)}个月份策略", flush=True)
for m in sorted(strategy_lib.keys()):
    sl=strategy_lib[m]
    print(f"{m}: {sl['win_rate']:.0f}% 涨{sl['params'][0]}~{sl['params'][1]} 上涨比{sl['features']['up_ratio']:.0%} 大涨比{sl['features']['big_rise_ratio']:.0%}", flush=True)

# ===== 3. 策略选择器 =====
print(f"\n{'='*60}", flush=True)
print("策略选择器（丰富特征版）", flush=True)
print('-'*60, flush=True)

def select_for_today(target_date):
    """为某天选择最优策略"""
    # 用前5天计算近期市场特征
    idx=dates.index(target_date)
    lookback=dates[max(0,idx-4):idx+1]
    curr_feats=get_market_features(lookback)
    
    best_score=999; best_month=None
    for m,sl in strategy_lib.items():
        f=sl['features']
        # 加权距离
        score=abs(curr_feats['avg_p']-f['avg_p'])*3+\
              abs(curr_feats['up_ratio']-f['up_ratio'])*10+\
              abs(curr_feats['big_rise_ratio']-f['big_rise_ratio'])*10+\
              abs(curr_feats['active_stocks']-f['active_stocks'])*0.05
        if score<best_score and sl['win_rate']>=50:
            best_score=score; best_month=m
    
    if best_month:
        return best_month, strategy_lib[best_month]
    return None, None

# 用不同日期的市场演示
for label, days_ago in [("📈近期涨市",-5),("📉近期跌市",-15),("➡当前",-1)]:
    td=dates[dates.index('2026-05-22')+days_ago] if '2026-05-22' in dates else dates[-1]
    # 前5天特征
    idx=dates.index(td)
    lk=dates[max(0,idx-4):idx+1]
    f=get_market_features(lk)
    
    m,sl=select_for_today(td)
    if sl:
        p=sl['params']
        print(f"{label:<12}前5天涨{f['avg_p']:.1f}%涨比{f['up_ratio']:.0%} → 选{m}策略(胜率{sl['win_rate']:.0f}%)", flush=True)
        print(f"           选股:涨{p[0]}~{p[1]}量{p[2]}~{p[3]}换{p[4]}~{p[5]}", flush=True)
