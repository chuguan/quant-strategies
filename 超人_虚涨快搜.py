"""虚涨日快速搜索"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

def classify_market(dt):
    stocks=data.get(dt,[])
    if not stocks: return 'flat'
    ps=[s.get('p',0) or 0 for s in stocks]
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    avg_p=sum(ps)/len(ps)
    avg_vr=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5:
        if hot>=15 and avg_vr>=0.9: return 'real_up'
        else: return 'fake_up'
    elif avg_p<-0.5: return 'down'
    else: return 'flat'

fakes=[dt for dt in dates if classify_market(dt)=='fake_up']
print(f"虚涨日: {len(fakes)}天", flush=True)

def run(pm,pv,vm,vx,hm,hx,sz,cm,cx,pw,cw,hb,jb,jl,mb,mw):
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
            if jv>150: continue
            cl=s.get('cl',0)
            if cl<cm or cl>cx: continue
            nh=s.get('n',0) or 0
            if nh<=0: continue
            buy=s.get('close',0); dif=s.get('dif_val',0) or 0
            macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
            close=s.get('close',0); ma5=s.get('ma5',0) or 0
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            score=p*pw+cl*cw+ps2*0.3+macd_s*mw+mb*above5+(hb*2 if 5<=hsl<=7 else 0)+(jb if jv>70 else 0)+(jl if jv<20 else 0)
            cand.append((score,nh,p,nm,code,cl,vr,hsl,jv))
        if not cand: continue
        cand.sort(key=lambda x:(-x[0], -x[2]))
        nd+=1
        if cand[0][1]>=2.5: wins+=1
    return wins, nd

best_w=0; best_p=None
# 缩小搜索
for pm,pv in [(-2,8),(-1,8),(0,8),(3,8),(5,8)]:
 for vm,vx in [(0.6,2.5),(0.6,3.0)]:
  for hm,hx in [(3,20),(5,20)]:
   for sz in [200,300]:
    for cm,cx in [(30,95),(50,95)]:
     for pw in [1.0,2.0]:
      for cw in [0.05,0.1]:
       for jb in [0,2]:
        for jl in [0,2,3]:
         for mb in [0,3]:
          for mw in [0.3]:
           w,n=run(pm,pv,vm,vx,hm,hx,sz,cm,cx,pw,cw,0,jb,jl,mb,mw)
           if w*100/n>best_w and n:
               best_w=w*100/n; best_p=(pm,pv,vm,vx,hm,hx,sz,cm,cx,pw,cw,jb,jl,mb,mw,w,n)

if best_p:
    print(f"\n最佳: {best_p[14]}/{best_p[15]}({best_w:.1f}%)", flush=True)
    print(f"选股: 涨{best_p[0]}~{best_p[1]}量{best_p[2]}~{best_p[3]}换{best_p[4]}~{best_p[5]}CL{best_p[6]}~{best_p[7]}", flush=True)
    print(f"评分: 涨×{best_p[9]}+CL×{best_p[10]}+J>70+{best_p[11]}+J<20+{best_p[12]}+MA5+{best_p[13]}", flush=True)
    
    # 每日明细
    print(f"\n每日冠军:", flush=True)
    for dt in fakes:
        pm,pv,vm,vx,hm,hx,sz,cm,cx=best_p[0:9]
        pw,cw,jb,jl,mb,mw=best_p[9:15]
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
            if jv>150: continue
            cl=s.get('cl',0)
            if cl<cm or cl>cx: continue
            nh=s.get('n',0) or 0
            if nh<=0: continue
            buy=s.get('close',0); dif=s.get('dif_val',0) or 0
            macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
            close=s.get('close',0); ma5=s.get('ma5',0) or 0
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            score=p*pw+cl*cw+ps2*0.3+macd_s*mw+mb*above5+(jb if jv>70 else 0)+(jl if jv<20 else 0)
            cand.append((score,nh,p,nm,cl,jv))
        if cand:
            cand.sort(key=lambda x:(-x[0], -x[2]))
            t='🔥' if cand[0][1]>=5 else('✅' if cand[0][1]>=2.5 else'❌')
            print(f"  {dt}: {cand[0][3][:8]:<10} 涨{cand[0][2]:+.1f}% CL{cand[0][4]:.0f} J{cand[0][5]:.0f} → {cand[0][1]:+.1f}%{t}", flush=True)
else:
    print("无结果", flush=True)
