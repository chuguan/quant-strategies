"""2025年全面突破——从v8出发，逐个因子+组合搜索"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target = [d for d in dates if d >= '2025-01-01' and d < '2026-01-01']

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

# 预计算
print(f"2025年共{len(target)}天，预计算...", flush=True)
all_data={}
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
        is_yang=s.get('is_yang',0); close=s.get('close',0)
        ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
        wr_t,wr_y,y_p=calc_wr(code,dt); nh=get_nxt(code,dt)
        fp=os.path.join(CACHE_DIR,f'{code}.json'); klines=None
        if os.path.exists(fp):
            try:
                with open(fp) as f: klines=json.load(f)
            except: pass
        
        wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
        yp=-3 if y_p>7 else 0
        macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
        
        f1=1 if 1.8<=vr<2.0 else 0
        f2=2 if 2.0<=vr<=2.5 else 0
        f3=2 if 5<=hsl<=7 else 0
        f4=-2 if hsl>10 else 0
        f5=3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
        f6=-3 if ma5<ma10<ma20 else 0
        f7=0
        if klines:
            idx=next((i for i,k in enumerate(klines) if k['date']==dt), None)
            if idx is not None and idx>=5:
                h5=max(k['high'] for k in klines[idx-4:idx+1])
                if close>h5 and close>ma20: f7=3
        f8=2 if 50<=sz<=200 else (-2 if sz<50 or sz>200 else 0)
        f9=2 if is_yang and vr>1.2 else 0
        f10=1 if macd_g and dif>0 else 0
        f11=0
        if klines:
            idx=next((i for i,k in enumerate(klines) if k['date']==dt), None)
            if idx is not None and idx>=10:
                c10=klines[idx-9]['close']
                if (close/c10-1)*100 < 20 and vr>2.5 and p<3: f11=-5
        
        cand.append((p,cl,vr,hsl,sz,buy,dif,macd_g,above5,is_yang,close,
                     ma5,ma10,ma20,wr_t,wr_y,y_p,jv,nm,
                     f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11))
    if cand: all_data[dt]=cand

total=sum(len(v) for v in all_data.values())
print(f"共{len(all_data)}天, {total}只, 均{total//len(all_data)}只/天", flush=True)

# ===== 基线（突破v8 on 2025） =====
w_base=0; nd_base=0
for dt in target:
    if dt not in all_data: continue
    cand=[]
    for c in all_data[dt]:
        p,cl,vr,hsl,sz,buy,dif,macd_g,above5,is_yang,close=c[:11]
        ma5,ma10,ma20,wr_t,wr_y,y_p,jv,nm=c[11:19]
        f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11=c[19:]
        wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
        yp=-3 if y_p>7 else 0
        macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
        base=p*2.5+cl*0.1+ps(buy)*0.3+macd_s*0.3+3*above5+wr_s*0.5+yp
        cand.append((base, nh, p))
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[2]))
    nd_base+=1
    if cand[0][1]>=2.5: w_base+=1

base_rate = w_base*100/nd_base if nd_base else 0
print(f"\n2025年突破v8基线: {w_base}/{nd_base}({base_rate:.1f}%)", flush=True)

# ===== 逐个因子测试 =====
f_names = ['f1量比1.8','f2量比2.0','f3换手5~7','f4换手>10','f5均多头',
           'f6均空头','f7突破前H','f8市值50-200','f9收阳+VR','f10MACD金','f11高位量']

print(f"\n{'因子':<12} {'最佳w':>5} {'胜率':>7} {'变化':>7} {'T3%':>5}", flush=True)
print('-'*40, flush=True)

valid = []
for i in range(11):
    best_rate=0; best_w=0; best_t3=0
    for w in [0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0]:
        wins=0; nd=0; t3=0
        for dt in target:
            if dt not in all_data: continue
            cand=[]
            for c in all_data[dt]:
                p,cl,vr,hsl,sz,buy,dif,macd_g,above5,is_yang,close=c[:11]
                ma5,ma10,ma20,wr_t,wr_y,y_p,jv,nm=c[11:19]
                fv=list(c[19:])
                wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
                yp=-3 if y_p>7 else 0
                macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                base=p*2.5+cl*0.1+ps(buy)*0.3+macd_s*0.3+3*above5+wr_s*0.5+yp+fv[i]*w
                cand.append((base, nh, p))
            if not cand: continue
            cand.sort(key=lambda x: (-x[0], -x[2]))
            nd+=1
            if cand[0][1]>=2.5: wins+=1
            if any(c[1]>=2.5 for c in cand[:3]): t3+=1
        rate=wins*100/nd if nd else 0
        if rate > best_rate:
            best_rate=rate; best_w=w; best_t3=t3*100/nd if nd else 0
    chg = best_rate - base_rate
    if chg > 0:
        print(f"✅{f_names[i]:<10} {best_w:>5.1f} {best_rate:>6.1f}% +{chg:>.1f}% {best_t3:>5.1f}%", flush=True)
        valid.append((i, best_w, best_rate))
    else:
        print(f"❌{f_names[i]:<10} {best_w:>5.1f} {best_rate:>6.1f}% {chg:>+5.1f}%", flush=True)

# ===== 组合测试 =====
if valid:
    print(f"\n=== 组合测试 ===", flush=True)
    # 选最好的一个
    best_v = sorted(valid, key=lambda x: -x[2])[0]
    active = [(19+best_v[0], best_v[1])]
    cur_rate = best_v[2]
    print(f"起始: +{f_names[best_v[0]]} w={best_v[1]} → {best_v[2]:.1f}%", flush=True)
    
    for _ in range(4):
        best_add=None; best_new_rate=cur_rate
        for vi, vw, vr in valid:
            idx=19+vi
            if idx in [a[0] for a in active]: continue
            wins=0; nd=0
            for dt in target:
                if dt not in all_data: continue
                cand=[]
                for c in all_data[dt]:
                    p,cl,vr2,hsl,sz,buy,dif,macd_g,above5,is_yang,close=c[:11]
                    ma5,ma10,ma20,wr_t,wr_y,y_p,jv,nm=c[11:19]
                    fv=list(c[19:])
                    wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
                    yp=-3 if y_p>7 else 0
                    macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                    s=p*2.5+cl*0.1+ps(buy)*0.3+macd_s*0.3+3*above5+wr_s*0.5+yp
                    for ai,aw in active: s += fv[ai-19]*aw
                    s += fv[idx-19]*vw
                    cand.append((s, nh, p))
                if not cand: continue
                cand.sort(key=lambda x: (-x[0], -x[2]))
                nd+=1
                if cand[0][1]>=2.5: wins+=1
            rate=wins*100/nd if nd else 0
            if rate > best_new_rate:
                best_new_rate=rate; best_add=(vi, idx, vw)
        if best_add and best_new_rate > cur_rate:
            vi, idx, vw = best_add
            active.append((idx, vw))
            cur_rate = best_new_rate
            print(f"  +{f_names[vi]} w={vw} → {cur_rate:.1f}%", flush=True)
        else:
            break
    
    if len(active) > 1:
        print(f"\n最终组合({len(active)}因子): {cur_rate:.1f}%", flush=True)
        for ai, aw in active:
            print(f"  +{f_names[ai-19]} w={aw}", flush=True)
