"""
30交易日逐天明细：评分第1名，标记达标/不达标
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
    ap=sum(ps)/len(ps)
    vrs=[x.get('vol_ratio',0) or 0 for x in s if x.get('vol_ratio',0)]
    av=sum(vrs)/len(vrs) if vrs else 0
    ht=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if ht<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

mods = {
    'real_up': importlib.import_module('大道至简_真实涨日_评分策略'),
    'fake_up': importlib.import_module('大道至简_虚涨日_评分策略'),
    'down': importlib.import_module('大道至简_跌日_评分策略'),
    'flat': importlib.import_module('大道至简_横盘_评分策略'),
}
score_fns = {
    'real_up': mods['real_up'].真实涨日_评分,
    'fake_up': mods['fake_up'].虚涨日_评分,
    'down': mods['down'].跌日_评分,
    'flat': mods['flat'].横盘_评分,
}
mk_names = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}

def fl(s_list, lv):
    pool=[]
    for sx in s_list:
        code=sx.get('code','')
        p=(sx.get('p',0) or 0)
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
            'code':code,'nm':names.get(code,'')[:8],'p':p,
            'cl':cl,'vr':vr,'hsl':(ri.get('hsl',0) or 0) if ri else 0,
            'dif':(sx.get('dif_val',0) or 0),'mg':(sx.get('macd_golden',0) or 0),
            'a5':(sx.get('above_ma5',0) or 0),'wrv':(sx.get('wr',0) or 0),
            'jv':(sx.get('j_val',0) or 0),'kv':(sx.get('k_val',0) or 0),
            'dv':(sx.get('d_val',0) or 0),'kdj_g':(sx.get('kdj_golden',0) or 0),
            'buy_c':(sx.get('close',0) or 0),'nh':nh,
        })
    return pool

# 用30个交易日
recent_dates = dates[-35:-5]

for mk in ['real_up','down','flat','fake_up']:
    levels=mods[mk].LEVELS
    sf=score_fns[mk]
    name=mk_names[mk]
    
    print(f'\n{"="*70}')
    print(f'{name} | 最近30个交易日')
    print(f'{"="*70}')
    print(f'{"日期":<12} {"行情":<8} {"冠军":<10} {"今涨":>6} {"买入":>8} {"次日最高":>8}  结果')
    print('-'*70)
    
    wins=0; total=0
    for dt in recent_dates:
        s=data.get(dt,[]); m=cm(s)
        if m!=mk: continue
        
        pool=None
        for lv in levels:
            p=fl(s,lv)
            if len(p)>8: pool=p; break
        if not pool: continue
        
        total+=1
        for x in pool: x['sc']=sf(x)
        pool.sort(key=lambda x: -x['sc'])
        c=pool[0]
        
        win=c['nh']>=2.5
        if win: wins+=1
        tag='✅ 达标' if win else '❌ 不达标'
        
        print(f'{dt:<12} {name:<8} {c["nm"]:<10} {c["p"]:>+5.1f}% {c["buy_c"]:>8.2f} {c["nh"]:>+6.1f}%  {tag}')
    
    rate=wins/total*100 if total else 0
    print(f'\n  出票{total}天')
    print(f'  达标{wins}天 不达标{total-wins}天')
    print(f'  30天胜率: {rate:.1f}%')
