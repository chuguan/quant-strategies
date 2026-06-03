"""测试排名公式：加WR下穿35 +5分"""
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
    """WR(14): (HH14-Close)/(HH14-LL14)*100, WR<35时加分"""
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx < 14: return 0
        h14 = max(k['high'] for k in kdata[idx-13:idx+1])
        l14 = min(k['low'] for k in kdata[idx-13:idx+1])
        c = kdata[idx]['close']
        wr = (h14 - c) / (h14 - l14) * 100 if h14 != l14 else 50
        return wr
    except: return 0

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

# 测试：原版公式 vs 加WR
tests = {
    '涨x2+CL+价+MACDx0.5+5日': lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11],
    '+WR<35+5': lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + (5 if c[12] < 35 else 0),
}

# 也试试WR不同阈值
for wr_thresh, wr_score in [(30,5), (35,5), (40,5), (35,3), (35,8)]:
    label = f'WR<{wr_thresh}+{wr_score}'
    wins=0; ndays=0
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
            wr=calc_wr(code, dt)
            nh=get_nxt(code,dt)
            cand.append((cl, nm, code, p, vr, hsl, sz, buy, nh, dif, macd_g, above5, wr))
        if not cand: continue
        cand.sort(key=lambda c: (-(c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + (wr_score if c[12] < wr_thresh else 0)), -c[3]))
        ndays+=1
        if cand[0][8]>=2.5: wins+=1
    print(f'{label:<15}: {wins}/{ndays}({wins*100/ndays:.1f}%)')
