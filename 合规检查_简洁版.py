"""检查4策略 — 每天出票数≥10 + 涨幅<8%"""
import pickle, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if '2025-01-01'<=x<'2026-06-01']

def is_main(code):
    return not (code.startswith('sz300') or code.startswith('sh688') or code.startswith('sh8'))

def cm(stocks):
    if not stocks: return 'flat'
    ps=[s.get('p',0) or 0 for s in stocks]
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    avg_p=sum(ps)/len(ps); avg_vr=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    if avg_p<-0.5: return 'down'
    return 'flat'

def md(dif,mg):
    if mg and dif>0.5: return 10
    if mg and dif>0.2: return 8
    if mg: return 6
    if dif>0.5: return 4
    if dif>0: return 2
    return 0

# 4策略参数（L0最严格级）
LV0={
'real_up':[3,7,0.6,2.5,5,15,200,60,90],
'fake_up':[0,6,0.6,2.5,5,20,200,30,95],
'down':[-3,7,0.4,3.5,1,30,300,10,98],
'flat':[0,7,0.6,2.5,3,20,200,40,95],
}
W={
'real_up':{'pw':2.5,'cw':0.05,'mw':0.3,'m5':3,'vb':1,'hb':0.3,'wb':2,'jb':2,'jlb':2},
'fake_up':{'pw':1.0,'cw':0.05,'mw':0.5,'m5':0,'vb':0,'hb':0,'wb':0,'jb':0,'jlb':0},
'down':{'pw':1.5,'cw':0.05,'mw':0.3,'m5':2,'vb':0,'hb':0,'wb':0,'jb':0,'jlb':3},
'flat':{'pw':1.5,'cw':0.05,'mw':0.3,'m5':2,'vb':1,'hb':0.3,'wb':0,'jb':0,'jlb':2},
}

mn={'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
mk_order=['real_up','fake_up','down','flat']

for mk in mk_order:
    lv=LV0[mk]
    p1,p2,v1,v2,h1,h2,sz,c1,c2=lv
    w=W[mk]
    
    nd=0; min_pool=999; max_p=-999
    pool_problems=0; price_problems=0
    pool_over_10=0
    
    for dt in dates:
        stocks=data.get(dt,[])
        if not stocks or cm(stocks)!=mk: continue
        
        # 用L0筛选
        ca=[]
        for s in stocks:
            code=s['code']
            if not is_main(code): continue
            p=s.get('p',0) or 0
            if p<p1 or p>p2: continue
            if p>=8: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<v1 or vr>v2: continue
            ri=real.get(code)
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<h1 or hsl>h2: continue
            if (ri.get('shizhi',0) or 0)>=sz: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl=s.get('cl',0)
            if cl<c1 or cl>c2: continue
            nh=s.get('n',0) or 0
            if nh<=0: continue
            ca.append(p)
        
        if len(ca)<10:
            pool_problems+=1
            continue
        
        pool_over_10+=1
        nd+=1
        min_pool=min(min_pool,len(ca))
        max_p=max(max_p,max(ca))
    
    print(f"\n{'='*55}")
    print(f" {mn[mk]} ({nd}天可用, 缺池{pool_problems}天)")
    print(f"{'='*55}")
    print(f" 选股条件: 涨{p1}~{p2}% 量{v1}~{v2} 换{h1}~{h2}% CL{c1}~{c2}% 市值<{sz}亿")
    print(f" 候选池:   最小{min_pool}只  平均{sumpool/nd:.0f}只" if nd>0 else "候选池:   无数据")
    print(f" 最大涨幅:  {max_p:+.1f}% {'✅ <8%' if max_p<8 else '❌ ≥8%!'}")
    print(f" 池≥10:     {pool_over_10}/{nd}天 ✅" if nd>0 else " 池≥10:     无数据")
    min_pool = min_pool if nd>0 else 0

print(f"\n\n{'='*55}")
print(" 汇总")
print(f"{'='*55}")
print(f" {'策略':<12} {'天数':>5} {'最小池':>6} {'最大涨':>7} {'池≥10':>6} {'合规':>5}")
for mk in mk_order:
    lv=LV0[mk]
    p1,p2,v1,v2,h1,h2,sz,c1,c2=lv
    w=W[mk]
    nd=0; mp=999; mx=-999; p10=0; pp=0
    sumpool=0
    for dt in dates:
        stocks=data.get(dt,[])
        if not stocks or cm(stocks)!=mk: continue
        ca=[]
        for s in stocks:
            code=s['code']
            if not is_main(code): continue
            p=s.get('p',0) or 0
            if p<p1 or p>p2: continue
            if p>=8: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<v1 or vr>v2: continue
            ri=real.get(code)
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<h1 or hsl>h2: continue
            if (ri.get('shizhi',0) or 0)>=sz: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl=s.get('cl',0)
            if cl<c1 or cl>c2: continue
            nh=s.get('n',0) or 0
            if nh<=0: continue
            ca.append(p)
        if len(ca)>=10:
            p10+=1; nd+=1; mp=min(mp,len(ca)); mx=max(mx,max(ca)); sumpool+=len(ca)
        else: pp+=1
    ok='✅' if mx<8 and pp==0 else '⚠️'
    print(f" {mn[mk]:<12}{nd+pp:>5}d {mp if nd else '-':>6} {mx:+.1f}%{mx<8:>6} {p10:>4}/{nd+pp} {ok:>5}")
