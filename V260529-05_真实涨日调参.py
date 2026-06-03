"""
真实涨日p_w=1.5精细调参
"""
import pickle,os;d=pickle.load(open('C:/Users/12546/AppData/Local/hermes/scripts/big_cache_full.pkl','rb'))
data,real,names=d['data'],d['real'],d['names']
dates=sorted(x for x in data.keys() if '2025-01-01'<=x<'2026-06-01')

def cls(stocks):
    if not stocks:return 'flat'
    ps=[s.get('p',0)or 0 for s in stocks]
    if not ps:return 'flat'
    ap=sum(ps)/len(ps);vrs=[s.get('vol_ratio',0)or 0 for s in stocks if s.get('vol_ratio',0)]
    av=sum(vrs)/len(vrs)if vrs else 0;hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5:return 'fake_up' if hot<15 or av<0.9 else 'real_up'
    if ap<-0.5:return 'down';return 'flat'

lv={'p_min':3,'p_max':7,'vr_min':0.6,'vr_max':2.5,'hs_min':5,'hs_max':15,'sz_max':200,'cl_min':60,'cl_max':90}

def filter_pool(ss):
    pool=[]
    for s in ss:
        c=s.get('code','')
        p=s.get('p',0)or 0
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
    return pool

def score_pool(pool,fn):
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
    scd.sort(key=lambda x:(-x['sc']))
    return scd

def bt(fn,md=None):
    td=dates[-md:]if md else dates
    r30={'w':0,'t':0};r80={'w':0,'t':0};ra={'w':0,'t':0}
    for dt in td:
        ss=data.get(dt,[]); 
        if not ss or cls(ss)!='real_up':continue
        pool=filter_pool(ss)
        if len(pool)<=8:continue
        scd=score_pool(pool,fn)
        if not scd:continue
        ra['t']+=1
        if scd[0]['nh']>=2.5:ra['w']+=1
        idx=td.index(dt);df=len(td)-1-idx
        if df<30:r30['t']+=1
        if scd[0]['nh']>=2.5 and df<30:r30['w']+=1
        if df<80:r80['t']+=1
        if scd[0]['nh']>=2.5 and df<80:r80['w']+=1
    return r30,r80,ra

def fm(r):return f"{r['w']*100/r['t']:.1f}%({r['w']}/{r['t']})"if r['t']else'—'

def mk(pw=1.5,od=-8,ed=3,em=3,mb=3):
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
        sc=p*pw+cl*0.05+ps2*0.3+ms*0.3
        sc+=(mb if a5 else 0)
        sc+=(1*1.5 if 1.0<=vr<=1.5 else 0)
        sc+=(0.3*2 if 5<=hsl<=7 else 0)
        sc+=(2 if wrv<25 else 0)
        sc+=(2 if jv>kv>dv else 0)
        sc+=(2 if 20<=jv<=40 else 0)
        if od and p>5 and cl>80:sc+=od
        if ed and dif>0.5:sc+=ed
        if em and mg:sc+=em
        return sc
    return fn

tests=[
    ('V260529-03(p2.5_od-8_e3_m3)',mk(2.5,-8,3,3,3)),
    ('B05_p1.5_od-8_e3_m3_mb3(突破)',mk(1.5,-8,3,3,3)),
    ('B1_p1.5_od-5_e3_m3',mk(1.5,-5,3,3,3)),
    ('B2_p1.5_od-8_e2_m2',mk(1.5,-8,2,2,3)),
    ('B3_p1.5_od-8_e0_m0',mk(1.5,-8,0,0,3)),
    ('B4_p1.5_od0_e3_m3',mk(1.5,0,3,3,3)),
    ('B5_p1.5_od-8_e3_m3_mb4',mk(1.5,-8,3,3,4)),
    ('B6_p1.5_od-8_e3_m3_mb5',mk(1.5,-8,3,3,5)),
    ('B7_p1.5_od-10_e3_m3',mk(1.5,-10,3,3,3)),
    ('B8_p1.5_od-5_e0_m0',mk(1.5,-5,0,0,3)),
    ('B9_p1.5_od-8_e3_m0',mk(1.5,-8,3,0,3)),
    ('B10_p1.5_od-8_e0_m3',mk(1.5,-8,0,3,3)),
]

print('='*70)
print('真实涨日p_w=1.5精细调参')
print('目标: 30天≥80%🔥  80天≥70%🔵')
print('='*70)
print(f"{'变体':<35} {'30天':<12} {'80天':<12} {'全量':<12}")
print('-'*70)
for n,fn in tests:
    r30,r80,ra=bt(fn)
    r30s=fm(r30);r80s=fm(r80);ras=fm(ra)
    ok30='🔥' if r30['t'] and r30['w']*100/r30['t']>=80 else ''
    ok80='🔵' if r80['t'] and r80['w']*100/r80['t']>=70 else ''
    print(f'{n:<35} {r30s+ok30:<12} {r80s+ok80:<12} {ras:<12}')
