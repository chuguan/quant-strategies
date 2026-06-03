"""
跌日优化 — 基于分析结果重构
核心发现：跌日冠军全是涨的(p6.3%)，不是超卖反转
新方向：跌日追强（找动量最好的票，它在跌日能逆势涨，明天还能冲）
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
print(f"跌日{len(ddates)}天",flush=True)

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
    print(f"{name:35s}| 30天 {f(w30,t30):>15s} {'🔥' if v30>=80 else f'差{80-v30:.1f}%':5s}| 80天 {f(w80,t80):>15s} {'✅' if v80>=70 else f'差{70-v80:.1f}%'}",flush=True)
    return v30,v80

print(f"{'='*80}")
print("基准 vs 新逻辑：")
print()

# 基准
def old_fn(s):
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
    return round(sc,1)

run(old_fn, "V260529-08 基准")

# ===== 新逻辑：跌日追强 =====
# 方向：在跌日选p5-6.5%的强票，避p>6.5，避J>80
def make_fn(pw=1.5, p_high_pen=-2, j_bonus=2, j_high_pen=-2, 
            cl_bonus=2, vr_bonus=2, hsl_bonus=2, dif_bonus=2,
            use_wr=False, use_cl_low=False, use_deep=False):
    def fn(s):
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
        sc=p*pw+cl*0.05+ps2*0.3+ms*0.3
        sc+=(2 if a5 else 0)
        
        # 旧逻辑（可选保留）
        if use_wr and wrv>75: sc+=3
        if use_cl_low and cl<15: sc+=3
        if use_deep and p<-3: sc+=2
        
        # 新逻辑：基于分析
        # p 5-6.5%最佳，>=6.5%要惩罚
        if p_high_pen and p>=6.5: sc+=p_high_pen
        # J值60-80最佳，>80要惩罚
        if j_bonus and 60<=jv<=80: sc+=j_bonus
        if j_high_pen and jv>80: sc+=j_high_pen
        # CL 60-80加分
        if cl_bonus and 60<=cl<=80: sc+=cl_bonus
        # VR 0.6-1.0加分
        if vr_bonus and 0.6<=vr<=1.0: sc+=vr_bonus
        # 换手0-3%加分
        if hsl_bonus and hsl<=3: sc+=hsl_bonus
        # DIF 0-0.5加分
        if dif_bonus and 0<=dif<=0.5: sc+=dif_bonus
        # KDJ金叉加分
        if kdj_g: sc+=2
        
        return round(sc,1)
    return fn

# 新逻辑版本1：纯追强
run(make_fn(pw=1.5, use_wr=False, use_cl_low=False, use_deep=False), "新逻辑1: 纯追强(去反转)")
# 新逻辑2：追强+保留超卖
run(make_fn(pw=1.5, use_wr=True, use_cl_low=True, use_deep=True), "新逻辑2: 追强+保留反转")

# 逐个验证分析结论
print(f"\n单项调整测试（在旧基准上加新逻辑因子）：")
# 先做个基础函数方便对比
def base_v2(s):
    """在旧基准上逐步加新因子"""
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

def adjust(**kw):
    def fn(s):
        sc=base_v2(s)
        p=s['p'];cl=s['cl'];vr=s['vr'];hsl=s['hsl']
        dif=s['dif'];jv=s['jv'];kdj_g=s['kdj_g']
        for k,v in kw.items():
            if k=='p6_pen' and p>=6.5: sc+=v
            if k=='j80_pen' and jv>80: sc+=v
            if k=='j60_bonus' and 60<=jv<=80: sc+=v
            if k=='cl60_bonus' and 60<=cl<=80: sc+=v
            if k=='vr_low_bonus' and 0.6<=vr<=1.0: sc+=v
            if k=='hsl_low_bonus' and hsl<=3: sc+=v
            if k=='dif_mod_bonus' and 0<=dif<=0.5: sc+=v
            if k=='kdj_b' and kdj_g: sc+=v
            if k=='pw' and p: pass  # handled by base_v2
        return round(sc,1)
    return fn

# 单因子测试
tests = [
    (adjust(p6_pen=-2), "p>6.5惩罚-2"),
    (adjust(j80_pen=-2), "J>80惩罚-2"),
    (adjust(j60_bonus=2), "J60-80加分+2"),
    (adjust(cl60_bonus=2), "CL60-80加分+2"),
    (adjust(vr_low_bonus=2), "VR0.6-1.0加分+2"),
    (adjust(hsl_low_bonus=2), "HSL<3%加分+2"),
    (adjust(dif_mod_bonus=2), "DIF0-0.5加分+2"),
    (adjust(kdj_b=2), "KDJ金叉+2"),
    # 双组合
    (adjust(p6_pen=-2, j80_pen=-2), "p惩罚+J惩罚"),
    (adjust(p6_pen=-2, j60_bonus=2), "p惩罚+J60加分"),
    (adjust(j80_pen=-2, cl60_bonus=2), "J惩罚+CL60加分"),
    # 多组合
    (adjust(p6_pen=-2, j80_pen=-2, cl60_bonus=2), "p+J惩罚+CL60"),
    (adjust(p6_pen=-2, j80_pen=-2, cl60_bonus=2, vr_low_bonus=2), "p+J惩罚+CL+VR"),
    # 全组合
    (adjust(p6_pen=-2, j80_pen=-2, cl60_bonus=2, vr_low_bonus=2, hsl_low_bonus=2, dif_mod_bonus=2), "全组合"),
    (adjust(p6_pen=-2, j80_pen=-2, cl60_bonus=2, vr_low_bonus=2, hsl_low_bonus=2, dif_mod_bonus=2, kdj_b=2), "全组合+KDJ"),
]
for fn,nm in tests:
    run(fn,nm)

# 换个思路：p_w从1.0提升到1.5，加新因子
print(f"\n新方向：提p_w到1.5+分析因子：")
for pw in [1.2,1.5,1.8,2.0]:
    def mk(p=pw):
        def fn(s):
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
            sc=p*p+cl*0.05+ps2*0.3+ms*0.3
            sc+=(2 if a5 else 0)
            # 保留反转信号但降权
            sc+=(2 if wrv>75 else 0)
            sc+=(2 if cl<15 else 0)
            # 新因子
            if p>=6.5: sc-=2
            if 60<=jv<=80: sc+=2
            if jv>80: sc-=2
            if 60<=cl<=80: sc+=2
            if 0.6<=vr<=1.0: sc+=2
            if hsl<=3: sc+=2
            if 0<dif<=0.5: sc+=2
            if kdj_g: sc+=2
            return round(sc,1)
        return fn
    run(mk(), f"p_w={pw}+新因子")

# 最优版
def best(s):
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
    sc=p*1.5+cl*0.05+ps2*0.3+ms*0.3
    sc+=(2 if a5 else 0)
    # 反转信号保留但非主导
    sc+=(2 if wrv>75 else 0)
    sc+=(2 if cl<15 else 0)
    # 核心新因子
    if p>=6.5: sc-=2       # 涨幅太高=透支
    if 60<=jv<=80: sc+=2  # J值健康区加分
    if jv>80: sc-=2       # J值超高惩罚
    if 60<=cl<=80: sc+=2  # CL健康区加分
    if 0.6<=vr<=1.0: sc+=2  # 低量比稳定
    if hsl<=3: sc+=2      # 低换手稳定
    if kdj_g: sc+=2       # KDJ金叉
    return round(sc,1)

run(best, "最优版(p1.5+新因子)")

print(f"\n  🎯 目标：30天80%🔥  80天70%✅")
