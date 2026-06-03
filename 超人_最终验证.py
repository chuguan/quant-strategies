"""验证近28天最佳因子在全年表现"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target28 = [d for d in dates if d >= '2026-04-10']
target_all = [d for d in dates if d >= '2026-01-01']

def get_nxt(code, date):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is not None and idx+1 < len(kdata):
            bc = kdata[idx]['close']
            return (kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
    except: return 0

def calc_wr(code, date):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 50, 50, 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx < 14: return 50, 50, 0
        h14 = max(k['high'] for k in kdata[idx-13:idx+1])
        l14 = min(k['low'] for k in kdata[idx-13:idx+1])
        c = kdata[idx]['close']
        wr_t = (h14-c)/(h14-l14)*100 if h14!=l14 else 50
        if idx < 15: return wr_t, 50, 0
        h14_y = max(k['high'] for k in kdata[idx-14:idx])
        l14_y = min(k['low'] for k in kdata[idx-14:idx])
        c_y = kdata[idx-1]['close']
        wr_y = (h14_y-c_y)/(h14_y-l14_y)*100 if h14_y!=l14_y else 50
        y_p = (kdata[idx-1]['close']/kdata[idx-2]['close']-1)*100 if idx>=2 else 0
        return wr_t, wr_y, y_p
    except: return 50, 50, 0

def ps(p): return min(10, max(1, 11-p/10))

P_MIN,P_MAX=5,8; VR_MIN,VR_MAX=0.8,2.0; HSL_MIN,HSL_MAX=5,15; SZ_MAX=300; CL_MIN,CL_MAX=60,90; J_MAX=100

def run_test(target_dates, add_f3=0, add_f5=0, add_f9=0):
    wins=0; nd=0; t3=0
    for dt in target_dates:
        cand=[]
        for s in data.get(dt, []):
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
            yp=-3 if y_p>7 else 0
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            
            bonus=0
            if add_f3: bonus += (2 if 5<=hsl<=7 else 0)*add_f3
            if add_f5: 
                if ma5>ma10>ma20 and ma5>close*0.98: bonus += 3*add_f5
            if add_f9:
                if is_yang and vr>1.2: bonus += 2*add_f9
            
            score=p*2.5+cl*0.1+ps(buy)*0.3+macd_s*0.3+3*above5+wr_s*0.5+yp+bonus
            cand.append((score,p,nh))
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[2]))
        nd+=1
        if cand[0][2]>=2.5: wins+=1
        if any(c[2]>=2.5 for c in cand[:3]): t3+=1
    return wins, nd, t3

tests = [
    ("近28天 基线", target28, 0, 0, 0),
    ("近28天 +换手5~7×0.5", target28, 0.5, 0, 0),
    ("近28天 +收阳VR×0.3", target28, 0, 0, 0.3),
    ("近28天 +均多×0.3", target28, 0, 0.3, 0),
    ("近28天 +换手+收阳", target28, 0.5, 0, 0.3),
    ("近28天 +换手+均多+收阳", target28, 0.5, 0.3, 0.3),
    ("全年 基线", target_all, 0, 0, 0),
    ("全年 +均多×0.3", target_all, 0, 0.3, 0),
    ("全年 +换手5~7×0.5", target_all, 0.5, 0, 0),
    ("全年 +收阳VR×0.3", target_all, 0, 0, 0.3),
    ("全年 +均多+换手", target_all, 0.5, 0.3, 0),
    ("全年 +均多+收阳", target_all, 0, 0.3, 0.3),
]

for label, td, f3, f5, f9 in tests:
    w,n,d=t=run_test(td, f3, f5, f9)
    print(f"{label:<25}: {w}/{n}({w*100/n:.1f}%) T3{d*100/n:.1f}%", flush=True)
