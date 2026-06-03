"""
确定性选冠军：换手率+CL双因子硬排序
"""
import pickle, sys, os
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
    {'p_min':0,'p_max':7,'vr_min':0.5,'vr_max':2.5,'cl_min':20,'cl_max':98,'hs_min':2,'hs_max':30,'sz_max':300},
    {'p_min':-10,'p_max':7,'vr_min':0.1,'vr_max':10,'cl_min':0,'cl_max':100,'hs_min':0.1,'hs_max':100,'sz_max':10000},
]

levels_real = [
    {'name':'L1','p_min':5,'p_max':7,'vr_min':0.6,'vr_max':3.0,'cl_min':50,'cl_max':95,'hs_min':3,'hs_max':20,'sz_max':200,'no_macd':1},
    {'name':'L2','p_min':4,'p_max':7,'vr_min':0.5,'vr_max':3.0,'cl_min':40,'cl_max':95,'hs_min':3,'hs_max':25,'sz_max':300,'no_macd':1},
    {'name':'L3','p_min':3,'p_max':7,'vr_min':0.5,'vr_max':3.5,'cl_min':30,'cl_max':98,'hs_min':3,'hs_max':30,'sz_max':400},
    {'name':'L4','p_min':0,'p_max':7,'vr_min':0.2,'vr_max':5.0,'cl_min':10,'cl_max':100,'hs_min':1,'hs_max':50,'sz_max':5000},
]

levels_flat = [
    {'name':'L1','p_min':4,'p_max':7,'vr_min':0.6,'vr_max':2.0,'cl_min':40,'cl_max':90,'hs_min':3,'hs_max':20,'sz_max':200,'no_macd':1},
    {'name':'L2','p_min':3,'p_max':7,'vr_min':0.5,'vr_max':2.5,'cl_min':30,'cl_max':90,'hs_min':3,'hs_max':20,'sz_max':200},
    {'name':'L3','p_min':2,'p_max':7,'vr_min':0.4,'vr_max':3.0,'cl_min':20,'cl_max':95,'hs_min':2,'hs_max':30,'sz_max':300},
    {'name':'L4','p_min':0,'p_max':7,'vr_min':0.3,'vr_max':5.0,'cl_min':10,'cl_max':98,'hs_min':1,'hs_max':40,'sz_max':500},
    {'name':'L5','p_min':-10,'p_max':7,'vr_min':0.1,'vr_max':10,'cl_min':0,'cl_max':100,'hs_min':0.1,'hs_max':100,'sz_max':10000},
]

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

# 测试: 多种冠军选择方式
def test_method(name, levels, sort_key):
    w=0; t=0; day_list=[]
    for dt in dates:
        s=data.get(dt,[]); m=cm(s)
        if m not in ['real_up','down','flat']: continue
        pool=None
        for lv in levels:
            p=fl(s,lv)
            if len(p)>8: pool=p; break
        if not pool or len(pool)<=8: continue
        t+=1
        pool.sort(key=sort_key, reverse=True)
        win=pool[0]['nh']>=2.5
        if win: w+=1
        day_list.append(pool[0])
    rate=w/t*100 if t else 0
    r30=sum(1 for d in day_list[-30:] if d['nh']>=2.5)/min(30,len(day_list))*100
    return rate, w, t, r30, day_list[-30:]

print('='*70)
print('确定性冠军选择测试')
print('='*70)

# 跌日: 换手率>评分>CL
print('\n=== 跌日 ===')
r,w,t,r30,_=test_method('换手率优先', levels_down, lambda x: x['hsl'])
print(f'  换手率(降序): {r:.1f}% ({w}/{t}) 30天{r30:.1f}%')

r,w,t,r30,_=test_method('换手+CL', levels_down, lambda x: x['hsl']*0.7 + x['cl']*0.3)
print(f'  换手*0.7+CL*0.3: {r:.1f}% ({w}/{t})')

r,w,t,r30,_=test_method('换手-CL惩罚', levels_down, lambda x: x['hsl']*1.0 - max(0,x['cl']-80)*0.2)
print(f'  换手-CL>80惩罚: {r:.1f}% ({w}/{t})')

# 真实涨日
print('\n=== 真实涨日 ===')
r,w,t,r30,_=test_method('换手率优先', levels_real, lambda x: x['hsl'])
print(f'  换手率(降序): {r:.1f}% ({w}/{t}) 30天{r30:.1f}%')

r,w,t,r30,_=test_method('换手+CL', levels_real, lambda x: x['hsl']*0.7 + x['cl']*0.3)
print(f'  换手*0.7+CL*0.3: {r:.1f}% ({w}/{t})')

# 横盘
print('\n=== 横盘 ===')
r,w,t,r30,_=test_method('换手率优先', levels_flat, lambda x: x['hsl'])
print(f'  换手率(降序): {r:.1f}% ({w}/{t}) 30天{r30:.1f}%')

r,w,t,r30,days=test_method('换手+CL', levels_flat, lambda x: x['hsl']*0.6 + x['cl']*0.4)
print(f'  换手*0.6+CL*0.4: {r:.1f}% ({w}/{t}) 30天{r30:.1f}%')

# 30天明细
print(f'\n横盘 换手+CL 最后30天:')
for d in days:
    tag='✅' if d['nh']>=2.5 else '❌'
    print(f'  {d["p"]:+.1f}% CL{d["cl"]:.0f} 换手{d["hsl"]:.1f}% 次日{d["nh"]:+.1f}% {tag}')
