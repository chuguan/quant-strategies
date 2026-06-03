"""验证全年最优：CL×0.3+涨×1.5+MACD×0.5+MA5+5"""
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
            h1 = (kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
            c1 = (kdata[idx+1]['close']/bc-1)*100 if bc>0 else 0
            return h1, c1, kdata[idx]['close']
    except: return 0, 0, 0

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

# 原公式 vs 新公式
CL_W=0.3; P_W=1.5; MACD_W=0.5; MA5_B=5

print(f"2026年(全{len(target)}天):", flush=True)
print(f"新公式: CL×{CL_W} + 涨×{P_W} + 价格×0.3 + MACD×{MACD_W} + MA5+{MA5_B}", flush=True)
print()

wins=0; ndays=0; champ_5=0; top3_w=0; top3_5=0
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
        nh, nc, _ = get_nxt(code, dt)
        score = p*P_W + cl*CL_W + ps(buy)*0.3 + ms(dif,macd_g)*MACD_W + MA5_B*above5
        cand.append((score, p, nh, nm, code, cl, vr, buy, nc))
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[1]))
    ndays+=1
    if cand[0][2]>=2.5: wins+=1
    if cand[0][2]>=5.0: champ_5+=1
    if any(c[2]>=2.5 for c in cand[:3]): top3_w+=1
    if any(c[2]>=5.0 for c in cand[:3]): top3_5+=1

print(f"冠军达2.5%: {wins}/{ndays}({wins*100/ndays:.1f}%)")
print(f"冠军达5%: {champ_5}/{ndays}({champ_5*100/ndays:.1f}%)")
print(f"Top3任意达2.5%: {top3_w}/{ndays}({top3_w*100/ndays:.1f}%)")
print(f"Top3任意达5%: {top3_5}/{ndays}({top3_5*100/ndays:.1f}%)")

print()
print("=== 近20天每日冠军 ===")
for dt in target[-20:]:
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
        nh, nc, _ = get_nxt(code, dt)
        score = p*P_W + cl*CL_W + ps(buy)*0.3 + ms(dif,macd_g)*MACD_W + MA5_B*above5
        cand.append((score, p, nh, nm, code, cl, vr, buy, nc))
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[1]))
    c=cand[0]
    tag='🔥' if c[2]>=5 else('✅' if c[2]>=2.5 else'❌')
    print(f"{dt} {c[3][:8]:<10}({c[4]:<8}) 涨{c[1]:.1f}% CL{c[5]:.0f}% 分{c[0]:.0f} → 高{c[2]:+.1f}% 收{c[8]:+.1f}%{tag}")
