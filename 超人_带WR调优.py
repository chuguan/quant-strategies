"""包含WR下穿35的全量数据优化"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target = [d for d in dates if d >= '2026-01-01']

def get_nxt(code, date):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 0, 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is not None and idx+1 < len(kdata):
            bc = kdata[idx]['close']
            return ((kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0,
                    (kdata[idx+1]['close']/bc-1)*100 if bc>0 else 0)
    except: return 0, 0

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

def ps(price):
    if price<15: return 10
    return max(1, 11 - price/10)

def ms(dif, g):
    if g and dif>0.5: return 10
    if g and dif>0.2: return 8
    if g: return 6
    if dif>0.5: return 4
    if dif>0: return 2
    if dif>-0.3: return 0
    if dif>-0.5: return -3
    return -5

# WR比例浮动评分
def wr_score(wr_t, wr_y):
    if wr_t >= 35: return 0
    if wr_y >= 35:  # 刚下穿
        depth = min(15, 35 - wr_t)
        return depth * 5 / 15  # 最深15→5分
    return 0  # 已经在下穿区不算

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
        wr_t, wr_y = calc_wr(code, dt)
        nh, nc = get_nxt(code, dt)
        wr_s = wr_score(wr_t, wr_y)
        cand.append((p,cl,vr,hsl,buy,nh,dif,macd_g,above5,wr_s,nm,code,nc))
    if cand:
        all_data[dt]=cand

print(f"共{len(all_data)}天", flush=True)

# 网格搜索（带WR）
best=[]
for cl_w in [0.3, 0.5, 0.7, 0.8, 0.9, 1.0]:
    for p_w in [1.0, 1.5, 2.0, 2.5]:
        for wr_w in [0.3, 0.5, 0.7, 1.0, 1.5]:
            for macd_w in [0.3, 0.5]:
                for ma5_b in [5, 10]:
                    wins=0; ndays=0
                    for dt in target:
                        if dt not in all_data: continue
                        cand=all_data[dt]
                        scored=[(c[0]*p_w + c[1]*cl_w + ps(c[4])*0.3 + ms(c[6],c[7])*macd_w + ma5_b*c[8] + c[9]*wr_w, c[5], c[0]) for c in cand]
                        scored.sort(key=lambda x: (-x[0], -x[2]))
                        ndays+=1
                        if scored[0][1]>=2.5: wins+=1
                    wr_rate=wins*100/ndays
                    if wr_rate>=62:
                        best.append((wr_rate,cl_w,p_w,wr_w,macd_w,ma5_b))

best.sort(key=lambda x:-x[0])
print(f"\n{'胜率':>6} {'CLw':>4} {'涨w':>4} {'WRw':>4} {'Mw':>4} {'MA5':>4}", flush=True)
for r in best[:40]:
    print(f"{r[0]:>5.1f}% {r[1]:>4.1f} {r[2]:>4.1f} {r[3]:>4.1f} {r[4]:>4.1f} {r[5]:>4}", flush=True)

# 再看原公式（同参数集）
print("\n--- 原公式(涨×2+CL×1 无WR) ---", flush=True)
wins=0; ndays=0
for dt in target:
    if dt not in all_data: continue
    cand=all_data[dt]
    scored=[(c[0]*2 + c[1]*1 + ps(c[4])*0.5 + ms(c[6],c[7])*0.5 + 10*c[8], c[5], c[0]) for c in cand]
    scored.sort(key=lambda x: (-x[0], -x[2]))
    ndays+=1
    if scored[0][1]>=2.5: wins+=1
print(f"全年: {wins}/{ndays}({wins*100/ndays:.1f}%)", flush=True)
