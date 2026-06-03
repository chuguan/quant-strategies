"""虚涨日快速测试"""
import pickle, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

def cls(dt):
    st=data.get(dt,[]);
    if not st: return 'flat'
    ps=[s.get('p',0) or 0 for s in st]
    avg_p=sum(ps)/len(ps); avg_vr=sum(s.get('vol_ratio',0) or 0 for s in st)/len(st)
    hot=sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    elif avg_p<-0.5: return 'down'
    else: return 'flat'

fakes=[dt for dt in dates if cls(dt)=='fake_up']
print(f'虚涨日: {len(fakes)}天')
for dt in fakes: print(f'  {dt}', flush=True)

# 快速测试：放宽涨幅到负
def test(pm,pv,vm,vx,hm,hx,sz):
    wins=0; nd=0
    for dt in fakes:
        cand=[]
        for s in data.get(dt,[]):
            code=s['code'];p=s['p']
            if p<pm or p>pv: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<vm or vr>vx: continue
            ri=real.get(code)
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<hm or hsl>hx: continue
            sz2=(ri.get('shizhi',0) or 0)
            if sz2>=sz: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv=s.get('j_val',0) or 0
            if jv>120: continue
            cl=s.get('cl',0)
            if cl<40 or cl>95: continue
            nh=s.get('n',0) or 0
            if nh<=0: continue
            buy=s.get('close',0); dif=s.get('dif_val',0) or 0
            macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
            close=s.get('close',0)
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            # 反转信号：J<20加分，CL低加分
            j_score=(3 if jv<20 else 2 if jv>70 else 0)
            cl_score=(40-cl)*0.1 if cl<50 else 0
            score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+j_score+cl_score
            cand.append((score,nh,p,nm,cl,jv))
        if cand:
            cand.sort(key=lambda x:(-x[0],-x[2]))
            nd+=1
            if cand[0][1]>=2.5: wins+=1
    return wins, nd

# 测试几个组合
tests=[
    (-2,8,0.6,3,3,25,300),
    (-1,8,0.6,3,5,25,300),
    (0,8,0.6,3,3,20,200),
    (3,8,0.6,2.5,5,20,300),
    (5,8,0.6,2.5,5,15,300),
]
for t in tests:
    w,n=test(*t)
    print(f"涨{t[0]}~{t[1]}量{t[2]}~{t[3]}换{t[4]}~{t[5]}市值<{t[6]}: {w}/{n}({w*100/n:.0f}%)", flush=True)
