"""分级放宽选股直到≥10只 - 分析极端情况"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target = [d for d in dates if d >= '2026-01-01']

def get_nxt(code, date):
    fp=os.path.join(CACHE_DIR,f'{code}.json')
    if not os.path.exists(fp): return 0
    try:
        with open(fp) as f: kdata=json.load(f)
        idx=next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx+1 >= len(kdata): return 0
        bc=kdata[idx]['close']
        nh=(kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
        if abs(nh)>50: return 0
        return nh or 0
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

# 5级放宽
LEVELS = [
    {'n':'L0','p_min':5,'p_max':8,'vr_min':0.8,'vr_max':2.0,'hsl_min':5,'hsl_max':15,'sz_max':300,'cl_min':60,'cl_max':90,'j_max':100},
    {'n':'L1','p_min':4,'p_max':9,'vr_min':0.6,'vr_max':2.5,'hsl_min':3,'hsl_max':20,'sz_max':300,'cl_min':50,'cl_max':95,'j_max':120},
    {'n':'L2','p_min':3,'p_max':10,'vr_min':0.5,'vr_max':3.0,'hsl_min':2,'hsl_max':25,'sz_max':400,'cl_min':40,'cl_max':98,'j_max':150},
    {'n':'L3','p_min':2,'p_max':11,'vr_min':0.4,'vr_max':3.5,'hsl_min':1,'hsl_max':30,'sz_max':500,'cl_min':30,'cl_max':99,'j_max':200},
    {'n':'L4','p_min':1,'p_max':12,'vr_min':0.3,'vr_max':4.0,'hsl_min':0.5,'hsl_max':35,'sz_max':1000,'cl_min':20,'cl_max':100,'j_max':300},
]

def count_candidates(dt, li):
    """统计某天某级候选数"""
    L=LEVELS[li]
    cnt=0
    for s in data.get(dt,[]):
        code,p=s['code'],s['p']
        if p<L['p_min'] or p>L['p_max']: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<L['vr_min'] or vr>L['vr_max']: continue
        ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<L['hsl_min'] or hsl>L['hsl_max']: continue
        sz=(ri.get('shizhi',0) or 0)
        if sz>=L['sz_max']: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>L['j_max']: continue
        cl=s.get('cl',0)
        if cl<L['cl_min'] or cl>L['cl_max']: continue
        cnt+=1
    return cnt

def get_candidates(dt, li):
    """获取某天某级候选（完整数据）"""
    L=LEVELS[li]
    cand=[]
    for s in data.get(dt,[]):
        code,p=s['code'],s['p']
        if p<L['p_min'] or p>L['p_max']: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<L['vr_min'] or vr>L['vr_max']: continue
        ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<L['hsl_min'] or hsl>L['hsl_max']: continue
        sz=(ri.get('shizhi',0) or 0)
        if sz>=L['sz_max']: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>L['j_max']: continue
        cl=s.get('cl',0)
        if cl<L['cl_min'] or cl>L['cl_max']: continue
        buy=s.get('close',0); dif=s.get('dif_val',0) or 0
        macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
        is_yang=s.get('is_yang',0); close=s.get('close',0)
        ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
        cand.append((code,p,cl,vr,hsl,sz,nm,buy,dif,macd_g,above5,is_yang,close,ma5,ma10,ma20,jv))
    return cand

# === 分析每级每天候选数 ===
print("=== 每级候选数分布 ===", flush=True)
for li in range(len(LEVELS)):
    cnts=[]
    for dt in target:
        n=count_candidates(dt, li)
        if n>0: cnts.append(n)
    if cnts:
        w10=sum(1 for x in cnts if x>=10)
        w5=sum(1 for x in cnts if x>=5)
        w3=sum(1 for x in cnts if x>=3)
        print(f"{LEVELS[li]['n']:<4}  <3:{len([x for x in cnts if x<3])}天 <5:{len([x for x in cnts if x<5])}天 <10:{len([x for x in cnts if x<10])}天 ≥10:{w10}天 均{sum(cnts)/len(cnts):.0f}只", flush=True)

# === 看看哪些极端天数需要放宽到多少级 ===
print(f"\n=== 需要放宽的极值天数 ===", flush=True)
target_needed=[]
for dt in target:
    for li in range(len(LEVELS)):
        n=count_candidates(dt, li)
        if n>=10:
            target_needed.append((dt, li, n))
            break
    else:
        target_needed.append((dt, -1, count_candidates(dt, len(LEVELS)-1)))

for dt, li, n in target_needed:
    if li>=1:  # 需要放宽的
        l0=count_candidates(dt,0)
        print(f"{dt}: L0={l0}只 → 需L{li}={n}只", flush=True)
