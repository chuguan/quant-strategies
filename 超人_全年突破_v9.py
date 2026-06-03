"""== 超人策略突破记录 ==
v1 (CL排序版): 固定选股条件，CL降序排名
v2 (原始评分版): 涨×2+CL×1+价格+MACD+MA5+10
v3-v6: 各种小调，均已丢失
v7 (2026-05-25): CL×0.2+涨×2.0+WR×0.3(下穿30)+MACD×0.5+MA5+3
  近28天78.6% 全年62.9%
v8 (2026-05-25): CL×0.1+涨×2.5+WR×0.5(下穿35)+MACD×0.3+MA5+3+前日>7%扣3
  近28天82.1% 全年62.9%
v8+f3 (2026-05-25): v8+换手5~7×0.5
  近28天85.7% 全年61.8%
v8+f9 (2026-05-25): v8+收阳+VR>1.2×0.3
  近28天85.7% 全年62.9%
v8+f5 (2026-05-25): v8+均线多头×0.3
  近28天82.1% 全年64.0%
"""

# ===== 全年策略全面搜索 =====
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
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

# 预计算全量
print("预计算全年...", flush=True)
all_data={}
for dt in target_all:
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
        
        # 所有因子值
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

print(f"共{len(all_data)}天, 总{sum(len(v) for v in all_data.values())}只", flush=True)

# ===== 全面搜索：base权重 + 新因子权重 =====
# 搜索突破v8的base权重（CLw, Pw, WRw, y_pen, ma5_b）+ 新因子权重
print(f"\n{'冠%':>5} {'T3%':>5} {'CL':>4} {'涨':>4} {'WR':>3} {'扣':>3} {'M5':>3} {'f3':>3} {'f5':>3} {'f9':>3} {'f1':>3} {'f8':>3}", flush=True)

results=[]
for cl_w in [0.05, 0.1, 0.15]:
    for p_w in [2.0, 2.5, 3.0]:
        for wr_w in [0.3, 0.5, 0.7]:
            for y_pen in [0, 3]:
                for ma5_b in [0, 3, 5]:
                    for f3_w in [0, 0.3, 0.5, 0.7]:
                        for f5_w in [0, 0.3, 0.5]:
                            for f9_w in [0, 0.3, 0.5]:
                                for f1_w in [0, 0.3, 0.5]:
                                    for f8_w in [0, 0.3, 0.5]:
                                        wins=0; nd=0; t3=0
                                        for dt in target_all:
                                            if dt not in all_data: continue
                                            cand=[]
                                            for c in all_data[dt]:
                                                p,cl,vr,hsl,sz,buy,dif,macd_g,above5,is_yang,close = c[:11]
                                                ma5,ma10,ma20,wr_t,wr_y,y_p,jv,nm = c[11:19]
                                                f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11 = c[19:]
                                                
                                                wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
                                                yp=-y_pen if y_p>7 else 0
                                                macd_s = (10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                                                
                                                base = p*p_w + cl*cl_w + ps(buy)*0.3 + macd_s*0.3 + ma5_b*above5 + wr_s*wr_w + yp
                                                new = f1*f1_w + f3*f3_w + f5*f5_w + f8*f8_w + f9*f9_w
                                                
                                                cand.append((base+new, nh, p))
                                            if not cand: continue
                                            cand.sort(key=lambda x: (-x[0], -x[2]))
                                            nd+=1
                                            if cand[0][1]>=2.5: wins+=1
                                            if any(c[1]>=2.5 for c in cand[:3]): t3+=1
                                        rate=wins*100/nd if nd else 0
                                        if rate >= 64.0:  # 只记录>=64.0的
                                            results.append((rate, t3*100/nd, cl_w, p_w, wr_w, y_pen, ma5_b, f3_w, f5_w, f9_w, f1_w, f8_w))

results.sort(key=lambda x: (-x[0], -x[1]))
for r in results[:30]:
    print(f"{r[0]:>4.1f}% {r[1]:>4.1f}% {r[2]:>4.2f} {r[3]:>4.1f} {r[4]:>3.1f} {r[5]:>3} {r[6]:>3} {r[7]:>3.1f} {r[8]:>3.1f} {r[9]:>3.1f} {r[10]:>3.1f} {r[11]:>3.1f}", flush=True)

# 最佳结果详情
if results:
    best = results[0]
    print(f"\n=== 全年最佳突破 ===", flush=True)
    print(f"胜率: {best[0]:.1f}% ({wins if 'wins' in dir() else '?'}天)", flush=True)
    print(f"参数: CL×{best[2]} + 涨×{best[3]} + WR×{best[4]} + 扣{best[5]} + MA5+{best[6]} + f3×{best[7]} + f5×{best[8]} + f9×{best[9]} + f1×{best[10]} + f8×{best[11]}", flush=True)
