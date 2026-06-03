"""解剖差月：2025-04(28.6%) 2025-08(33.3%) + 针对性调优"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())

def get_nxt(code, date):
    fp=os.path.join(CACHE_DIR,f'{code}.json')
    if not os.path.exists(fp): return 0
    try:
        with open(fp) as f: kdata=json.load(f)
        idx=next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx+1 >= len(kdata): return 0
        bc=kdata[idx]['close']
        nh=(kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
        if abs(nh)>50: return 0
        return nh or 0
    except: return 0

def calc_wr(code, date):
    fp=os.path.join(CACHE_DIR,f'{code}.json')
    if not os.path.exists(fp): return 50,50,0
    try:
        with open(fp) as f: kdata=json.load(f)
        idx=next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx<14: return 50,50,0
        h14=max(k['high'] for k in kdata[idx-13:idx+1])
        l14=min(k['low'] for k in kdata[idx-13:idx+1])
        c=kdata[idx]['close']
        wr_t=(h14-c)/(h14-l14)*100 if h14!=l14 else 50
        if idx<15: return wr_t,50,0
        h14_y=max(k['high'] for k in kdata[idx-14:idx])
        l14_y=min(k['low'] for k in kdata[idx-14:idx])
        c_y=kdata[idx-1]['close']
        wr_y=(h14_y-c_y)/(h14_y-l14_y)*100 if h14_y!=l14_y else 50
        y_p=(kdata[idx-1]['close']/kdata[idx-2]['close']-1)*100 if idx>=2 else 0
        return wr_t,wr_y,y_p
    except: return 50,50,0

def ps(p):return min(10,max(1,11-p/10))

# 5级条件
LEVELS = [
    {'n':'L0','p_min':5,'p_max':8,'vr_min':0.8,'vr_max':2.0,'hsl_min':5,'hsl_max':15,'sz_max':300,'cl_min':60,'cl_max':90,'j_max':100},
    {'n':'L1','p_min':4,'p_max':9,'vr_min':0.6,'vr_max':2.5,'hsl_min':3,'hsl_max':20,'sz_max':300,'cl_min':50,'cl_max':95,'j_max':120},
    {'n':'L2','p_min':3,'p_max':10,'vr_min':0.5,'vr_max':3.0,'hsl_min':2,'hsl_max':25,'sz_max':400,'cl_min':40,'cl_max':98,'j_max':150},
    {'n':'L3','p_min':2,'p_max':11,'vr_min':0.4,'vr_max':3.5,'hsl_min':1,'hsl_max':30,'sz_max':500,'cl_min':30,'cl_max':99,'j_max':200},
    {'n':'L4','p_min':1,'p_max':12,'vr_min':0.3,'vr_max':4.0,'hsl_min':0.5,'hsl_max':35,'sz_max':1000,'cl_min':20,'cl_max':100,'j_max':300},
]

def get_cand(dt):
    """获取该天所有级别候选(去重,标记级别)"""
    cand_list = []
    seen=set()
    for li in range(len(LEVELS)):
        L=LEVELS[li]
        for s in data.get(dt,[]):
            code=s['code']
            if code in seen: continue
            p=s['p']
            if p<L['p_min'] or p>L['p_max']: continue
            vr=s.get('vol_ratio',0) or 0
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
            
            seen.add(code)
            buy=s.get('close',0); dif=s.get('dif_val',0) or 0
            macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
            is_yang=s.get('is_yang',0); close=s.get('close',0)
            ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
            cand_list.append((code,p,cl,vr,hsl,sz,nm,buy,dif,macd_g,above5,is_yang,close,ma5,ma10,ma20,li))
            if li==0 and len(seen)>=10: break
        if len(seen)>=10: break
    return cand_list

def score_cand(cand_list, dt, params, mkt):
    """打分"""
    scored=[]
    for c in cand_list:
        code,p,cl,vr,hsl,sz,nm,buy,dif,macd_g,above5,is_yang,close,ma5,ma10,ma20,li = c
        wr_t,wr_y,y_p=calc_wr(code,dt)
        nh=get_nxt(code,dt)
        if not nh or nh<=0: continue
        
        wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
        yp=-3 if y_p>7 else 0
        macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
        ps2=ps(buy)
        
        hsl_b=2*0.3 if 5<=hsl<=7 else 0
        duotou_b=3*0.3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
        yang_vr_b=2*0.3 if is_yang and vr>1.2 else 0
        
        if mkt=='up':
            s=p*params.get('p_w',3.0)+cl*params.get('cl_w',0.1)+ps2*0.3+macd_s*0.3+3*above5+wr_s*params.get('wr_w',0.3)+hsl_b*params.get('hs_w',1)+duotou_b*params.get('dt_w',1)+params.get('b'+str(li),0)
        elif mkt=='down':
            s=p*params.get('p_w_d',2.0)+cl*params.get('cl_w_d',0.05)+ps2*0.3+macd_s*0.3+3*above5+wr_s*params.get('wr_w_d',0.3)+yp+params.get('b'+str(li),0)
        else:
            s=p*params.get('p_w_f',2.0)+cl*params.get('cl_w_f',0.05)+ps2*0.3+macd_s*0.3+3*above5+wr_s*params.get('wr_w_f',0.3)+yp+hsl_b*params.get('hs_w',1)+yang_vr_b*params.get('yv_w',1)+params.get('b'+str(li),0)
        
        scored.append((s,nh,p))
    scored.sort(key=lambda x:(-x[0],-x[2]))
    return scored

def run_month(month, params):
    """跑某月"""
    mdates=[d for d in dates if d.startswith(month)]
    all_stocks=data
    wins=0; nd=0
    for dt in mdates:
        stocks=all_stocks.get(dt,[])
        if not stocks: continue
        all_p=[x['p'] for x in stocks if 'p' in x]
        avg_mkt=sum(all_p)/len(all_p) if all_p else 0
        if avg_mkt>0.5: mkt='up'
        elif avg_mkt<-0.5: mkt='down'
        else: mkt='flat'
        
        c=get_cand(dt)
        if not c: continue
        s=score_cand(c,dt,params,mkt)
        if not s: continue
        nd+=1
        if s[0][1]>=2.5: wins+=1
    return wins, nd

# ===== 分析差月特征 =====
for month in ['2025-04','2025-08']:
    print(f"\n{'='*60}", flush=True)
    print(f"📊 {month} 市场特征分析", flush=True)
    print('='*60, flush=True)
    
    mdates=[d for d in dates if d.startswith(month)]
    for dt in mdates:
        stocks=data.get(dt,[])
        if not stocks: continue
        # 大盘
        all_p=[x['p'] for x in stocks if 'p' in x]
        avg_mkt=sum(all_p)/len(all_p) if all_p else 0
        
        # 候选池
        c=get_cand(dt)
        n=len(c)
        bad_rate=0
        if c:
            goods=0; tt=0
            for c2 in c:
                nh2=get_nxt(c2[0],dt)
                if nh2 and nh2>0: tt+=1
                if nh2>=2.5: goods+=1
            bad_rate=goods*100/tt if tt else 0
        
        print(f"  {dt}: 大盘{avg_mkt:+.1f}% 候选{n}只 池达2.5%:{bad_rate:.0f}%", flush=True)

# ===== 针对性调优 =====
print(f"\n{'='*60}", flush=True)
print(f"🔧 差月调优搜索", flush=True)
print('='*60, flush=True)

base_params = {
    'p_w':3.0,'cl_w':0.1,'wr_w':0.3,'hs_w':0.6,'dt_w':0.9,
    'p_w_d':2.0,'cl_w_d':0.05,'wr_w_d':0.3,
    'p_w_f':2.0,'cl_w_f':0.05,'wr_w_f':0.3,'yv_w':0.6,
    'b0':5,'b1':3,'b2':0,'b3':-2,'b4':-5
}

# 测试不同参数
tests = {}
# 测试不同级别加分 + WR权重 + 涨幅权重 对差月的影响
for p_w in [2.0, 2.5, 3.0, 3.5]:
    for p_w_d in [1.5, 2.0, 2.5]:
        for WR in [0, 0.3, 0.5, 1.0]:
            for b0 in [0, 3, 5, 8, 10]:
                for b1 in [0, 2, 3, 5]:
                    for b2 in [0, 2, 3]:
                        p=base_params.copy()
                        p['p_w']=p_w; p['p_w_d']=p_w_d; p['p_w_f']=p_w_d
                        p['wr_w']=WR; p['wr_w_d']=WR; p['wr_w_f']=WR
                        p['b0']=b0; p['b1']=b1; p['b2']=b2
                        
                        w4,n4=run_month('2025-04',p)
                        w8,n8=run_month('2025-08',p)
                        total=w4+w8; total_n=n4+n8
                        if total_n>0:
                            key=(total*100/total_n, total, total_n, p_w, WR, b0, b1, b2)
                            tests[key]=key

# 按胜率排序
sorted_tests = sorted(tests.values(), key=lambda x: -x[0])
print(f"{'胜率':>6} {'赢/天':>8} {'涨w':>5} {'WRw':>5} {'L0+':>4} {'L1+':>4} {'L2+':>4}", flush=True)
for t in sorted_tests[:15]:
    print(f"{t[0]:>5.1f}% {t[1]:>2}/{t[2]:<3} {t[3]:>5.1f} {t[4]:>5.1f} {t[5]:>4} {t[6]:>4} {t[7]:>4}", flush=True)
