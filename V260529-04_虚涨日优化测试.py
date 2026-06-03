"""
V260529-04 虚涨日评分优化测试
当前: p_w=1.0+MACD×0.5(极简) → 全量88.2%但30天无数据
尝试加新因子看能否稳住
"""
import pickle,os,sys,importlib
SCRIPTS_DIR=os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR);sys.path.insert(0,SCRIPTS_DIR)
d=pickle.load(open('big_cache_full.pkl','rb'))
data,real,names=d['data'],d['real'],d['names']
dates=sorted(x for x in data.keys() if '2025-01-01'<=x<'2026-06-01')

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

lv={'p_min':0,'p_max':6,'vr_min':0.6,'vr_max':2.5,'hs_min':5,'hs_max':20,'sz_max':200,'cl_min':30,'cl_max':95}

def base(s):
    """原始虚涨日评分"""
    p=s['p'];cl=s['cl'];dif=s['dif'];mg=s['mg'];bc=s['buy_c']
    ms=0
    if mg and dif>0.5:ms=10
    elif mg and dif>0.2:ms=8
    elif mg:ms=6
    elif dif>0.5:ms=4
    elif dif>0:ms=2
    ps2=min(10,max(1,11-bc/10))if bc else 0
    return p*1.0+cl*0.05+ps2*0.3+ms*0.5

def vA(s):
    """A: 加MA5站上+2"""
    return base(s)+(2 if s['a5']else 0)
def vB(s):
    """B: p_w=1.0→1.5"""
    sc=base(s);sc+=s['p']*0.5;return sc
def vC(s):
    """C: 加WR超卖(>75→+3)"""
    return base(s)+(3 if s['wrv']>75 else 0)
def vD(s):
    """D: p_w=1.5+MA5"""
    return base(s)+(2 if s['a5']else 0)+s['p']*0.5
def vE(s):
    """E: 加j_low(20≤J≤40→+2)"""
    return base(s)+(2 if 20<=s['jv']<=40 else 0)
def vF(s):
    """F: KDJ金叉+2"""
    sc=base(s);sc+=(2 if s['kdj_g']else 0);return sc

tests=[
    ('原始极简',base),('A_MA5+2',vA),('B_p_w=1.5',vB),
    ('C_WR超卖',vC),('D_p1.5+MA5',vD),('E_j_low+2',vE),('F_KDJ金叉',vF),
]

def bt(fn,md=None):
    td=dates[-md:]if md else dates
    r30={'w':0,'t':0};r80={'w':0,'t':0};ra={'w':0,'t':0}
    for dt in td:
        ss=data.get(dt,[]); 
        if not ss or cls(ss)!='fake_up':continue
        pool=[]
        for s in ss:
            c=s.get('code','');p=s.get('p',0)or 0
            if p<lv['p_min']or p>lv['p_max']:continue
            if p>=8:continue;vr=s.get('vol_ratio',0)or 0
            if vr<lv['vr_min']or vr>lv['vr_max']:continue
            ri=real.get(c)
            if not ri:continue;hsl=(ri.get('hsl',0)or 0)
            if hsl<lv['hs_min']or hsl>lv['hs_max']:continue
            if(ri.get('shizhi',0)or 0)>=lv['sz_max']:continue
            nm=names.get(c,'')
            if 'ST'in nm or '*ST'in nm or '退'in nm:continue
            cl=s.get('cl',0)
            if cl<lv['cl_min']or cl>lv['cl_max']:continue
            if(s.get('n',0)or 0)<=0:continue
            pool.append(s)
        if len(pool)<=8:continue
        scd=[]
        for s in pool:
            sd={'p':s.get('p',0)or 0,'cl':s.get('cl',0),'vr':s.get('vol_ratio',0)or 0,
                'hsl':(real.get(s['code'],{}).get('hsl',0)or 0),
                'dif':s.get('dif_val',0)or 0,'mg':s.get('macd_golden',0),
                'a5':s.get('above_ma5',0)or 0,'wrv':0,
                'jv':s.get('j_val',0)or 0,'kv':s.get('k_val',0)or 0,
                'dv':s.get('d_val',0)or 0,'kdj_g':s.get('kdj_golden',0)or 0,
                'buy_c':s.get('close',0)or 0}
            sc=fn(sd);nh=s.get('n',0)or 0
            scd.append({'sc':sc,'nh':nh})
        if not scd:continue
        scd.sort(key=lambda x:(-x['sc']))
        ra['t']+=1
        if scd[0]['nh']>=2.5:ra['w']+=1
        idx=td.index(dt);df=len(td)-1-idx
        if df<30:r30['t']+=1
        if scd[0]['nh']>=2.5 and df<30:r30['w']+=1
        if df<80:r80['t']+=1
        if scd[0]['nh']>=2.5 and df<80:r80['w']+=1
    return r30,r80,ra

def fm(r):return f"{r['w']*100/r['t']:.1f}%({r['w']}/{r['t']})"if r['t']else'—'

print("="*60)
print("V260529-04 虚涨日评分优化测试")
print(f"总天数:17天 | 近80天:5天 | 近30天:{sum(1 for dt in dates[-30:] if cls(data.get(dt,[]))=='fake_up')}天")
print("="*60)
print(f"{'变体':<14} {'30天':<12} {'80天':<12} {'全量':<12}")
print("-"*60)
for n,fn in tests:
    r30,r80,ra=bt(fn)
    print(f"{n:<14} {fm(r30):<12} {fm(r80):<12} {fm(ra):<12}")
