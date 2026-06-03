"""
大道至简策略 v2.0 — 4策略×5级独立放宽
每个子策略有自己专属的L0~L4放宽阶梯
"""
import pickle, os, sys
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR)

def load_cache():
    with open('big_cache_full.pkl', 'rb') as f:
        cache = pickle.load(f)
    return cache['data'], cache['real'], cache['names']

def cm(stocks):
    if not stocks: return 'flat'
    ps=[s.get('p',0) or 0 for s in stocks]
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    avg_p=sum(ps)/len(ps); avg_vr=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    if avg_p<-0.5: return 'down'
    return 'flat'

def md(dif,mg):
    if mg and dif>0.5: return 10
    if mg and dif>0.2: return 8
    if mg: return 6
    if dif>0.5: return 4
    if dif>0: return 2
    return 0

# ============================================================
# 4个策略 × 5级放宽（各自定制）
# 每级格式: [p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz_max,cl_min,cl_max]
# ============================================================

# 📈 真实涨日 — 池原本就够，只需微宽
LEVELS_REAL = [
    [3,7,0.6,2.5,5,15,200,60,90],     # L0最优
    [2,7,0.6,2.5,3,20,200,50,95],     # L1
    [1,7,0.5,3.0,2,25,300,40,95],     # L2  
    [0,7,0.4,3.5,1,30,400,30,98],     # L3
    [-1,7,0.3,4.0,0.5,35,500,20,99],  # L4极限
]

# 🎭 虚涨日 — 池本来就很足(平均156)
LEVELS_FAKE = [
    [0,6,0.6,2.5,5,20,200,30,95],    # L0最优
    [-1,6,0.5,3.0,3,25,200,20,95],   # L1
    [-1,7,0.4,3.5,2,30,300,15,98],   # L2
    [-2,7,0.3,4.0,1,35,400,10,99],   # L3
    [-3,7,0.2,5.0,0.5,40,500,0,100], # L4
]

# 📉 跌日 — 池严重缺，大踏步放宽
LEVELS_DOWN = [
    [-1,7,0.6,2.5,3,20,200,30,90],   # L0（原来涨5~8%完全没池，直接放宽到0~7%）
    [-2,7,0.5,3.0,2,25,200,20,95],   # L1
    [-3,7,0.4,3.5,1,30,300,10,98],   # L2
    [-4,7,0.3,4.0,0.5,35,400,5,99],  # L3
    [-5,7,0.2,5.0,0.3,40,500,0,100], # L4
]

# ➖ 横盘 — 同样严重缺池
LEVELS_FLAT = [
    [0,7,0.6,2.5,3,20,200,40,95],    # L0
    [-1,7,0.5,3.0,2,25,200,30,95],   # L1
    [-2,7,0.4,3.5,1,30,300,20,98],   # L2
    [-3,7,0.3,4.0,0.5,35,400,10,99], # L3
    [-5,7,0.2,5.0,0.3,40,500,0,100], # L4
]

LEVELS_MAP = {'real_up':LEVELS_REAL, 'fake_up':LEVELS_FAKE, 'down':LEVELS_DOWN, 'flat':LEVELS_FLAT}
PENALTY = [0, -1, -2, -3, -5]  # 放宽级补偿分

# ============================================================
# 4个策略评分权重
# ============================================================
W = {
    'real_up': {'pw':2.5,'cw':0.05,'mw':0.3,'m5':3,'vb':1,'hb':0.3,'wb':2,'jb':2,'jlb':2},
    'fake_up': {'pw':1.0,'cw':0.05,'mw':0.5,'m5':0,'vb':0,'hb':0,'wb':0,'jb':0,'jlb':0},
    'down':    {'pw':2.0,'cw':0.05,'mw':0.3,'m5':2,'vb':0,'hb':0,'wb':0,'jb':0,'jlb':0},
    'flat':    {'pw':1.5,'cw':0.05,'mw':0.3,'m5':2,'vb':1,'hb':0.3,'wb':0,'jb':0,'jlb':2},
}

def run(stocks, real, names):
    mkt = cm(stocks)
    lvs = LEVELS_MAP[mkt]
    w = W[mkt]
    
    cand = None; used = 0
    for li, lv in enumerate(lvs):
        p1,p2,v1,v2,h1,h2,sz,c1,c2 = lv
        ca = []
        for s in stocks:
            code=s['code'];p=s.get('p',0) or 0
            if p<p1 or p>p2: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<v1 or vr>v2: continue
            ri=real.get(code)
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<h1 or hsl>h2: continue
            if (ri.get('shizhi',0) or 0)>=sz: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl=s.get('cl',0)
            if cl<c1 or cl>c2: continue
            nh=s.get('n',0) or 0
            if nh<=0: continue
            dif=s.get('dif_val',0) or 0; mg=s.get('macd_golden',0)
            buy=s.get('close',0) or 0; a5=s.get('above_ma5',0) or 0
            wrv=s.get('wr_val',0) or 0; jv=s.get('j_val',0) or 0
            
            ms=md(dif,mg); ps2=min(10,max(1,11-buy/10)) if buy else 0
            sc=p*w['pw']+cl*w['cw']+ps2*0.3+ms*w['mw']
            sc+=(w['m5'] if a5 else 0)
            sc+=(w['vb']*1.5 if 1.0<=vr<=1.5 else 0)
            sc+=(w['hb']*2 if 5<=hsl<=7 else 0)
            sc+=(w['wb'] if wrv<-80 else 0)
            sc+=(w['jb'] if jv>70 else 0)
            sc+=(w['jlb'] if jv<20 else 0)
            ca.append({'score':sc,'n':nh,'p':p,'name':nm[:12],'code':code,'cl':cl,'vr':vr,'hsl':hsl})
        if len(ca) >= 10:
            cand = ca; used = li; break
    if not cand:
        cand = ca if 'ca' in dir() else []
        used = len(lvs)-1
    
    if cand and PENALTY[used]:
        for c in cand: c['score'] += PENALTY[used]
    
    cand.sort(key=lambda x: (-x['score'], -x['p']))
    return mkt, used, cand

if __name__ == '__main__':
    data, real, names = load_cache()
    dates = [x for x in sorted(data.keys()) if '2025-01-01' <= x < '2026-06-01']
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 全量回测
    ln=['L0严格','L1微宽','L2中宽','L3较宽','L4极限']
    mk_nm={'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
    cd={'real_up':0,'fake_up':0,'down':0,'flat':0}
    cw={'real_up':0,'fake_up':0,'down':0,'flat':0}
    ct={'real_up':0,'fake_up':0,'down':0,'flat':0}
    lu={i:0 for i in range(5)}
    td=0
    
    for dt in dates:
        stocks=data.get(dt,[])
        if not stocks: continue
        mk,lv,cand=run(stocks,real,names)
        if not cand: continue
        td+=1; cd[mk]+=1; lu[lv]+=1
        if cand[0]['n']>=2.5: cw[mk]+=1
        if any(c['n']>=2.5 for c in cand[:3]): ct[mk]+=1

    
    print(f"\n{'='*55}")
    print(f"  大道至简 v2.0 — 4策略×5级独立放宽")
    print(f"{'='*55}")
    print(f"\n  交易日: {td}")
    print(f"  总冠军: {sum(cw.values())}/{td}={sum(cw.values())*100/td:.1f}%")
    print(f"  总Top3: {sum(ct.values())}/{td}={sum(ct.values())*100/td:.1f}%")
    print(f"\n  放宽级分布:")
    for i in range(5):
        print(f"    {ln[i]}: {lu[i]}天 ({lu[i]*100/td:.1f}%)")
    print(f"\n  分行情:")
    for mk in ['real_up','fake_up','down','flat']:
        if cd[mk]:
            cr=cw[mk]*100/cd[mk]; tr=ct[mk]*100/cd[mk]
            lv_dist = {}
            for dt in dates:
                s=data.get(dt,[])
                if not s: continue
                if cm(s)!=mk: continue
                _,lv,_=run(s,real,names)
                lv_dist[lv]=lv_dist.get(lv,0)+1
            lv_str=','.join(f'{ln[k]}{v}天' for k,v in sorted(lv_dist.items()))
            print(f"    {mk_nm[mk]}: {cd[mk]}天 冠军{cr:.1f}% Top3{tr:.1f}% | {lv_str}")
