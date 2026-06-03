"""
失败日调优 — 加3条惩罚规则
1. J>90惩罚-2（超买区域）
2. VR>2.0惩罚-2（异常放量=出货）
3. 跌日CL<15减反转力度（超卖在跌日无效）
分别测试每个策略的改进效果
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
rdates=sorted(set(dt for dt in da if data.get(dt) and cm(data[dt]) in ['real_up','down','flat','fake_up']))

# 各策略模块+LEVELS
MODS={
    'real_up':importlib.import_module('大道至简_真实涨日_评分策略'),
    'fake_up':importlib.import_module('大道至简_虚涨日_评分策略'),
    'down':importlib.import_module('大道至简_跌日_评分策略'),
    'flat':importlib.import_module('大道至简_横盘_评分策略'),
}
FN_NAMES={'real_up':'真实涨日_评分','fake_up':'虚涨日_评分','down':'跌日_评分','flat':'横盘_评分'}
MKT_NAMES={'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}

def bs(s):
    c=s.get('code','');ri=real.get(c,{})
    return {'p':s.get('p',0) or 0,'cl':s.get('cl',0),'vr':s.get('vol_ratio',0) or 0,
        'hsl':(ri.get('hsl',0) or 0),'dif':s.get('dif_val',0) or 0,'mg':s.get('macd_golden',0) or 0,
        'a5':s.get('above_ma5',0) or 0,'wrv':s.get('wr_val',0) or 20,
        'jv':s.get('j_val',0) or 0,'kv':s.get('k_val',0) or 0,'dv':s.get('d_val',0) or 0,
        'kdj_g':s.get('kdj_golden',0) or 0,'buy_c':s.get('close',0) or 0}

def run_bt(name, make_fn_for_mkt):
    """跑全行情30天+80天回测"""
    totals = {}  # mkt -> {'w30':0,'t30':0,'w80':0,'t80':0,'w':0,'t':0}
    for mkt in ['real_up','fake_up','down','flat']:
        totals[mkt]={'w':0,'t':0,'w30':0,'t30':0,'w80':0,'t80':0}
    
    # 收集各行情日期
    mkt_dates={m:[] for m in ['real_up','fake_up','down','flat']}
    for dt in da:
        ss=data.get(dt,[])
        if not ss:continue
        mk=cm(ss)
        mkt_dates[mk].append(dt)
    
    for mkt,mk_name in MKT_NAMES.items():
        mod=MODS[mkt]
        fn=make_fn_for_mkt(mkt)
        lv=mod.LEVELS
        dates=mkt_dates[mkt]
        
        for i,dt in enumerate(dates):
            ss=data.get(dt,[])
            if not ss:continue
            cand=None
            for l in lv:
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
            champ_nh=scd[0][1]
            
            dfe=len(dates)-i
            t=totals[mkt]
            t['t']+=1
            if champ_nh>=2.5:t['w']+=1
            if dfe<=80:t['t80']+=1
            if dfe<=80 and champ_nh>=2.5:t['w80']+=1
            if dfe<=30:t['t30']+=1
            if dfe<=30 and champ_nh>=2.5:t['w30']+=1
    
    def f(w,t):return f"{w*100/t:.1f}%" if t else"—"
    total_w=sum(t['w'] for t in totals.values())
    total_t=sum(t['t'] for t in totals.values())
    
    print(f"\n{name}")
    print(f"{'行情':10s} | {'30天':>10s} | {'80天':>10s} | {'全量':>10s}")
    print(f"{'-'*50}")
    for mkt in ['real_up','fake_up','down','flat']:
        t=totals[mkt]
        r30=f(t['w30'],t['t30'])
        r80=f(t['w80'],t['t80'])
        ra=f(t['w'],t['t'])
        print(f"{MKT_NAMES[mkt]:10s} | {r30:>10s} | {r80:>10s} | {ra:>10s}")
    total_r=f(total_w,total_t)
    print(f"{'总':10s} | {'':>10s} | {'':>10s} | {total_r:>10s}")
    return total_w/total_t if total_t else 0

# ===== 基准 =====
def make_original(mkt):
    mod=MODS[mkt];fn_name=FN_NAMES[mkt]
    return getattr(mod,fn_name)

print(f"{'='*65}")
print("原始版 vs 加惩罚版：")
print(f"{'='*65}")

run_bt("【原始版（基准）】", make_original)

# ===== 惩罚版1：全面加惩罚 =====
def make_penalized(mkt):
    """在原评分基础上加J>90惩罚、VR>2.0惩罚"""
    mod=MODS[mkt];fn_name=FN_NAMES[mkt]
    orig=getattr(mod,fn_name)
    
    def fn(s):
        sc=orig(s)
        # J>90惩罚（所有行情）
        if s['jv']>90: sc-=2
        # VR>2.0惩罚（所有行情）
        if s['vr']>2.0: sc-=2
        # 跌日CL<15不奖励（超卖无效）
        if mkt=='down' and s['cl']<15: sc-=3  # 撤销原+3奖励
        return round(sc,1)
    return fn

run_bt("【全面惩罚版】", make_penalized)

# ===== 惩罚版2：只加J和VR惩罚，不减CL超卖 =====
def make_penalized_v2(mkt):
    mod=MODS[mkt];fn_name=FN_NAMES[mkt]
    orig=getattr(mod,fn_name)
    
    def fn(s):
        sc=orig(s)
        if s['jv']>90: sc-=2
        if s['vr']>2.0: sc-=2
        return round(sc,1)
    return fn

run_bt("【J+VR惩罚版】", make_penalized_v2)

# ===== 惩罚版3：只加J惩罚 =====
def make_jpen(mkt):
    mod=MODS[mkt];fn_name=FN_NAMES[mkt]
    orig=getattr(mod,fn_name)
    def fn(s):
        sc=orig(s)
        if s['jv']>90: sc-=2
        return round(sc,1)
    return fn

run_bt("【仅J>90惩罚版】", make_jpen)

# ===== 惩罚版4：只加VR惩罚 =====
def make_vrpen(mkt):
    mod=MODS[mkt];fn_name=FN_NAMES[mkt]
    orig=getattr(mod,fn_name)
    def fn(s):
        sc=orig(s)
        if s['vr']>2.0: sc-=2
        return round(sc,1)
    return fn

run_bt("【仅VR>2.0惩罚版】", make_vrpen)

# ===== 惩罚版5：只跌日去CL超卖 =====
def make_down_nocl(mkt):
    mod=MODS[mkt];fn_name=FN_NAMES[mkt]
    orig=getattr(mod,fn_name)
    def fn(s):
        sc=orig(s)
        if mkt=='down' and s['cl']<15: sc-=3
        return round(sc,1)
    return fn

run_bt("【仅跌日去CL超卖】", make_down_nocl)

print(f"\n{'='*65}")
print("最佳版本将更新到策略文件")
