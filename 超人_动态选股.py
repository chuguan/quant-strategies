"""动态选股：候选不足3只时自动放宽条件"""
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

# 标准参数
SP_MIN,SP_MAX=5,8; SV_MIN,SV_MAX=0.8,2.0; SH_MIN,SH_MAX=5,15; SZ=300; SC_MIN,SC_MAX=60,90; SJ=100

# 扩大参数（逐步放宽）
EXPAND = [
    # (涨幅, 量比, 换手, CL)
    ((4, 9), (0.6, 2.5), (3, 20), (50, 95)),  # 一级扩大
    ((3, 10), (0.5, 3.0), (2, 25), (40, 98)), # 二级扩大
    ((2, 12), (0.4, 4.0), (1, 30), (30, 100)),# 三级扩大
]

def select_stocks(dt, expand_level=0):
    """选股，expand_level=0=标准，1=一级扩大，2=二级，3=三级"""
    if expand_level==0:
        pp=(SP_MIN,SP_MAX); vv=(SV_MIN,SV_MAX); hh=(SH_MIN,SH_MAX); cc=(SC_MIN,SC_MAX)
    else:
        pp, vv, hh, cc = EXPAND[expand_level-1]
    
    cand=[]
    for s in data.get(dt, []):
        code,p=s['code'],s['p']
        if p<pp[0] or p>pp[1]: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<vv[0] or vr>vv[1]: continue
        ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<hh[0] or hsl>hh[1]: continue
        sz=(ri.get('shizhi',0) or 0)
        if sz>=SZ: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>SJ: continue
        cl=s.get('cl',0)
        if cl<cc[0] or cl>cc[1]: continue
        buy=s.get('close',0); dif=s.get('dif_val',0) or 0
        macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
        is_yang=s.get('is_yang',0); close=s.get('close',0)
        ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
        wr_t,wr_y,y_p=calc_wr(code,dt); nh=get_nxt(code,dt)
        wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
        macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
        all_p=[x['p'] for x in data.get(dt,[]) if 'p' in x]
        avg_mkt=sum(all_p)/len(all_p) if all_p else 0
        if avg_mkt>0.5: mkt='up'
        elif avg_mkt<-0.5: mkt='down'
        else: mkt='flat'
        yp=-3 if y_p>7 else 0
        hsl_b=2*0.3 if 5<=hsl<=7 else 0
        duotou_b=3*0.3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
        yang_vr_b=2*0.3 if is_yang and vr>1.2 else 0
        if mkt=='up':
            score=p*3.0+cl*0.1+ps(buy)*0.3+macd_s*0.3+3*above5+wr_s*0.3+hsl_b+duotou_b
        elif mkt=='down':
            score=p*2.0+cl*0.05+ps(buy)*0.3+macd_s*0.3+3*above5+wr_s*0.3+yp
        else:
            score=p*2.0+cl*0.05+ps(buy)*0.3+macd_s*0.3+3*above5+wr_s*0.3+yp+hsl_b+yang_vr_b
        if nh and nh>0:
            cand.append((score,nh,p,nm,code,expand_level))
    return cand

# 回测
c_wins=0; c_total=0; r_wins=0; r_total=0; t_wins=0; t_total=0; any3_w=0; any3_5=0
expanded_days=[]

for dt in target:
    # 逐步：先用标准，不够就一级，再不够二级，再不够三级
    cand=[]
    for el in range(4):
        cand=select_stocks(dt, el)
        if len(cand)>=3:  # 够了就停
            if el>0: expanded_days.append((dt, el, len(cand)))
            break
    
    if not cand: continue
    cand.sort(key=lambda x:(-x[0],-x[2]))
    
    c_total+=1
    if cand[0][1]>=2.5: c_wins+=1
    if len(cand)>=2:
        r_total+=1
        if cand[1][1]>=2.5: r_wins+=1
    if len(cand)>=3:
        t_total+=1
        if cand[2][1]>=2.5: t_wins+=1
        if any(c[1]>=2.5 for c in cand[:3]): any3_w+=1
        if any(c[1]>=5 for c in cand[:3]): any3_5+=1

print(f"v10切换策略 + 动态扩大选股 | 2026年", flush=True)
print(f"{'名次':<15} {'达标≥2.5%':<18} {'爆涨≥5%':<12}", flush=True)
print('-'*48, flush=True)
print(f"{'🥇冠军':<15} {c_wins:>3}/{c_total:<3}({c_wins*100/c_total:.1f}%)", flush=True)
print(f"{'🥈亚军':<15} {r_wins:>3}/{r_total:<3}({r_wins*100/r_total:.1f}%)", flush=True)
print(f"{'🥉季军':<15} {t_wins:>3}/{t_total:<3}({t_wins*100/t_total:.1f}%)", flush=True)
print(f"{'📊Top3任意':<15} {any3_w:>3}/{t_total:<3}({any3_w*100/t_total:.1f}%)  5%:{any3_5:>2}/{t_total:<3}({any3_5*100/t_total:.1f}%)", flush=True)

print(f"\n扩大选股的天数({len(expanded_days)}天):", flush=True)
for dt,el,ln in expanded_days:
    print(f"  {dt}: 扩大级别{el} → {ln}只", flush=True)
