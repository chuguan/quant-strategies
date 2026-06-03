"""
V260529-04 跌日L级参数收紧测试
当前L级: p_min=-3/p_max=7/vr_min=0.4/vr_max=3.5/hs=1~30/CL=10~98 → 平均1071只/天太松
测试收紧不同参数维度
"""
import pickle,os,sys,importlib
SCRIPTS_DIR=os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR);sys.path.insert(0,SCRIPTS_DIR)
d=pickle.load(open('big_cache_full.pkl','rb'))
data,real,names=d['data'],d['real'],d['names']
dates=sorted(x for x in data.keys() if '2025-01-01'<=x<'2026-06-01')

mod=importlib.import_module('大道至简_跌日_评分策略')

def cls(stocks):
    if not stocks:return 'flat'
    ps=[s.get('p',0)or 0 for s in stocks]
    vrs=[s.get('vol_ratio',0)or 0 for s in stocks if s.get('vol_ratio',0)]
    if not ps:return 'flat'
    ap=sum(ps)/len(ps);av=sum(vrs)/len(vrs)if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5:return 'fake_up' if hot<15 or av<0.9 else 'real_up'
    if ap<-0.5:return 'down'
    return 'flat'

def bt(lv_params,md=None):
    """回测指定L级参数"""
    td=dates[-md:]if md else dates
    r30={'w':0,'t':0};r80={'w':0,'t':0};ra={'w':0,'t':0};pl=[]
    for dt in td:
        ss=data.get(dt,[]); 
        if not ss or cls(ss)!='down':continue
        pool=[]
        for s in ss:
            c=s.get('code','');p=s.get('p',0)or 0
            if p<lv_params['p_min']or p>lv_params['p_max']:continue
            if p>=8:continue
            vr=s.get('vol_ratio',0)or 0
            if vr<lv_params['vr_min']or vr>lv_params['vr_max']:continue
            ri=real.get(c)
            if not ri:continue
            hsl=(ri.get('hsl',0)or 0)
            if hsl<lv_params['hs_min']or hsl>lv_params['hs_max']:continue
            if(ri.get('shizhi',0)or 0)>=lv_params['sz_max']:continue
            nm=names.get(c,'')
            if 'ST'in nm or '*ST'in nm or '退'in nm:continue
            cl=s.get('cl',0)
            if cl<lv_params['cl_min']or cl>lv_params['cl_max']:continue
            if(s.get('n',0)or 0)<=0:continue
            pool.append(s)
        if len(pool)<=8:continue
        pl.append(len(pool))
        
        scored=[]
        for s in pool:
            sd={'p':s.get('p',0)or 0,'cl':s.get('cl',0),'vr':s.get('vol_ratio',0)or 0,
                'hsl':(real.get(s['code'],{}).get('hsl',0)or 0),
                'dif':s.get('dif_val',0)or 0,'mg':s.get('macd_golden',0),
                'a5':s.get('above_ma5',0)or 0,'wrv':0,
                'jv':s.get('j_val',0)or 0,'kv':s.get('k_val',0)or 0,
                'dv':s.get('d_val',0)or 0,'kdj_g':s.get('kdj_golden',0)or 0,
                'buy_c':s.get('close',0)or 0}
            sc=mod.跌日_评分(sd);nh=s.get('n',0)or 0
            scored.append({'sc':sc,'nh':nh})
        if not scored:continue
        scored.sort(key=lambda x:(-x['sc']))
        ra['t']+=1
        if scored[0]['nh']>=2.5:ra['w']+=1
        idx=td.index(dt);df=len(td)-1-idx
        if df<30:r30['t']+=1
        if scored[0]['nh']>=2.5 and df<30:r30['w']+=1
        if df<80:r80['t']+=1
        if scored[0]['nh']>=2.5 and df<80:r80['w']+=1
    avg_p=sum(pl)/len(pl)if pl else 0
    return r30,r80,ra,avg_p

def fm(r):return f"{r['w']*100/r['t']:.1f}%({r['w']}/{r['t']})"if r['t']else'—'

# 当前L级
BASE={'name':'L','p_min':-3,'p_max':7,'vr_min':0.4,'vr_max':3.5,'hs_min':1,'hs_max':30,'sz_max':300,'cl_min':10,'cl_max':98}

tests=[
    ('当前L级(基线)',BASE),
    # 收紧涨幅下限
    ('A_p_min=-1',{**BASE,'p_min':-1}),
    ('B_p_min=0',{**BASE,'p_min':0}),
    ('C_p_min=2',{**BASE,'p_min':2}),
    ('D_p_min=3',{**BASE,'p_min':3}),
    # 收紧CL
    ('E_CL_min=30',{**BASE,'cl_min':30}),
    ('F_CL_min=50',{**BASE,'cl_min':50}),
    # 收紧量比
    ('G_vr_min=0.6',{**BASE,'vr_min':0.6}),
    ('H_vr_min=0.8',{**BASE,'vr_min':0.8}),
    # 收紧上限
    ('I_p_max=6',{**BASE,'p_max':6}),
    # 组合
    ('J_p_min=0+CL30',{**BASE,'p_min':0,'cl_min':30}),
    ('K_p_min=2+CL30',{**BASE,'p_min':2,'cl_min':30}),
    ('L_p_min=3+CL30',{**BASE,'p_min':3,'cl_min':30}),
    ('M_p_min=2+vr0.6',{**BASE,'p_min':2,'vr_min':0.6}),
    ('N_p_min=3+vr0.6',{**BASE,'p_min':3,'vr_min':0.6}),
]

print("="*80)
print("V260529-04 跌日L级参数收紧测试")
print("="*80)
print(f"{'变体':<18} {'30天':<14} {'80天':<14} {'全量':<14} {'平均池':>6}")
print("-"*80)
for n,lv in tests:
    r30,r80,ra,ap=bt(lv)
    print(f"{n:<18} {fm(r30):<14} {fm(r80):<14} {fm(ra):<14} {ap:>5.0f}")
