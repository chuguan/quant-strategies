"""虚涨日：放宽涨幅到负数，用反转信号找好货"""
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
    
    if avg_p > 0.5:
        if hot >= 15 and avg_vr >= 0.9: return 'real_up'
        else: return 'fake_up'
    elif avg_p < -0.5: return 'down'
    else: return 'flat'

# 统计虚涨日特征
fakes=[dt for dt in dates if classify_market(dt)=='fake_up']
print(f"虚涨日共{len(fakes)}天", flush=True)

# ===== 虚涨日：放宽涨幅限制，搜索最优 =====
def run_test_fake(mkts, p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz,cm,cx,jm,p_w,cl_w,hsl_b,j_b,vr_b,ma5_b,macd_w,j_low_b):
    wins=0; nd=0
    for dt in mkts:
        cand=[]
        for s in data.get(dt,[]):
            code=s['code'];p=s['p']
            if p<p_min or p>p_max: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<vr_min or vr>vr_max: continue
            ri=real.get(code)
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<hs_min or hsl>hs_max: continue
            sz2=(ri.get('shizhi',0) or 0)
            if sz2>=sz: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv=s.get('j_val',0) or 0
            if jv>jm: continue
            cl=s.get('cl',0)
            if cl<cm or cl>cx: continue
            nh=s.get('n',0) or 0
            if nh<=0: continue
            buy=s.get('close',0); dif=s.get('dif_val',0) or 0
            macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
            is_yang=s.get('is_yang',0); close=s.get('close',0)
            ma5=s.get('ma5',0) or 0
            
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
            j_plus=j_b if jv>70 else 0
            j_low=j_low_b if jv<20 else 0  # J值超卖加分（反转信号）
            vr_plus=vr_b*1.5 if 1.2<=vr<=1.5 else 0
            
            score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_plus+j_low+vr_plus
            cand.append((score,nh,p,nm,code))
        if not cand: continue
        cand.sort(key=lambda x:(-x[0], -x[2]))
        nd+=1
        if cand[0][1]>=2.5: wins+=1
    return wins, nd

print(f"\n{'='*60}", flush=True)
print("虚涨日：搜最优（涨幅可到负数）", flush=True)
print('-'*60, flush=True)

best_w=0; best_p=None
# 搜索范围扩大：涨幅可以到负
for p_min in [-3, -1, 0, 2, 4, 5]:
 for p_max in [5, 8, 10, 12]:
  if p_max-p_min<3: continue
  for vr_min,vr_max in [(0.6,2.5),(0.6,3.0),(0.8,3.0)]:
   for hs_min,hs_max in [(3,20),(3,25),(5,20)]:
    for sz in [200,300,500]:
     for cm,cx in [(30,95),(40,95),(50,95),(20,90)]:
      for p_w in [1.0,1.5,2.0,2.5]:
       for cl_w in [0.05,0.1,0.15]:
        for j_b in [0,2,3]:
         for j_low_b in [0,2,3]:  # J<20加分（超卖反转）
          for hsl_b in [0,0.3]:
           for ma5_b in [0,3]:
            for macd_w in [0.3,0.5]:
                w,n=run_test_fake(fakes,p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz,cm,cx,150,p_w,cl_w,hsl_b,j_b,vr_b:=0,ma5_b,macd_w,j_low_b)
                rate=w*100/n if n else 0
                if rate>best_w:
                    best_w=rate; best_p=(p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz,cm,cx,p_w,cl_w,j_b,j_low_b,hsl_b,ma5_b,macd_w,w,n)

if best_p:
    print(f"\n** 虚涨日最优 **", flush=True)
    print(f"胜率: {best_p[16]}/{best_p[17]}({best_w:.1f}%) [{len(fakes)}天]", flush=True)
    print(f"选股: 涨{best_p[0]}%~{best_p[1]}% 量{best_p[2]}~{best_p[3]} 换{best_p[4]}~{best_p[5]}% 市值<{best_p[6]} CL{best_p[7]}%~{best_p[8]}%", flush=True)
    print(f"评分: 涨×{best_p[9]}+CL×{best_p[10]}+J>70+{best_p[11]}+J<20+{best_p[12]}+换手+{best_p[13]}+MA5+{best_p[14]}+MACD×{best_p[15]}", flush=True)
    
    # 展示哪些票被选中
    print(f"\n虚涨日每日冠军明细:", flush=True)
    for dt in fakes:
        p_min=best_p[0];p_max=best_p[1];vr_min=best_p[2];vr_max=best_p[3]
        hs_min=best_p[4];hs_max=best_p[5];sz=best_p[6];cm=best_p[7];cx=best_p[8]
        p_w=best_p[9];cl_w=best_p[10];j_b=best_p[11];j_low_b=best_p[12]
        hsl_b=best_p[13];ma5_b=best_p[14];macd_w=best_p[15]
        
        cand=[]
        for s in data.get(dt,[]):
            code=s['code'];p=s['p']
            if p<p_min or p>p_max: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<vr_min or vr>vr_max: continue
            ri=real.get(code)
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<hs_min or hsl>hs_max: continue
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
            is_yang=s.get('is_yang',0); close=s.get('close',0)
            ma5=s.get('ma5',0) or 0
            
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
            j_plus=j_b if jv>70 else 0
            j_low=j_low_b if jv<20 else 0
            
            score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_plus+j_low
            cand.append((score,nh,p,nm,code,cl,vr,hsl,jv))
        
        if cand:
            cand.sort(key=lambda x:(-x[0], -x[2]))
            tag='🔥' if cand[0][1]>=5 else('✅' if cand[0][1]>=2.5 else'❌')
            j_str=f"J{cand[0][8]:.0f}" if cand[0][8]<20 or cand[0][8]>70 else ''
            print(f"  {dt}: {cand[0][3][:8]:<10} 涨{cand[0][2]:+.1f}% CL{cand[0][5]:.0f}% J{cand[0][8]:.0f} → +{cand[0][1]:.1f}%{tag}", flush=True)
