"""
达标vs不达标冠军特征对比
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

for mk in ['real_up','down','flat']:
    levels=mods[mk].LEVELS
    sf=score_fns[mk]
    name=mk_names[mk]
    
    wins=[]; fails=[]
    for dt in dates:
        s=data.get(dt,[]); m=cm(s)
        if m!=mk: continue
        pool=None
        for lv in levels:
            p=fl(s,lv)
            if len(p)>8: pool=p; break
        if not pool: continue
        for x in pool: x['sc']=sf(x)
        pool.sort(key=lambda x: -x['sc'])
        c=pool[0]
        if c['nh']>=2.5: wins.append(c)
        else: fails.append(c)
    
    print(f'\n{"="*70}')
    print(f'{name} | 达标{len(wins)}天 不达标{len(fails)}天')
    print(f'{"="*70}')
    
    # 数值对比
    keys=[('p','今涨%'),('cl','CL'),('vr','量比'),('hsl','换手%'),('jv','J值'),('sc','评分'),('nh','次日最高%')]
    print(f'\n{"指标":<10} {"达标均值":>10} {"不达标均值":>10} {"差距":>8}')
    print('-'*45)
    for k,lb in keys:
        wm=sum(x[k] for x in wins)/len(wins)
        lm=sum(x[k] for x in fails)/len(fails)
        print(f'{lb:<10} {wm:>10.2f} {lm:>10.2f} {wm-lm:>+8.2f}')
    
    # 比率对比
    bool_keys=[('mg','MACD金叉'),('a5','站MA5'),('kdj_g','KDJ金叉')]
    for k,lb in bool_keys:
        wr=sum(x[k] for x in wins)/len(wins)*100
        lr=sum(x[k] for x in fails)/len(fails)*100
        print(f'{lb:<10} {wr:>9.1f}% {lr:>9.1f}% {wr-lr:>+8.1f}%')
    
    # 不达标特征总结
    print(f'\n❌ 不达标天特征:')
    for k,lb in keys[:6]:
        wm=sum(x[k] for x in wins)/len(wins)
        lm=sum(x[k] for x in fails)/len(fails)
        diff=wm-lm
        if abs(diff)>0.3:  # 有实质差异的
            if diff>0: print(f'  达标方{lb}更高 (差+{diff:.1f})')
            else: print(f'  不达标方{lb}更高 (差{diff:.1f})')
    
    # 看看不达标天里，跌的冠军和池里最优的差距
    print(f'\n📊 不达标日: 冠军 vs 池内最优:')
    for dt in dates:
        s=data.get(dt,[]); m=cm(s)
        if m!=mk: continue
        pool=None
        for lv in levels:
            p=fl(s,lv)
            if len(p)>8: pool=p; break
        if not pool: continue
        for x in pool: x['sc']=sf(x)
        pool.sort(key=lambda x: -x['sc'])
        c=pool[0]
        if c['nh']<2.5:
            # 找池里达标的天花板
            best_nh=max(x['nh'] for x in pool)
            print(f'  冠军{c["nm"]}({c["nh"]:.1f}%) 池最高{best_nh:.1f}% 差{best_nh-c["nh"]:.1f}%')
