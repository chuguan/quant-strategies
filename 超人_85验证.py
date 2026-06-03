"""验证85.7%因子：收阳+VR>1.2+2 和 换手5~7+2 —— 近28天+全年"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())

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

def run_bt(target):
    wins=0; ndays=0; t3=0; total_n=0
    for dt in target:
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
            is_yang=s.get('is_yang',0)
            wr_t,wr_y,y_p=calc_wr(code,dt); nh=get_nxt(code,dt)
            
            # 新因子
            bonus = 0
            if is_yang and vr > 1.2: bonus += 2  # 收阳+VR>1.2
            if 5 <= hsl <= 7: bonus += 2  # 换手5~7
            
            wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
            yp=-3 if y_p>7 else 0
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            score=p*2.5+cl*0.1+ps(buy)*0.3+macd_s*0.3+3*above5+wr_s*0.5+yp+bonus*0.5
            
            cand.append((score, p, nh))
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[2]))
        ndays+=1; total_n+=len(cand)
        if cand[0][1]>=2.5: wins+=1  # wait, this should be cand[0][1]? No, 
        if cand[0][2]>=2.5: w+=1  # need to fix
        if any(c[2]>=2.5 for c in cand[:3]): t3+=1
    return wins, ndays, t3

# Simplify - rewrite properly
for period_name, period_dates in [("近28天", [d for d in dates if d>='2026-04-10']), 
                                    ("全年", [d for d in dates if d>='2026-01-01'])]:
    print(f"\n=== {period_name} ===", flush=True)
    
    # 基线 (突破v8)
    labels = [("突破v8(基线)", 0, 0), 
              ("+收阳+VR>1.2+2×0.5", 1, 0.5),
              ("+换手5~7+2×0.5", 0, 0.5),
              ("+两者都加×0.5", 1, 0.5)]
    
    for label, add_yang, add_hsl_w in labels:
        wins=0; ndays=0; t3w=0
        for dt in period_dates:
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
                is_yang=s.get('is_yang',0)
                wr_t,wr_y,y_p=calc_wr(code,dt); nh=get_nxt(code,dt)
                wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
                yp=-3 if y_p>7 else 0
                macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                
                bonus = 0
                if add_yang and is_yang and vr>1.2: bonus += 2
                if add_hsl_w>0 and 5<=hsl<=7: bonus += 2
                
                score=p*2.5+cl*0.1+ps(buy)*0.3+macd_s*0.3+3*above5+wr_s*0.5+yp+bonus*0.5
                cand.append((score,p,nh))
            if not cand: continue
            cand.sort(key=lambda x: (-x[0], -x[2]))
            ndays+=1
            if cand[0][2]>=2.5: wins+=1
            if any(c[2]>=2.5 for c in cand[:3]): t3w+=1
        
        chg = f'{wins*100/ndays-82.1:+.1f}' if label!='突破v8(基线)' else ''
        print(f"{label:<25}: {wins}/{ndays}({wins*100/ndays:.1f}%){chg:>6} T3{t3w*100/ndays:.1f}%", flush=True)
