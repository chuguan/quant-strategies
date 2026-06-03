""""横盘优化"""
import pickle, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if '2024-01-01'<=x<'2026-06-01']
def mb(c): return not (c.startswith('sz300') or c.startswith('sh688') or c.startswith('sh8'))
def cm(s):
    if not s: return 'flat'
    ps=[x.get('p',0) or 0 for x in s]
    vrs=[x.get('vol_ratio',0) or 0 for x in s if x.get('vol_ratio',0)]
    ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0; ht=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if ht<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'
fd=[]
for dt in dates:
    stocks=data.get(dt,[])
    if not stocks: continue
    if cm(stocks)=='flat': fd.append(dt)
print(f'横盘{len(fd)}天', flush=True)

def md(d,m):
    if m and d>0.5: return 10
    if m and d>0.2: return 8
    if m: return 6
    if d>0.5: return 4
    if d>0: return 2
    return 0

bw=0; bp=None
for p1 in [0,1]:
 for p2 in [6,7]:
  for v1 in [0.6,0.8]:
   for v2 in [2.5,3.0]:
    for h1 in [3,5]:
     for h2 in [20,25]:
      for sz in [200,300]:
       for c1 in [30,40,50]:
        for c2 in [90,95]:
         tc0=0
         for dt in fd:
             ca=[]
             for s in data.get(dt,[]):
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
                 ca.append(1)
             if len(ca)>=10: tc0+=1
         if tc0<len(fd)*0.85: continue
         for pw in [0.5,1.0,1.5,2.0]:
          for mw in [0,0.3,0.5]:
           for m5 in [0,2,3]:
            for vb in [0,1]:
             for wb in [0,1,2]:
              for jlb in [0,2,3]:
               w=0; tc=0
               for dt in fd:
                   ca=[]
                   for s in data.get(dt,[]):
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
                       sc=p*pw+cl*0.05+ps2*0.3+ms*mw
                       sc+=(m5 if a5 else 0)+(vb*1.5 if 1.0<=vr<=1.5 else 0)+(wb if wrv<-80 else 0)+(jlb if jv<20 else 0)
                       ca.append((sc,nh))
                   if len(ca)<10: continue
                   ca.sort(key=lambda x:-x[0]); tc+=1
                   if ca[0][1]>=2.5: w+=1
               if tc==0: continue
               r=w*100/tc
               if r>max(bw,55):
                   if r>bw: bw=r; bp=(p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,mw,m5,vb,wb,jlb,w,tc)
                   print(f'{w}/{tc}={r:.1f}% | 涨{p1}~{p2} 量{v1}~{v2} 换{h1}~{h2} CL{c1}~{c2} {sz}亿 | 涨x{pw}+CLx0.05+MACDx{mw}+MA5x{m5}+VRx{vb}+WRx{wb}+J<20x{jlb}', flush=True)
if bp:
    p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,mw,m5,vb,wb,jlb,w,tc=bp
    print(f'')
    print(f'** 横盘最优: {w}/{tc}={bw:.1f}%')
    print(f'涨{p1}~{p2}% 量{v1}~{v2} 换{h1}~{h2}% CL{c1}~{c2}% {sz}亿')
    print(f'涨x{pw}+CLx0.05+MACDx{mw}+MA5x{m5}+VRx{vb}+WRx{wb}+J<20x{jlb}')
