"""找放宽到L4后仍<10只的天"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-02-01']

LEVELS = [
    {'n':'L0','p_min':5,'p_max':8,'vr_min':0.8,'vr_max':2.0,'hsl_min':5,'hsl_max':15,'sz_max':300,'cl_min':60,'cl_max':90,'j_max':100},
    {'n':'L1','p_min':4,'p_max':9,'vr_min':0.6,'vr_max':2.5,'hsl_min':3,'hsl_max':20,'sz_max':300,'cl_min':50,'cl_max':95,'j_max':120},
    {'n':'L2','p_min':3,'p_max':10,'vr_min':0.5,'vr_max':3.0,'hsl_min':2,'hsl_max':25,'sz_max':400,'cl_min':40,'cl_max':98,'j_max':150},
    {'n':'L3','p_min':2,'p_max':11,'vr_min':0.4,'vr_max':3.5,'hsl_min':1,'hsl_max':30,'sz_max':500,'cl_min':30,'cl_max':99,'j_max':200},
    {'n':'L4','p_min':1,'p_max':12,'vr_min':0.3,'vr_max':4.0,'hsl_min':0.5,'hsl_max':35,'sz_max':1000,'cl_min':20,'cl_max':100,'j_max':300},
]

def cnt(dt, li):
    L=LEVELS[li]
    n=0
    for s in data.get(dt,[]):
        code=s['code']; p=s['p']
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
        n+=1
    return n

print(f"共{len(dates)}个交易日 (2025-02至今)\n", flush=True)

# 先看各级覆盖
for li in range(len(LEVELS)):
    L=LEVELS[li]
    vals=[cnt(dt,li) for dt in dates]
    w10=sum(1 for x in vals if x>=10)
    print(f"{L['n']:<4}: ≥10={w10}天 min={min(vals)} max={max(vals)} 中{ sorted(vals)[len(vals)//2] }", flush=True)

# 找需要放宽到哪一级
print(f"\n=== 放宽后仍<10只的天 ===", flush=True)
bad=[]
for dt in dates:
    need_li=-1
    for li in range(len(LEVELS)):
        if cnt(dt, li)>=10:
            need_li=li
            break
    if need_li==-1:
        n_=cnt(dt, len(LEVELS)-1)
        bad.append((dt,n_))
        print(f"❌ {dt}: L4也只{n_}只", flush=True)
    elif need_li>=1:
        l0=cnt(dt,0)
        l1=cnt(dt,1)
        print(f"⚠️ {dt}: L0={l0} → L{need_li}={cnt(dt,need_li)}只", flush=True)

print(f"\n共{len(bad)}个交易日放宽到L4后仍<10只", flush=True)
print(f"✅ 其余{len(dates)-len(bad)}天放宽后都有≥10只", flush=True)
