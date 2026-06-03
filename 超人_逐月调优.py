"""逐月搜索最优选股+评分参数"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

def run_test(mdates,p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max):
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
            if jv>100: continue
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
            
            score=p*2.5+cl*0.1+ps2*0.3+macd_s*0.3+3*above5+hsl_b
            
            cand.append((score,nh,p))
        if not cand: continue
        cand.sort(key=lambda x:(-x[0], -x[2]))
        nd+=1
        if cand[0][1]>=2.5: wins+=1
    return wins, nd

# 所有月份
months = sorted(set(d[:7] for d in dates))
print(f"{'月份':<10} {'天数':>4} {'最优选股':<35} {'胜率':>6}", flush=True)
print('-'*65, flush=True)

for month in months:
    mdates=[d for d in dates if d.startswith(month)]
    best_w=0; best_p=None
    # 尽量搜
    pmins=[4,5]; pmaxs=[8,9]
    vrms=[0.6,0.8]; vrmxs=[2.0,2.5]
    hslms=[3,5]; hslmxs=[12,15,20]
    szmxs=[200,300]
    clms=[50,55,60]; clmxs=[85,90,95]
    
    for p_min in pmins:
     for p_max in pmaxs:
      if p_max-p_min<3: continue
      for vr_min in vrms:
       for vr_max in vrmxs:
        for hsl_min in hslms:
         for hsl_max in hslmxs:
          for sz_max in szmxs:
           for cl_min in clms:
            for cl_max in clmxs:
                w,n=run_test(mdates,p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max)
                rate=w*100/n if n else 0
                if rate>best_w:
                    best_w=rate; best_p=(p_min,p_max,vr_min,vr_max,hsl_min,hsl_max,sz_max,cl_min,cl_max,w,n)
    
    if best_p:
        desc=f"涨{best_p[0]}~{best_p[1]}量{best_p[2]}~{best_p[3]}换{best_p[4]}~{best_p[5]}市值<{best_p[6]}CL{best_p[7]}~{best_p[8]}"
        print(f"{month:<10} {best_p[10]:>4} {desc:<35} {best_p[9]*100/best_p[10]:>5.1f}%", flush=True)
