"""测试排名公式：全部按比例浮动"""
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

# 全部按比例浮动评分
def score(px, cl, vr, hs, sz, jv, buy, dif, macd_g, above5):
    # 涨分(0~30): 5.5~6.5%最佳，两侧递减
    if 5.5 <= px <= 6.5: p_score = 30
    else: p_score = 30 * (1 - abs(px - 6) / 4)  # 离6越远分越低
    p_score = max(0, min(30, p_score))
    
    # CL分(0~25): 70~85%最佳
    if 70 <= cl <= 85: cl_score = 25
    else: cl_score = 25 * (1 - abs(cl - 77.5) / 30)
    cl_score = max(0, min(25, cl_score))
    
    # 量比分(0~15): 0.8~1.2最佳
    if 0.8 <= vr <= 1.2: vr_score = 15
    else: vr_score = 15 * (1 - abs(vr - 1.0) / 1.5)
    vr_score = max(0, min(15, vr_score))
    
    # 换手分(0~10): 8~12%最佳
    if 8 <= hs <= 12: hs_score = 10
    else: hs_score = 10 * (1 - abs(hs - 10) / 15)
    hs_score = max(0, min(10, hs_score))
    
    # 股价分(0~10): 越低分越高，连续递减
    price_score = 10 * max(0, min(1, (100 - buy) / 100))
    
    # J值分(0~5): 60~100最佳
    if 60 <= jv <= 100: j_score = 5
    elif jv <= 120: j_score = 3
    else: j_score = 1
    
    # MACD分(0~10): 按DIF大小和金叉浮动
    macd_score = 5 * (1 + dif/0.5)  # dif越大分越高
    if macd_g: macd_score += 5  # 金叉加分
    macd_score = max(-5, min(10, macd_score))
    
    # 站上5日线分(0~10): 越远越高
    ma5_score = 10 if above5 else 0
    
    total = p_score + cl_score + vr_score + hs_score + price_score + j_score + macd_score + ma5_score
    return total

p_min,p_max=5,8; vr_min,vr_max=0.8,2.0; hsl_min,hsl_max=5,15; sz_max=300; cl_min,cl_max=60,90; j_max=100

# 对比
tests = {
    '原版CL排序': lambda c: (-c[0], -c[3]),
    '涨x2+CL': lambda c: (-(c[3]*2+c[0]), -c[3]),
    '连续评分(全浮动)': lambda c: (-score(c[3],c[0],c[4],c[5],c[6],c[10],c[7],c[9],c[11],c[12]), -c[3]),
    '涨x2+CL+价+MACD+5日': lambda c: (-(c[3]*2+c[0]+ps(c[7])*0.5+ms(c[9],c[11])*0.5+10*c[12]), -c[3]),
}

def ps(price):
    return 10*max(0,min(1,(100-price)/100))

def ms(dif,g):
    s=5*(1+dif/0.5)
    if g: s+=5
    return max(-5,min(10,s))

for label, sort_key in tests.items():
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
            nh=get_nxt(code,dt)
            cand.append((cl,nm,code,p,vr,hsl,sz,buy,nh,dif,m))
        if not cand: continue
        cand.sort(key=sort_key)
        ndays+=1
        if cand[0][8]>=2.5: wins+=1
    print(f'{label:<30}: {wins}/{ndays}({wins*100/ndays:.1f}%)')
