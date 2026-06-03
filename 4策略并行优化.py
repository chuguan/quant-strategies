"""4策略并行优化引擎"""
import pickle, os, sys
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if '2024-01-01'<=x<'2026-06-01']

def mb(c):
    return not (c.startswith('sz300') or c.startswith('sh688') or c.startswith('sh8'))

def cm(stocks):
    if not stocks: return 'flat'
    ps=[s.get('p',0) or 0 for s in stocks]
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0
    ht=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if ht<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

# 分好行情
mk_day={mk:[] for mk in ['real_up','fake_up','down','flat']}
for dt in dates:
    stocks=data.get(dt,[])
    if not stocks: continue
    mk=cm(stocks)
    mk_day[mk].append(dt)

for mk in ['real_up','fake_up','down','flat']:
    print(f'{mk}: {len(mk_day[mk])}天')

def md(dif,mg):
    if mg and dif>0.5: return 10
    if mg and dif>0.2: return 8
    if mg: return 6
    if dif>0.5: return 4
    if dif>0: return 2
    return 0

def run(dts,p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,vb,hb,wb,jb,jlb):
    w=0; tc=0
    for dt in dts:
        ca=[]; stocks=data.get(dt,[])
        for s in stocks:
            code=s['code']
            if not mb(code): continue
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
            dif=s.get('dif_val',0) or 0; mg=s.get('macd_golden',0)
            buy=s.get('close',0) or 0; a5=s.get('above_ma5',0) or 0
            wrv=s.get('wr_val',0) or 0; jv=s.get('j_val',0) or 0
            ms=md(dif,mg); ps2=min(10,max(1,11-buy/10)) if buy else 0
            sc=p*pw+cl*cw+ps2*0.3+ms*mw
            sc+=(m5 if a5 else 0)+(vb*1.5 if 1.0<=vr<=1.5 else 0)
            sc+=(hb*2 if 5<=hsl<=7 else 0)+(wb if wrv<-80 else 0)+(jb if jv>70 else 0)+(jlb if jv<20 else 0)
            ca.append((sc,nh))
        if len(ca)<10: continue
        ca.sort(key=lambda x:-x[0])
        tc+=1
        if ca[0][1]>=2.5: w+=1
    return w,tc

# ===== 生成条件空间 =====
def gen_cond(p1s,p2s,v1s,v2s,h1s,h2s,szs,c1s,c2s):
    r=[]
    for p1 in p1s:
     for p2 in p2s:
      if p2-p1<2: continue
      for v1 in v1s:
       for v2 in v2s:
        for h1 in h1s:
         for h2 in h2s:
          for sz in szs:
           for c1 in c1s:
            for c2 in c2s:
             r.append((p1,p2,v1,v2,h1,h2,sz,c1,c2))
    return r

score_combos=[(pw,cw,mw,m5,vb,hb,wb,jb,jlb)
 for pw in [0.5,1.0,1.5,2.0,2.5]
 for cw in [0,0.03,0.05]
 for mw in [0,0.3,0.5]
 for m5 in [0,2,3]
 for vb in [0,1]
 for hb in [0,0.3]
 for wb in [0,1,2]
 for jb in [0,2]
 for jlb in [0,2,3]
]

def search(name, dts, conds, min_cov=0.85):
    bw=0; bp=None
    for p1,p2,v1,v2,h1,h2,sz,c1,c2 in conds:
        tc0=run(dts,p1,p2,v1,v2,h1,h2,sz,c1,c2,1,0.05,0.3,0,0,0,0,0,0)[1]
        if tc0<len(dts)*min_cov: continue
        for pw,cw,mw,m5,vb,hb,wb,jb,jlb in score_combos:
            w,tc=run(dts,p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,vb,hb,wb,jb,jlb)
            if tc==0: continue
            r=w*100/tc
            if r>max(bw,50):
                if r>bw: bw=r; bp=(p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,vb,hb,wb,jb,jlb,w,tc)
                c=f'涨{p1}~{p2}% 量{v1}~{v2} 换{h1}~{h2} CL{c1}~{c2} {sz}亿'
                s=f'涨x{pw}+CLx{cw}+MACDx{mw}+MA5x{m5}+VRx{vb}+HSLx{hb}+WRx{wb}+J>70x{jb}+J<20x{jlb}'
                print(f'  [{name}] {w}/{tc}={r:.1f}% | {c} | {s}', flush=True)
    return bw,bp

ln=['L0','L1','L2','L3','L4']

# 1. 真实涨日
print(f'\n{"="*60}')
print("【📈 真实涨日】")
c1=gen_cond([2,3],[6,7],[0.6,0.8],[2.0,2.5],[3,5],[15,20],[200,300],[50,60],[90,95])
bw1,bp1=search("真实涨日", mk_day['real_up'], c1)
if bp1: print(f'** 最优: {bp1[12]}/{bp1[13]}={bw1:.1f}%')

# 2. 虚涨日
print(f'\n{"="*60}')
print("【🎭 虚涨日】")
c2=gen_cond([0,2],[5,6],[0.6,0.8],[2.5,3.0],[3,5],[20,25],[200,300],[30,40,50],[90,95])
bw2,bp2=search("虚涨日", mk_day['fake_up'], c2, 0.5)
if bp2: print(f'** 最优: {bp2[12]}/{bp2[13]}={bw2:.1f}%')

# 3. 跌日
print(f'\n{"="*60}')
print("【📉 跌日】")
c3=gen_cond([-3,-1,0],[5,6,7],[0.4,0.6],[2.5,3.5],[1,3],[25,30],[200,300],[10,20,30],[90,95,98])
bw3,bp3=search("跌日", mk_day['down'], c3)
if bp3: print(f'** 最优: {bp3[12]}/{bp3[13]}={bw3:.1f}%')

# 4. 横盘
print(f'\n{"="*60}')
print("【➖ 横盘】")
c4=gen_cond([0,1],[6,7],[0.6,0.8],[2.5,3.0],[3,5],[20,25],[200,300],[30,40,50],[90,95])
bw4,bp4=search("横盘", mk_day['flat'], c4)
if bp4: print(f'** 最优: {bp4[12]}/{bp4[13]}={bw4:.1f}%')
