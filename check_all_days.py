"""找2025-02至今所有放宽后仍<10只的天数"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-02-01']

# 5级条件
LEVELS = [
    {'n':'L0','p_min':5,'p_max':8,'vr_min':0.8,'vr_max':2.0,'hsl_min':5,'hsl_max':15,'sz_max':300,'cl_min':60,'cl_max':90,'j_max':100},
    {'n':'L1','p_min':4,'p_max':9,'vr_min':0.6,'vr_max':2.5,'hsl_min':3,'hsl_max':20,'sz_max':300,'cl_min':50,'cl_max':95,'j_max':120},
    {'n':'L2','p_min':3,'p_max':10,'vr_min':0.5,'vr_max':3.0,'hsl_min':2,'hsl_max':25,'sz_max':400,'cl_min':40,'cl_max':98,'j_max':150},
    {'n':'L3','p_min':2,'p_max':11,'vr_min':0.4,'vr_max':3.5,'hsl_min':1,'hsl_max':30,'sz_max':500,'cl_min':30,'cl_max':99,'j_max':200},
    {'n':'L4','p_min':1,'p_max':12,'vr_min':0.3,'vr_max':4.0,'hsl_min':0.5,'hsl_max':35,'sz_max':1000,'cl_min':20,'cl_max':100,'j_max':300},
]

def cnt(dt, li):
    L=LEVELS[li]; n=0
    for s in data.get(dt,[]):
        code,p=s['code'],s['p']
        if p<L['p_min'] or p>L['p_max']: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<L['vr_min'] or vr>L['vr_max']: continue; ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<L['hsl_min'] or hsl>L['hsl_max']: continue; sz=(ri.get('shizhi',0) or 0)
        if sz>=L['sz_max']: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>L['j_max']: continue
        cl=s.get('cl',0)
        if cl<L['cl_min'] or cl>L['cl_max']: continue; n+=1
    return n

print(f"统计: {len(dates)}天 (2025-02至今)\n", flush=True)

# 统计各级
for li in range(len(LEVELS)):
    L=LEVELS[li]
    w10=0; less3=0; less5=0; all_n=[]
    for dt in dates:
        n=cnt(dt, li)
        all_n.append(n)
        if n>=10: w10+=1
        if n<3: less3+=1
        if n<5: less5+=1
    avg=sum(all_n)/len(all_n) if all_n else 0
    med=sorted(all_n)[len(all_n)//2] if all_n else 0
    print(f"{L['n']:<4}: ≥10={w10}({w10*100/len(dates):.0f}%) <5={less5}天 <3={less3}天 均{avg:.0f} 中{med}", flush=True)

print(f"\n=== 放宽后仍<10只的天数 ===", flush=True)
bad_days=[]
for dt in dates:
    for li in range(len(LEVELS)):
        n=cnt(dt, li)
        if n>=10: break
    else:  # L4都不够
        bad_days.append((dt, n))
        print(f"{dt}: L4也只{n}只 ❌", flush=True)

if not bad_days:
    print("✅ 所有天数都有≥10只候选！", flush=True)
else:
    print(f"\n{len(bad_days)}天无法达标", flush=True)

# 看看各级的候选数分布
print(f"\n=== 各级数量分布 ===", flush=True)
for li in range(len(LEVELS)):
    vals=[cnt(dt,li) for dt in dates]
    p10=sum(1 for x in vals if x>=10)*100/len(vals)
    print(f"{LEVELS[li]['n']}: 最小{min(vals)} 最大{max(vals)} 中位{sorted(vals)[len(vals)//2]} ≥10:{p10:.0f}%", flush=True)
