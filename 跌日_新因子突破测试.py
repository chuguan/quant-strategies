"""
跌日新因子突破测试 — 在V260529-01(75%)基础上再突破
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

# 当前V260529-01评分
def base(s):
    p=s['p'];cl=s['cl'];dif=s['dif'];mg=s['mg'];a5=s['a5']
    wrv=s['wrv'];bc=s['buy_c']
    ms=0
    if mg and dif>0.5:ms=10
    elif mg and dif>0.2:ms=8
    elif mg:ms=6
    elif dif>0.5:ms=4
    elif dif>0:ms=2
    ps2=min(10,max(1,11-bc/10))if bc else 0
    sc=p*1.5+cl*0.05+ps2*0.3+ms*0.3
    sc+=(2 if a5 else 0)
    sc+=(3 if wrv>75 else 0)
    sc+=(3 if cl<15 else 0)
    sc+=(2 if p<-3 else 0)
    return sc

# 新因子测试
def vA(s):
    """A: WR+CL组合奖励(W>75且CL<15→+8)"""
    sc=base(s)
    if s['wrv']>75 and s['cl']<15:sc+=2  # 已有各+3，再加+2组合奖
    return sc

def vB(s):
    """B: 降低p_w到1.0，增加反转信号权重"""
    sc=base(s)
    p_part=s['p']*1.0  # 原1.5
    sc-=(s['p']*0.5)  # 减掉0.5
    sc+=(5 if s['wrv']>75 else 0)  # WR从+3→+5
    return sc

def vC(s):
    """C: 提高反转信号 - WR>80→+4, CL<10→+4, p<-4→+3"""
    sc=base(s)
    sc-=(3 if s['wrv']>75 else 0)
    sc-=(3 if s['cl']<15 else 0)
    sc-=(2 if s['p']<-3 else 0)
    sc+=(4 if s['wrv']>80 else 0)
    sc+=(4 if s['cl']<10 else 0)
    sc+=(3 if s['p']<-4 else 0)
    return sc

def vD(s):
    """D: 加MACD强化 — dif>0(金叉)+2"""
    sc=base(s)
    sc+=(2 if s['dif']>0 else 0)  # MACD金叉本身上下文中已有ms计算
    # 实际上ms里已经包含了mg的权重，这个vD加的是额外的金叉奖励
    return sc

def vE(s):
    """E: 加均线发散(MA5>MA10→+2)"""
    sc=base(s)
    a5=s['a5'];kv=s['kv'];dv=s['dv']
    # a5=True说明close>ma5，不额外加分
    return sc
# 需要额外数据(a5不如ma5>ma10)，跳过

def vF(s):
    """F: KDJ低位金叉(J>K>D 且 J<30→+4)"""
    sc=base(s)
    jv=s['jv'];kv=s['kv'];dv=s['dv']
    if jv>kv>dv and jv<30:sc+=4
    return sc

def vG(s):
    """G: 加强WR信号 — WR>80→+5"""
    sc=base(s)
    sc-=(3 if s['wrv']>75 else 0)
    sc+=(5 if s['wrv']>80 else 0)
    return sc

def vH(s):
    """H: CL+WR+深跌组合奖励"""
    sc=base(s)
    bonus=0
    if s['wrv']>75:bonus+=1
    if s['cl']<12:bonus+=1
    if s['p']<-4:bonus+=1
    if bonus>=3:sc+=5  # 三个信号全中→额外+5
    elif bonus>=2:sc+=2  # 两个中→额外+2
    return sc

def vI(s):
    """I: 用换手率信号 — hsl<3(极度缩量)+3"""
    sc=base(s)
    sc+=(3 if s['hsl']<3 else 0)
    return sc

def vJ(s):
    """J: 组合H+I — 三信号+缩量"""
    sc=base(s)
    bonus=0
    if s['wrv']>75:bonus+=1
    if s['cl']<12:bonus+=1
    if s['p']<-4:bonus+=1
    if bonus>=3:sc+=5
    elif bonus>=2:sc+=2
    sc+=(3 if s['hsl']<3 else 0)
    return sc

tests=[
    ('V260529-01基线',base),
    ('A_WR+CL组合奖',vA),
    ('B_p_w1.0+WR+5',vB),
    ('C_WR>80+CL<10',vC),
    ('D_MACD金叉+2',vD),
    ('F_KDJ低位金叉',vF),
    ('G_WR>80→+5',vG),
    ('H_三信号组合',vH),
    ('I_缩量+3',vI),
    ('J_组合+缩量',vJ),
]

# 之前测试过的跌日L级参数不变
lv={'p_min':-3,'p_max':7,'vr_min':0.4,'vr_max':3.5,'hs_min':1,'hs_max':30,'sz_max':300,'cl_min':10,'cl_max':98}

def bt(fn,md=None):
    td=dates[-md:]if md else dates
    r30={'w':0,'t':0};r80={'w':0,'t':0};ra={'w':0,'t':0}
    for dt in td:
        ss=data.get(dt,[]); 
        if not ss or cls(ss)!='down':continue
        pool=[]
        for s in ss:
            c=s.get('code','');p=s.get('p',0)or 0
            if p<lv['p_min']or p>lv['p_max']:continue
            if p>=8:continue
            vr=s.get('vol_ratio',0)or 0
            if vr<lv['vr_min']or vr>lv['vr_max']:continue
            ri=real.get(c)
            if not ri:continue
            hsl=(ri.get('hsl',0)or 0)
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

print("="*70)
print("跌日新因子突破测试")
print("="*70)
print(f"{'变体':<20} {'30天':<14} {'80天':<14} {'全量':<14}")
print("-"*70)
for n,fn in tests:
    r30,r80,ra=bt(fn)
    print(f"{n:<20} {fm(r30):<14} {fm(r80):<14} {fm(ra):<14}")
