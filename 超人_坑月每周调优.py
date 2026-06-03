"""坑月逐周调优：3个差月每周找最优评分"""
import pickle, json, os
from datetime import datetime, timedelta
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

def get_week(dt_str):
    """返回周编号 2025-W01"""
    dt=datetime.strptime(dt_str,'%Y-%m-%d')
    iso=dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"

# 坑月
bad_months = {'2025-06':'6月','2025-08':'8月','2025-10':'10月'}

P_BASE = {'p_min':5,'p_max':8,'vr_min':0.8,'vr_max':2.0,
          'hsl_min':3,'hsl_max':12,'sz_max':300,'cl_min':50,'cl_max':90,'j_max':120}

for month, mlabel in bad_months.items():
    mdates=[d for d in dates if d.startswith(month)]
    print(f"\n{'='*60}", flush=True)
    print(f"【{mlabel}】{len(mdates)}天 逐周调优", flush=True)
    print('-'*60, flush=True)
    
    # 按周分组
    weeks={}
    for dt in mdates:
        wk=get_week(dt)
        weeks.setdefault(wk,[]).append(dt)
    
    for wk, wk_dates in sorted(weeks.items()):
        if len(wk_dates)<2: continue
        
        # 对本周搜最优评分权重
        best_w=0; best_ps=None
        # 搜索参数范围
        for cl_w in [0.05,0.1,0.15,0.2]:
         for p_w in [2.0,2.5,3.0]:
          for macd_w in [0.3,0.5]:
           for ma5_b in [0,3,5]:
            for hsl_b in [0,0.3,0.6]:  # 换手5~7加分权重
             for j_bonus in [0,1,2,3]:  # J>70加分
              for vr_bonus in [0,0.3,0.6]:  # 量比1.2~1.5加分
                wins=0; nd=0
                for dt in wk_dates:
                    cand=[]
                    for s in data.get(dt,[]):
                        code=s['code'];p=s['p']
                        if p<P_BASE['p_min'] or p>P_BASE['p_max']: continue
                        vr=s.get('vol_ratio',0) or 0
                        if vr<P_BASE['vr_min'] or vr>P_BASE['vr_max']: continue
                        ri=real.get(code)
                        if not ri: continue
                        hsl=(ri.get('hsl',0) or 0)
                        if hsl<P_BASE['hsl_min'] or hsl>P_BASE['hsl_max']: continue
                        sz=(ri.get('shizhi',0) or 0)
                        if sz>=P_BASE['sz_max']: continue
                        nm=names.get(code,'')
                        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                        jv=s.get('j_val',0) or 0
                        if jv>P_BASE['j_max']: continue
                        cl=s.get('cl',0)
                        if cl<P_BASE['cl_min'] or cl>P_BASE['cl_max']: continue
                        nh=s.get('n',0) or 0
                        if nh<=0: continue
                        buy=s.get('close',0); dif=s.get('dif_val',0) or 0
                        macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
                        is_yang=s.get('is_yang',0); close=s.get('close',0)
                        ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
                        
                        macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                        ps2=min(10,max(1,11-buy/10))
                        
                        # 加分项
                        hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
                        j_plus=j_bonus if jv>70 else 0
                        vr_plus=vr_bonus*1.5 if 1.2<=vr<=1.5 else (vr_bonus*0.5 if 1.5<vr<=2.0 else 0)
                        
                        score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_plus+vr_plus
                        cand.append((score,nh,p))
                    if not cand: continue
                    cand.sort(key=lambda x:(-x[0], -x[2]))
                    nd+=1
                    if cand[0][1]>=2.5: wins+=1
                
                rate=wins*100/nd if nd else 0
                if rate>best_w:
                    best_w=rate
                    best_ps=(cl_w,p_w,macd_w,ma5_b,hsl_b,j_bonus,vr_bonus,wins,nd)
        
        if best_ps:
            desc=f"CL×{best_ps[0]}+涨×{best_ps[1]}+MACD×{best_ps[2]}+MA5+{best_ps[3]}+换手×{best_ps[4]}+J+{best_ps[5]}+量比+{best_ps[6]}"
            print(f"{wk:<12} {best_ps[8]:>2}天 {best_ps[7]:>2}/{best_ps[8]:<2}({best_w:>4.1f}%) {desc}", flush=True)
    
    # 整月最优
    best_w=0; best_ps=None
    for p_w in [2.0,2.5,3.0]:
     for cl_w in [0.05,0.1,0.15]:
      for hsl_b in [0,0.3,0.6]:
       for j_bonus in [0,2,3]:
        for vr_bonus in [0,0.3]:
         for ma5_b in [0,3,5]:
          for macd_w in [0.3,0.5]:
            wins=0; nd=0
            for dt in mdates:
                cand=[]
                for s in data.get(dt,[]):
                    code=s['code'];p=s['p']
                    if p<P_BASE['p_min'] or p>P_BASE['p_max']: continue
                    vr=s.get('vol_ratio',0) or 0
                    if vr<P_BASE['vr_min'] or vr>P_BASE['vr_max']: continue
                    ri=real.get(code)
                    if not ri: continue
                    hsl=(ri.get('hsl',0) or 0)
                    if hsl<P_BASE['hsl_min'] or hsl>P_BASE['hsl_max']: continue
                    sz=(ri.get('shizhi',0) or 0)
                    if sz>=P_BASE['sz_max']: continue
                    nm=names.get(code,'')
                    if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                    jv=s.get('j_val',0) or 0
                    if jv>P_BASE['j_max']: continue
                    cl=s.get('cl',0)
                    if cl<P_BASE['cl_min'] or cl>P_BASE['cl_max']: continue
                    nh=s.get('n',0) or 0
                    if nh<=0: continue
                    buy=s.get('close',0); dif=s.get('dif_val',0) or 0
                    macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
                    is_yang=s.get('is_yang',0); close=s.get('close',0)
                    ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
                    
                    macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                    ps2=min(10,max(1,11-buy/10))
                    hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
                    j_plus=j_bonus if jv>70 else 0
                    vr_plus=vr_bonus*1.5 if 1.2<=vr<=1.5 else 0
                    
                    score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_plus+vr_plus
                    cand.append((score,nh,p))
                if not cand: continue
                cand.sort(key=lambda x:(-x[0], -x[2]))
                nd+=1
                if cand[0][1]>=2.5: wins+=1
            rate=wins*100/nd if nd else 0
            if rate>best_w:
                best_w=rate; best_ps=(p_w,cl_w,hsl_b,j_bonus,vr_bonus,ma5_b,macd_w,wins,nd)
    
    if best_ps:
        print(f"\n【{mlabel}整月最优】", flush=True)
        print(f"  胜率: {best_ps[7]}/{best_ps[8]}({best_w:.1f}%)", flush=True)
        print(f"  评分: 涨×{best_ps[0]}+CL×{best_ps[1]}+换手+{best_ps[2]}+J+{best_ps[3]}+量比+{best_ps[4]}+MA5+{best_ps[5]}+MACD×{best_ps[6]}", flush=True)
