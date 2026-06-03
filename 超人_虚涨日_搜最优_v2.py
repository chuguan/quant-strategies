"""虚涨日17天：涨幅<8%搜最优评分"""
import pickle, os, sys
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

# 找出虚涨日
fakes=[dt for dt in dates if classify_market(dt)=='fake_up']
print(f"虚涨日共{len(fakes)}天")
for dt in fakes:
    stocks=data.get(dt,[])
    ps=[s.get('p',0) or 0 for s in stocks]
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    avg_p=sum(ps)/len(ps)
    avg_vr=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    print(f"  {dt}: 平均涨{avg_p:+.2f}% 量比{avg_vr:.2f} 热门股{hot}只")

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
            
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
            j_plus=j_b if jv>70 else 0
            j_low=j_low_b if jv<20 else 0
            vr_plus=vr_b*1.5 if 1.2<=vr<=1.5 else 0
            
            score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_plus+j_low+vr_plus
            cand.append((score,nh,p,nm,code))
        if not cand: continue
        cand.sort(key=lambda x:(-x[0], -x[2]))
        nd+=1
        if cand[0][1]>=2.5: wins+=1
    return wins, nd

print(f"\n{'='*60}")
print("虚涨日：搜最优（涨幅<8%+反转信号）")
print(f"共{len(fakes)}天")
print('-'*60)

best_w=0; best_p=None; total=0
# 涨幅<8%，允许到负值
for p_min in [-3, -1, 0, 2]:
 for p_max in [4, 5, 6, 7]:
  if p_max-p_min<3: continue
  for vr_min,vr_max in [(0.6,2.5),(0.6,3.0),(0.8,2.5),(0.8,3.0)]:
   for hs_min,hs_max in [(3,20),(3,25),(5,20)]:
    for sz in [200,300,500]:
     for cm,cx in [(30,95),(40,95),(50,95)]:
      for p_w in [1.0,1.5,2.0,2.5,3.0]:
       for cl_w in [0.05,0.1,0.15]:
        for j_b in [0,2,3]:
         for j_low_b in [0,2,3,5]:
          for hsl_b in [0,0.3]:
           for ma5_b in [0,3]:
            for macd_w in [0.3,0.5,0.8]:
             for vr_b in [0,1]:
                 w,n=run_test_fake(fakes,p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz,cm,cx,150,p_w,cl_w,hsl_b,j_b,vr_b,ma5_b,macd_w,j_low_b)
                 rate=w*100/n if n else 0
                 total+=1
                 if rate>best_w:
                     best_w=rate; best_p=(p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz,cm,cx,p_w,cl_w,j_b,j_low_b,hsl_b,ma5_b,macd_w,w,n,vr_b)
                     print(f"  新优: {w}/{n}={rate:.1f}% | 涨{p_min}~{p_max}% 量{vr_min}~{vr_max} 换{hs_min}~{hs_max} CL{cm}~{cx} | 评分涨×{p_w}+CL×{cl_w}+J>70+{j_b}+J<20+{j_low_b}+换5-7+{hsl_b}+量1.2-1.5+{vr_b}+MA5+{ma5_b}+MACD×{macd_w}", flush=True)

print(f"\n{'='*60}")
print(f"搜索完成，共{total}种组合")
if best_p:
    print(f"\n** 虚涨日最优 **")
    print(f"胜率: {best_p[16]}/{best_p[17]}({best_w:.1f}%) [{len(fakes)}天]")
    print(f"选股: 涨{best_p[0]}%~{best_p[1]}% 量{best_p[2]}~{best_p[3]} 换{best_p[4]}~{best_p[5]}% 市值<{best_p[6]}e8 CL{best_p[7]}%~{best_p[8]}%")
    print(f"评分: 涨×{best_p[9]}+CL×{best_p[10]}+J>70+{best_p[11]}+J<20+{best_p[12]}+换5-7+{best_p[13]}+量1.2-1.5+{best_p[18]}+MA5+{best_p[14]}+MACD×{best_p[15]}")
    
    # 展示每日冠军
    print(f"\n虚涨日每日冠军明细:")
    p_min=best_p[0];p_max=best_p[1];vr_min=best_p[2];vr_max=best_p[3]
    hs_min=best_p[4];hs_max=best_p[5];sz=best_p[6];cm=best_p[7];cx=best_p[8]
    p_w=best_p[9];cl_w=best_p[10];j_b=best_p[11];j_low_b=best_p[12]
    hsl_b=best_p[13];ma5_b=best_p[14];macd_w=best_p[15];vr_b=best_p[18]
    
    for dt in fakes:
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
            
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
            j_plus=j_b if jv>70 else 0
            j_low=j_low_b if jv<20 else 0
            vr_plus=vr_b*1.5 if 1.2<=vr<=1.5 else 0
            
            score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_plus+j_low+vr_plus
            cand.append((score,nh,p,nm,code,cl,vr,hsl,jv,p,buy,dif,macd_g,above5))
        if cand:
            cand.sort(key=lambda x:(-x[0], -x[2]))
            tag='🔥' if cand[0][1]>=5 else('✅' if cand[0][1]>=2.5 else'❌')
            print(f"  {dt}: {cand[0][3][:8]:<10} {cand[0][4]} 涨{cand[0][2]:+.1f}% CL{cand[0][5]:.0f}% 量{cand[0][6]:.2f} J{cand[0][8]:.0f} → +{cand[0][1]:.1f}%{tag}")

    # 统计Top3胜率
    wins3=0; nd3=0
    for dt in fakes:
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
            
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
            j_plus=j_b if jv>70 else 0
            j_low=j_low_b if jv<20 else 0
            vr_plus=vr_b*1.5 if 1.2<=vr<=1.5 else 0
            
            score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_plus+j_low+vr_plus
            cand.append((score,nh,p,nm,code))
        if cand:
            cand.sort(key=lambda x:(-x[0], -x[2]))
            nd3+=1
            top3_nh=[c[1] for c in cand[:3]]
            if any(nh>=2.5 for nh in top3_nh): wins3+=1
    print(f"\nTop3任意达标: {wins3}/{nd3}={wins3*100/nd3:.1f}%")
else:
    print("无结果")
