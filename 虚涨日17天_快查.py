"""先查出17天虚涨日列表"""
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

fakes=[dt for dt in dates if classify_market(dt)=='fake_up']
print(f"虚涨日共{len(fakes)}天")
print()

# 每个虚涨日：有多少候选符合"涨<8%"的股票？
for dt in fakes:
    stocks=data.get(dt,[])
    ps=[s.get('p',0) or 0 for s in stocks]
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    avg_p=sum(ps)/len(ps)
    avg_vr=sum(vrs)/len(vrs) if vrs else 0
    
    # 各种涨幅区间有多少票
    cnt_neg=sum(1 for p in ps if p<0)
    cnt_0_3=sum(1 for p in ps if 0<=p<3)
    cnt_3_5=sum(1 for p in ps if 3<=p<5)
    cnt_5_8=sum(1 for p in ps if 5<=p<8)
    cnt_8p=sum(1 for p in ps if p>=8)
    
    # 超卖股（J<20）数量
    j20=sum(1 for s in stocks if (s.get('j_val',0) or 0)<20)
    
    print(f"{dt}: 均{avg_p:+.2f}% 量{avg_vr:.2f} | 涨负{cnt_neg} 0~3:{cnt_0_3} 3~5:{cnt_3_5} 5~8:{cnt_5_8} ≥8:{cnt_8p} | J<20:{j20}")

# 再搜最优：分两步
# Step 1: 先搜选股条件（不涉及评分权重）
from itertools import product

print(f"\n{'='*60}")
print("Step1: 搜最优选股条件（含涨幅<8%）")
print('-'*60)

best_w=0; best_cond=None
# 条件搜索（用简单评分=涨幅排序）
for p_min,p_max in [(0,4),(0,5),(0,6),(0,7),(-1,5),(-1,6),(-1,7),(2,7)]:
 for vr_min,vr_max in [(0.6,2.5),(0.6,3.0),(0.8,2.5),(0.8,3.0)]:
  for hs_min,hs_max in [(3,20),(3,25),(5,20),(5,15)]:
   for sz in [200,300,500]:
    for cm,cx in [(30,95),(40,95),(50,95)]:
        wins=0; nd=0
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
                cl=s.get('cl',0)
                if cl<cm or cl>cx: continue
                nh=s.get('n',0) or 0
                if nh<=0: continue
                cand.append((p,nh,code))
            if cand:
                cand.sort(key=lambda x:(-x[0]))
                nd+=1
                if cand[0][1]>=2.5: wins+=1
        rate=wins*100/nd if nd else 0
        if rate>best_w:
            best_w=rate; best_cond=(p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz,cm,cx,wins,nd)
            print(f"  新优: {wins}/{nd}={rate:.1f}% | 涨{p_min}~{p_max}% 量{vr_min}~{vr_max} 换{hs_min}~{hs_max}% 市值<{sz}亿 CL{cm}~{cx}%", flush=True)

if best_cond:
    print(f"\n** 最优选股条件 **")
    p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz,cm,cx,wins,nd=best_cond
    print(f"胜率: {wins}/{nd}={best_w:.1f}% [{len(fakes)}天]")
    print(f"选股: 涨{p_min}%~{p_max}% 量{vr_min}~{vr_max} 换{hs_min}~{hs_max}% 市值<{sz}亿 CL{cm}%~{cx}%")
    
    # Step 2: 固定选股条件，搜评分权重
    print(f"\n{'='*60}")
    print("Step2: 固定条件→搜评分权重")
    print('-'*60)
    
    best_w2=0; best_score=None
    for p_w in [1.0,1.5,2.0,2.5,3.0]:
     for cl_w in [0.05,0.1,0.15]:
      for j_b in [0,2,3,5]:
       for j_low_b in [0,2,3,5]:
        for hsl_b in [0,0.3,0.5]:
         for ma5_b in [0,3]:
          for macd_w in [0.3,0.5,0.8]:
           for vr_b in [0,1]:
            for wr_b in [0,2]:
                wins=0; nd=0
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
                        cl=s.get('cl',0)
                        if cl<cm or cl>cx: continue
                        nh=s.get('n',0) or 0
                        if nh<=0: continue
                        jv=s.get('j_val',0) or 0
                        dif=s.get('dif_val',0) or 0
                        macd_g=s.get('macd_golden',0)
                        above5=s.get('above_ma5',0)
                        
                        macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                        ps2=min(10,max(1,11-s.get('close',0)/10))
                        hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
                        j_plus=j_b if jv>70 else 0
                        j_low=j_low_b if jv<20 else 0
                        vr_plus=vr_b*1.5 if 1.2<=vr<=1.5 else 0
                        wr=s.get('wr_val',0) or 0
                        wr_plus=wr_b if wr<-80 else 0
                        
                        score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_plus+j_low+vr_plus+wr_plus
                        cand.append((score,nh,p,nm,code))
                    if cand:
                        cand.sort(key=lambda x:(-x[0], -x[2]))
                        nd+=1
                        if cand[0][1]>=2.5: wins+=1
                rate=wins*100/nd if nd else 0
                if rate>best_w2:
                    best_w2=rate; best_score=(p_w,cl_w,j_b,j_low_b,hsl_b,ma5_b,macd_w,vr_b,wr_b,wins,nd)
                    print(f"  新优: {wins}/{nd}={rate:.1f}% | 涨×{p_w}+CL×{cl_w}+J>70+{j_b}+J<20+{j_low_b}+换5-7+{hsl_b}+量1.2-1.5+{vr_b}+WR<-80+{wr_b}+MA5+{ma5_b}+MACD×{macd_w}", flush=True)
    
    if best_score:
        p_w,cl_w,j_b,j_low_b,hsl_b,ma5_b,macd_w,vr_b,wr_b,wins,nd=best_score
        print(f"\n** 虚涨日最优 **")
        print(f"胜率: {wins}/{nd}={best_w2:.1f}% [{len(fakes)}天]")
        print(f"选股: 涨{p_min}%~{p_max}% 量{vr_min}~{vr_max} 换{hs_min}~{hs_max}% 市值<{sz}亿 CL{cm}%~{cx}%")
        print(f"评分: 涨×{p_w}+CL×{cl_w}+J>70+{j_b}+J<20+{j_low_b}+换5-7+{hsl_b}+量1.2-1.5+{vr_b}+WR<-80+{wr_b}+MA5+{ma5_b}+MACD×{macd_w}")
        
        # 每日明细
        print(f"\n每日冠军:")
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
                cl=s.get('cl',0)
                if cl<cm or cl>cx: continue
                nh=s.get('n',0) or 0
                if nh<=0: continue
                jv=s.get('j_val',0) or 0
                dif=s.get('dif_val',0) or 0
                macd_g=s.get('macd_golden',0)
                above5=s.get('above_ma5',0)
                wr=s.get('wr_val',0) or 0
                
                macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                ps2=min(10,max(1,11-s.get('close',0)/10))
                hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
                j_plus=j_b if jv>70 else 0
                j_low=j_low_b if jv<20 else 0
                vr_plus=vr_b*1.5 if 1.2<=vr<=1.5 else 0
                wr_plus=wr_b if wr<-80 else 0
                
                score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_plus+j_low+vr_plus+wr_plus
                cand.append((score,nh,p,nm,code,cl,vr,hsl,jv,wr))
            if cand:
                cand.sort(key=lambda x:(-x[0], -x[2]))
                tag='🔥' if cand[0][1]>=5 else('✅' if cand[0][1]>=2.5 else'❌')
                wr_s=f"WR{cand[0][9]:.0f}" if cand[0][9] and cand[0][9]<-80 else ''
                print(f"  {dt}: {cand[0][3][:8]:<10} {cand[0][4]} 涨{cand[0][2]:+.1f}% CL{cand[0][5]:.0f}% J{cand[0][8]:.0f}{wr_s} → +{cand[0][1]:.1f}%{tag}")
        
        # Top3统计
        wins3=0
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
                cl=s.get('cl',0)
                if cl<cm or cl>cx: continue
                nh=s.get('n',0) or 0
                if nh<=0: continue
                jv=s.get('j_val',0) or 0
                dif=s.get('dif_val',0) or 0
                macd_g=s.get('macd_golden',0)
                above5=s.get('above_ma5',0)
                wr=s.get('wr_val',0) or 0
                
                macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
                ps2=min(10,max(1,11-s.get('close',0)/10))
                hsl_plus=hsl_b*2 if 5<=hsl<=7 else 0
                j_plus=j_b if jv>70 else 0
                j_low=j_low_b if jv<20 else 0
                vr_plus=vr_b*1.5 if 1.2<=vr<=1.5 else 0
                wr_plus=wr_b if wr<-80 else 0
                
                score=p*p_w+cl*cl_w+ps2*0.3+macd_s*macd_w+ma5_b*above5+hsl_plus+j_plus+j_low+vr_plus+wr_plus
                cand.append((score,nh,p,nm,code))
            if cand:
                cand.sort(key=lambda x:(-x[0], -x[2]))
                top3_nh=[c[1] for c in cand[:3]]
                if any(nh>=2.5 for nh in top3_nh): wins3+=1
        print(f"\nTop3任意达标: {wins3}/{len(fakes)}={wins3*100/len(fakes):.1f}%")
