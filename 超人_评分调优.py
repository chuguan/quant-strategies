"""仅调评分机制 - 不改变选票条件 - 继续突破82.1%"""
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
def ms(dif, g):
    if g and dif>0.5: return 10
    if g and dif>0.2: return 8
    if g: return 6
    if dif>0.5: return 4
    if dif>0: return 2
    return 0 if dif>-0.3 else -3 if dif>-0.5 else -5

# 固定选票条件（不改变候选数）
p_min,p_max=5,8; vr_min,vr_max=0.8,2.0; hsl_min,hsl_max=5,15; sz_max=300; cl_min,cl_max=60,90; j_max=100

# 预计算（固定选票结果）
print("预计算固定候选池...", flush=True)
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
        wr_t, wr_y, y_p = calc_wr(code, dt)
        nh = get_nxt(code, dt)
        cand.append((p,cl,vr,buy,nh,dif,macd_g,above5,wr_t,wr_y,y_p,nm,code))
    if cand: all_data[dt]=cand

total_cand = sum(len(v) for v in all_data.values())
print(f"{len(all_data)}天, 共{total_cand}只候选, 均{total_cand//len(all_data)}只/天", flush=True)

# ===== 评分机制搜索 =====
print(f"\n{'冠2.5':>6} {'CLw':>5} {'涨w':>5} {'WRw':>5} {'Wth':>4} {'Mw':>5} {'M5':>4} {'扣分':>4} {'T3':>5} {'型':>4}", flush=True)

results = []

# 不同WR评分方式
for wr_type in ['比例(下穿)', '二进制', '比例(绝对值)']:
    for cl_w in [0.05, 0.1, 0.15, 0.2]:
        for p_w in [1.5, 2.0, 2.5, 3.0]:
            for wr_w in [0.3, 0.5, 0.7, 1.0, 2.0, 3.0, 5.0]:
                for wr_th in [25, 30, 35, 40]:
                    for macd_w in [0.3, 0.5]:
                        for ma5_b in [0, 3, 5]:
                            for y_pen in [0, 3, 5]:
                                wins=0; ndays=0; t3w=0
                                for dt in target:
                                    if dt not in all_data: continue
                                    cand=all_data[dt]
                                    scored=[]
                                    for c in cand:
                                        p,cl,vr,buy,nh,dif,macd_g,above5,wr_t,wr_y,y_p,nm,code = c
                                        # WR评分方式
                                        if wr_type == '比例(下穿)':
                                            wr_s = min(5, max(0, (wr_th-wr_t)*5/wr_th)) if wr_t < wr_th and wr_y >= wr_th else 0
                                        elif wr_type == '二进制':
                                            wr_s = 5 if wr_t < wr_th and wr_y >= wr_th else 0
                                        else:  # 比例(绝对值)
                                            wr_s = min(5, 5*(wr_th-wr_t)/wr_th) if wr_t < wr_th else 0
                                        yp = -y_pen if y_p > 7 and y_pen > 0 else 0
                                        score = p*p_w + cl*cl_w + ps(buy)*0.3 + ms(dif,macd_g)*macd_w + ma5_b*above5 + wr_s*wr_w + yp
                                        scored.append((score, nh, p))
                                    if not scored: continue
                                    scored.sort(key=lambda x: (-x[0], -x[2]))
                                    ndays+=1
                                    if scored[0][1]>=2.5: wins+=1
                                    if any(s[1]>=2.5 for s in scored[:3]): t3w+=1
                                wr_rate = wins*100/ndays
                                # 只保留T3>=85%的（不牺牲Top3）
                                if t3w*100/ndays >= 85:
                                    results.append((wr_rate, cl_w, p_w, wr_w, wr_th, macd_w, ma5_b, y_pen, t3w*100/ndays, wr_type[:2]))

results.sort(key=lambda x: (-x[0], -x[8]))
for r in results[:20]:
    print(f"{r[0]:>5.1f}% {r[1]:>5.2f} {r[2]:>5.1f} {r[3]:>5.1f} {r[4]:>4} {r[5]:>5.1f} {r[6]:>4} {r[7]:>4} {r[8]:>4.1f}% {r[9]:>4}", flush=True)

# 当前突破公式
print(f"\n=== 当前突破公式结果 ===", flush=True)
cl_w=0.1; p_w=2.5; wr_type='比例(下穿)'; wr_th=35; wr_w=0.5; macd_w=0.3; ma5_b=3; y_pen=3
wins=0; ndays=0
for dt in target:
    if dt not in all_data: continue
    cand=all_data[dt]
    scored=[]
    for c in cand:
        p,cl,vr,buy,nh,dif,macd_g,above5,wr_t,wr_y,y_p,nm,code = c
        wr_s = min(5, max(0, (wr_th-wr_t)*5/wr_th)) if wr_t < wr_th and wr_y >= wr_th else 0
        yp = -y_pen if y_p > 7 and y_pen > 0 else 0
        score = p*p_w + cl*cl_w + ps(buy)*0.3 + ms(dif,macd_g)*macd_w + ma5_b*above5 + wr_s*wr_w + yp
        scored.append((score, nh, p, nm, code, cl, wr_t, wr_y, wr_s, yp))
    if not scored: continue
    scored.sort(key=lambda x: (-x[0], -x[2]))
    ndays+=1
    if scored[0][1]>=2.5: wins+=1
print(f"突破v8: {wins}/{ndays}({wins*100/ndays:.1f}%)", flush=True)
