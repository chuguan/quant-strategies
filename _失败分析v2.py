"""
失败分析 + 含当日涨幅(p) + 虚涨日全量
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

recent=dates[-35:-5]

for mk in ['real_up','down','flat','fake_up']:
    levels=mods[mk].LEVELS
    sf=score_fns[mk]
    name=mk_names[mk]
    
    print(f'\n{"="*70}')
    print(f'{name}')
    print(f'{"="*70}')
    print(f'{"日期":<12} {"级":<3} {"候选":>4} {"池质%":>6} {"冠军":<10} {"今涨%":>6} {"评分":>5} {"买入":>8} {"次日最":>6}')
    print('-'*70)
    
    wins=fails=0
    fail_list=[]
    win_list=[]
    total_days=0
    
    for dt in dates:  # 全量
        s=data.get(dt,[])
        m=classify_mkt(s)
        if m!=mk: continue
        total_days+=1
        
        pool=None; used_lvl=None
        for lv in levels:
            p=filter_level(s, lv)
            if len(p)>8: pool=p; used_lvl=lv['name']; break
        
        if not pool:
            if total_days<=30:
                print(f'{dt:<12} {"—":>3} {"—":>4} {"—":>6} {"弃权":<10}')
            continue
        
        pool_qual=sum(1 for x in pool if x['nh']>=2.5)
        pool_rate=pool_qual/len(pool)*100
        
        for x in pool: x['sc']=sf(x)
        pool.sort(key=lambda x: -x['sc'])
        c=pool[0]
        
        if total_days<=30:
            nh_str=f"{c['nh']:.1f}%"
            tag='✅' if c['nh']>=2.5 else '❌'
            print(f'{dt:<12} {used_lvl:<3} {len(pool):>4} {pool_rate:>5.1f}% {c["nm"]:<10} {c["p"]:>5.1f}% {c["sc"]:>5.1f} {c["buy_c"]:>8.2f} {nh_str:>5} {tag}')
        
        if c['nh']>=2.5:
            wins+=1
            win_list.append(c)
        else:
            fails+=1
            fail_list.append(c)
    
    total=wins+fails
    print(f'\n  总: {total_days}天, 出票{total}/{total_days}天({total/total_days*100:.0f}%), 冠军{wins}/{total}={wins/total*100:.1f}%')
    
    if fail_list:
        print(f'\n  ❌ 失败天({len(fail_list)}天):')
        for f in fail_list[:10]:
            print(f'    {f["nm"]:<10} 今涨{f["p"]:+.1f}% cl={f["cl"]:.0f} vr={f["vr"]:.1f} hsl={f["hsl"]:.1f}% mg={f["mg"]} 评分{f["sc"]:.1f} 次日{f["nh"]:+.1f}%')
        if len(fail_list)>10:
            print(f'    ... 还有{len(fail_list)-10}天')
        
        if win_list:
            print(f'\n  赢家vs输家特征:')
            for key,lb in [('p','今涨'),('cl','CL'),('vr','量比'),('hsl','换手'),('sc','评分')]:
                wm=sum(x[key] for x in win_list)/len(win_list)
                lm=sum(x[key] for x in fail_list)/len(fail_list)
                print(f'    {lb}: 赢家{wm:.1f} vs 输家{lm:.1f} (差{+wm-lm:+.1f})')
            for key,lb in [('mg','MACD金叉'),('a5','站MA5')]:
                wr=sum(x[key] for x in win_list)/len(win_list)*100
                lr=sum(x[key] for x in fail_list)/len(fail_list)*100
                print(f'    {lb}: 赢家{wr:.0f}% vs 输家{lr:.0f}% (差{+wr-lr:+.0f}%)')
