"""继续突破：尝试更多参数组合 + 前日涨幅扣分 + RSI + 不同WR"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target = [d for d in dates if d >= '2026-04-10']

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
    if not os.path.exists(fp): return 50, 50
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx < 14: return 50, 50
        h14 = max(k['high'] for k in kdata[idx-13:idx+1])
        l14 = min(k['low'] for k in kdata[idx-13:idx+1])
        c = kdata[idx]['close']
        wr_t = (h14-c)/(h14-l14)*100 if h14!=l14 else 50
        if idx < 15: return wr_t, 50, 50
        h14_y = max(k['high'] for k in kdata[idx-14:idx])
        l14_y = min(k['low'] for k in kdata[idx-14:idx])
        c_y = kdata[idx-1]['close']
        wr_y = (h14_y-c_y)/(h14_y-l14_y)*100 if h14_y!=l14_y else 50
        # 前日涨幅
        y_p = (kdata[idx-1]['close']/kdata[idx-2]['close']-1)*100 if idx>=2 else 0
        return wr_t, wr_y, y_p
    except: return 50, 50, 0

def calc_rsi(code, date, period=6):
    """RSI(6)快速RSI"""
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 50
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx < period: return 50
        gains = []
        for i in range(idx-period+1, idx+1):
            change = kdata[i]['close'] - kdata[i-1]['close']
            gains.append(change)
        avg_gain = sum(g for g in gains if g>0) / period
        avg_loss = abs(sum(g for g in gains if g<0)) / period
        if avg_loss == 0: return 100
        rs = avg_gain / avg_loss
        return 100 - (100/(1+rs))
    except: return 50

def ps(price): return min(10, max(1, 11-price/10))
def ms(dif, g):
    if g and dif>0.5: return 10
    if g and dif>0.2: return 8
    if g: return 6
    if dif>0.5: return 4
    if dif>0: return 2
    return 0 if dif>-0.3 else -3 if dif>-0.5 else -5

p_min,p_max=5,8; vr_min,vr_max=0.8,2.0; hsl_min,hsl_max=5,15; sz_max=300; cl_min,cl_max=60,90; j_max=100

# 预计算
print("预计算...", flush=True)
all_data = {}
for dt in target:
    cand=[]
    for s in data.get(dt, []):
        code,p=s['code'],s['p']
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
        if jv>j_max: continue
        cl=s.get('cl',0)
        if cl<cl_min or cl>cl_max: continue
        buy=s.get('close',0)
        dif=s.get('dif_val',0) or 0
        macd_g=s.get('macd_golden',0)
        above5=s.get('above_ma5',0)
        is_yang=s.get('is_yang',0)
        wr_t, wr_y, y_p = calc_wr(code, dt)
        rsi6 = calc_rsi(code, dt)
        nh = get_nxt(code, dt)
        cand.append((p,cl,vr,buy,nh,dif,macd_g,above5,is_yang,wr_t,wr_y,y_p,rsi6,nm,code))
    if cand:
        all_data[dt]=cand

print(f"{len(all_data)}天, 共{sum(len(v) for v in all_data.values())}只", flush=True)

# ===== 思路1: 不同WR阈值 =====
print(f"\n=== 思路1: WR阈值 + 前日涨幅扣分 ===", flush=True)
results = []
for cl_w in [0.1, 0.2, 0.3]:
    for p_w in [1.5, 2.0, 2.5]:
        for wr_th in [25, 30, 35]:
            for wr_w in [0.3, 0.5]:
                for macd_w in [0.3, 0.5]:
                    for ma5_b in [3, 5]:
                        for y_penalty in [0, 3, 5]:  # 前日涨>7%扣分
                            wins=0; ndays=0; t3w=0; total_n=0
                            for dt in target:
                                if dt not in all_data: continue
                                cand=all_data[dt]
                                scored=[]
                                for c in cand:
                                    p,cl,vr,buy,nh,dif,macd_g,above5,is_yang,wr_t,wr_y,y_p,rsi6,nm,code = c
                                    wr_s = min(5, max(0, (wr_th-wr_t)*5/wr_th)) if wr_t < wr_th and wr_y >= wr_th else 0
                                    yp = -y_penalty if y_p > 7 and y_penalty > 0 else 0  # 前日涨>7%扣分
                                    score = p*p_w + cl*cl_w + ps(buy)*0.3 + ms(dif,macd_g)*macd_w + ma5_b*above5 + wr_s*wr_w + yp
                                    scored.append((score, nh, p))
                                if not scored: continue
                                scored.sort(key=lambda x: (-x[0], -x[2]))
                                ndays+=1; total_n+=len(scored)
                                if scored[0][1]>=2.5: wins+=1
                                if any(s[1]>=2.5 for s in scored[:3]): t3w+=1
                            wr_rate=wins*100/ndays
                            results.append((wr_rate, cl_w, p_w, wr_th, wr_w, macd_w, ma5_b, y_penalty, t3w*100/ndays, total_n//ndays))

results.sort(key=lambda x: (-x[0], -x[8]))
print(f"{'胜率':>6} {'CLw':>4} {'涨w':>4} {'WRth':>4} {'WRw':>4} {'Mw':>4} {'M5':>4} {'扣分':>4} {'T3_2.5':>7} {'只':>4}", flush=True)
for r in results[:15]:
    print(f"{r[0]:>5.1f}% {r[1]:>4.1f} {r[2]:>4.1f} {r[3]:>4} {r[4]:>4.1f} {r[5]:>4.1f} {r[6]:>4} {r[7]:>4} {r[8]:>5.1f}% {r[9]:>4}", flush=True)

# ===== 思路2: WR二进制 + RSI过滤 =====
print(f"\n=== 思路2: WR二进制 + RSI低值加分 ===", flush=True)
results2 = []
for cl_w in [0.1, 0.15, 0.2]:
    for p_w in [1.5, 2.0]:
        for wr_w_bin in [2, 3, 5]:  # WR下穿直接加固定分
            for wr_th in [25, 30]:
                for rsi_add in [0, 1, 2]:  # RSI<35加分
                    for macd_w in [0.3, 0.5]:
                        for ma5_b in [3, 5]:
                            wins=0; ndays=0; t3w=0
                            for dt in target:
                                if dt not in all_data: continue
                                cand=all_data[dt]
                                scored=[]
                                for c in cand:
                                    p,cl,vr,buy,nh,dif,macd_g,above5,is_yang,wr_t,wr_y,y_p,rsi6,nm,code = c
                                    wr_s = wr_w_bin if wr_t < wr_th and wr_y >= wr_th else 0
                                    rsi_s = rsi_add if rsi6 < 35 else 0
                                    score = p*p_w + cl*cl_w + ps(buy)*0.3 + ms(dif,macd_g)*macd_w + ma5_b*above5 + wr_s + rsi_s
                                    scored.append((score, nh, p))
                                if not scored: continue
                                scored.sort(key=lambda x: (-x[0], -x[2]))
                                ndays+=1
                                if scored[0][1]>=2.5: wins+=1
                                if any(s[1]>=2.5 for s in scored[:3]): t3w+=1
                            results2.append((wins*100/ndays, cl_w, p_w, wr_w_bin, wr_th, rsi_add, macd_w, ma5_b, t3w*100/ndays))

results2.sort(key=lambda x: (-x[0], -x[8]))
print(f"{'胜率':>6} {'CLw':>4} {'涨w':>4} {'WR加':>4} {'WRth':>4} {'RSI+':>4} {'Mw':>4} {'M5':>4}", flush=True)
for r in results2[:15]:
    print(f"{r[0]:>5.1f}% {r[1]:>4.2f} {r[2]:>4.1f} {r[3]:>4} {r[4]:>4} {r[5]:>4} {r[6]:>4.1f} {r[7]:>4}", flush=True)

# ===== 对比 =====
print(f"\n=== 当前最优 vs 原公式 ===", flush=True)
for label, p_w, cl_w, wr_w, wr_th, macd_w, ma5_b in [
    ("突破公式(CL×0.2+涨×2+WR×0.3@30)", 2.0, 0.2, 0.3, 30, 0.5, 3),
    ("原公式(涨×2+CL×1)", 2.0, 1.0, 0, 0, 0.5, 10),
]:
    wins=0; ndays=0; t3w=0
    for dt in target:
        if dt not in all_data: continue
        cand=all_data[dt]
        scored=[]
        for c in cand:
            p,cl,vr,buy,nh,dif,macd_g,above5,is_yang,wr_t,wr_y,y_p,rsi6,nm,code = c
            if wr_w > 0:
                wr_s = min(5, max(0, (wr_th-wr_t)*5/wr_th)) if wr_t < wr_th and wr_y >= wr_th else 0
            else:
                wr_s = 0
            score = p*p_w + cl*cl_w + ps(buy)*0.3 + ms(dif,macd_g)*macd_w + ma5_b*above5 + wr_s*wr_w
            scored.append((score, nh, p))
        if not scored: continue
        scored.sort(key=lambda x: (-x[0], -x[2]))
        ndays+=1
        if scored[0][1]>=2.5: wins+=1
        if any(s[1]>=2.5 for s in scored[:3]): t3w+=1
    print(f"{label:<35}: {wins}/{ndays}({wins*100/ndays:.1f}%) T3{t3w}/{ndays}({t3w*100/ndays:.1f}%)", flush=True)
