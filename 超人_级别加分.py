"""分级放宽+级别加分 - 保证放宽后胜率不降"""
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

# 5级放宽条件
LEVELS = [
    {'n':'L0','p_min':5,'p_max':8,'vr_min':0.8,'vr_max':2.0,'hsl_min':5,'hsl_max':15,'sz_max':300,'cl_min':60,'cl_max':90,'j_max':100},
    {'n':'L1','p_min':4,'p_max':9,'vr_min':0.6,'vr_max':2.5,'hsl_min':3,'hsl_max':20,'sz_max':300,'cl_min':50,'cl_max':95,'j_max':120},
    {'n':'L2','p_min':3,'p_max':10,'vr_min':0.5,'vr_max':3.0,'hsl_min':2,'hsl_max':25,'sz_max':400,'cl_min':40,'cl_max':98,'j_max':150},
    {'n':'L3','p_min':2,'p_max':11,'vr_min':0.4,'vr_max':3.5,'hsl_min':1,'hsl_max':30,'sz_max':500,'cl_min':30,'cl_max':99,'j_max':200},
    {'n':'L4','p_min':1,'p_max':12,'vr_min':0.3,'vr_max':4.0,'hsl_min':0.5,'hsl_max':35,'sz_max':1000,'cl_min':20,'cl_max':100,'j_max':300},
]

def get_candidates(dt):
    """获取该天所有级别的候选，每只标记来源级别"""
    all_cand=[]
    seen=set()
    for li in range(len(LEVELS)):
        L=LEVELS[li]
        for s in data.get(dt,[]):
            code,p=s['code'],s['p']
            if code in seen: continue
            if p<L['p_min'] or p>L['p_max']: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<L['vr_min'] or vr>L['vr_max']: continue
            ri=real.get(code)
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<L['hsl_min'] or hsl>L['hsl_max']: continue
            sz=(ri.get('shizhi',0) or 0)
            if sz>=L['sz_max']: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv=s.get('j_val',0) or 0
            if jv>L['j_max']: continue
            cl=s.get('cl',0)
            if cl<L['cl_min'] or cl>L['cl_max']: continue
            
            seen.add(code)
            buy=s.get('close',0); dif=s.get('dif_val',0) or 0
            macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
            is_yang=s.get('is_yang',0); close=s.get('close',0)
            ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
            all_cand.append({'code':code,'p':p,'cl':cl,'vr':vr,'hsl':hsl,'sz':sz,'nm':nm,'buy':buy,
                           'dif':dif,'macd_g':macd_g,'above5':above5,'is_yang':is_yang,'close':close,
                           'ma5':ma5,'ma10':ma10,'ma20':ma20,'lev':li})
            if li==0 and len(seen)>=10: break  # L0已够
        if len(seen)>=10: break
    return all_cand

# 预计算
print("预计算...", flush=True)
CACHE = {}
for dt in target:
    cand = get_candidates(dt)
    if cand:
        for c in cand:
            wr_t,wr_y,y_p = calc_wr(c['code'], dt)
            nh = get_nxt(c['code'], dt)
            c['wr_t']=wr_t; c['wr_y']=wr_y; c['y_p']=y_p; c['nh']=nh
        CACHE[dt]=cand

print(f"{len(CACHE)}天", flush=True)

# 测试不同级别加分组合
print(f"\n{'L0分':>5} {'L1分':>5} {'L2分':>5} {'L3分':>5} {'L4分':>5} {'冠军%':>6} {'T3%':>5}", flush=True)

results=[]
for b0 in [0, 3, 5, 8, 10]:
    for b1 in [0, 2, 3, 5]:
        for b2 in [0, 2, 3]:
            for b3 in [0, -2, -3]:
                for b4 in [0, -3, -5]:
                    bonuses = [b0, b1, b2, b3, b4]
                    wins=0; nd=0; t3=0; tt=0
                    for dt in target:
                        if dt not in CACHE: continue
                        stocks=data.get(dt,[])
                        all_p=[x['p'] for x in stocks if 'p' in x]
                        avg_mkt=sum(all_p)/len(all_p) if all_p else 0
                        if avg_mkt>0.5: mkt='up'
                        elif avg_mkt<-0.5: mkt='down'
                        else: mkt='flat'
                        
                        cand=[]
                        for c in CACHE[dt]:
                            p=0;cl=0;vr=0;hsl=0;buy=0;dif=0;macd_g=0;above5=0;is_yang=0;close=0;ma5=0;ma10=0;ma20=0;li=0
                            p=c['p'];cl=c['cl'];vr=c['vr'];hsl=c['hsl'];buy=c['buy']
                            dif=c['dif'];macd_g=c['macd_g'];above5=c['above5']
                            is_yang=c['is_yang'];close=c['close'];ma5=c['ma5'];ma10=c['ma10'];ma20=c['ma20']
                            wr_t=c['wr_t'];wr_y=c['wr_y'];y_p=c['y_p'];nh=c['nh'];li=c['lev']
                            
                            wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
                            yp=-3 if y_p>7 else 0
                            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                            ps2=ps(buy)
                            hsl_b=2*0.3 if 5<=hsl<=7 else 0
                            duotou_b=3*0.3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
                            yang_vr_b=2*0.3 if is_yang and vr>1.2 else 0
                            
                            if mkt=='up':
                                score=p*3.0+cl*0.1+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.3+hsl_b+duotou_b+bonuses[li]
                            elif mkt=='down':
                                score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.3+yp+bonuses[li]
                            else:
                                score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.3+yp+hsl_b+yang_vr_b+bonuses[li]
                            
                            if nh and nh>0:
                                cand.append((score,nh,p))
                        
                        if not cand: continue
                        cand.sort(key=lambda x:(-x[0],-x[2]))
                        nd+=1
                        if cand[0][1]>=2.5: wins+=1
                        if len(cand)>=3:
                            tt+=1
                            if any(c[1]>=2.5 for c in cand[:3]): t3+=1
                    
                    rate=wins*100/nd if nd else 0
                    if rate >= 67:  # 只展示≥67%
                        results.append((rate, t3*100/tt if tt else 0, bonuses[0], bonuses[1], bonuses[2], bonuses[3], bonuses[4]))

results.sort(key=lambda x:(-x[0], -x[1]))
for r in results[:20]:
    print(f"{r[2]:>5} {r[3]:>5} {r[4]:>5} {r[5]:>5} {r[6]:>5} {r[0]:>5.1f}% {r[1]:>5.1f}%", flush=True)

# 最佳组合详细
if results:
    best=results[0]
    print(f"\n=== 最佳 ==", flush=True)
    print(f"级别加分: L0+{best[2]} L1+{best[3]} L2+{best[4]} L3+{best[5]} L4+{best[6]}", flush=True)
    print(f"冠军率: {best[0]:.1f}% | Top3: {best[1]:.1f}%", flush=True)
