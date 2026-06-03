"""全2026年回测 — 最优公式(涨×1.5+CL×0.8+WR×1.0)"""
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

# 参数
p_min,p_max=5,8; vr_min,vr_max=0.8,2.0; hsl_min,hsl_max=5,15; sz_max=300; cl_min,cl_max=60,90; j_max=100

# 新公式 vs 原公式
P_W=1.5; CL_W=0.8; WR_W=1.0

print(f"2026年共 {len(target)} 个交易日")
print()

# 全部回测
for label, P_W, CL_W, WR_W in [("原公式(涨×2+CL×1)", 2.0, 1.0, 0), 
                                 ("新公式(涨×1.5+CL×0.8+WR×1)", 1.5, 0.8, 1.0)]:
    wins=0; ndays=0; total_n=0; champ_5pct=0
    top3_wins=0; top3_5pct=0
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
            is_yang=s.get('is_yang',0)
            wr_t, wr_y = calc_wr(code, dt)
            nh, nc = get_nxt(code, dt)
            
            wr_s = min(5, max(0, (35-wr_t)*5/15)) if wr_t < 35 and wr_y >= 35 else 0
            
            score = p*P_W + cl*CL_W + ps(buy)*0.3 + ms(dif,macd_g)*0.3 + 5*above5 + wr_s*WR_W
            
            cand.append((score, p, nh, nm, code, cl, vr, wr_t, wr_y, wr_s))
        
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[1]))
        ndays+=1
        total_n+=len(cand)
        if cand[0][2]>=2.5: wins+=1
        if cand[0][2]>=5.0: champ_5pct+=1
        if any(c[2]>=2.5 for c in cand[:3]): top3_wins+=1
        if any(c[2]>=5.0 for c in cand[:3]): top3_5pct+=1
    
    print(f"\n{label}:")
    print(f"  总天数: {ndays}")
    print(f"  冠军达2.5%: {wins}/{ndays}({wins*100/ndays:.1f}%)")
    print(f"  冠军达5%: {champ_5pct}/{ndays}({champ_5pct*100/ndays:.1f}%)")
    print(f"  Top3任意达2.5%: {top3_wins}/{ndays}({top3_wins*100/ndays:.1f}%)")
    print(f"  Top3任意达5%: {top3_5pct}/{ndays}({top3_5pct*100/ndays:.1f}%)")
    print(f"  均候选: {total_n/ndays:.0f}只")

print("\n\n=== 2026全量 每日冠军详情(新公式) ===")
P_W=1.5; CL_W=0.8; WR_W=1.0
month_wins = {}
for dt in target:
    month = dt[:7]
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
        is_yang=s.get('is_yang',0)
        wr_t, wr_y = calc_wr(code, dt)
        nh, nc = get_nxt(code, dt)
        wr_s = min(5, max(0, (35-wr_t)*5/15)) if wr_t < 35 and wr_y >= 35 else 0
        score = p*P_W + cl*CL_W + ps(buy)*0.3 + ms(dif,macd_g)*0.3 + 5*above5 + wr_s*WR_W
        cand.append((score, p, nh, nm, code, cl, vr, wr_t, wr_y, wr_s, buy))
    if not cand: continue
    cand.sort(key=lambda x: (-x[0], -x[1]))
    c=cand[0]
    tag='🔥' if c[2]>=5 else('✅' if c[2]>=2.5 else'❌')
    print(f"{dt} 冠军{c[3][:8]:<10}({c[4]:<8}) 涨{c[1]:.1f}% CL{c[5]:.0f}% 量{c[6]:.2f} WR{c[7]:.0f}/{c[8]:.0f}+{c[9]:.1f} 分{c[0]:.0f} → {c[2]:+.1f}%{tag}")
    
    if month not in month_wins:
        month_wins[month] = {'total':0, 'wins':0}
    month_wins[month]['total'] += 1
    if c[2]>=2.5: month_wins[month]['wins']+=1

print()
print("=== 按月度统计 ===")
for m in sorted(month_wins.keys()):
    d=month_wins[m]
    print(f"{m}: {d['wins']}/{d['total']}({d['wins']*100/d['total']:.1f}%)")
