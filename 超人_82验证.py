"""验证82.1%突破：CL×0.1+涨×2.5+WR×0.5(下穿35)+MACD×0.3+MA5+3+前日>7%扣3"""
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
        y_p = (c-c_y)/c_y*100
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

p_min,p_max=5,8; vr_min,vr_max=0.8,2.0; hsl_min,hsl_max=5,15; sz_max=300; cl_min,cl_max=60,90; j_max=100
CL_W=0.1; P_W=2.5; WR_W=0.5; WR_TH=35; MACD_W=0.3; MA5_B=3; Y_PEN=3

print(f"公式: CL×{CL_W}+涨×{P_W}+WR×{WR_W}(下穿{WR_TH})+MACD×{MACD_W}+MA5+{MA5_B}+前日>7%扣{Y_PEN}", flush=True)
print()

wins=0; ndays=0; w5=0; t3w=0; t35=0
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
        nh, nc = get_nxt(code, dt)
        wr_s = min(5, max(0, (WR_TH-wr_t)*5/WR_TH)) if wr_t < WR_TH and wr_y >= WR_TH else 0
        yp = -Y_PEN if y_p > 7 else 0
        score = p*P_W + cl*CL_W + ps(buy)*0.3 + ms(dif,macd_g)*MACD_W + MA5_B*above5 + wr_s*WR_W + yp
        cand.append((score, p, nh, nm, code, cl, vr, wr_t, wr_y, wr_s, yp, y_p, nc, buy))
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[1]))
    ndays+=1
    if cand[0][2]>=2.5: wins+=1
    if cand[0][2]>=5: w5+=1
    if any(c[2]>=2.5 for c in cand[:3]): t3w+=1
    if any(c[2]>=5 for c in cand[:3]): t35+=1
    
    tag='🔥' if cand[0][2]>=5 else('✅' if cand[0][2]>=2.5 else'❌')
    wr_str=f'WR{cand[0][7]:.0f}/{cand[0][8]:.0f}+{cand[0][9]:.1f}' if cand[0][9]>0 else f'WR{cand[0][7]:.0f}'
    yp_str=f'前日{cand[0][11]:+.1f}%/扣{cand[0][10]:.0f}' if cand[0][10]!=0 else ''
    print(f"{dt}: {cand[0][3][:8]:<10} 涨{cand[0][1]:.1f}% CL{cand[0][5]:.0f}% {wr_str} {yp_str} 分{cand[0][0]:.0f} → {cand[0][2]:+.1f}%{tag}", flush=True)
    for i,c in enumerate(cand[:3]):
        tg='🔥' if c[2]>=5 else('✅' if c[2]>=2.5 else'')
        if tg:
            print(f"  Top{i+1}: {c[3]} {c[2]:+.1f}%{tg}", flush=True)

print(f"\n冠军达2.5%: {wins}/{ndays}({wins*100/ndays:.1f}%)", flush=True)
print(f"冠军达5%: {w5}/{ndays}({w5*100/ndays:.1f}%)", flush=True)
print(f"Top3任意达2.5%: {t3w}/{ndays}({t3w*100/ndays:.1f}%)", flush=True)
print(f"Top3任意达5%: {t35}/{ndays}({t35*100/ndays:.1f}%)", flush=True)
