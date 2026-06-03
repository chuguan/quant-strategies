"""从82.1%出发，逐个新因子测试（全年）— 只留提高胜率的"""
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

# ===== 预计算所有数据 =====
def precompute(target):
    data_cache={}
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
            
            # 突破v8基础分
            wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
            yp=-3 if y_p>7 else 0
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            base=p*2.5+cl*0.1+ps(buy)*0.3+macd_s*0.3+3*above5+wr_s*0.5+yp
            
            # 新因子值
            f1 = 1 if 1.8<=vr<2.0 else 0  # 量比
            f2 = 2 if 2.0<=vr<=2.5 else 0  # 量比
            f3 = 2 if 5<=hsl<=7 else 0  # 换手
            f4 = -2 if hsl>10 else 0  # 换手>10
            
            f5 = 3 if ma5>ma10>ma20 and ma5>close*0.98 else 0  # 均线多头
            f6 = -3 if ma5<ma10<ma20 else 0  # 均线空头
            
            f7 = 0  # 突破
            if klines:
                idx=next((i for i,k in enumerate(klines) if k['date']==dt), None)
                if idx is not None and idx>=5:
                    h5=max(k['high'] for k in klines[idx-4:idx+1])
                    if close>h5 and close>ma20: f7=3
            
            f8 = 2 if 50<=sz<=200 else (-2 if sz<50 or sz>200 else 0)  # 市值
            f9 = 2 if is_yang and vr>1.2 else 0  # 收阳+放量
            f10 = 1 if macd_g and dif>0 else 0  # MACD金叉+DIF>0
            
            f11 = 0  # 高位放量滞涨
            if klines:
                idx=next((i for i,k in enumerate(klines) if k['date']==dt), None)
                if idx is not None and idx>=10:
                    c10=klines[idx-9]['close']
                    if (close/c10-1)*100 < 20 and vr>2.5 and p<3: f11=-5
            
            cand.append((base, p, nh, nm, code, cl, f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11))
        if cand: data_cache[dt]=cand
    return data_cache

print("预计算...", flush=True)
dc28 = precompute(target28)
dc_all = precompute(target_all)
print(f"近28天: {len(dc28)}天, 全年: {len(dc_all)}天", flush=True)

# ===== 逐个因子测试 =====
f_names = ['f1量比1.8','f2量比2.0','f3换手5~7','f4换手>10',
           'f5均多头','f6均空头','f7突破前H','f8市值50-200',
           'f9收阳+VR','f10MACD金','f11高位放量']

def run_backtest(target_dates, dc, f_idx, f_w):
    wins=0; nd=0; t3w=0
    for dt in target_dates:
        if dt not in dc: continue
        cand = [(c[0]+c[f_idx]*f_w, c[2], c[1]) for c in dc[dt]]
        cand.sort(key=lambda x: (-x[0], -x[2]))
        nd+=1
        if cand[0][1]>=2.5: wins+=1
        if any(c[1]>=2.5 for c in cand[:3]): t3w+=1
    return wins, nd, t3w

def get_base(dc, target_dates):
    wins=0; nd=0
    for dt in target_dates:
        if dt not in dc: continue
        cand = [(c[0], c[2], c[1]) for c in dc[dt]]
        cand.sort(key=lambda x: (-x[0], -x[2]))
        nd+=1
        if cand[0][1]>=2.5: wins+=1
    return wins, nd

for period_name, target_dates, dc in [("近28天", target28, dc28), ("全年", target_all, dc_all)]:
    base_w, base_nd = get_base(dc, target_dates)
    base_rate = base_w*100/base_nd if base_nd else 0
    print(f"\n{'='*60}", flush=True)
    print(f"  {period_name} | 基线(突破v8): {base_w}/{base_nd}({base_rate:.1f}%)", flush=True)
    print(f"{'='*60}", flush=True)
    
    valid_factors = []
    for i in range(11):
        best_rate = 0; best_w = 0
        for w in [0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0]:
            wins, nd, t3 = run_backtest(target_dates, dc, 6+i, w)  # f1 starts at index 6
            rate = wins*100/nd if nd else 0
            if rate > best_rate:
                best_rate = rate; best_w = w
        chg = best_rate - base_rate
        if chg > 0:
            valid_factors.append((i, best_rate, best_w, chg))
            print(f"  ✅ {f_names[i]:<14} w={best_w:>3.1f} → {best_rate:.1f}%(+{chg:.1f}%)", flush=True)
    
    # 如果有有效因子，试组合
    if valid_factors:
        print(f"\n  --- 组合测试 ---", flush=True)
        
        # 先加最好的一个
        best = sorted(valid_factors, key=lambda x: -x[1])[0]
        i, best_rate, best_w, _ = best
        current_active = [(6+i, best_w)]  # (index, weight)
        current_rate = best_rate
        
        added = [f_names[i]]
        print(f"  起始: +{f_names[i]} w={best_w} → {best_rate:.1f}%", flush=True)
        
        # 逐个加剩下的
        for _ in range(3):  # 最多加3次
            best_add = None; best_new_rate = current_rate
            for vi, vr, vw, _ in valid_factors:
                idx = 6+vi
                if idx in [a[0] for a in current_active]: continue
                # 测加上这个
                wins=0; nd=0
                for dt in target_dates:
                    if dt not in dc: continue
                    cand=[]
                    for c in dc[dt]:
                        s = c[0]
                        for ai, aw in current_active: s += c[ai]*aw
                        s += c[idx]*vw
                        cand.append((s, c[2], c[1]))
                    if not cand: continue
                    cand.sort(key=lambda x: (-x[0], -x[2]))
                    nd+=1
                    if cand[0][1]>=2.5: wins+=1
                rate = wins*100/nd if nd else 0
                if rate > best_new_rate:
                    best_new_rate = rate; best_add = (vi, idx, vw)
            
            if best_add and best_new_rate > current_rate:
                vi, idx, vw = best_add
                current_active.append((idx, vw))
                current_rate = best_new_rate
                added.append(f_names[vi])
                print(f"  +{f_names[vi]} w={vw} → {best_new_rate:.1f}%", flush=True)
            else:
                break
        
        if len(added) > 1:
            print(f"  最终组合: {' + '.join(added)} → {current_rate:.1f}%", flush=True)
