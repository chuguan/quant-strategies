"""综合测试：WR下穿35+主力资金+大箱体突破 全部比例浮动评分"""
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
    """Williams %R (14日)"""
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 50
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx < 14: return 50
        h14 = max(k['high'] for k in kdata[idx-13:idx+1])
        l14 = min(k['low'] for k in kdata[idx-13:idx+1])
        c = kdata[idx]['close']
        return (h14 - c) / (h14 - l14) * 100 if h14 != l14 else 50
    except: return 50

def box_break(code, date):
    """箱体突破：比例浮动评分"""
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx < 20: return 0
        h20 = max(k['high'] for k in kdata[idx-19:idx+1])
        c = kdata[idx]['close']
        # 比例浮动：close/h20=0.97→0分, 1.0→3分, 1.02→5分
        ratio = c / h20
        if ratio <= 0.97: return 0
        return min(5, (ratio - 0.97) * 100 * 5/3)
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

def wr_score_prop(wr):
    """WR下穿35比例浮动评分：WR越低分越高，35→0, 20→~2.14, 0→5"""
    if wr >= 35: return 0
    return 5 * (35 - wr) / 35

def fund_score_prop(vr, is_yang):
    """主力资金增大比例浮动：量比越高×收阳→越高，封顶5"""
    if not is_yang or vr <= 0.8: return 0
    return min(5, (vr - 0.8) * 5 / 1.2)  # vr=2.0→5分

p_min,p_max=5,8; vr_min,vr_max=0.8,2.0; hsl_min,hsl_max=5,15; sz_max=300; cl_min,cl_max=60,90; j_max=100

# ===== 测试各种组合 =====
tests = [
    # 基线（不加新因子）
    ('基线(涨x2+CL+价+MACD+5日)', 
     lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11]),
    # 逐个加
    ('+WR浮动', 
     lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + wr_score_prop(c[12])),
    ('+资金浮动', 
     lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + fund_score_prop(c[4], c[13])),
    ('+箱体浮动', 
     lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + c[14]),
    # 两两组合
    ('+WR+资金', 
     lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + wr_score_prop(c[12]) + fund_score_prop(c[4], c[13])),
    ('+WR+箱体', 
     lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + wr_score_prop(c[12]) + c[14]),
    ('+资金+箱体', 
     lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + fund_score_prop(c[4], c[13]) + c[14]),
    # 三因子全加
    ('+WR+资金+箱体(全浮动)', 
     lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + wr_score_prop(c[12]) + fund_score_prop(c[4], c[13]) + c[14]),
    # 试试不同的WR权重
    ('WR(30→5)+资金+箱体', 
     lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + min(5, 5*(30-wr_score_prop(c[12])*6)) + fund_score_prop(c[4], c[13]) + c[14]),
]

for label, sort_key in tests:
    wins=0; ndays=0; total_n=0
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
            wr=calc_wr(code, dt)
            bx=box_break(code, dt)
            nh=get_nxt(code,dt)
            cand.append((cl,nm,code,p,vr,hsl,sz,buy,nh,dif,macd_g,above5,wr,is_yang,bx))
        if not cand: continue
        cand.sort(key=lambda c: (-sort_key(c), -c[3]))
        ndays+=1
        total_n+=len(cand)
        if cand[0][8]>=2.5: wins+=1
    print(f'{label:<35}: {wins}/{ndays}({wins*100/ndays:.1f}%) | 均{total_n/ndays:.0f}只')

print()

# ===== 最佳组合详细输出 =====
print("=== 最佳组合详情(三因子全加) ===")
wins=0; ndays=0
top3_win=0; top3_5pct=0
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
        wr=calc_wr(code, dt)
        bx=box_break(code, dt)
        nh=get_nxt(code,dt)
        cand.append((cl,nm,code,p,vr,hsl,sz,buy,nh,dif,macd_g,above5,wr,is_yang,bx))
    if not cand: continue
    # 三因子全加排名
    def key_fn(c):
        return -(c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + wr_score_prop(c[12]) + fund_score_prop(c[4], c[13]) + c[14])
    cand.sort(key=key_fn)
    ndays+=1
    if cand[0][8]>=2.5: wins+=1
    if any(c[8]>=2.5 for c in cand[:3]): top3_win+=1
    if any(c[8]>=5.0 for c in cand[:3]): top3_5pct+=1

print(f'冠军达2.5%: {wins}/{ndays}({wins*100/ndays:.1f}%)')
print(f'前3任意达2.5%: {top3_win}/{ndays}({top3_win*100/ndays:.1f}%)')
print(f'前3任意达5%: {top3_5pct}/{ndays}({top3_5pct*100/ndays:.1f}%)')
