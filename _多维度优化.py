"""
多维度综合评分优化 - 针对每个行情独立调整
"""
import pickle, sys, os, importlib
sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dev/current'))

with open(os.path.join(os.path.dirname(__file__), 'big_cache_full.pkl'), 'rb') as f:
    cache = pickle.load(f)
data = cache['data']
real_data = cache.get('real', {})
names = cache.get('names', {})

dates = sorted(x for x in data.keys() if '2025-06-01' <= x < '2026-06-01')
def cm(s):
    ps=[x.get('p',0) or 0 for x in s]
    if not ps: return 'flat'
    ap=sum(ps)/len(ps); vrs=[x.get('vol_ratio',0) or 0 for x in s if x.get('vol_ratio',0)]
    av=sum(vrs)/len(vrs) if vrs else 0; ht=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if ht<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

levels_down = [
    {'p_min':2,'p_max':7,'vr_min':0.6,'vr_max':1.5,'cl_min':40,'cl_max':90,'hs_min':5,'hs_max':20,'sz_max':150,'a5_req':1,'kdj_g_req':1},
    {'p_min':2,'p_max':7,'vr_min':0.6,'vr_max':1.5,'cl_min':40,'cl_max':90,'hs_min':5,'hs_max':20,'sz_max':150,'a5_req':1},
    {'p_min':2,'p_max':7,'vr_min':0.6,'vr_max':2.0,'cl_min':30,'cl_max':95,'hs_min':3,'hs_max':25,'sz_max':200},
]
levels_real = importlib.import_module('大道至简_真实涨日_评分策略').LEVELS
levels_flat = importlib.import_module('大道至简_横盘_评分策略').LEVELS

def fl(s_list, lv):
    pool=[]
    for sx in s_list:
        code=sx.get('code',''); p=(sx.get('p',0) or 0)
        if p<lv['p_min'] or p>lv['p_max']: continue
        if p>=8: continue
        vr=(sx.get('vol_ratio',0) or 0)
        if vr<lv.get('vr_min',0) or vr>lv.get('vr_max',99): continue
        cl=(sx.get('cl',0) or 0)
        if cl<lv.get('cl_min',0) or cl>lv.get('cl_max',100): continue
        ri=real_data.get(code)
        if ri:
            hsl=(ri.get('hsl',0) or 0)
            if hsl<lv.get('hs_min',0) or hsl>lv.get('hs_max',99): continue
            szv=ri.get('shizhi',0) or 0
            if isinstance(szv,(int,float)) and szv>1: szv*=1e-8
            if szv>=lv.get('sz_max',99999): continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        nh=(sx.get('n',0) or 0)
        if nh<=0: continue
        if lv.get('a5_req',0) and (sx.get('above_ma5',0) or 0)<1: continue
        if lv.get('kdj_g_req',0) and (sx.get('kdj_golden',0) or 0)<1: continue
        if lv.get('no_macd',0) and (sx.get('macd_golden',0) or 0)>=1: continue
        pool.append({
            'p':p,'cl':cl,'hsl':(ri.get('hsl',0) or 0) if ri else 0,
            'vr':vr,'jv':(sx.get('j_val',0) or 0),
            'mg':(sx.get('macd_golden',0) or 0),
            'a5':(sx.get('above_ma5',0) or 0),
            'nh':nh,
        })
    return pool

# ===== 跌日: 尝试新评分 =====
print('=== 跌日 - 多维度评分测试 ===')
configs = {}

# 方法1: 换手优先 + CL惩罚
def test_score(pw, clw, hsw, cl_pen, j_pen, macd_b):
    def fn(s):
        sc = s['p']*pw + s['cl']*clw + s['hsl']*hsw
        if s['cl']>85: sc+=cl_pen
        if s['jv']>90: sc+=j_pen
        if s['mg']: sc+=macd_b
        return sc
    return fn

import itertools
best=0; best_fn=None; best_lbl=''
for pw,clw,hsw,cl_pen,j_pen,mg_b in itertools.product([1.0,1.5,2.0],[0.05,0.1],[0.2,0.5,1.0],[-3,-5],[-2,-5],[2,3]):
    fn=test_score(pw,clw,hsw,cl_pen,j_pen,mg_b)
    w=0; t=0
    for dt in dates:
        s=data.get(dt,[]); m=cm(s)
        if m!='down': continue
        pool=None
        for lv in levels_down:
            p=fl(s,lv)
            if len(p)>8: pool=p; break
        if not pool: continue
        t+=1
        for x in pool: x['sc']=fn(x)
        pool.sort(key=lambda x:-x['sc'])
        if pool[0]['nh']>=2.5: w+=1
    r=w/t*100 if t else 0
    if r>best:
        best=r; best_fn=fn
        best_lbl=f'pw{pw}_cl{clw}_hs{hsw}_pen{cl_pen}_j{j_pen}_mg{mg_b}'
        print(f'  新最佳: {r:.1f}% ({w}/{t}) {best_lbl}')

print(f'\n跌日最优: {best:.1f}% {best_lbl}')

# 方法2: 组合排名法
print('\n=== 跌日 - 组合排名法 ===')
wins=[0]*10
for dt in dates:
    s=data.get(dt,[]); m=cm(s)
    if m!='down': continue
    pool=None
    for lv in levels_down:
        p=fl(s,lv)
        if len(p)>8: pool=p; break
    if not pool: continue
    n=len(pool)
    # 按各维度排名
    by_p=sorted(pool, key=lambda x:-x['p'])
    by_hsl=sorted(pool, key=lambda x:-x['hsl'])
    by_cl=sorted(pool, key=lambda x:-x['cl'])
    by_jv_asc=sorted(pool, key=lambda x:x['jv'])  # J值越低越好
    
    for i in range(min(10,n)):
        # P排名前i
        p_set=set(id(x) for x in by_p[:max(1,i+1)])
        # 取P排名前1 + HSL排名前3 + CL排名前3中的交集的第一个
        # 简单: 取P前20%中HSL最高的
        cand=by_p[:max(1,n//5)]
        cand.sort(key=lambda x:-x['hsl'])
        if cand[0]['nh']>=2.5: wins[i]+=1

print(f'  组合排名(P前20%+HSL最高): {wins[0]}/{56}={wins[0]/56*100:.1f}%')

# 现有评分对比
print(f'  原版评分(跌日): {36}/{56}={36/56*100:.1f}%')
print(f'  池随机: ~{0.62*56:.0f}/{56}=62%')
