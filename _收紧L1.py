"""
收紧L1+原版评分：池小了，评分就好用了
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
            'vr':vr,'jv':(sx.get('j_val',0) or 0),'kv':(sx.get('k_val',0) or 0),
            'dv':(sx.get('d_val',0) or 0),'kdj_g':(sx.get('kdj_golden',0) or 0),
            'mg':(sx.get('macd_golden',0) or 0),
            'a5':(sx.get('above_ma5',0) or 0),'wrv':(sx.get('wr',0) or 0),
            'dif':(sx.get('dif_val',0) or 0),'buy_c':(sx.get('close',0) or 0),
            'nh':nh,
        })
    return pool

# 加载评分函数
mods = {
    'real_up': importlib.import_module('大道至简_真实涨日_评分策略'),
    'down': importlib.import_module('大道至简_跌日_评分策略'),
    'flat': importlib.import_module('大道至简_横盘_评分策略'),
}
sf_map = {
    'real_up': mods['real_up'].真实涨日_评分,
    'down': mods['down'].跌日_评分,
    'flat': mods['flat'].横盘_评分,
}

# 新收紧的L1~L4
tight_levels = {
    'down': [
        {'p_min':2,'p_max':7,'vr_min':0.6,'vr_max':1.5,'cl_min':40,'cl_max':85,'hs_min':8,'hs_max':20,'sz_max':150,'a5_req':1,'kdj_g_req':1},  # hsl>=8!
        {'p_min':2,'p_max':7,'vr_min':0.6,'vr_max':1.5,'cl_min':40,'cl_max':90,'hs_min':5,'hs_max':20,'sz_max':150,'a5_req':1,'kdj_g_req':0},
        {'p_min':2,'p_max':7,'vr_min':0.6,'vr_max':2.0,'cl_min':30,'cl_max':95,'hs_min':3,'hs_max':25,'sz_max':200},
        {'p_min':0,'p_max':7,'vr_min':0.5,'vr_max':2.5,'cl_min':20,'cl_max':98,'hs_min':2,'hs_max':30,'sz_max':300},
        {'p_min':-10,'p_max':7,'vr_min':0.1,'vr_max':10,'cl_min':0,'cl_max':100,'hs_min':0.1,'hs_max':100,'sz_max':10000},
    ],
    'real_up': [
        {'p_min':5,'p_max':7,'vr_min':0.6,'vr_max':3.0,'cl_min':50,'cl_max':85,'hs_min':5,'hs_max':20,'sz_max':200,'no_macd':1},
        {'p_min':4,'p_max':7,'vr_min':0.5,'vr_max':3.0,'cl_min':40,'cl_max':90,'hs_min':3,'hs_max':25,'sz_max':300,'no_macd':1},
        {'p_min':3,'p_max':7,'vr_min':0.5,'vr_max':3.5,'cl_min':30,'cl_max':95,'hs_min':3,'hs_max':30,'sz_max':400},
        {'p_min':0,'p_max':7,'vr_min':0.2,'vr_max':5.0,'cl_min':10,'cl_max':100,'hs_min':1,'hs_max':50,'sz_max':5000},
    ],
    'flat': [
        {'p_min':4,'p_max':7,'vr_min':0.6,'vr_max':2.0,'cl_min':50,'cl_max':85,'hs_min':5,'hs_max':20,'sz_max':200,'no_macd':1},
        {'p_min':3,'p_max':7,'vr_min':0.5,'vr_max':2.5,'cl_min':40,'cl_max':90,'hs_min':3,'hs_max':20,'sz_max':200},
        {'p_min':2,'p_max':7,'vr_min':0.4,'vr_max':3.0,'cl_min':30,'cl_max':95,'hs_min':2,'hs_max':30,'sz_max':300},
        {'p_min':0,'p_max':7,'vr_min':0.3,'vr_max':5.0,'cl_min':10,'cl_max':98,'hs_min':1,'hs_max':40,'sz_max':500},
        {'p_min':-10,'p_max':7,'vr_min':0.1,'vr_max':10,'cl_min':0,'cl_max':100,'hs_min':0.1,'hs_max':100,'sz_max':10000},
    ],
}

print('收紧L1 + 原版评分:')
for mk, name in [('down','跌日'),('real_up','真实涨日'),('flat','横盘')]:
    lvls=tight_levels[mk]
    sf=sf_map[mk]
    w=t=0; day_list=[]
    for dt in dates:
        s=data.get(dt,[]); m=cm(s)
        if m!=mk: continue
        pool=None
        for lv in lvls:
            p=fl(s,lv)
            if len(p)>8: pool=p; break
        if not pool: continue
        t+=1
        for x in pool: x['sc']=sf(x)
        pool.sort(key=lambda x:-x['sc'])
        if pool[0]['nh']>=2.5: w+=1
        day_list.append({'n':len(pool),'nh':pool[0]['nh'],'nm':pool[0].get('nm','?')})
    
    r=w/t*100 if t else 0
    r30=sum(1 for d in day_list[-30:] if d['nh']>=2.5)/min(30,len(day_list))*100
    avg_pool=sum(d['n'] for d in day_list)/len(day_list) if day_list else 0
    print(f'\n{name}:')
    print(f'  冠军: {r:.1f}% ({w}/{t})  30天: {r30:.1f}%  平均候选: {avg_pool:.0f}只')
