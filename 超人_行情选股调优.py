"""全优化：每行情的选股条件+评分公式"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

# 分行情
mkt_sets={'up':[],'down':[],'flat':[]}
for dt in dates:
    st=data.get(dt,[])
    if not st: continue
    ap=[x['p'] for x in st if 'p' in x]
    am=sum(ap)/len(ap) if ap else 0
    if am>0.5: mkt_sets['up'].append(dt)
    elif am<-0.5: mkt_sets['down'].append(dt)
    else: mkt_sets['flat'].append(dt)

print(f"涨日:{len(mkt_sets['up'])} 跌日:{len(mkt_sets['down'])} 横盘:{len(mkt_sets['flat'])}", flush=True)

def run_test(mkt_dates, p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max,
             cl_w,p_w,ma5_b,macd_w):
    """单行情回测"""
    wins=0; nd=0
    for dt in mkt_dates:
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
            score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5
            
            cand.append((score,nh,p))
        if not cand: continue
        cand.sort(key=lambda x:(-x[0], -x[2]))
        nd+=1
        if cand[0][1]>=2.5: wins+=1
    return wins, nd

# 每个行情单独搜最优参数
for mkt_name in ['down','flat','up']:
    mkt_dates=mkt_sets[mkt_name]
    if len(mkt_dates)<10: continue
    print(f"\n{'='*50}\n【{mkt_name}】{len(mkt_dates)}天 搜索最优参数", flush=True)
    
    best_w=0; best_p=None
    for p_min,p_max in [(4,9),(5,8),(5,9)]:
     for vr_min,vr_max in [(0.6,2.5),(0.8,2.0),(0.8,1.5)]:
      for hsl_min,hsl_max in [(3,20),(5,15),(5,12)]:
       for sz_max in [200,300,500]:
        for cl_min,cl_max in [(50,95),(60,90),(60,85),(55,90)]:
         for cl_w in [0.05,0.1,0.2]:
          for p_w in [2.0,2.5,3.0]:
           for ma5_b in [0,3,5]:
            for macd_w in [0.3,0.5]:
                w,n=run_test(mkt_dates,p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max,cl_w,p_w,ma5_b,macd_w)
                rate=w*100/n if n else 0
                if rate>best_w:
                    best_w=rate; best_p=(p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max,cl_w,p_w,ma5_b,macd_w,w,n)
    
    if best_p:
        print(f"最优胜率: {best_p[12]}/{best_p[13]}({best_w:.1f}%)", flush=True)
        print(f"选股: 涨{best_p[0]}~{best_p[1]}/量{best_p[2]}~{best_p[3]}/换{best_p[4]}~{best_p[5]}/市值<{best_p[6]}/CL{best_p[7]}~{best_p[8]}", flush=True)
        print(f"评分: CL×{best_p[9]}+涨×{best_p[10]}+MA5+{best_p[11]}+MACD×{best_p[14]}", flush=True)
