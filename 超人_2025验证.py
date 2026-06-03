"""2025年验证v10切换策略"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target = [d for d in dates if d >= '2025-01-01' and d < '2026-01-01']

def get_nxt(code, date):
    fp=os.path.join(CACHE_DIR,f'{code}.json')
    if not os.path.exists(fp): return 0
    try:
        with open(fp) as f: kdata=json.load(f)
        idx=next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx+1 >= len(kdata): return 0
        bc=kdata[idx]['close']
        nh=(kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
        if abs(nh) > 50: return 0
        return nh or 0
    except: return 0

def calc_wr(code, date):
    fp=os.path.join(CACHE_DIR,f'{code}.json')
    if not os.path.exists(fp): return 50,50,0
    try:
        with open(fp) as f: kdata=json.load(f)
        idx=next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx<14: return 50,50,0
        h14=max(k['high'] for k in kdata[idx-13:idx+1])
        l14=min(k['low'] for k in kdata[idx-13:idx+1])
        c=kdata[idx]['close']
        wr_t=(h14-c)/(h14-l14)*100 if h14!=l14 else 50
        if idx<15: return wr_t,50,0
        h14_y=max(k['high'] for k in kdata[idx-14:idx])
        l14_y=min(k['low'] for k in kdata[idx-14:idx])
        c_y=kdata[idx-1]['close']
        wr_y=(h14_y-c_y)/(h14_y-l14_y)*100 if h14_y!=l14_y else 50
        y_p=(kdata[idx-1]['close']/kdata[idx-2]['close']-1)*100 if idx>=2 else 0
        return wr_t,wr_y,y_p
    except: return 50,50,0

def ps(p):return min(10,max(1,11-p/10))

P_MIN,P_MAX=5,8;VR_MIN,VR_MAX=0.8,2.0;HSL_MIN,HSL_MAX=5,15;SZ_MAX=300;CL_MIN,CL_MAX=60,90;J_MAX=100

print(f"2025年共{len(target)}天", flush=True)

wins1=0; nd1=0; wins2=0; nd2=0
by_mkt={'up':[0,0,0,0],'down':[0,0,0,0],'flat':[0,0,0,0]}

for dt in target:
    stocks=data.get(dt,[])
    if not stocks: continue
    
    # 大盘信号
    all_p=[x['p'] for x in stocks if 'p' in x]
    avg_mkt=sum(all_p)/len(all_p) if all_p else 0
    if avg_mkt>0.5: mkt='up'
    elif avg_mkt<-0.5: mkt='down'
    else: mkt='flat'
    
    cand1=[]  # 单一v8
    cand2=[]  # 切换v10
    for s in stocks:
        code,p=s['code'],s['p']
        if p<P_MIN or p>P_MAX: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<VR_MIN or vr>VR_MAX: continue
        ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<HSL_MIN or hsl>HSL_MAX: continue
        sz=(ri.get('shizhi',0) or 0)
        if sz>=SZ_MAX: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>J_MAX: continue
        cl=s.get('cl',0)
        if cl<CL_MIN or cl>CL_MAX: continue
        buy=s.get('close',0); dif=s.get('dif_val',0) or 0
        macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
        is_yang=s.get('is_yang',0); close=s.get('close',0)
        ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
        wr_t,wr_y,y_p=calc_wr(code,dt); nh=get_nxt(code,dt)
        
        wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
        macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
        ps2=ps(buy)
        
        # 单一v8公式
        score1=p*2.5+cl*0.1+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.5+(-3 if y_p>7 else 0)
        
        # 切换v10公式
        yp=-3 if y_p>7 else 0
        hsl_b=2*0.3 if 5<=hsl<=7 else 0
        duotou_b=3*0.3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
        yang_vr_b=2*0.3 if is_yang and vr>1.2 else 0
        
        if mkt=='up':
            score2=p*3.0+cl*0.1+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.3+hsl_b+duotou_b
        elif mkt=='down':
            score2=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.3+yp
        else:
            score2=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.3+yp+hsl_b+yang_vr_b
        
        cand1.append((score1,nh,p))
        cand2.append((score2,nh,p))
    
    if cand1 and cand2:
        cand1.sort(key=lambda x:(-x[0],-x[2]))
        cand2.sort(key=lambda x:(-x[0],-x[2]))
        nd1+=1; nd2+=1
        
        win1=1 if cand1[0][1]>=2.5 else 0
        win2=1 if cand2[0][1]>=2.5 else 0
        wins1+=win1; wins2+=win2
        
        by_mkt[mkt][0]+=win1; by_mkt[mkt][1]+=1
        by_mkt[mkt][2]+=win2; by_mkt[mkt][3]+=1

print(f"\n2025年对比:", flush=True)
print(f"  单一v8: {wins1}/{nd1}({wins1*100/nd1:.1f}%)", flush=True)
print(f"  切换v10: {wins2}/{nd2}({wins2*100/nd2:.1f}%)", flush=True)
print(f"  变化: {wins2*100/nd2 - wins1*100/nd1:+.1f}%", flush=True)

print(f"\n行情细分:", flush=True)
for k in ['up','down','flat']:
    w1,t1,w2,t2=by_mkt[k]
    if t1:print(f"  {k}: 单一{w1}/{t1}({w1*100/t1:.1f}%) | 切换{w2}/{t2}({w2*100/t2:.1f}%)",flush=True)
