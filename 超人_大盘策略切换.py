"""大盘策略切换：涨日vs跌日，分别找最优公式"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target = [d for d in dates if d >= '2026-02-01']  # 够天数就行

def get_nxt(code, date):
    fp=os.path.join(CACHE_DIR,f'{code}.json')
    if not os.path.exists(fp): return 0
    try:
        with open(fp) as f: kdata=json.load(f)
        idx=next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is not None and idx+1 < len(kdata):
            bc=kdata[idx]['close']
            return (kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
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

P_MIN,P_MAX=5,8;VR_MIN,VR_MAX=0.8,2.0;HSL_MIN,HSL_MAX=5,15;SZ_MAX=300;CL_MIN,CL_MAX=60,90;J_MAX=100

# ===== 第一步：每天计算大盘信号 =====
# 大盘信号 = 所有股票平均涨幅为正=涨日
# 再加一个：前5日连续涨跌趋势
print("计算大盘信号...", flush=True)
market_signals = {}
for dt in target:
    stocks = data.get(dt, [])
    if not stocks: continue
    avg_p = sum(s.get('p',0) or 0 for s in stocks) / len(stocks)
    
    # 近5日趋势（用日期往前推）
    idx = dates.index(dt)
    lookback = [dates[j] for j in range(max(0,idx-4), idx)]
    trend_sign = 0
    for ld in lookback:
        ls = data.get(ld, [])
        if ls: trend_sign += (1 if sum(s.get('p',0) or 0 for s in ls)/len(ls) > 0 else -1)
    
    market_signals[dt] = {
        'avg_p': avg_p,
        'is_up': avg_p > 0.5,       # 大盘涨>0.5%
        'is_down': avg_p < -0.5,    # 大盘跌>0.5%
        'is_flat': -0.5 <= avg_p <= 0.5,  # 横盘
        'trend': trend_sign         # 近5日趋势
    }

# ===== 第二步：预计算所有数据 =====
print("预计算...", flush=True)
all_data={}
for dt in target:
    cand=[]
    for s in data.get(dt,[]):
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
            idx2=next((i for i,k in enumerate(klines) if k['date']==dt), None)
            if idx2 is not None and idx2>=5:
                h5=max(k['high'] for k in klines[idx2-4:idx2+1])
                if close>h5 and close>ma20: f7=3
        f8=2 if 50<=sz<=200 else (-2 if sz<50 or sz>200 else 0)
        f9=2 if is_yang and vr>1.2 else 0
        f10=1 if macd_g and dif>0 else 0
        f11=0
        if klines:
            idx3=next((i for i,k in enumerate(klines) if k['date']==dt), None)
            if idx3 is not None and idx3>=10:
                c10=klines[idx3-9]['close']
                if (close/c10-1)*100<20 and vr>2.5 and p<3: f11=-5
        
        cand.append((p,cl,vr,hsl,sz,buy,dif,macd_g,above5,is_yang,close,
                     ma5,ma10,ma20,wr_t,wr_y,y_p,jv,nm,
                     f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,nh))
    if cand: all_data[dt]=cand

# ===== 第三步：分别搜索涨日/跌日最优 =====
print(f"\n涨日/跌日/全量分别调优", flush=True)

def search_best(target_dates, label):
    best_rate=0; best_params=None
    for cl_w in [0.05, 0.1, 0.15]:
        for p_w in [2.0, 2.5, 3.0]:
            for wr_w in [0.3, 0.5, 0.7]:
                for y_pen in [0, 3]:
                    for ma5_b in [0, 3]:
                        for f3_w in [0, 0.3, 0.5]:
                            for f5_w in [0, 0.3, 0.5]:
                                for f9_w in [0, 0.3, 0.5]:
                                    wins=0; nd=0
                                    for dt in target_dates:
                                        if dt not in all_data: continue
                                        cand=[]
                                        for c in all_data[dt]:
                                            p,cl,vr,hsl,sz,buy,dif,macd_g,above5,is_yang,close=c[:11]
                                            ma5,ma10,ma20,wr_t,wr_y,y_p,jv,nm=c[11:19]
                                            fv=list(c[19:30]); nh=c[30]
                                            
                                            wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
                                            yp=-y_pen if y_p>7 else 0
                                            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                                            
                                            base=p*p_w+cl*cl_w+ps(buy)*0.3+macd_s*0.3+ma5_b*above5+wr_s*wr_w+yp
                                            new=fv[2]*f3_w+fv[4]*f5_w+fv[8]*f9_w  # f3, f5, f9
                                            
                                            cand.append((base+new, nh, p))
                                        if not cand: continue
                                        cand.sort(key=lambda x: (-x[0], -x[2]))
                                        nd+=1
                                        if cand[0][1]>=2.5: wins+=1
                                    rate=wins*100/nd if nd else 0
                                    if rate>best_rate:
                                        best_rate=rate; best_params=(cl_w,p_w,wr_w,y_pen,ma5_b,f3_w,f5_w,f9_w,wins,nd)
    return best_params, best_rate

# 全量
best_all, rate_all = search_best(target, "全量")
print(f"\n全量({len(target)}天): {best_all[7]}/{best_all[8]}({rate_all:.1f}%)", flush=True)
print(f"  CL×{best_all[0]} 涨×{best_all[1]} WR×{best_all[2]} 扣{best_all[3]} M5+{best_all[4]} f3×{best_all[5]} f5×{best_all[6]} f9×{best_all[7]}")

# 涨日
up_days=[dt for dt in target if dt in market_signals and market_signals[dt]['is_up']]
best_up, rate_up = search_best(up_days, "涨日")
print(f"\n涨日({len(up_days)}天): {best_up[7]}/{best_up[8]}({rate_up:.1f}%)", flush=True)
print(f"  CL×{best_up[0]} 涨×{best_up[1]} WR×{best_up[2]} 扣{best_up[3]} M5+{best_up[4]} f3×{best_up[5]} f5×{best_up[6]} f9×{best_up[7]})")

# 跌日
down_days=[dt for dt in target if dt in market_signals and market_signals[dt]['is_down']]
best_down, rate_down = search_best(down_days, "跌日")
print(f"\n跌日({len(down_days)}天): {best_down[7]}/{best_down[8]}({rate_down:.1f}%)", flush=True)
print(f"  CL×{best_down[0]} 涨×{best_down[1]} WR×{best_down[2]} 扣{best_down[3]} M5+{best_down[4]} f3×{best_down[5]} f5×{best_down[6]} f9×{best_down[7]})")

# 横盘
flat_days=[dt for dt in target if dt in market_signals and market_signals[dt]['is_flat']]
best_flat, rate_flat = search_best(flat_days, "横盘")
print(f"\n横盘({len(flat_days)}天): {best_flat[7]}/{best_flat[8]}({rate_flat:.1f}%)", flush=True)
print(f"  CL×{best_flat[0]} 涨×{best_flat[1]} WR×{best_flat[2]} 扣{best_flat[3]} M5+{best_flat[4]} f3×{best_flat[5]} f5×{best_flat[6]} f9×{best_flat[7]})")
