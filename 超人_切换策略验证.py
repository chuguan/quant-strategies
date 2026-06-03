"""验证：根据大盘切换公式的全年胜率"""
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
        if idx is not None and idx+1 < len(kdata):
            bc=kdata[idx]['close']
            return (kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
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

# 预计算 + 大盘信号
print("预计算...", flush=True)
market_sig={}
all_data={}

for dt in target:
    stocks=data.get(dt,[])
    if not stocks: continue
    avg_p=sum(s.get('p',0) or 0 for s in stocks)/len(stocks)
    
    # 大盘信号
    if avg_p>0.5: mkt='up'
    elif avg_p<-0.5: mkt='down'
    else: mkt='flat'
    market_sig[dt]=mkt
    
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
        fp2=os.path.join(CACHE_DIR,f'{code}.json'); klines=None
        if os.path.exists(fp2):
            try:
                with open(fp2) as f: klines=json.load(f)
            except: pass
        
        wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
        yp=-3 if y_p>7 else 0
        macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
        
        f3=2 if 5<=hsl<=7 else 0
        f5=3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
        f9=2 if is_yang and vr>1.2 else 0
        
        cand.append((p,cl,buy,dif,macd_g,above5,close,ma5,ma10,ma20,
                     wr_t,wr_y,y_p,nh,f3,f5,f9,nm))
    if cand: all_data[dt]=cand

# ===== 对比：单一公式 vs 切换策略 =====
print("\n=== 对比回测 ===", flush=True)

tests = [
    # 单一公式（突破v8）
    ("单一(突破v8)", 
     lambda mkt: {'cl_w':0.1,'p_w':2.5,'wr_w':0.5,'y_pen':3,'ma5_b':3,'f3_w':0,'f5_w':0,'f9_w':0}),
    # 切换策略
    ("切换(涨/跌/横各最优)", 
     lambda mkt: 
        {'cl_w':0.1,'p_w':3.0,'wr_w':0.3,'y_pen':0,'ma5_b':0,'f3_w':0.3,'f5_w':0.3,'f9_w':0} if mkt=='up' else
        {'cl_w':0.05,'p_w':2.0,'wr_w':0.3,'y_pen':3,'ma5_b':0,'f3_w':0,'f5_w':0,'f9_w':0} if mkt=='down' else
        {'cl_w':0.05,'p_w':2.0,'wr_w':0.3,'y_pen':3,'ma5_b':0,'f3_w':0.3,'f5_w':0,'f9_w':0.3}),
]

for label, get_params in tests:
    wins=0; nd=0; t3=0; by_mkt={'up':[0,0],'down':[0,0],'flat':[0,0]}
    for dt in target:
        if dt not in all_data: continue
        mkt=market_sig.get(dt,'flat')
        p=get_params(mkt)
        cand=[]
        for c in all_data[dt]:
            pp,cl,buy,dif,macd_g,above5,close,ma5,ma10,ma20,wr_t,wr_y,y_p,nh,f3,f5,f9,nm=c
            
            wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
            yp=-p['y_pen'] if y_p>7 else 0
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            
            score=pp*p['p_w']+cl*p['cl_w']+ps(buy)*0.3+macd_s*0.3+p['ma5_b']*above5+wr_s*p['wr_w']+yp+f3*p['f3_w']+f5*p['f5_w']+f9*p['f9_w']
            cand.append((score,nh,pp))
        if not cand:continue
        cand.sort(key=lambda x:(-x[0],-x[2]))
        nd+=1
        if cand[0][1]>=2.5: wins+=1; by_mkt[mkt][0]+=1
        by_mkt[mkt][1]+=1
        if any(c[1]>=2.5 for c in cand[:3]): t3+=1
    
    print(f"{label:<20}: 冠军{wins}/{nd}({wins*100/nd:.1f}%) T3{t3*100/nd:.1f}%", flush=True)
    for k in ['up','down','flat']:
        w,t=by_mkt[k]
        if t:print(f"  {k}: {w}/{t}({w*100/t:.1f}%)",flush=True)
