"""叠加新维度：在突破v8(82.1%)评分公式上加新因子，选股不变"""
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

# ===== 选股条件：完全不改变 =====
P_MIN, P_MAX = 5, 8
VR_MIN, VR_MAX = 0.8, 2.0
HSL_MIN, HSL_MAX = 5, 15
SZ_MAX = 300
CL_MIN, CL_MAX = 60, 90
J_MAX = 100

# ===== 预计算基础数据（选股固定） =====
print("预计算...", flush=True)
all_data = {}
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
        wr_t, wr_y, y_p = calc_wr(code, dt)
        nh=get_nxt(code, dt)
        
        # K线数据
        fp=os.path.join(CACHE_DIR,f'{code}.json')
        klines=None
        if os.path.exists(fp):
            try:
                with open(fp) as f: klines=json.load(f)
            except: pass
        
        cand.append((p,cl,vr,hsl,sz,buy,nh,dif,macd_g,above5,is_yang,close,
                     ma5,ma10,ma20,wr_t,wr_y,y_p,jv,nm,code,klines))
    if cand: all_data[dt]=cand

total=sum(len(v) for v in all_data.values())
print(f"{len(all_data)}天, {total}只, 均{total//len(all_data)}只/天", flush=True)

# ===== 新维度评分函数 =====
def new_bonus(cl, vr, hsl, sz, ma5, ma10, ma20, close, is_yang, macd_g, dif, klines, dt):
    """所有新维度加分/减分，返回加分总和"""
    bonus = 0
    
    # === 量能维度加分 ===
    # 量比加分（选股本身已限制0.8~2.0，只对1.8~2.0加分）
    if 1.8 <= vr < 2.0: bonus += 1
    elif 2.0 <= vr <= 2.5: bonus += 2
    
    # 换手率加分  
    if 5 <= hsl <= 7: bonus += 2
    elif 3 <= hsl < 5: bonus += 1
    elif hsl > 10: bonus -= 2
    
    # === 趋势维度加分 ===
    # 均线多头
    if ma5 > ma10 > ma20 and ma5 > close*0.98: bonus += 3
    elif ma5 < ma10 < ma20: bonus -= 3
    
    # 突破前5日高点+20日线
    if klines:
        idx = next((i for i,k in enumerate(klines) if k['date']==dt), None)
        if idx is not None and idx >= 5:
            h5 = max(k['high'] for k in klines[idx-4:idx+1])
            if close > h5 and close > ma20: bonus += 3
    
    # 筹码峰（无法获取，跳过）
    
    # === 资金维度加分 ===
    # 市值加分
    if 50 <= sz <= 200: bonus += 2
    elif sz < 50 or sz > 200: bonus -= 2
    
    # 收阳+量比大=资金流入
    if is_yang and vr > 1.2: bonus += 2
    if macd_g and dif > 0: bonus += 1
    
    # 大单净流入（无数据，跳过）
    
    # === 高位放量滞涨减分 ===
    if klines:
        idx = next((i for i,k in enumerate(klines) if k['date']==dt), None)
        if idx is not None and idx >= 10:
            c10 = klines[idx-9]['close']
            pct_10d = (close/c10-1)*100
            if pct_10d < 20 and vr > 2.5 and pct_10d < 3:
                bonus -= 5
    
    return bonus

# ===== 批量测试新维度权重 =====
print(f"\n{'冠2.5':>6} {'T3':>5} {'乘数':>4} {'CLw':>4} {'涨w':>4} {'WRw':>4} {'扣分':>4} {'M5':>4}", flush=True)

results = []
for mult in [0.3, 0.5, 0.7, 1.0, 1.5, 2.0]:  # 新维度总乘数
    for cl_w in [0.1]:
        for p_w in [2.5]:
            for wr_w in [0.5]:
                for y_pen in [3]:
                    for ma5_b in [3]:
                        wins=0; ndays=0; t3w=0
                        for dt in target:
                            if dt not in all_data: continue
                            cand=[]
                            for c in all_data[dt]:
                                p,cl,vr,hsl,sz,buy,nh,dif,macd_g,above5,is_yang,close = c[:12]
                                ma5,ma10,ma20,wr_t,wr_y,y_p,jv,nm,code,klines = c[12:]
                                
                                # 突破v8基础分
                                wr_s = min(5, max(0, (35-wr_t)*5/35)) if wr_t < 35 and wr_y >= 35 else 0
                                yp = -y_pen if y_p > 7 else 0
                                base = p*p_w + cl*cl_w + ps(buy)*0.3 + \
                                       (10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else
                                        4 if dif>0.5 else 2 if dif>0 else 0)*0.3 + \
                                       ma5_b*above5 + wr_s*wr_w + yp
                                
                                # 新增维度加分
                                new = new_bonus(cl, vr, hsl, sz, ma5, ma10, ma20, close, 
                                               is_yang, macd_g, dif, klines, dt)
                                
                                score = base + new * mult
                                cand.append((score, p, nh, nm, code, cl, new))
                            if not cand: continue
                            cand.sort(key=lambda x: (-x[0], -x[1]))
                            ndays+=1
                            if cand[0][2]>=2.5: wins+=1
                            if any(c[2]>=2.5 for c in cand[:3]): t3w+=1
                        wr_rate=wins*100/ndays
                        results.append((wr_rate, t3w*100/ndays, mult, cl_w, p_w, wr_w, y_pen, ma5_b, t3w))

results.sort(key=lambda x: (-x[0], -x[1]))
for r in results[:20]:
    print(f"{r[0]:>5.1f}% {r[1]:>5.1f}% {r[2]:>4.1f} {r[3]:>4.1f} {r[4]:>4.1f} {r[5]:>4.1f} {r[6]:>4} {r[7]:>4}", flush=True)

# 最佳组合详情
print(f"\n=== 最佳组合 ===", flush=True)
best = results[0]
mult = best[2]; cl_w=0.1; p_w=2.5; wr_w=0.5; y_pen=3; ma5_b=3
wins=0; ndays=0; t3w=0; total_new=0
print(f"{'日期':<12} {'冠军':<10} {'涨%':>5} {'CL':>3} {'基分':>5} {'新增':>5} {'总分':>5} {'次高':>6}", flush=True)
print('-'*58, flush=True)
for dt in target:
    if dt not in all_data: continue
    cand=[]
    for c in all_data[dt]:
        p,cl,vr,hsl,sz,buy,nh,dif,macd_g,above5,is_yang,close=c[:12]
        ma5,ma10,ma20,wr_t,wr_y,y_p,jv,nm,code,klines=c[12:]
        wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
        yp=-y_pen if y_p>7 else 0
        base=p*p_w+cl*cl_w+ps(buy)*0.3+(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)*0.3+ma5_b*above5+wr_s*wr_w+yp
        new=new_bonus(cl,vr,hsl,sz,ma5,ma10,ma20,close,is_yang,macd_g,dif,klines,dt)*mult
        cand.append((base+new,p,nh,nm,code,cl,new,base))
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[1]))
    ndays+=1; c=cand[0]
    total_new+=c[6]
    tag='🔥' if c[2]>=5 else('✅' if c[2]>=2.5 else'❌')
    if c[2]>=2.5: wins+=1
    if any(c2[2]>=2.5 for c2 in cand[:3]): t3w+=1
    print(f"{dt}: {c[3][:8]:<10} {c[1]:>5.1f} {c[5]:>3.0f} {c[7]:>5.0f} {c[6]:>+5.1f} {c[0]:>5.0f} {c[2]:>+5.1f}%{tag}", flush=True)

print(f"\n冠军达2.5%: {wins}/{ndays}({wins*100/ndays:.1f}%)", flush=True)
print(f"Top3任意达2.5%: {t3w}/{ndays}({t3w*100/ndays:.1f}%)", flush=True)
print(f"新维度均加分: {total_new/max(ndays,1):.1f}分", flush=True)
