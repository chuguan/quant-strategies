"""虚涨日17天完整优化"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

def cls(dt):
    st=data.get(dt,[]);
    if not st: return 'flat'
    ps=[s.get('p',0) or 0 for s in st]; avg_vr=sum(s.get('vol_ratio',0) or 0 for s in st)/len(st)
    avg_p=sum(ps)/len(ps); hot=sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    elif avg_p<-0.5: return 'down'
    else: return 'flat'

fakes=[dt for dt in dates if cls(dt)=='fake_up']
print(f"虚涨日17天，搜索最优评分...", flush=True)

# 搜最优评分（拓宽条件固定）
P_MIN,P_MAX=0,8; VR_MIN,VR_MAX=0.6,3.0; HSL_MIN,HSL_MAX=3,20; SZ_MAX=200; CL_MIN,CL_MAX=40,95; J_MAX=120

best_w=0; best_p=None
for p_w in [1.0,1.5,2.0,2.5]:
 for cl_w in [0.05,0.1,0.15]:
  for macd_w in [0.3,0.5]:
   for ma5_b in [0,3]:
    for j_b in [0,2,3,4]:   # J>70加分
     for jl in [0,2,3,4]:   # J<20加分（超卖反转）
      for cl50 in [0,1,2]:  # CL<50加分
       for hsl_b in [0,0.3]: # 换手5~7加分
        wins=0; nd=0
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
                buy=s.get('close',0); dif=s.get('dif_val',0) or 0
                macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
                close=s.get('close',0); ma5=s.get('ma5',0) or 0
                
                macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                ps2=min(10,max(1,11-buy/10))
                hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
                j_score=(jl if jv<20 else j_b if jv>70 else 0)
                cl_low=(40-cl)*cl50*0.1 if cl<50 else 0
                
                score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_score+cl_low
                cand.append((score,nh,p,nm,cl,jv,code))
            if cand:
                cand.sort(key=lambda x:(-x[0],-x[2]))
                nd+=1
                if cand[0][1]>=2.5: wins+=1
        
        rate=wins*100/nd if nd else 0
        if rate>best_w:
            best_w=rate; best_p=(p_w,cl_w,macd_w,ma5_b,j_b,jl,cl50,hsl_b,wins,nd)

if best_p:
    print(f"\n✅ 虚涨日最优评分: {best_p[8]}/{best_p[9]}({best_w:.1f}%) [17天]", flush=True)
    print(f"评分: 涨×{best_p[0]}+CL×{best_p[1]}+MACD×{best_p[2]}+MA5+{best_p[3]}+J>70+{best_p[4]}+J<20+{best_p[5]}+CL低分+{best_p[6]}+换手+{best_p[7]}", flush=True)
    
    # 每日明细
    print(f"\n每天冠军:", flush=True)
    for dt in fakes:
        p_w=best_p[0];cl_w=best_p[1];macd_w=best_p[2];ma5_b=best_p[3]
        j_b=best_p[4];jl=best_p[5];cl50=best_p[6];hsl_b=best_p[7]
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
            buy=s.get('close',0); dif=s.get('dif_val',0) or 0
            macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
            close=s.get('close',0); ma5=s.get('ma5',0) or 0
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
            j_score=(jl if jv<20 else j_b if jv>70 else 0)
            cl_low=(40-cl)*cl50*0.1 if cl<50 else 0
            score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_score+cl_low
            cand.append((score,nh,p,nm,cl,jv,code))
        if cand:
            cand.sort(key=lambda x:(-x[0],-x[2]))
            t='🔥' if cand[0][1]>=5 else('✅' if cand[0][1]>=2.5 else'❌')
            j_str=f"J{cand[0][5]:.0f}" if cand[0][5]<20 or cand[0][5]>70 else ''
            print(f"  {dt}: {cand[0][3][:8]:<10} 涨{cand[0][2]:+.1f}% CL{cand[0][4]:.0f} {j_str} → {cand[0][1]:+.1f}%{t}", flush=True)
