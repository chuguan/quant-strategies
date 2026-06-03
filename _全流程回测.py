"""
完整回测：L1→L5分级选股 + 评分 → 冠军胜率
输出近30天逐日明细
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

def classify_mkt(stocks):
    ps=[s.get('p',0) or 0 for s in stocks]
    if not ps: return 'flat'
    ap=sum(ps)/len(ps)
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    av=sum(vrs)/len(vrs) if vrs else 0
    ht=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if ht<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

# 加载4个评分策略
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

def filter_level(s_list, lv):
    """多维度过滤+额外条件"""
    pool=[]
    for sx in s_list:
        code=sx.get('code','')
        p=(sx.get('p',0) or 0)
        if p<lv['p_min'] or p>lv['p_max']: continue
        if p>=8: continue  # 基本准则
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
        
        # 多维额外过滤
        if lv.get('a5_req',0) and (sx.get('above_ma5',0) or 0)<1: continue
        if lv.get('kdj_g_req',0) and (sx.get('kdj_golden',0) or 0)<1: continue
        if lv.get('no_macd',0) and (sx.get('macd_golden',0) or 0)>=1: continue
        
        pool.append({
            'code':code,'nm':names.get(code,'')[:6],'p':p,
            'cl':cl,'vr':vr,'hsl':(ri.get('hsl',0) or 0) if ri else 0,
            'dif':(sx.get('dif_val',0) or 0),'mg':(sx.get('macd_golden',0) or 0),
            'a5':(sx.get('above_ma5',0) or 0),'wrv':(sx.get('wr',0) or 0),
            'jv':(sx.get('j_val',0) or 0),'kv':(sx.get('k_val',0) or 0),
            'dv':(sx.get('d_val',0) or 0),'kdj_g':(sx.get('kdj_golden',0) or 0),
            'buy_c':(sx.get('close',0) or 0),'nh':nh,
        })
    return pool

def run_backtest(days, mkt_key):
    """对指定行情，逐天分级选股+评分"""
    levels = mods[mkt_key].LEVELS
    score_fn = score_fns[mkt_key]
    name = mk_names[mkt_key]
    
    results=[]
    for dt in days:
        s=data.get(dt,[])
        m=classify_mkt(s)
        if m!=mkt_key: continue
        
        # 分级选股
        pool=None; used_lvl=None
        for lv in levels:
            p=filter_level(s, lv)
            if len(p)>8:
                pool=p; used_lvl=lv['name']; break
        
        if not pool:
            results.append({'dt':dt,'lvl':'弃权','n':0,'pool_rate':0,'champ':None})
            continue
        
        # 池质量
        pool_qual=sum(1 for x in pool if x['nh']>=2.5)
        pool_rate=pool_qual/len(pool)*100
        
        # 评分排序
        for x in pool:
            x['sc']=score_fn(x)
        pool.sort(key=lambda x: -x['sc'])
        champ=pool[0]
        
        results.append({
            'dt':dt,'lvl':used_lvl,'n':len(pool),
            'pool_rate':pool_rate,'pool_qual':pool_qual,
            'champ':{'nm':champ['nm'],'code':champ['code'],'sc':champ['sc'],
                     'buy_c':champ['buy_c'],'nh':champ['nh'],'p':champ['p']}
        })
    
    return results, name

# 近30天（避开缓存最后一天无次日数据）
recent=dates[-35:-5]

for mk in ['real_up','down','flat','fake_up']:
    results, name = run_backtest(recent, mk)
    if not results: continue
    
    print(f'\n{"="*80}')
    print(f'{name} | 共{len(results)}天')
    print(f'{"="*80}')
    
    # 逐日明细
    print(f"{'日期':<12} {'级别':<5} {'候选':>5} {'池质量':>8} {'冠军':<10} {'评分':>5} {'买入':>8} {'次日最高':>8}")
    print('-'*80)
    for r in results:
        if not r['champ']:
            print(f"{r['dt']:<12} {'弃权':<5} {'—':>5} {'—':>8} {'—':<10} {'—':>5} {'—':>8} {'—':>8}")
        else:
            c=r['champ']
            nh_str=f"{c['nh']:.1f}%"
            if c['nh']>=2.5: nh_str+=' ✅'
            print(f"{r['dt']:<12} {r['lvl']:<5} {r['n']:>5} {r['pool_rate']:>7.1f}% {c['nm']:<10} {c['sc']:>5.1f} {c['buy_c']:>8.2f} {nh_str:>12}")
    
    # 汇总
    total=len([r for r in results if r['champ']])
    wins=sum(1 for r in results if r['champ'] and r['champ']['nh']>=2.5)
    champ_rate=wins/total*100 if total else 0
    avg_pool=sum(r['pool_rate'] for r in results if r['champ'])/total if total else 0
    
    print(f'\n  汇总: 出票{total}/{len(results)}天({total/len(results)*100:.0f}%)')
    print(f'  池均质量: {avg_pool:.1f}%')
    print(f'  冠军胜率(≥2.5%): {champ_rate:.1f}% ({wins}/{total})')
    
    # 近30天
    last30=[r for r in results if r['champ']][-30:]
    if last30:
        w30=sum(1 for r in last30 if r['champ']['nh']>=2.5)
        print(f'  最近30天冠军胜率: {w30/len(last30)*100:.1f}% ({w30}/{len(last30)})')
