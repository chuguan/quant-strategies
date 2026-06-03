"""4类行情分型 V3 — 真实涨日最优 + 虚涨日策略 全量回测"""
import pickle, os, sys

os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
print("Loading...", flush=True)
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, real, names = d['data'], d['real'], d['names']
dates = [x for x in sorted(data.keys()) if '2025-01-01' <= x < '2026-06-01']
print(f"{len(dates)}天", flush=True)

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

def filt(s,p1,p2,v1,v2,h1,h2,sz,c1,c2):
    code=s['code'];p=s.get('p',0) or 0
    if p<p1 or p>p2: return None
    vr=s.get('vol_ratio',0) or 0
    if vr<v1 or vr>v2: return None
    ri=real.get(code)
    if not ri: return None
    hsl=(ri.get('hsl',0) or 0)
    if hsl<h1 or hsl>h2: return None
    if (ri.get('shizhi',0) or 0)>=sz: return None
    nm=names.get(code,'')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return None
    cl=s.get('cl',0)
    if cl<c1 or cl>c2: return None
    nh=s.get('n',0) or 0
    if nh<=0: return None
    return {'nm':nm[:12],'code':code,'p':p,'cl':cl,'vr':vr,'nh':nh,
            'buy':s.get('close',0) or 0,'dif':s.get('dif_val',0) or 0,'mg':s.get('macd_golden',0),
            'a5':s.get('above_ma5',0) or 0,'hsl':hsl,'wrv':s.get('wr_val',0) or 0}

# ===== 各策略评分 =====
def real_score(x):
    ms=md(x['dif'],x['mg']); ps2=min(10,max(1,11-x['buy']/10)) if x['buy'] else 0
    m5p=3 if x['a5'] else 0; vrp=1.5 if 1.0<=x['vr']<=1.5 else 0
    hsp=0.6 if 5<=x['hsl']<=7 else 0; wrp=2 if x['wrv']<-80 else 0
    return x['p']*2.5 + x['cl']*0.05 + ps2*0.3 + ms*0.3 + m5p + vrp + hsp + wrp

def fake_score(x):
    ms=md(x['dif'],x['mg']); ps2=min(10,max(1,11-x['buy']/10)) if x['buy'] else 0
    return x['p']*1.0 + x['cl']*0.05 + ps2*0.3 + ms*0.5

def down_score(x):
    ms=md(x['dif'],x['mg']); ps2=min(10,max(1,11-x['buy']/10)) if x['buy'] else 0
    return x['p']*2.0 + x['cl']*0.05 + ps2*0.3 + ms*0.3

def flat_score(x):
    return down_score(x)

# 参数
REAL_P = (3,7,0.6,2.5,5,15,200,60,90)
FAKE_P = (0,6,0.6,2.5,5,20,200,30,95)
MAIN_P = (5,8,0.8,2.0,5,15,300,60,90)

cwins={'real_up':0,'fake_up':0,'down':0,'flat':0}
ctot={'real_up':0,'fake_up':0,'down':0,'flat':0}
twins={'real_up':0,'fake_up':0,'down':0,'flat':0}
ttot={'real_up':0,'fake_up':0,'down':0,'flat':0}
ca=0; ta=0

for dt in dates:
    stocks=data.get(dt,[])
    if not stocks: continue
    mk=cm(stocks)
    cand=[]
    if mk=='fake_up':
        for s in stocks:
            x=filt(s,*FAKE_P)
            if not x: continue; x['score']=fake_score(x); cand.append(x)
    elif mk=='real_up':
        for s in stocks:
            x=filt(s,*REAL_P)
            if not x: continue; x['score']=real_score(x); cand.append(x)
    elif mk=='down':
        for s in stocks:
            x=filt(s,*MAIN_P)
            if not x: continue; x['score']=down_score(x); cand.append(x)
    else:
        for s in stocks:
            x=filt(s,*MAIN_P)
            if not x: continue; x['score']=flat_score(x); cand.append(x)
    if not cand: continue
    cand.sort(key=lambda x:(-x['score'],-x['p']))
    ta+=1; ctot[mk]+=1; ttot[mk]+=1
    if cand[0]['nh']>=2.5: ca+=1; cwins[mk]+=1
    if any(c['nh']>=2.5 for c in cand[:3]): twins[mk]+=1; tw=True

print(f"\n{'='*60}")
print("4行情分型 V3 — 真实涨日最优+虚涨日")
print(f"{'='*60}")
print(f"交易日: {ta}")
print(f"\n【总胜率】")
print(f"  冠军达标: {ca}/{ta}={ca*100/ta:.1f}%")
print(f"  Top3达标: {sum(twins.values())}/{ta}={sum(twins.values())*100/ta:.1f}%")
print(f"\n【分行情】")
for mk,nm in [('real_up','📈真实涨日'),('fake_up','🎭虚涨日'),('down','📉跌日'),('flat','➖横盘')]:
    if ctot[mk]:
        cr=cwins[mk]*100/ctot[mk]; tr=twins[mk]*100/ttot[mk]
        print(f"  {nm}: {ctot[mk]}天 | 冠军{cr:.1f}% | Top3{tr:.1f}%")

# 旧版对比
print(f"\n{'='*60}")
print("对比旧版(v10不分虚涨日)")
old_c=0; old_t3=0
for dt in dates:
    stocks=data.get(dt,[])
    if not stocks: continue; cand=[]
    for s in stocks:
        x=filt(s,5,8,0.8,2.0,5,15,300,60,90)
        if not x: continue
        ms=md(x['dif'],x['mg']); ps2=min(10,max(1,11-x['buy']/10)) if x['buy'] else 0
        m5p=3 if x['a5'] else 0
        x['score']=x['p']*3.0+x['cl']*0.1+ps2*0.3+ms*0.3+m5p
        cand.append(x)
    if not cand: continue
    cand.sort(key=lambda x:(-x['score'],-x['p']))
    if cand[0]['nh']>=2.5: old_c+=1
    if any(c['nh']>=2.5 for c in cand[:3]): old_t3+=1
print(f"  旧版冠军: {old_c}/{ta}={old_c*100/ta:.1f}%")
print(f"  新版冠军: {ca}/{ta}={ca*100/ta:.1f}% (diff {ca-old_c:+d})")
print(f"  旧版Top3: {old_t3}/{ta}={old_t3*100/ta:.1f}%")
print(f"  新版Top3: {sum(twins.values())}/{ta}={sum(twins.values())*100/ta:.1f}% (diff {sum(twins.values())-old_t3:+d})")
