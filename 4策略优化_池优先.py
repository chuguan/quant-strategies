"""4策略优化 - 池≥10优先"""
import pickle, os, sys

os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, real, names = d['data'], d['real'], d['names']
dates = [x for x in sorted(data.keys()) if '2025-01-01' <= x < '2026-06-01']

def cm(stocks):
    if not stocks: return 'flat'
    ps=[s.get('p',0) or 0 for s in stocks]
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    avg_p=sum(ps)/len(ps); avg_vr=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    if avg_p<-0.5: return 'down'
    return 'flat'

mkts={'real_up':[],'fake_up':[],'down':[],'flat':[]}
for dt in dates:
    stocks=data.get(dt,[]);
    if not stocks: continue
    mk=cm(stocks)
    mkts[mk].append(dt)

def md(dif,mg):
    if mg and dif>0.5: return 10
    if mg and dif>0.2: return 8
    if mg: return 6
    if dif>0.5: return 4
    if dif>0: return 2
    return 0

def test(dts, p1, p2, v1, v2, h1, h2, sz, c1, c2, pw, cw, mw, m5):
    w=0; tc=0
    for dt in dts:
        ca=[]
        for s in data.get(dt,[]):
            code=s['code']
            p=s.get('p',0) or 0
            if p<p1 or p>p2: continue
            vol=s.get('vol_ratio',0) or 0
            if vol<v1 or vol>v2: continue
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
            dif=s.get('dif_val',0) or 0
            mg=s.get('macd_golden',0)
            buy=s.get('close',0) or 0
            a5=s.get('above_ma5',0) or 0
            ms=md(dif,mg)
            ps2=min(10,max(1,11-buy/10)) if buy else 0
            m5p=m5 if a5 else 0
            sc=p*pw+cl*cw+ps2*0.3+ms*mw+m5p
            ca.append((sc,nh))
        if len(ca)<10: continue
        ca.sort(key=lambda x:-x[0])
        tc+=1
        if ca[0][1]>=2.5: w+=1
    return w, tc

def run_search(name, dts, conds, pw_r, cw_r, mw_r, m5_r, min_cov=0.85):
    bw=0; bp=None
    for p1,p2,v1,v2,h1,h2,sz,c1,c2 in conds:
        tc0=test(dts,p1,p2,v1,v2,h1,h2,sz,c1,c2,1.0,0.05,0.3,0)[1]
        if tc0<len(dts)*min_cov: continue
        for pw in pw_r:
         for cw in cw_r:
          for mw in mw_r:
           for m5 in m5_r:
            w,tc=test(dts,p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5)
            if tc==0: continue
            r=w*100/tc
            if r>max(bw,30):
                if r>bw: bw=r; bp=(p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,w,tc)
                print(f'  {w}/{tc}={r:.1f}% | 涨{p1}~{p2}% 量{v1}~{v2} 换{h1}~{h2} CL{c1}~{c2} {sz}亿 | 涨x{pw}+CLx{cw}+MACDx{mw}+MA5x{m5}', flush=True)
    return bw, bp

# 条件生成
def gen_cond(p1s,p2s,v1s,v2s,h1s,h2s,szs,c1s,c2s):
    r=[]
    for p1 in p1s:
     for p2 in p2s:
      if p2-p1<3: continue
      for v1 in v1s:
       for v2 in v2s:
        for h1 in h1s:
         for h2 in h2s:
          for sz in szs:
           for c1 in c1s:
            for c2 in c2s:
             r.append((p1,p2,v1,v2,h1,h2,sz,c1,c2))
    return r

common_scores = ([0.5,1.0,1.5,2.0], [0,0.03,0.05], [0,0.3,0.5], [0,2,3])

# 1. 横盘 - 大范围保池
print('【横盘 124天】')
c1=gen_cond([-1,0,2],[5,6,7],[0.6,0.8],[2.5,3.0],[3,5],[20,25],[200,300],[30,40,50],[90,95])
bw1,bp1=run_search("横盘", mkts['flat'], c1, *common_scores)
if bp1:
    p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,w,tc=bp1
    print(f'\n** 横盘最优: {w}/{tc}={bw1:.1f}%')
    print(f'  涨{p1}~{p2}% 量{v1}~{v2} 换{h1}~{h2} CL{c1}~{c2} {sz}亿')
    print(f'  涨x{pw}+CLx{cw}+MACDx{mw}+MA5x{m5}')

# 2. 跌日 - 大范围保池
print('\n【跌日 80天】')
bw2,bp2=run_search("跌日", mkts['down'], c1, *common_scores)
if bp2:
    p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,w,tc=bp2
    print(f'\n** 跌日最优: {w}/{tc}={bw2:.1f}%')
    print(f'  涨{p1}~{p2}% 量{v1}~{v2} 换{h1}~{h2} CL{c1}~{c2} {sz}亿')
    print(f'  涨x{pw}+CLx{cw}+MACDx{mw}+MA5x{m5}')

# 3. 真实涨日 - 轻微放宽
print('\n【真实涨日 112天】')
c3=gen_cond([2,3],[6,7],[0.6,0.8],[2.0,2.5],[3,5],[15,20],[200,300],[50,60],[90,95])
bw3,bp3=run_search("真实涨日", mkts['real_up'], c3, *common_scores)
if bp3:
    p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,w,tc=bp3
    print(f'\n** 真实涨日最优: {w}/{tc}={bw3:.1f}%')
    print(f'  涨{p1}~{p2}% 量{v1}~{v2} 换{h1}~{h2} CL{c1}~{c2} {sz}亿')
    print(f'  涨x{pw}+CLx{cw}+MACDx{mw}+MA5x{m5}')

# 4. 虚涨日 - 窄搜索，池已够
print('\n【虚涨日 17天】')
c4=gen_cond([0,2],[5,6],[0.6,0.8],[2.5,3.0],[3,5],[20,25],[200,300],[30,40,50],[90,95])
bw4,bp4=run_search("虚涨日", mkts['fake_up'], c4, *common_scores, min_cov=0.5)
if bp4:
    p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,w,tc=bp4
    print(f'\n** 虚涨日最优: {w}/{tc}={bw4:.1f}%')
    print(f'  涨{p1}~{p2}% 量{v1}~{v2} 换{h1}~{h2} CL{c1}~{c2} {sz}亿')
    print(f'  涨x{pw}+CLx{cw}+MACDx{mw}+MA5x{m5}')
