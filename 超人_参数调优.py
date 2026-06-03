"""系统参数调优：找冠军最大胜率"""
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

def box_break(code, date):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 0, 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx < 20: return 0, 0
        h20 = max(k['high'] for k in kdata[idx-19:idx+1])
        l20 = min(k['low'] for k in kdata[idx-19:idx+1])
        c = kdata[idx]['close']
        return c/h20, (h20-l20)/l20*100
    except: return 0, 0

def ps(price):
    if price<15: return 10
    if price<25: return 9
    if price<35: return 8
    if price<45: return 7
    if price<55: return 5
    if price<70: return 3
    if price<90: return 2
    return 1

def ms(dif, g):
    if g and dif>0.5: return 10
    if g and dif>0.2: return 8
    if g: return 6
    if dif>0.5: return 4
    if dif>0: return 2
    if dif>-0.3: return 0
    if dif>-0.5: return -3
    return -5

p_min,p_max=5,8; vr_min,vr_max=0.8,2.0; hsl_min,hsl_max=5,15; sz_max=300; cl_min,cl_max=60,90; j_max=100

# ========== 预计算所有数据 ==========
print("预计算数据...", flush=True)
all_data = {}  # dt -> list of tuples
for dt in target:
    cand = []
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
        wr_t, wr_y = calc_wr(code, dt)
        ratio, amp = box_break(code, dt)
        nh, nc = get_nxt(code, dt)
        
        # 各因子基础分
        base_p = p  # 涨幅原始值
        base_cl = cl  # CL原始值
        price_s = ps(buy)
        macd_s = ms(dif, macd_g)
        ma5_s = 10 if above5 else 0
        
        # WR下穿35 (刚下穿才计)
        wr_s = min(5, max(0, (35-wr_t)*5/15)) if wr_t < 35 and wr_y >= 35 else 0
        
        # 资金增大 (收阳+量比)
        fund_s = min(5, max(0, (vr-0.8)*(p/5)*2)) if is_yang and vr>0.8 else 0
        
        # 箱体突破
        box_s = min(5, max(0, (ratio-0.97)*100*min(1.5,amp/15))) if ratio>0.97 else 0
        
        # CL加分
        cl_add_s = min(5, max(0, (cl-75)*0.5)) if cl>75 else 0
        
        cand.append((nm,code,p,cl,vr,hsl,buy,nh,dif,macd_g,above5,is_yang,
                     wr_t,wr_y,ratio,amp,nc,
                     base_p,base_cl,price_s,macd_s,ma5_s,wr_s,fund_s,box_s,cl_add_s))
    if cand:
        all_data[dt] = cand

print(f"共{len(all_data)}天数据", flush=True)

# ========== 参数搜索 ==========
# CL权重: 0.3~1.2
# 涨幅权重: 1.0~3.0
# WR权重: 0~2（乘以wr_s）
# 资金权重: 0~2
# 箱体权重: 0~2
# CL加分权重: 0~2
# 价格/MACD/MA5权重

best_win = 0
best_params = None
best_detail = None

results = []

# 先测CL权重降下来 + 新因子权重调大
for cl_w in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
    for p_w in [1.5, 2.0, 2.5]:
        for wr_w in [0, 0.5, 1.0, 1.5, 2.0]:
            for fund_w in [0, 0.5, 1.0, 1.5, 2.0]:
                for box_w in [0, 0.5, 1.0, 1.5, 2.0]:
                    for cla_w in [0, 0.5, 1.0, 1.5, 2.0]:
                        wins=0; ndays=0; total_n=0
                        for dt in target:
                            if dt not in all_data: continue
                            cand = all_data[dt]
                            # 评分 = 涨幅×p_w + CL×cl_w + 价格分×0.3 + MACD分×0.3 + MA5+5 + WR×wr_w + 资金×fund_w + 箱体×box_w + CL加分×cla_w
                            scored = []
                            for c in cand:
                                score = (c[17]*p_w + c[18]*cl_w + c[19]*0.3 + c[20]*0.3 + 5*c[21] + 
                                         c[22]*wr_w + c[23]*fund_w + c[24]*box_w + c[25]*cla_w)
                                scored.append((score, c[7], c[1], c[2], c[3]))
                            scored.sort(key=lambda x: (-x[0], -x[3]))
                            ndays += 1
                            total_n += len(scored)
                            if scored[0][1] >= 2.5:
                                wins += 1
                        
                        win_rate = wins*100/ndays
                        if win_rate > best_win:
                            best_win = win_rate
                            best_params = (cl_w, p_w, wr_w, fund_w, box_w, cla_w)
                            best_detail = f"{wins}/{ndays}({win_rate:.1f}%) 均{total_n/ndays:.0f}只"
                        
                        if win_rate >= 75 or (win_rate >= 70 and ndays >= 20):
                            results.append((win_rate, cl_w, p_w, wr_w, fund_w, box_w, cla_w, ndays, total_n//ndays))

results.sort(key=lambda x: -x[0])
print(f"\n=== 最优: {best_params} => {best_detail}", flush=True)
print(f"\n共有{len(results)}个组合胜率>=70%\n", flush=True)
print(f"{'胜率':>5} {'CLw':>4} {'涨w':>4} {'WRw':>4} {'金w':>4} {'箱w':>4} {'CL+':>4} {'天数':>4} {'均只':>4}", flush=True)
for r in results[:30]:
    print(f"{r[0]:>5.1f}% {r[1]:>4.1f} {r[2]:>4.1f} {r[3]:>4.1f} {r[4]:>4.1f} {r[5]:>4.1f} {r[6]:>4.1f} {r[7]:>4} {r[8]:>4}", flush=True)
