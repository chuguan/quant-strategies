"""
V260529-03 真实涨日评分优化测试
"""
import pickle,os,sys,importlib
SCRIPTS_DIR=os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR);sys.path.insert(0,SCRIPTS_DIR)
d=pickle.load(open('big_cache_full.pkl','rb'))
data,real,names=d['data'],d['real'],d['names']
dates=sorted(x for x in data.keys() if '2025-01-01'<=x<'2026-06-01')

mod=importlib.import_module('大道至简_真实涨日_评分策略')
lv={**mod.LEVELS[0],'name':'L'}

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

def bt(fn,md=None):
    td=dates[-md:]if md else dates
    r30={'w':0,'t':0};r80={'w':0,'t':0};ra={'w':0,'t':0}
    for dt in td:
        ss=data.get(dt,[])
        if not ss:continue
        if cls(ss)!='real_up':continue
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
            if (ri.get('shizhi',0)or 0)>=lv['sz_max']:continue
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
        if df<30:
            r30['t']+=1
            if scd[0]['nh']>=2.5:r30['w']+=1
        if df<80:
            r80['t']+=1
            if scd[0]['nh']>=2.5:r80['w']+=1
    return r30,r80,ra

def fm(r):return f"{r['w']*100/r['t']:.1f}%({r['w']}/{r['t']})"if r['t']else'—'

# ===== 当前基线（已含V260528加分） =====
def base(s):
    p=s['p'];cl=s['cl'];vr=s['vr'];hsl=s['hsl'];dif=s['dif'];mg=s['mg'];a5=s['a5']
    wrv=s['wrv'];jv=s['jv'];kv=s['kv'];dv=s['dv'];kdj_g=s['kdj_g'];bc=s['buy_c']
    ms=0
    if mg and dif>0.5:ms=10
    elif mg and dif>0.2:ms=8
    elif mg:ms=6
    elif dif>0.5:ms=4
    elif dif>0:ms=2
    ps2=min(10,max(1,11-bc/10))if bc else 0
    sc=p*2.5+cl*0.05+ps2*0.3+ms*0.3
    sc+=(3 if a5 else 0)
    sc+=(1*1.5 if 1.0<=vr<=1.5 else 0)
    sc+=(0.3*2 if 5<=hsl<=7 else 0)
    sc+=(2 if wrv<25 else 0)
    sc+=(2 if jv>kv>dv else 0)
    sc+=(2 if 20<=jv<=40 else 0)
    if p>5 and cl>80:sc-=8
    if dif>0.5:sc+=3
    if mg:sc+=3
    return sc

def vA(s):
    """A: p_w=2.0（原2.5）"""
    sc=base(s);sc-=s['p']*0.5;return sc
def vB(s):
    """B: p_w=3.0（提高追强）"""
    sc=base(s);sc+=s['p']*0.5;return sc
def vC(s):
    """C: 透支惩罚从-8改-5"""
    sc=base(s)
    if s['p']>5 and s['cl']>80:sc+=3  # -8→-5
    return sc
def vD(s):
    """D: 透支惩罚从-8改-10"""
    sc=base(s)
    if s['p']>5 and s['cl']>80:sc-=2  # -8→-10
    return sc
def vE(s):
    """E: MA5加分从3→5"""
    sc=base(s);sc+=(2 if s['a5']else 0);return sc
def vF(s):
    """F: 去掉透支惩罚"""
    sc=base(s)
    if s['p']>5 and s['cl']>80:sc+=8  # 去除-8
    return sc
def vG(s):
    """G: p_w=2.0 + 透支-10"""
    sc=base(s);sc-=s['p']*0.5
    if s['p']>5 and s['cl']>80:sc-=2
    return sc
def vH(s):
    """H: 加WR超卖(>75→+3)作为补充"""
    sc=base(s);sc+=(3 if s['wrv']>75 else 0);return sc
def vI(s):
    """I: ma5_b=5 + 透支-5"""
    sc=base(s);sc+=(2 if s['a5']else 0)
    if s['p']>5 and s['cl']>80:sc+=3
    return sc

tests=[
    ('基线(p_w=2.5+加分)',base),
    ('A_p_w=2.0',vA),
    ('B_p_w=3.0',vB),
    ('C_透支-8→-5',vC),
    ('D_透支-8→-10',vD),
    ('E_MA5_b=5',vE),
    ('F_去透支惩罚',vF),
    ('G_p_w2.0+透支-10',vG),
    ('H_加WR超卖+3',vH),
    ('I_MA5=5+透支-5',vI),
]

print("="*70)
print("V260529-03 真实涨日评分优化测试")
print("="*70)
print(f"{'变体':<22} {'30天':<16} {'80天':<16} {'全量':<16}")
print("-"*70)
for n,fn in tests:
    r30,r80,ra=bt(fn)
    print(f"{n:<22} {fm(r30):<16} {fm(r80):<16} {fm(ra):<16}")
