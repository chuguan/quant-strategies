"""v11全量回测（修正版：用缓存n字段，不依赖K线JSON）"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-02-01']

LEVELS = [
    {'n':'L0','p_min':5,'p_max':8,'vr_min':0.8,'vr_max':2.0,'hsl_min':5,'hsl_max':15,'sz_max':300,'cl_min':60,'cl_max':90,'j_max':100},
    {'n':'L1','p_min':4,'p_max':9,'vr_min':0.6,'vr_max':2.5,'hsl_min':3,'hsl_max':20,'sz_max':300,'cl_min':50,'cl_max':95,'j_max':120},
    {'n':'L2','p_min':3,'p_max':10,'vr_min':0.5,'vr_max':3.0,'hsl_min':2,'hsl_max':25,'sz_max':400,'cl_min':40,'cl_max':98,'j_max':150},
    {'n':'L3','p_min':2,'p_max':11,'vr_min':0.4,'vr_max':3.5,'hsl_min':1,'hsl_max':30,'sz_max':500,'cl_min':30,'cl_max':99,'j_max':200},
    {'n':'L4','p_min':1,'p_max':12,'vr_min':0.3,'vr_max':4.0,'hsl_min':0.5,'hsl_max':35,'sz_max':1000,'cl_min':20,'cl_max':100,'j_max':300},
]

def get_raw(date):
    """返回该天所有候选（去重，标记级别）——仅用缓存数据"""
    L0=LEVELS[0]
    stocks=data.get(date,[])
    # 先筛L0
    cand_l0=[]
    for s in stocks:
        code=s['code']; p=s['p']; vr=s.get('vol_ratio',0) or 0
        if p<L0['p_min'] or p>L0['p_max']: continue
        if vr<L0['vr_min'] or vr>L0['vr_max']: continue
        ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<L0['hsl_min'] or hsl>L0['hsl_max']: continue
        sz=(ri.get('shizhi',0) or 0)
        if sz>=L0['sz_max']: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>L0['j_max']: continue
        cl=s.get('cl',0)
        if cl<L0['cl_min'] or cl>L0['cl_max']: continue
        cand_l0.append(s)
    return cand_l0

# ===== 只用缓存数据跑回测 =====
total=0; wins=0; by_month={}

for dt in dates:
    stocks=data.get(dt,[])
    if not stocks: continue
    
    # 大盘方向
    all_p=[x['p'] for x in stocks if 'p' in x]
    avg_mkt=sum(all_p)/len(all_p) if all_p else 0
    if avg_mkt>0.5: mkt='up'
    elif avg_mkt<-0.5: mkt='down'
    else: mkt='flat'
    
    # 候选池（L0只有，不自动放宽）
    cand_l0=[]
    for s in stocks:
        code=s['code']; p=s['p']; vr=s.get('vol_ratio',0) or 0
        if p<5 or p>8: continue
        if vr<0.8 or vr>2.0: continue
        ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<5 or hsl>15: continue
        sz=(ri.get('shizhi',0) or 0)
        if sz>=300: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>100: continue
        cl=s.get('cl',0)
        if cl<60 or cl>90: continue
        cand_l0.append(s)
    
    if not cand_l0: continue
    
    # 评分
    cand=[]
    for s in cand_l0:
        code=s['code']; p=s['p']; cl=s.get('cl',0)
        vr=s.get('vol_ratio',0) or 0; nh=s.get('n',0) or 0
        if nh<=0: continue  # 有次日数据才参与
        dif=s.get('dif_val',0) or 0; macd_g=s.get('macd_golden',0)
        above5=s.get('above_ma5',0); buy=s.get('close',0)
        is_yang=s.get('is_yang',0); close=s.get('close',0)
        ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
        
        macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
        ps2=min(10,max(1,11-buy/10))
        hsl_b=2*0.3 if 5<=hsl<=7 else 0
        duotou_b=3*0.3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
        yang_vr_b=2*0.3 if is_yang and vr>1.2 else 0
        
        if mkt=='up':
            score=p*3.0+cl*0.1+ps2*0.3+macd_s*0.3+3*above5+hsl_b+duotou_b
        elif mkt=='down':
            score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5
        else:
            score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+hsl_b+yang_vr_b
        
        cand.append((score, nh, p, nm, code))
    
    if not cand: continue
    cand.sort(key=lambda x:(-x[0], -x[2]))
    total+=1
    month=dt[:7]
    by_month.setdefault(month,[0,0])
    by_month[month][1]+=1
    if cand[0][1]>=2.5:
        wins+=1
        by_month[month][0] += 1

# 输出
print(f"\n{'='*60}", flush=True)
print(f"  v11 冠军胜率 (仅L0, 用缓存n字段)", flush=True)
print(f"{'='*60}", flush=True)
print(f"{'月份':<10} {'天数':>4} {'冠军':>6} {'胜率':>6}", flush=True)
for m in sorted(by_month.keys()):
    w,t=by_month[m]
    print(f"{m:<10} {t:>4} {w:>3}/{t:<3} {w*100/t:>5.1f}%", flush=True)
print(f"{'─'*30}", flush=True)
print(f"{'总计':<10} {total:>4} {wins:>3}/{total:<3} {wins*100/total:>5.1f}%", flush=True)
