"""
跌日 — 冲刺30天85%
基础：基线 + VR0.6-1.0加分 + p>=6.5惩罚
调整惩罚/奖励值
"""
import pickle,os,sys,json,importlib
sys.path.insert(0,os.path.dirname(__file__))
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data,real,names=d['data'],d['real'],d['names']
da=[x for x in sorted(data.keys()) if '2025-01-01'<=x<'2026-06-01']
def cm(ss):
    if not ss:return'flat'
    ps=[s.get('p',0) or 0 for s in ss]
    vrs=[s.get('vol_ratio',0) or 0 for s in ss if s.get('vol_ratio',0)]
    if not ps:return'flat'
    ap=sum(ps)/len(ps);av=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5:return'fake_up' if hot<15 or av<0.9 else'real_up'
    if ap<-0.5:return'down'
    return'flat'
ddates=[]
for dt in da:
    ss=data.get(dt,[])
    if ss and cm(ss)=='down':ddates.append(dt)
mod=importlib.import_module('大道至简_跌日_评分策略')
LV=mod.LEVELS
def bs(s):
    c=s.get('code','');ri=real.get(c,{})
    return {'p':s.get('p',0) or 0,'cl':s.get('cl',0),'vr':s.get('vol_ratio',0) or 0,
        'hsl':(ri.get('hsl',0) or 0),'dif':s.get('dif_val',0) or 0,'mg':s.get('macd_golden',0) or 0,
        'a5':s.get('above_ma5',0) or 0,'wrv':s.get('wr_val',0) or 20,
        'jv':s.get('j_val',0) or 0,'kv':s.get('k_val',0) or 0,'dv':s.get('d_val',0) or 0,
        'kdj_g':s.get('kdj_golden',0) or 0,'buy_c':s.get('close',0) or 0}
def run(fn,name):
    wa=0;ta=0;w30=0;t30=0;w80=0;t80=0
    for i,dt in enumerate(ddates):
        ss=data.get(dt,[]);cand=None
        for l in LV:
            pool=[]
            for s in ss:
                code=s.get('code','');p=s.get('p',0) or 0
                if p<l['p_min'] or p>l['p_max']:continue
                if p>=8:continue
                vr=s.get('vol_ratio',0) or 0
                if vr<l['vr_min'] or vr>l['vr_max']:continue
                ri=real.get(code)
                if not ri:continue
                hsl=(ri.get('hsl',0) or 0)
                if hsl<l['hs_min'] or hsl>l['hs_max']:continue
                if (ri.get('shizhi',0) or 0)>=l['sz_max']:continue
                nm=names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm:continue
                cl=s.get('cl',0)
                if cl<l['cl_min'] or cl>l['cl_max']:continue
                if (s.get('n',0) or 0)<=0:continue
                pool.append(s)
            if len(pool)>8:cand=pool;break
        if not cand or len(cand)<=8:continue
        scd=[(fn(bs(s)),s.get('n',0) or 0) for s in cand]
        scd.sort(key=lambda x:(-x[0]))
        dfe=len(ddates)-i;ta+=1
        if scd[0][1]>=2.5:wa+=1
        if dfe<=80:t80+=1
        if dfe<=80 and scd[0][1]>=2.5:w80+=1
        if dfe<=30:t30+=1
        if dfe<=30 and scd[0][1]>=2.5:w30+=1
    def f(w,t):return f"{w*100/t:.1f}%({w}/{t})" if t else"—"
    v30=float(f(w30,t30).split('%')[0]) if t30 else 0
    v80=float(f(w80,t80).split('%')[0]) if t80 else 0
    f30="🔥" if v30>=85 else ""
    f80="✅" if v80>=70 else f"差{70-v80:.1f}%"
    print(f"{name:35s}| 30天 {f(w30,t30):>15s} {f30:2s}| 80天 {f(w80,t80):>15s} {f80:5s}")
    return v30,v80,w30,t30,w80,t80

def base(s):
    p=s['p'];cl=s['cl'];vr=s['vr'];hsl=s['hsl']
    dif=s['dif'];mg=s['mg'];a5=s['a5']
    wrv=s['wrv'];jv=s['jv'];kv=s['kv'];dv=s['dv']
    kdj_g=s['kdj_g'];bc=s['buy_c']
    ms=0
    if mg and dif>0.5:ms=10
    elif mg and dif>0.2:ms=8
    elif mg:ms=6
    elif dif>0.5:ms=4
    elif dif>0:ms=2
    ps2=min(10,max(1,11-bc/10)) if bc else 0
    sc=p*1.0+cl*0.05+ps2*0.3+ms*0.3
    sc+=(2 if a5 else 0)
    sc+=(3 if wrv>75 else 0)
    sc+=(3 if cl<15 else 0)
    sc+=(2 if p<-3 else 0)
    return sc

print(f"{'='*80}")
print(f"VR0.6-1.0+P惩罚 - 找30天最佳值：")

# VR值变化
for vr_val in [2,3]:
    for pn_val in [-1,-2,-3]:
        def mk(v=vr_val, pn=pn_val):
            def fn(s):
                sc=base(s)
                p=s['p'];vr=s['vr']
                if 0.6<=vr<=1.0: sc+=v
                if p>=6.5: sc+=pn
                return round(sc,1)
            return fn
        run(mk(), f"VR+{vr_val} p{pn_val}")

print(f"\n🏆 候选排行：")
# 前面结果中VR+2 p-2最好但跑出来不对，重新确认
for vr_val in [2,3]:
    for pn_val in [-1,-2,-3]:
        def mk(v=vr_val, pn=pn_val):
            def fn(s):
                sc=base(s)
                p=s['p'];vr=s['vr']
                if 0.6<=vr<=1.0: sc+=v
                if p>=6.5: sc+=pn
                return round(sc,1)
            return fn
        run(mk(), f"VR{vr_val}+p{pn_val}")
