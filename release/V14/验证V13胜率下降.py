"""V13不同时间窗口胜率对比"""
import pickle, os, sys, importlib

V13_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d['real'], d['names']
with open(os.path.join(V13_DIR, 'features_30d.pkl'), 'rb') as f:
    precomputed = pickle.load(f)

def mkt_class(ss):
    if not ss: return 'flat'
    ps=[s.get('p',0) or 0 for s in ss]
    ap=sum(ps)/len(ps)
    vrs=[s.get('vol_ratio',0) or 0 for s in ss if s.get('vol_ratio',0)]
    av=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

MK_MAP={'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO=['L0','L1','L2','L3','L4']

def load_mod(name):
    fp=os.path.join(V13_DIR,'评分策略',f'分而治之_V10_{name}_评分策略.py')
    spec = importlib.util.spec_from_file_location('m', fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

STRATS={}
for n in ['真实涨日','虚涨日','跌日','横盘']: STRATS[n]=load_mod(n)

def get_feats(c,d): return precomputed.get((c,d),{})

def is_me(s,c,dt):
    f=get_feats(c,dt)
    if not f: return False
    sl5=f.get('slope5',0); t4s=f.get('t4_shadow',0)
    d3=f.get('d3',0); d2=f.get('d2',0); d1=f.get('d1',0)
    cu=f.get('cons_up',0); pk=f.get('peak_decay',0)
    pv=s.get('p',0) or 0
    if sl5>8 and t4s>25: return True
    if sl5>10 and t4s>18: return True
    if cu>=5 and sl5>15: return True
    if pk>5 and sl5>5 and pv<6: return True
    if sl5>5 and t4s>30: return True
    if cu>=4 and sl5>10 and pv<7: return True
    if d3>=5 and d3>d2>d1 and pv<7: return True
    if d2>=5 and d1>=3 and cu<3: return True
    if d3<-3 and d2>4 and pv<6: return True
    return False

def comp_7d(c,dt,pt):
    ad=sorted(data.keys()); idx=ad.index(dt)
    pr=ad[max(0,idx-6):idx]; gs=[]
    for pd in pr:
        f=False
        for s in data[pd]:
            if s['code']==c: gs.append(s.get('p',0) or 0); f=True; break
        if not f: gs.append(0)
    gs.append(pt); n=len(gs)
    if n<5: return 0
    d6,d5,d4,d3,d2,d1,p=gs[-7:] if n>=7 else [0]*(7-n)+gs
    pm=p>=max(gs[:-1]) if len(gs)>1 else True; a7=sum(gs)/n; pe=0
    wr=50
    for s in data.get(dt,[]):
        if s['code']==c: wr=s.get('wr_val',50) or s.get('wrv',50); break
    if wr<10 and pm and a7<2.0 and p<6: pe-=8
    if pm and a7<0.8 and p<8:
        if a7<0: pe-=15
        elif a7<0.3: pe-=12
        elif a7<0.7: pe-=8
        else: pe-=5
    if d1<-1.5 and d2<-1.0 and p>3 and a7<1.0: pe-=8
    if max(d4,d3,d2)>5 and d1<0 and d2<0: pe-=10
    if n>=5 and d5>d1 and d5>d2 and p<=d5:
        rs=(d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
        if rs<=2: pe-=8
    if n>=5:
        l5=gs[-5:]
        if all(l5[i]>=l5[i+1] for i in range(len(l5)-1)): pe-=10
    return pe

all_dates=sorted(data.keys())
print('='*60)
print('V13收盘价数据——不同30天窗口对比')
print('='*60)

for label, cutoff in [('原脚本(到5/22)', '2026-05-22'), ('含最新(到5/28)', '2026-05-29')]:
    dates=[d for d in all_dates if d<=cutoff]
    recent=dates[-30:]
    wi=0; ta=0; fails=[]
    for dt in recent:
        ss=data.get(dt,[]); ss=[s for s in ss if (s.get('p',0) or 0)<8]
        if not ss: continue
        mk=mkt_class(ss); mk_cn=MK_MAP.get(mk,'横盘')
        mod=STRATS[mk_cn]; LEVELS=mod.LEVELS
        lm={l['name']:i for i,l in enumerate(LEVELS)}
        pool=None
        for ln in LO:
            if ln not in lm: continue
            lv=LEVELS[lm[ln]]; cand=[]
            for s in ss:
                p=s.get('p',0) or 0
                if p<lv['p_min'] or p>min(lv.get('p_max',10),8): continue
                vr=s.get('vol_ratio',0) or 0
                if vr<lv['vr_min'] or vr>lv['vr_max']: continue
                ri=real.get(s['code'],{}); hsl=ri.get('hsl',0) or 0
                if hsl<lv.get('hs_min',0) or hsl>lv.get('hs_max',99): continue
                if (ri.get('shizhi',0) or 0)>=lv.get('sz_max',9999): continue
                nm=names.get(s['code'],'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl=s.get('cl',0)
                if cl<lv.get('cl_min',0) or cl>lv.get('cl_max',100): continue
                if is_me(s,s['code'],dt): continue
                cand.append(s)
            if len(cand)>=10: pool=cand; break
        if not pool: continue
        stk={}
        for s in pool:
            p=s.get('p',0) or 0; d=s.get('dif_val',0) or s.get('dif',0) or 0
            w=s.get('wr_val',50) or s.get('wrv',50); c=s.get('cl',50)
            h=s.get('hsl',0); dv=s.get('d_val',50) or s.get('dv',50)
            v=s.get('vol_ratio',1) or 1; po=s.get('pos_in_day',50)
            a5=s.get('above_ma5',0); mg=s.get('macd_golden',0) or s.get('mg',0)
            kg=s.get('kdj_golden',0) or s.get('kdj_g',0)
            feats=get_feats(s['code'],dt)
            t4s=feats.get('t4_shadow',0); sl5=feats.get('slope5',0); cu=feats.get('cons_up',0)
            nm=names.get(s['code'],'')
            sc=min(p/3.0,1)*70 + min(d/0.5,1)*50 + max(0,min((50-w)/30,1))*30
            sc+=min(c/80,1)*30 + min(h/8,1)*20 + min(dv/65,1)*20
            sc+=min(v/1.3,1)*20 + max(0,min((100-po)/50,1))*10
            if a5: sc+=8
            if d>0.3 and p>2.0: sc+=8
            if w<30 and c>75: sc+=5
            if h>5 and v>1.1: sc+=5
            if mg and kg: sc+=3
            if t4s>50: sc-=20
            if sl5>15 and p<4: sc-=15
            if sl5>4 and t4s>30: sc-=8
            sc+=comp_7d(s['code'],dt,p)
            stk[round(sc,1)]=s
        scored=sorted(stk.items(),key=lambda x:-x[0])
        ta+=1
        champ=scored[0][1]
        nh=champ.get('n',0) or 0
        nm=names.get(champ['code'],'?')
        p=champ.get('p',0) or 0
    if nh>=2.5: wi+=1
    else:
        code=champ['code']
        fails.append(f'{dt} {nm}({code}) p={p:.1f}% nh={nh:+.1f}%')
    print(f'\n{label}:')
    print(f'  胜率: {wi}/{ta} = {wi*100/ta:.1f}%')
    if fails:
        print(f'  失败日({len(fails)}次):')
        for f in fails: print(f'    {f}')

print('\n' + '='*60)
print('原因：5/25-5/27大盘连续下跌，选股再准也难次日冲2.5%')
