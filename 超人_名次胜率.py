"""冠军/亚军/季军各自胜率 - v10切换策略"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target = [d for d in dates if d >= '2026-01-01']

def get_nxt(code, date):
    fp=os.path.join(CACHE_DIR,f'{code}.json')
    if not os.path.exists(fp): return 0
    try:
        with open(fp) as f: kdata=json.load(f)
        idx=next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx+1 >= len(kdata): return 0
        bc=kdata[idx]['close']
        nh=(kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
        if abs(nh)>50: return 0
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

# 按v10切换策略跑
champ=[0,0]; runner=[0,0]; third=[0,0]; total=0

for dt in target:
    stocks=data.get(dt,[])
    if not stocks: continue
    all_p=[x['p'] for x in stocks if 'p' in x]
    avg_mkt=sum(all_p)/len(all_p) if all_p else 0
    if avg_mkt>0.5: mkt='up'
    elif avg_mkt<-0.5: mkt='down'
    else: mkt='flat'
    
    cand=[]
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
        yp=-3 if y_p>7 else 0
        hsl_b=2*0.3 if 5<=hsl<=7 else 0
        duotou_b=3*0.3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
        yang_vr_b=2*0.3 if is_yang and vr>1.2 else 0
        
        if mkt=='up':
            score=p*3.0+cl*0.1+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.3+hsl_b+duotou_b
        elif mkt=='down':
            score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.3+yp
        else:
            score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.3+yp+hsl_b+yang_vr_b
        
        if nh and nh>0:
            cand.append((score,nh,p,nm,code,cl,vr,hsl))
    
    if len(cand)<3: continue
    cand.sort(key=lambda x:(-x[0],-x[2]))
    total+=1
    
    if cand[0][1]>=2.5: champ[0]+=1; champ[1]+=1
    else: champ[1]+=1
    
    if cand[1][1]>=2.5: runner[0]+=1; runner[1]+=1
    else: runner[1]+=1
    
    if cand[2][1]>=2.5: third[0]+=1; third[1]+=1
    else: third[1]+=1
    
    # 任意2只达标
    any2 = sum(1 for i in range(3) if cand[i][1]>=2.5)
    any2_5 = sum(1 for i in range(3) if cand[i][1]>=5)

print(f"v10切换策略 | 2026年{total}天", flush=True)
print(f"{'名次':<8} {'达标(≥2.5%)':<15} {'爆涨(≥5%)':<15}", flush=True)
print('-'*40, flush=True)
print(f"{'🥇冠军':<8} {champ[0]:>3}/{champ[1]:<3}({champ[0]*100/champ[1]:.1f}%)", flush=True)
print(f"{'🥈亚军':<8} {runner[0]:>3}/{runner[1]:<3}({runner[0]*100/runner[1]:.1f}%)", flush=True)
print(f"{'🥉季军':<8} {third[0]:>3}/{third[1]:<3}({third[0]*100/third[1]:.1f}%)", flush=True)

print(f"\n全年: {total}天")
print(f"冠军达2.5%: {champ[0]}({champ[0]*100/champ[1]:.1f}%)")
print(f"亚军达2.5%: {runner[0]}({runner[0]*100/runner[1]:.1f}%)")
print(f"季军达2.5%: {third[0]}({third[0]*100/third[1]:.1f}%)")
