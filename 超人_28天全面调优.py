"""近28天全面调优 —— 记录每一次突破"""
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
        if idx < 15: return wr_t, 50
        h14_y = max(k['high'] for k in kdata[idx-14:idx])
        l14_y = min(k['low'] for k in kdata[idx-14:idx])
        c_y = kdata[idx-1]['close']
        wr_y = (h14_y-c_y)/(h14_y-l14_y)*100 if h14_y!=l14_y else 50
        return wr_t, wr_y
    except: return 50, 50

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
print("预计算近28天...", flush=True)
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
        wr_t, wr_y = calc_wr(code, dt)
        nh = get_nxt(code, dt)
        cand.append((p,cl,vr,buy,nh,dif,macd_g,above5,wr_t,wr_y,nm,code))
    if cand:
        all_data[dt]=cand

print(f"{len(all_data)}天, 共{sum(len(v) for v in all_data.values())}只候选", flush=True)

# ===== 网格搜索 =====
print(f"\n{'ID':>3} {'CLw':>4} {'涨w':>4} {'WRw':>4} {'Mw':>4} {'M5':>4} {'Wthr':>4} {'冠2.5':>7} {'冠5%':>6} {'T3_2.5':>7} {'T3_5%':>6} {'均只':>4}", flush=True)

results = []

# WR下穿的不同阈值
for wr_threshold in [25, 30, 35, 40]:
    for cl_w in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        for p_w in [1.0, 1.5, 2.0, 2.5]:
            for wr_w in [0.3, 0.5, 0.7, 1.0, 1.5, 2.0]:
                for macd_w in [0.3, 0.5]:
                    for ma5_b in [3, 5, 10]:
                        wins=0; ndays=0; w5=0; t3w=0; t35=0; total_n=0
                        for dt in target:
                            if dt not in all_data: continue
                            cand=all_data[dt]
                            scored=[]
                            for c in cand:
                                p,cl,vr,buy,nh,dif,macd_g,above5,wr_t,wr_y,nm,code = c
                                wr_s = min(5, max(0, (wr_threshold-wr_t)*5/wr_threshold)) if wr_t < wr_threshold and wr_y >= wr_threshold else 0
                                score = p*p_w + cl*cl_w + ps(buy)*0.3 + ms(dif,macd_g)*macd_w + ma5_b*above5 + wr_s*wr_w
                                scored.append((score, nh, p))
                            if not scored: continue
                            scored.sort(key=lambda x: (-x[0], -x[2]))
                            ndays+=1; total_n+=len(scored)
                            if scored[0][1]>=2.5: wins+=1
                            if scored[0][1]>=5: w5+=1
                            if any(s[1]>=2.5 for s in scored[:3]): t3w+=1
                            if any(s[1]>=5 for s in scored[:3]): t35+=1
                        wr_rate=wins*100/ndays
                        results.append((wr_rate, w5*100/ndays, t3w*100/ndays, t35*100/ndays, 
                                       cl_w, p_w, wr_w, macd_w, ma5_b, wr_threshold, total_n//ndays))

results.sort(key=lambda x: (-x[0], -x[1], -x[2]))
best = results[0]
print(f"\n========== 突破记录 ==========", flush=True)
print(f"时间: 2026-04-10 ~ 2026-05-22 ({len(target)}天)", flush=True)
print(f"公式: CL×{best[4]} + 涨×{best[5]} + WR×{best[6]}(下穿{best[9]}) + MACD×{best[7]} + MA5+{best[8]}", flush=True)
print(f"冠军达2.5%: {best[0]:.1f}%", flush=True)
print(f"冠军达5%: {best[1]:.1f}%", flush=True)
print(f"Top3任意达2.5%: {best[2]:.1f}%", flush=True)
print(f"Top3任意达5%: {best[3]:.1f}%", flush=True)
print(f"均候选: {best[10]}只", flush=True)

print(f"\n=== 全部突破记录 (前30) ===", flush=True)
for i, r in enumerate(results[:30]):
    print(f"#{i+1:<2} CL{r[4]:>4.1f} 涨{r[5]:>4.1f} WR{r[6]:>4.1f}@<{r[9]:<2} M{r[7]:>3.1f} M5{r[8]:>3} | 冠{r[0]:>5.1f}% 冠5{r[1]:>5.1f}% T3{r[2]:>5.1f}% T35{r[3]:>5.1f}% | {r[10]}只", flush=True)

# 也记录原公式做对比
print(f"\n=== 原公式对比 ===", flush=True)
for label, p_w, cl_w, wr_w, macd_w, ma5_b in [
    ("原(涨×2+CL×1)", 2.0, 1.0, 0, 0.5, 10),
    ("当前(CL×0.8+涨×1.5+WR×1.0@35)", 1.5, 0.8, 1.0, 0.3, 5),
]:
    wins=0; ndays=0; w5=0; t3w=0; t35=0
    for dt in target:
        if dt not in all_data: continue
        cand=all_data[dt]
        scored=[]
        for c in cand:
            p,cl,vr,buy,nh,dif,macd_g,above5,wr_t,wr_y,nm,code = c
            if wr_w > 0:
                wr_s = min(5, max(0, (35-wr_t)*5/15)) if wr_t < 35 and wr_y >= 35 else 0
            else:
                wr_s = 0
            score = p*p_w + cl*cl_w + ps(buy)*0.3 + ms(dif,macd_g)*macd_w + ma5_b*above5 + wr_s*wr_w
            scored.append((score, nh, p))
        if not scored: continue
        scored.sort(key=lambda x: (-x[0], -x[2]))
        ndays+=1
        if scored[0][1]>=2.5: wins+=1
        if scored[0][1]>=5: w5+=1
        if any(s[1]>=2.5 for s in scored[:3]): t3w+=1
        if any(s[1]>=5 for s in scored[:3]): t35+=1
    print(f"{label:<35}: 冠{wins}/{ndays}({wins*100/ndays:.1f}%) T3{t3w}/{ndays}({t3w*100/ndays:.1f}%)", flush=True)
