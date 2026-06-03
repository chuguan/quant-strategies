"""4类市场分类 + 各策略调优"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

# ===== 分类当天市场 =====
def classify_market(dt):
    """返回 真实涨/虚涨/跌/横盘"""
    stocks=data.get(dt,[])
    if not stocks: return 'flat'
    
    ps=[s.get('p',0) or 0 for s in stocks]
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    avg_p=sum(ps)/len(ps)
    avg_vr=sum(vrs)/len(vrs) if vrs else 0
    
    # 涨5~8%的股票数和占比
    hot=sum(1 for p in ps if 5<=p<=8)
    hot_ratio=hot/len(ps) if ps else 0
    up_ratio=sum(1 for p in ps if p>0)/len(ps) if ps else 0
    
    if avg_p > 0.5:
        # 涨日：判断真假
        if hot >= 15 and avg_vr >= 0.9:  # 活跃+量能足
            return 'real_up'
        else:
            return 'fake_up'
    elif avg_p < -0.5:
        return 'down'
    else:
        return 'flat'

# ===== 统计各类天数 =====
mkt_counts={k:[] for k in ['real_up','fake_up','down','flat']}
for dt in dates:
    mkt=classify_market(dt)
    mkt_counts[mkt].append(dt)

print("=== 市场分类统计 ===", flush=True)
for k,v in sorted(mkt_counts.items()):
    print(f"{k:<12}: {len(v)}天", flush=True)

# ===== 用缓存n字段回测 =====
def run_test(mkt_dates, p_min=5,p_max=8,vr_min=0.8,vr_max=2.0,hs_min=3,hs_max=12,
             sz=300,cm=50,cx=90,jm=120,p_w=2.5,cl_w=0.1,hsl_b=0,j_b=0,vr_b=0,ma5_b=3,macd_w=0.3):
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
            if hsl<hs_min or hsl>hs_max: continue
            sz2=(ri.get('shizhi',0) or 0)
            if sz2>=sz: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv=s.get('j_val',0) or 0
            if jv>jm: continue
            cl=s.get('cl',0)
            if cl<cm or cl>cx: continue
            nh=s.get('n',0) or 0
            if nh<=0: continue
            buy=s.get('close',0); dif=s.get('dif_val',0) or 0
            macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
            is_yang=s.get('is_yang',0); close=s.get('close',0)
            ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
            
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
            j_plus=j_b if jv>70 else 0
            vr_plus=vr_b*1.5 if 1.2<=vr<=1.5 else 0
            
            score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_plus+vr_plus
            cand.append((score,nh,p))
        if not cand: continue
        cand.sort(key=lambda x:(-x[0], -x[2]))
        nd+=1
        if cand[0][1]>=2.5: wins+=1
    return wins, nd

# ===== 每类市场搜最优 =====
for mkt_name in ['real_up','fake_up','down','flat']:
    mkts=mkt_counts[mkt_name]
    if len(mkts)<5: continue
    
    best_w=0; best_p=None
    # 搜索参数
    for p_min,p_max in [(5,8),(4,9)]:
     for vr_min,vr_max in [(0.8,2.0),(0.6,2.5)]:
      for hs_min,hs_max in [(3,12),(5,15)]:
       for sz in [200,300]:
        for cm,cx in [(50,90),(60,90),(55,85)]:
         for p_w in [2.0,2.5,3.0]:
          for cl_w in [0.05,0.1,0.15]:
           for hsl_b in [0,0.3]:
            for j_b in [0,2]:
             for vr_b in [0,0.3]:
              for ma5_b in [0,3]:
               for macd_w in [0.3,0.5]:
                w,n=run_test(mkts,p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz,cm,cx,120,p_w,cl_w,hsl_b,j_b,vr_b,ma5_b,macd_w)
                rate=w*100/n if n else 0
                if rate>best_w:
                    best_w=rate; best_p=(p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz,cm,cx,p_w,cl_w,hsl_b,j_b,vr_b,ma5_b,macd_w,w,n)
    
    if best_p:
        print(f"\n【{mkt_name}】{len(mkts)}天 最优胜率{best_w:.1f}%", flush=True)
        print(f"  选股:涨{best_p[0]}~{best_p[1]}量{best_p[2]}~{best_p[3]}换{best_p[4]}~{best_p[5]}市值<{best_p[6]}CL{best_p[7]}~{best_p[8]}", flush=True)
        print(f"  评分:涨×{best_p[9]}+CL×{best_p[10]}+换手+{best_p[11]}+J+{best_p[12]}+量比+{best_p[13]}+MA5+{best_p[14]}+MACD×{best_p[15]}", flush=True)
