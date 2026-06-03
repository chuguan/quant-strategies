"""虚涨日·快搜"""
import pickle, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

def cls(dt):
    st=data.get(dt,[]);ps=[s.get('p',0) or 0 for s in st]
    avg_vr=sum(s.get('vol_ratio',0) or 0 for s in st)/len(st)
    if sum(ps)/len(ps)>0.5: return 'fake_up' if sum(1 for p in ps if 5<=p<=8)<15 or avg_vr<0.9 else 'real_up'
    elif sum(ps)/len(ps)<-0.5: return 'down'
    else: return 'flat'
fakes=[dt for dt in dates if cls(dt)=='fake_up']
print(f"虚涨日{len(fakes)}天",flush=True)

# 固定选股
P_MIN,P_MAX=0,8;VR_MIN,VR_MAX=0.6,3.0;HSL_MIN,HSL_MAX=3,20;SZ_MAX=200;CL_MIN,CL_MAX=40,95;J_MAX=120

# 只搜评分参数
best_w=0;bp=None
for pw,clw in [(1.0,0.05),(1.5,0.1),(2.0,0.1),(2.0,0.05),(2.5,0.1)]:
 for mw in [0.3,0.5]:
  for mb in [0,3]:
   for jh in [0,2,3]:  # J>70
    for jl in [0,2,3]:  # J<20
     for cl50 in [0,1]:  # CL<50
      for hb in [0,0.3]:
       wins=0;nd=0
       for dt in fakes:
        cand=[]
        for s in data.get(dt,[]):
            code=s['code'];p=s['p']
            if p<P_MIN or p>P_MAX: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<VR_MIN or vr>VR_MAX: continue
            ri=real.get(code)
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<HSL_MIN or hsl>HSL_MAX: continue
            sz2=(ri.get('shizhi',0) or 0)
            if sz2>=SZ_MAX: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv=s.get('j_val',0) or 0
            if jv>J_MAX: continue
            cl=s.get('cl',0)
            if cl<CL_MIN or cl>CL_MAX: continue
            nh=s.get('n',0) or 0
            if nh<=0: continue
            buy=s.get('close',0);dif=s.get('dif_val',0) or 0
            macd_g=s.get('macd_golden',0);above5=s.get('above_ma5',0)
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            hsl_plus=hb*2 if 5<=hsl<=7 else 0
            j_score=(jl if jv<20 else jh if jv>70 else 0)
            cl_low=cl50*(40-cl)*0.1 if cl<50 else 0
            score=p*pw+cl*clw+ps2*0.3+macd_s*mw+mb*above5+hsl_plus+j_score+cl_low
            cand.append((score,nh,p,nm,cl,jv))
        if cand:
            cand.sort(key=lambda x:(-x[0],-x[2]));nd+=1
            if cand[0][1]>=2.5: wins+=1
       rate=wins*100/nd
       if rate>best_w: best_w=rate;bp=(pw,clw,mw,mb,jh,jl,cl50,hb,wins,nd)

if bp:
    print(f"\n✅ {bp[8]}/{bp[9]}({best_w:.0f}%)",flush=True)
    print(f"评分:涨×{bp[0]}+CL×{bp[1]}+MACD×{bp[2]}+MA5+{bp[3]}+J>70+{bp[4]}+J<20+{bp[5]}+CL低+{bp[6]}+换手+{bp[7]}",flush=True)
    print(f"\n每日:",flush=True)
    pw,clw,mw,mb,jh,jl,cl50,hb=bp[:8]
    for dt in fakes:
        cand=[]
        for s in data.get(dt,[]):
            code=s['code'];p=s['p']
            if p<P_MIN or p>P_MAX: continue;vr=s.get('vol_ratio',0) or 0
            if vr<VR_MIN or vr>VR_MAX: continue;ri=real.get(code)
            if not ri: continue;hsl=(ri.get('hsl',0) or 0)
            if hsl<HSL_MIN or hsl>HSL_MAX: continue;sz2=(ri.get('shizhi',0) or 0)
            if sz2>=SZ_MAX: continue;nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv=s.get('j_val',0) or 0;if jv>J_MAX: continue
            cl=s.get('cl',0);if cl<CL_MIN or cl>CL_MAX: continue
            nh=s.get('n',0) or 0;if nh<=0: continue
            buy=s.get('close',0);dif=s.get('dif_val',0) or 0;macd_g=s.get('macd_golden',0)
            above5=s.get('above_ma5',0)
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            j_score=(jl if jv<20 else jh if jv>70 else 0)
            cl_low=cl50*(40-cl)*0.1 if cl<50 else 0
            hsl_plus=hb*2 if 5<=hsl<=7 else 0
            score=p*pw+cl*clw+ps2*0.3+macd_s*mw+mb*above5+hsl_plus+j_score+cl_low
            cand.append((score,nh,p,nm,cl,jv,code))
        if cand:
            cand.sort(key=lambda x:(-x[0],-x[2]))
            t='🔥' if cand[0][1]>=5 else('✅' if cand[0][1]>=2.5 else'❌')
            print(f"  {dt}: {cand[0][3][:8]:<10} 涨{cand[0][2]:+.1f}% CL{cand[0][4]:.0f} J{cand[0][5]:.0f} → {cand[0][1]:+.1f}%{t}",flush=True)
