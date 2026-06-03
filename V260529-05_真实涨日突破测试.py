"""
真实涨日V260529-05 全面突破测试
目标: 30天≥80%, 80天≥70%
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

lv={'p_min':3,'p_max':7,'vr_min':0.6,'vr_max':2.5,'hs_min':5,'hs_max':15,'sz_max':200,'cl_min':60,'cl_max':90}

def buildfn(p_w,cl_w=0.05,macd_w=0.3,ma5_b=3,vr_b=1,hs_b=0.3,wr_b=2,j_b=2,j_low_b=2,overdraft=-8,extra_dif=3,extra_mg=3,add_wr75=0,add_cl15=0):
    def fn(s):
        p=s['p'];cl=s['cl'];vr=s['vr'];hsl=s['hsl'];dif=s['dif'];mg=s['mg']
        a5=s['a5'];wrv=s['wrv'];jv=s['jv'];kv=s['kv'];dv=s['dv'];bc=s['buy_c']
        ms=0
        if mg and dif>0.5:ms=10
        elif mg and dif>0.2:ms=8
        elif mg:ms=6
        elif dif>0.5:ms=4
        elif dif>0:ms=2
        ps2=min(10,max(1,11-bc/10))if bc else 0
        sc=p*p_w+cl*cl_w+ps2*0.3+ms*macd_w
        sc+=(ma5_b if a5 else 0)
        sc+=(vr_b*1.5 if 1.0<=vr<=1.5 else 0)
        sc+=(hs_b*2 if 5<=hsl<=7 else 0)
        sc+=(wr_b if wrv<25 else 0)
        sc+=(j_b if jv>kv>dv else 0)
        sc+=(j_low_b if 20<=jv<=40 else 0)
        if overdraft and p>5 and cl>80:sc+=overdraft
        if extra_dif and dif>0.5:sc+=extra_dif
        if extra_mg and mg:sc+=extra_mg
        if add_wr75 and wrv>75:sc+=add_wr75
        if add_cl15 and cl<15:sc+=add_cl15
        return sc
    return fn

tests=[
    ('V260529-03基线',buildfn(2.5)),
    # 降低p_w + 不同组合
    ('A_p_w=2.0',buildfn(2.0)),
    ('B_p_w=1.5',buildfn(1.5)),
    ('C_p_w=1.0',buildfn(1.0)),
    # 去掉透支惩罚
    ('D_p_w2.5_无透支',buildfn(2.5,overdraft=0)),
    ('E_p_w2.0_无透支',buildfn(2.0,overdraft=0)),
    # 降低透支
    ('F_p_w2.5_透支-5',buildfn(2.5,overdraft=-5)),
    # 加强安全信号
    ('G_p_w2.0_透支-5',buildfn(2.0,overdraft=-5)),
    ('H_p_w2.0_MA5=5',buildfn(2.0,ma5_b=5)),
    # 简化版(只保留核心)
    ('I_简p2.0+ma5+wr',buildfn(2.0,ma5_b=3,wr_b=2,j_b=0,j_low_b=0,hs_b=0,vr_b=0,overdraft=0,extra_dif=0,extra_mg=0)),
    ('J_简p2.0+ma5+macd',buildfn(2.0,ma5_b=3,wr_b=0,j_b=0,j_low_b=0,hs_b=0,vr_b=0,overdraft=0,extra_dif=0,extra_mg=3)),
    # 激进加强
    ('K_p_w=3.0_透支-10',buildfn(3.0,overdraft=-10)),
    ('L_p_w=3.0_MA5=5',buildfn(3.0,ma5_b=5)),
    # 降p_w+加WR超卖(跌日经验)
    ('M_p_w2.0+WR75+3',buildfn(2.0,add_wr75=3)),
    ('N_p_w1.5+WR75+3',buildfn(1.5,add_wr75=3)),
]

def bt(fn,md=None):
    td=dates[-md:]if md else dates
    r30={'w':0,'t':0};r80={'w':0,'t':0};ra={'w':0,'t':0}
    for dt in td:
        ss=data.get(dt,[]); 
        if not ss or cls(ss)!='real_up':continue
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

print("="*65)
print("真实涨日V260529-05 全面突破测试")
print(f"目标: 30天≥80%  80天≥70%")
print("="*65)
print(f"{'变体':<24} {'30天':<12} {'80天':<12} {'全量':<12}")
print("-"*65)
for n,fn in tests:
    r30,r80,ra=bt(fn)
    r30s=fm(r30);r80s=fm(r80);ras=fm(ra)
    # 标记达标
    ok30='🔥' if r30['t'] and r30['w']*100/r30['t']>=80 else ''
    ok80='🔥' if r80['t'] and r80['w']*100/r80['t']>=70 else ''
    print(f"{n:<24} {r30s+ok30:<12} {r80s+ok80:<12} {ras:<12}")
