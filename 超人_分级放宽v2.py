"""分级放宽选股直到≥10只候选 + 验证对冠军胜率影响"""
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

# 5级放宽条件
LEVELS = [
    {'name':'L0严格','p_min':5,'p_max':8,'vr_min':0.8,'vr_max':2.0,'hsl_min':5,'hsl_max':15,'sz_max':300,'cl_min':60,'cl_max':90,'j_max':100},
    {'name':'L1微宽','p_min':4,'p_max':9,'vr_min':0.6,'vr_max':2.5,'hsl_min':3,'hsl_max':20,'sz_max':300,'cl_min':50,'cl_max':95,'j_max':120},
    {'name':'L2中宽','p_min':3,'p_max':10,'vr_min':0.5,'vr_max':3.0,'hsl_min':2,'hsl_max':25,'sz_max':400,'cl_min':40,'cl_max':98,'j_max':150},
    {'name':'L3较宽','p_min':2,'p_max':11,'vr_min':0.4,'vr_max':3.5,'hsl_min':1,'hsl_max':30,'sz_max':500,'cl_min':30,'cl_max':99,'j_max':200},
    {'name':'L4极限','p_min':1,'p_max':12,'vr_min':0.3,'vr_max':4.0,'hsl_min':0.5,'hsl_max':35,'sz_max':1000,'cl_min':20,'cl_max':100,'j_max':300},
]

def get_candidates(dt, level_idx):
    """获取某天的候选，用给定level"""
    p_min=LEVELS[level_idx]['p_min']; p_max=LEVELS[level_idx]['p_max']
    vr_min=LEVELS[level_idx]['vr_min']; vr_max=LEVELS[level_idx]['vr_max']
    hsl_min=LEVELS[level_idx]['hsl_min']; hsl_max=LEVELS[level_idx]['hsl_max']
    sz_max=LEVELS[level_idx]['sz_max']
    cl_min=LEVELS[level_idx]['cl_min']; cl_max=LEVELS[level_idx]['cl_max']
    j_max=LEVELS[level_idx]['j_max']
    
    cand=[]
    for s in data.get(dt,[]):
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
        cand.append((code,p,cl,vr,hsl,sz,nm,buy,n_val,  # incomplete - need more
                     s.get('dif_val',0) or 0,s.get('macd_golden',0),s.get('above_ma5',0),
                     s.get('is_yang',0),s.get('close',0),s.get('ma5',0) or 0,
                     s.get('ma10',0) or 0,s.get('ma20',0) or 0,
                     s.get('j_val',0) or 0,s.get('vol_ratio',0) or 0))
    return cand

# 先跑全量预计算各水平
print("分析2026年候选数分布...", flush=True)
level_usage = {i:0 for i in range(len(LEVELS))}
level_cand_counts = {i:[] for i in range(len(LEVELS))}

for dt in target:
    needed_level = 0
    for li in range(len(LEVELS)):
        cand = get_candidates(dt, li)
        if len(cand) >= 10:
            needed_level = li
            break
    level_usage[needed_level] += 1
    cand = get_candidates(dt, needed_level)
    level_cand_counts[needed_level].append(len(cand))

print(f"\n=== 各级使用频次 ===", flush=True)
for li in range(len(LEVELS)):
    cnt = level_usage[li]
    if cnt > 0:
        data = level_cand_counts[li]
        print(f"{LEVELS[li]['name']:<12}: {cnt:>3}天 ({cnt*100/len(target):.0f}%) | 候选均值{sum(data)/len(data):.0f} 中位{sorted(data)[len(data)//2]:.0f}", flush=True)

# 用v10切换策略跑完整回测（带分级放宽）
print(f"\n=== v10切换策略 + 分级放宽 ===", flush=True)
wins=0; nd=0; rw=0; rt=0; tw=0; tt=0; any3=0; any35=0

for dt in target:
    stocks=data.get(dt,[])
    if not stocks: continue
    all_p=[x['p'] for x in stocks if 'p' in x]
    avg_mkt=sum(all_p)/len(all_p) if all_p else 0
    if avg_mkt>0.5: mkt='up'
    elif avg_mkt<-0.5: mkt='down'
    else: mkt='flat'
    
    # 分级放宽
    cand_raw = []
    for li in range(len(LEVELS)):
        cand_raw = get_candidates(dt, li)
        if len(cand_raw) >= 10:
            used_level = li
            break
    if len(cand_raw) < 10:  # 极限还是不够
        used_level = len(LEVELS)-1
    
    # 评分
    cand=[]
    for c in cand_raw:
        code,p,cl,vr,hsl,sz = c[:6]
        buy=s.get('close',0); dif=c[9]; macd_g=c[10]; above5=c[11]
        is_yang=c[12]; close=c[13]; ma5=c[14]; ma10=c[15]; ma20=c[16]
        wr_t,wr_y,y_p=calc_wr(code,dt); nh=get_nxt(code,dt)
        wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
        macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
        ps2=ps(buy); yp=-3 if y_p>7 else 0
        hsl_b=2*0.3 if 5<=hsl<=7 else 0
        duotou_b=3*0.3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
        yang_vr_b=2*0.3 if is_yang and vr>1.2 else 0
        
        if mkt=='up':
            score=p*3.0+cl*0.1+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.3+hsl_b+duotou_b
        elif mkt=='down':
            score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.3+yp
        else:
            score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+wr_s*0.3+yp+hsl_b+yang_vr_b
        
        if nh and nh>0:
            cand.append((score,nh,p))
    
    if not cand: continue
    cand.sort(key=lambda x:(-x[0],-x[2]))
    nd+=1
    if cand[0][1]>=2.5: wins+=1
    if len(cand)>=2:
        rt+=1
        if cand[1][1]>=2.5: rw+=1
    if len(cand)>=3:
        tt+=1
        if cand[2][1]>=2.5: tw+=1
        if any(cand[i][1]>=2.5 for i in range(3)): any3+=1
        if any(cand[i][1]>=5 for i in range(3)): any35+=1

print(f"冠军≥2.5%: {wins}/{nd}({wins*100/nd:.1f}%)", flush=True)
print(f"亚军≥2.5%: {rw}/{rt}({rw*100/rt:.1f}%)", flush=True)
print(f"季军≥2.5%: {tw}/{tt}({tw*100/tt:.1f}%)", flush=True)
print(f"Top3任意≥2.5%: {any3}/{tt}({any3*100/tt:.1f}%)", flush=True)
print(f"Top3任意≥5%: {any35}/{tt}({any35*100/tt:.1f}%)", flush=True)
