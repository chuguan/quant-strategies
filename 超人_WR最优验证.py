"""验证最优带WR公式：CL×0.3+涨×2.0+WR×0.3(绝对值)+MACD×0.5+MA5+5"""
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
    if not os.path.exists(fp): return 0, 0, 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is not None and idx+1 < len(kdata):
            bc = kdata[idx]['close']
            return ((kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0,
                    (kdata[idx+1]['close']/bc-1)*100 if bc>0 else 0,
                    kdata[idx]['close'])
    except: return 0, 0, 0

def calc_wr(code, date):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 50
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx < 14: return 50
        h14 = max(k['high'] for k in kdata[idx-13:idx+1])
        l14 = min(k['low'] for k in kdata[idx-13:idx+1])
        c = kdata[idx]['close']
        return (h14-c)/(h14-l14)*100 if h14!=l14 else 50
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

# 最优带WR公式
CL_W=0.3; P_W=2.0; MACD_W=0.5; MA5_B=5; WR_W=0.3

print(f"最优带WR公式: CL×{CL_W} + 涨×{P_W} + WR×{WR_W}(绝对值) + MACD×{MACD_W} + MA5+{MA5_B}", flush=True)
print(f"WR评分: WR<35则 min(5, 5*(35-WR)/35)*{WR_W}", flush=True)
print()

# 对比原公式
for label, p_w, cl_w, wr_w, macd_w, ma5_b in [
    ("原(涨×2+CL×1)", 2.0, 1.0, 0, 0.5, 10),
    ("新(含WR绝对值)", P_W, CL_W, WR_W, MACD_W, MA5_B),
]:
    wins=0; ndays=0; champ_5=0; top3_w=0; top3_5=0; total_n=0; w5=0
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
            wr_v=calc_wr(code, dt)
            nh, nc, _ = get_nxt(code, dt)
            wr_s = min(5, 5*(35-wr_v)/35) if wr_v < 35 else 0
            score = p*p_w + cl*cl_w + ps(buy)*0.3 + ms(dif,macd_g)*macd_w + ma5_b*above5 + wr_s*wr_w
            cand.append((score, p, nh, nm, code, cl, vr, wr_v, wr_s))
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[1]))
        ndays+=1; total_n+=len(cand)
        if cand[0][2]>=2.5: wins+=1
        if cand[0][2]>=5: champ_5+=1
        if any(c[2]>=2.5 for c in cand[:3]): top3_w+=1
        if any(c[2]>=5 for c in cand[:3]): top3_5+=1
        if cand[0][2]>=2.5: w5+=1
    
    print(f"{label}:")
    print(f"  冠军达2.5%: {wins}/{ndays}({wins*100/ndays:.1f}%)")
    print(f"  冠军达5%: {champ_5}/{ndays}({champ_5*100/ndays:.1f}%)")
    print(f"  Top3任意达2.5%: {top3_w}/{ndays}({top3_w*100/ndays:.1f}%)")
    print(f"  Top3任意达5%: {top3_5}/{ndays}({top3_5*100/ndays:.1f}%)")
    print(f"  均候选: {total_n/ndays:.0f}只")
    print()

# 每月明细
print("=== 月度明细(新公式) ===")
month_wins={}
for dt in target:
    month=dt[:7]
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
        wr_v=calc_wr(code, dt)
        nh, nc, _ = get_nxt(code, dt)
        wr_s = min(5, 5*(35-wr_v)/35) if wr_v < 35 else 0
        score = p*P_W + cl*CL_W + ps(buy)*0.3 + ms(dif,macd_g)*MACD_W + MA5_B*above5 + wr_s*WR_W
        cand.append((score, p, nh, nm, code, cl, vr, wr_v, wr_s))
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[1]))
    tag='🔥' if cand[0][2]>=5 else('✅' if cand[0][2]>=2.5 else '❌')
    if month not in month_wins:
        month_wins[month]={'total':0,'wins':0}
    month_wins[month]['total']+=1
    if cand[0][2]>=2.5: month_wins[month]['wins']+=1
    wr_str=f"WR{cand[0][7]:.0f}+{cand[0][8]:.1f}" if cand[0][8]>0 else f"WR{cand[0][7]:.0f}"
    print(f"{dt}: {cand[0][3][:8]:<10} 涨{cand[0][1]:.1f}% CL{cand[0][5]:.0f}% {wr_str} 分{cand[0][0]:.0f} → {cand[0][2]:+.1f}%{tag}")

print()
for m in sorted(month_wins.keys()):
    d=month_wins[m]
    print(f"{m}: {d['wins']}/{d['total']}({d['wins']*100/d['total']:.1f}%)")
