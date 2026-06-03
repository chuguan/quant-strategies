"""
跌日30天深度分析 — 看赢家和输家的差异，再优化
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
print(f"跌日共{len(ddates)}天",flush=True)

mod=importlib.import_module('大道至简_跌日_评分策略')
LV=mod.LEVELS

def bs(s):
    c=s.get('code','');ri=real.get(c,{})
    return {'p':s.get('p',0) or 0,'cl':s.get('cl',0),'vr':s.get('vol_ratio',0) or 0,
        'hsl':(ri.get('hsl',0) or 0),'dif':s.get('dif_val',0) or 0,'mg':s.get('macd_golden',0) or 0,
        'a5':s.get('above_ma5',0) or 0,'wrv':s.get('wr_val',0) or 20,
        'jv':s.get('j_val',0) or 0,'kv':s.get('k_val',0) or 0,'dv':s.get('d_val',0) or 0,
        'kdj_g':s.get('kdj_golden',0) or 0,'buy_c':s.get('close',0) or 0}

# 收集所有跌日冠军数据
champ_wins=[];champ_losses=[]
for dt in ddates:
    ss=data.get(dt,[])
    if not ss:continue
    cand=None
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
    
    # 用模块评分函数
    fn=getattr(mod,'跌日_评分')
    scored=[]
    for s in cand:
        sc=fn(bs(s))
        nh=s.get('n',0) or 0
        p=s.get('p',0) or 0
        scored.append({'sc':sc,'nh':nh,'p':p,'cl':s.get('cl',0),'vr':s.get('vol_ratio',0) or 0,
            'dif':s.get('dif_val',0) or 0,'mg':s.get('macd_golden',0) or 0,
            'a5':s.get('above_ma5',0) or 0,'wrv':s.get('wr_val',0) or 20,
            'jv':s.get('j_val',0) or 0,'kdj_g':s.get('kdj_golden',0) or 0,'hsl':(real.get(s.get('code',''),{}).get('hsl',0) or 0),
            'nm':names.get(s.get('code',''),'?')[:8]})
    scored.sort(key=lambda x:(-x['sc']))
    champ=scored[0]
    r={'date':dt,'nm':champ['nm'],'sc':champ['sc'],'nh':champ['nh'],
        'p':champ['p'],'cl':champ['cl'],'vr':champ['vr'],'dif':champ['dif'],
        'mg':champ['mg'],'a5':champ['a5'],'wrv':champ['wrv'],'jv':champ['jv'],
        'kdj_g':champ['kdj_g'],'hsl':champ['hsl'],'pool':len(cand),'win':champ['nh']>=2.5}
    if r['win']:champ_wins.append(r)
    else:champ_losses.append(r)

print(f"\n{'='*70}")
print(f"【分析1】跌日冠军 赢家({len(champ_wins)}次) vs 输家({len(champ_losses)}次)")
print(f"{'='*70}")
def avg(lst,key):return round(sum(r[key] for r in lst)/len(lst),2) if lst else 0
for key,nm in [('p','当日涨幅'),('cl','CL'),('vr','量比'),('hsl','换手'),
                ('dif','DIF'),('mg','金叉'),('a5','MA5'),('wrv','WR'),
                ('jv','J值'),('kdj_g','KDJ金叉'),('sc','评分')]:
    wa=avg(champ_wins,key);la=avg(champ_losses,key)
    diff=round(wa-la,2)
    print(f"  {nm:10s}: 赢={wa:>8.2f}  输={la:>8.2f}  差={diff:+>8.2f}")

print(f"\n【分析2】参数分段胜率")
for key,nm,bins in [('p','涨幅%',[(-3,0),(0,2),(2,3.5),(3.5,5),(5,6.5),(6.5,8)]),
                   ('cl','CL%',[(0,20),(20,40),(40,60),(60,80),(80,100)]),
                   ('vr','量比',[(0,0.6),(0.6,1.0),(1.0,1.5),(1.5,2.5),(2.5,5)]),
                   ('wrv','WR',[(0,25),(25,50),(50,75),(75,100)]),
                   ('jv','J值',[(0,20),(20,40),(40,60),(60,80),(80,100)]),
                   ('dif','DIF',[(-2,-0.5),(-0.5,0),(0,0.5),(0.5,2)]),
                   ('hsl','换手',[(0,3),(3,6),(6,10),(10,15),(15,30)])]:
    print(f"\n  {nm}:")
    for lo,hi in bins:
        w=sum(1 for r in champ_wins if lo<=r[key]<=hi)
        l=sum(1 for r in champ_losses if lo<=r[key]<=hi)
        t=w+l
        wr=round(w*100/t,1) if t else 0
        if t>=3:  # 只显示样本>=3的
            print(f"    {lo:>6.1f}-{hi:<6.1f}: {w}胜/{t}总={wr}% {'⚠️' if wr<60 else '✅' if wr>=70 else '➡'}")

# 最后30天（日历）的跌日详情
print(f"\n{'='*70}")
print(f"【分析3】最近30天（日历）跌日详情")
print(f"{'='*70}")
recent30_dd = [r for r in champ_wins+champ_losses if r['date']>='2026-04-20']
recent30_dd.sort(key=lambda x:x['date'])
for r in recent30_dd:
    ok="✅" if r['win'] else "❌"
    print(f"  {r['date']} | {r['nm']:10s} | 涨{r['p']:+>5.1f}% | CL{r['cl']:.0f} | VR{r['vr']:.2f} | WR{r['wrv']:.0f} | J{r['jv']:.0f} | 次日{r['nh']:+>5.1f}% {ok}")
print(f"  胜率: {sum(1 for r in recent30_dd if r['win'])}/{len(recent30_dd)}={sum(1 for r in recent30_dd if r['win'])*100/len(recent30_dd):.1f}%")
