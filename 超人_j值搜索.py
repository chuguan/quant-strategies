"""搜索J值加分最优方式"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

LEVELS = [
    {'p_min':5,'p_max':8,'vr_min':0.8,'vr_max':2.0,'hsl_min':5,'hsl_max':15,'sz_max':300,'cl_min':60,'cl_max':90,'j_max':100},
    {'p_min':4,'p_max':9,'vr_min':0.6,'vr_max':2.5,'hsl_min':3,'hsl_max':20,'sz_max':300,'cl_min':50,'cl_max':95,'j_max':120},
    {'p_min':3,'p_max':10,'vr_min':0.5,'vr_max':3.0,'hsl_min':2,'hsl_max':25,'sz_max':400,'cl_min':40,'cl_max':98,'j_max':150},
]
BONUS = [5, 3, 0]

# 不同J值加分方式
j_methods = []

# 方式1: J>70 加固定分，J<60 扣分
for j_add in [2,3,4,5]:
    for j_pen in [0,1,2,3]:
        j_methods.append((f'J>70+{j_add} J<60-{j_pen}', 
                         lambda jv, j_a=j_add, j_p=j_pen: j_a if jv>70 else (-j_p if jv<60 else 0)))

# 方式2: 比例分 (jv-60)*w
for w in [0.1, 0.15, 0.2, 0.25, 0.3]:
    j_methods.append((f'J比例×{w}',
                     lambda jv, ww=w: (jv-60)*ww if jv>60 else 0))

# 方式3: J>80大加，J>70小加
for j80 in [4,5,6]:
    for j70 in [1,2,3]:
        j_methods.append((f'J>80+{j80} J>70+{j70}',
                         lambda jv, j8=j80, j7=j70: j8 if jv>80 else (j7 if jv>70 else 0)))

print(f"{'方式':<30} {'总计':>7} {'8月':>6} {'10月':>6} {'6月':>6}", flush=True)

for name, j_fn in j_methods:
    total=0; wins=0
    m_bad={m:[0,0] for m in ['2025-06','2025-08','2025-10']}
    for dt in dates:
        stocks=data.get(dt,[])
        if not stocks: continue
        all_p=[x['p'] for x in stocks if 'p' in x]
        avg_mkt=sum(all_p)/len(all_p) if all_p else 0
        mkt='up' if avg_mkt>0.5 else ('down' if avg_mkt<-0.5 else 'flat')
        
        seen=set(); candidates=[]
        for li in range(min(len(LEVELS), 3)):
            L=LEVELS[li]
            for s in stocks:
                code=s['code']
                if code in seen: continue
                p=s['p']; vr=s.get('vol_ratio',0) or 0
                if p<L['p_min'] or p>L['p_max']: continue
                if vr<L['vr_min'] or vr>L['vr_max']: continue
                ri=real.get(code)
                if not ri: continue
                hsl=(ri.get('hsl',0) or 0)
                if hsl<L['hsl_min'] or hsl>L['hsl_max']: continue
                sz=(ri.get('shizhi',0) or 0)
                if sz>=L['sz_max']: continue
                nm=names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                jv=s.get('j_val',0) or 0
                if jv>L['j_max']: continue
                cl=s.get('cl',0)
                if cl<L['cl_min'] or cl>L['cl_max']: continue
                nh=s.get('n',0) or 0
                if nh<=0: continue
                seen.add(code)
                candidates.append((s,li))
                if len(seen)>=10: break
            if len(seen)>=10: break
        
        if len(candidates)<3: continue
        
        scored=[]
        for s,li in candidates:
            p=s['p']; cl=s.get('cl',0); vr=s.get('vol_ratio',0) or 0
            nh=s.get('n',0) or 0; dif=s.get('dif_val',0) or 0
            macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
            buy=s.get('close',0); is_yang=s.get('is_yang',0)
            close=s.get('close',0); ma5=s.get('ma5',0) or 0
            ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
            jv=s.get('j_val',0) or 0
            
            macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
            ps2=min(10,max(1,11-buy/10))
            hsl_b=2*0.3 if 5<=hsl<=7 else 0
            duotou_b=3*0.3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
            yang_vr_b=2*0.3 if is_yang and vr>1.2 else 0
            j_bonus = j_fn(jv) if mkt!='up' else 0
            
            if mkt=='up':
                score=p*3.0+cl*0.1+ps2*0.3+macd_s*0.3+3*above5+hsl_b+duotou_b+BONUS[li]
            elif mkt=='down':
                score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+BONUS[li]+j_bonus
            else:
                score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+hsl_b+yang_vr_b+BONUS[li]+j_bonus
            
            scored.append((score,nh,p))
        
        if not scored: continue
        scored.sort(key=lambda x:(-x[0], -x[2]))
        total+=1; month=dt[:7]
        if scored[0][1]>=2.5: wins+=1
        if month in m_bad:
            m_bad[month][1]+=1
            if scored[0][1]>=2.5: m_bad[month][0]+=1
    
    r=wins*100/total if total else 0
    m8=f"{m_bad['2025-08'][0]}/{m_bad['2025-08'][1]}({m_bad['2025-08'][0]*100/max(m_bad['2025-08'][1],1):.0f}%)" if m_bad['2025-08'][1] else '-'
    m10=f"{m_bad['2025-10'][0]}/{m_bad['2025-10'][1]}({m_bad['2025-10'][0]*100/max(m_bad['2025-10'][1],1):.0f}%)" if m_bad['2025-10'][1] else '-'
    m6=f"{m_bad['2025-06'][0]}/{m_bad['2025-06'][1]}({m_bad['2025-06'][0]*100/max(m_bad['2025-06'][1],1):.0f}%)" if m_bad['2025-06'][1] else '-'
    if r>=64.0:
        print(f"{name:<30} {r:>5.1f}% {m8:>6} {m10:>6} {m6:>6}", flush=True)
