"""
V260529 各行情最新版本统一回测
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

# 各行情评分模块+L级参数
STRATS={
    'real_up':{'mod':'大道至简_真实涨日_评分策略','fn':'真实涨日_评分',
        'lv':{'p_min':3,'p_max':7,'vr_min':0.6,'vr_max':2.5,'hs_min':5,'hs_max':15,'sz_max':200,'cl_min':60,'cl_max':90}},
    'fake_up':{'mod':'大道至简_虚涨日_评分策略','fn':'虚涨日_评分',
        'lv':{'p_min':0,'p_max':6,'vr_min':0.6,'vr_max':2.5,'hs_min':5,'hs_max':20,'sz_max':200,'cl_min':30,'cl_max':95}},
    'down':{'mod':'大道至简_跌日_评分策略','fn':'跌日_评分',
        'lv':{'p_min':-3,'p_max':7,'vr_min':0.4,'vr_max':3.5,'hs_min':1,'hs_max':30,'sz_max':300,'cl_min':10,'cl_max':98}},
    'flat':{'mod':'大道至简_横盘_评分策略','fn':'横盘_评分',
        'lv':{'p_min':0,'p_max':7,'vr_min':0.6,'vr_max':2.5,'hs_min':3,'hs_max':20,'sz_max':200,'cl_min':40,'cl_max':95}},
}

print("="*65)
print("V260529 各行情最新版本胜率")
print("="*65)
print(f"{'行情':<8} {'版本':<14} {'30天':<12} {'80天':<12} {'全量':<12}")
print("-"*65)

for mk in ['real_up','fake_up','down','flat']:
    info=STRATS[mk]; mod=importlib.import_module(info['mod'])
    fn=getattr(mod,info['fn']); lv=info['lv']
    
    # 回测
    td=dates[-333:]
    r30={'w':0,'t':0};r80={'w':0,'t':0};ra={'w':0,'t':0}
    for dt in td:
        ss=data.get(dt,[])
        if not ss or cls(ss)!=mk:continue
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
    
    # 版本号映射
    ver={'real_up':'V260529-03','fake_up':'原始版','down':'V260529-01','flat':'V260529-02'}
    r30s=f"{r30['w']*100/r30['t']:.1f}%({r30['w']}/{r30['t']})"if r30['t']else'—'
    r80s=f"{r80['w']*100/r80['t']:.1f}%({r80['w']}/{r80['t']})"if r80['t']else'—'
    ras=f"{ra['w']*100/ra['t']:.1f}%({ra['w']}/{ra['t']})"if ra['t']else'—'
    print(f"{info['mod'].replace('大道至简_','').replace('_评分策略',''):<8} {ver[mk]:<14} {r30s:<12} {r80s:<12} {ras:<12}")

# 总计
print("-"*65)
tot30={'w':0,'t':0};tot80={'w':0,'t':0};tota={'w':0,'t':0}
for mk in ['real_up','fake_up','down','flat']:
    info=STRATS[mk]; mod=importlib.import_module(info['mod'])
    fn=getattr(mod,info['fn']); lv=info['lv']
    for dt in dates:
        ss=data.get(dt,[])
        if not ss or cls(ss)!=mk:continue
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
        tota['t']+=1
        if scd[0]['nh']>=2.5:tota['w']+=1
        idx=dates.index(dt);df=len(dates)-1-idx
        if df<30:tot30['t']+=1
        if scd[0]['nh']>=2.5 and df<30:tot30['w']+=1
        if df<80:tot80['t']+=1
        if scd[0]['nh']>=2.5 and df<80:tot80['w']+=1

t30s=f"{tot30['w']*100/tot30['t']:.1f}%({tot30['w']}/{tot30['t']})"if tot30['t']else'—'
t80s=f"{tot80['w']*100/tot80['t']:.1f}%({tot80['w']}/{tot80['t']})"if tot80['t']else'—'
tas=f"{tota['w']*100/tota['t']:.1f}%({tota['w']}/{tota['t']})"if tota['t']else'—'
print(f"{'合计':<8} {'':14} {t30s:<12} {t80s:<12} {tas:<12}")
