"""真实涨日 - 所有策略归档全跑"""
import pickle, os, sys

os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
print("Loading...", flush=True)
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

rud=[dt for dt in dates if cm(data.get(dt,[]))=='real_up']
print(f"真实涨日{len(rud)}天", flush=True)

def md(dif,mg):
    if mg and dif>0.5: return 10
    if mg and dif>0.2: return 8
    if mg: return 6
    if dif>0.5: return 4
    if dif>0: return 2
    return 0

def run(p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,vrhs,hsbs,wrb):
    wi=0
    for dt in rud:
        ca=[]
        for s in data.get(dt,[]):
            code=s['code']; p=s.get('p',0) or 0
            if p<p1 or p>p2: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<v1 or vr>v2: continue
            ri=real.get(code); 
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<h1 or hsl>h2: continue
            if (ri.get('shizhi',0) or 0)>=sz: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl=s.get('cl',0); 
            if cl<c1 or cl>c2: continue
            nh=s.get('n',0) or 0; 
            if nh<=0: continue
            dif=s.get('dif_val',0) or 0
            mg=s.get('macd_golden',0); buy=s.get('close',0) or 0
            a5=s.get('above_ma5',0) or 0; jv=s.get('j_val',0) or 0
            wrv=s.get('wr_val',0) or 0
            ms=md(dif,mg)
            ps2=min(10,max(1,11-buy/10)) if buy else 0
            hsb=hsbs*2 if 5<=hsl<=7 else 0
            jp=2 if jv>70 else 0
            jl=2 if jv<20 else 0
            vrp=vrhs*1.5 if 1.0<=vr<=1.5 else 0
            wrp=wrb if wrv<-80 else 0
            m5p=m5 if a5 else 0
            sc=p*pw+cl*cw+ps2*0.3+ms*mw+m5p+vrp+hsb+jp+jl+wrp
            ca.append((sc,nh))
        if ca:
            ca.sort(key=lambda x:-x[0])
            if ca[0][1]>=2.5: wi+=1
    return wi

# ===== 今晚所有存档的策略 =====
tests = []

# 1. 虚涨日策略
tests.append(("虚涨日策略", 0,6,0.6,2.5,5,20,200,30,95, 1.0,0.05,0.5,0,0,0,0))

# 2. 旧版v10涨日
tests.append(("旧版v10涨日", 5,8,0.8,2.0,5,15,300,60,90, 3.0,0.1,0.3,3,0,0.3,0))

# 3. 旧版v10跌日
tests.append(("旧版v10跌日", 5,8,0.8,2.0,5,15,300,60,90, 2.0,0.05,0.3,0,0,0,0))

# 4. 窄范围v21
tests.append(("窄范围v21", 5,7,0.8,2.0,5,15,300,65,90, 1.0,0.05,0.3,0,0,0,0))

# 5. 缩量v20
tests.append(("缩量v20", 0,6,1.0,2.5,5,20,200,30,95, 1.5,0.02,0.5,2,0,0,0))

best_w=0; best_t=None
print(f"\n{'='*60}")
print("所有归档策略跑真实涨日:")
print(f"{'='*60}")
for name,p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,vrhs,hsbs,wrb in tests:
    w=run(p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,vrhs,hsbs,wrb)
    r=w*100/len(rud)
    s=f"涨{p1}~{p2}% 量{v1}~{v2} 换{h1}~{h2} CL{c1}~{c2} {sz}亿"
    sc=f"涨x{pw}+CLx{cw}+MACDx{mw}+MA5x{m5}+VRx{vrhs}+HSLx{hsbs}+WRx{wrb}"
    print(f"  {w}/{len(rud)}={r:.1f}% | {name}")
    print(f"    条件: {s}")
    print(f"    评分: {sc}")
    if w>best_w: best_w=w; best_t=(name,p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,vrhs,hsbs,wrb,w)

# 补齐: 把今晚搜索引擎发现的最优选股条件+各评分也加上
cond_list=[(3,8,0.6,2.5,3,20,300,65,95),(3,8,0.6,2.0,3,20,300,50,95),(3,7,0.6,2.5,5,15,200,60,90),
           (4,8,0.6,2.5,3,20,300,65,90),(3,7,0.6,2.5,5,20,200,65,95),(3,8,0.6,2.5,3,20,300,50,95)]

score_list=[(1.0,0.05,0.3,0,0,0,0),(1.0,0.05,0.5,0,0,0,0),(1.5,0.05,0.3,2,0,0,0),
            (2.0,0.05,0.3,2,0,0.3,0),(1.0,0.1,0.3,3,0,0,0),(2.0,0.08,0.3,3,0,0.3,0),
            (0.5,0.15,0.3,0,0,0,0),(1.0,0.05,0,0,1,0,0),(1.0,0.05,0.3,2,1,0,0),
            (2.5,0.05,0.3,3,1,0.3,2),(1.0,0.03,0.3,2,0,0,0),(3.0,0.1,0.5,3,0,0.3,0)]

print(f"\n{'='*60}")
print("补充搜索:")
print(f"{'='*60}")
for p1,p2,v1,v2,h1,h2,sz,c1,c2 in cond_list:
    for pw,cw,mw,m5,vrhs,hsbs,wrb in score_list:
        w=run(p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,vrhs,hsbs,wrb)
        if w>best_w:
            best_w=w; best_t=("搜索最优",p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,vrhs,hsbs,wrb,w)
            r=w*100/len(rud)
            nm=f"涨{p1}~{p2}% 量{v1}~{v2} 换{h1}~{h2} CL{c1}~{c2} {sz}亿"
            sc=f"涨x{pw}+CLx{cw}+MACDx{mw}+MA5x{m5}+VRx{vrhs}+HSLx{hsbs}+WRx{wrb}"
            print(f"  {w}/{len(rud)}={r:.1f}% | {nm} | {sc}", flush=True)

# 最终结果
if best_t:
    name=best_t[0]; p1=best_t[1]; p2=best_t[2]; v1=best_t[3]; v2=best_t[4]
    h1=best_t[5]; h2=best_t[6]; sz=best_t[7]; c1=best_t[8]; c2=best_t[9]
    pw=best_t[10]; cw=best_t[11]; mw=best_t[12]; m5=best_t[13]
    vrhs=best_t[14]; hsbs=best_t[15]; wrb=best_t[16]; w=best_t[17]
    print(f"\n{'='*60}")
    print(f"** 真实涨日最终最优 **")
    print(f"来源: {name}")
    print(f"选股: 涨{p1}~{p2}% 量{v1}~{v2} 换{h1}~{h2}% CL{c1}~{c2}% 市值<{sz}亿")
    print(f"评分: 涨x{pw}+CLx{cw}+MACDx{mw}+MA5x{m5}+VR1-1.5x{vrhs}+换5-7x{hsbs}+WR<-80x{wrb}")
    print(f"冠军胜率: {w}/{len(rud)}={w*100/len(rud):.1f}%")
