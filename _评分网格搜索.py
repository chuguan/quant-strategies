"""
评分权重网格搜索 - 目标30天≥85%, 80天≥70%
针对各行情独立性测试权重组合
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

def run_test(mk, score_fn, label):
    levels=mods[mk].LEVELS
    all_days=[]; total_days=0
    for dt in dates:
        s=data.get(dt,[]); m=cm(s)
        if m!=mk: continue
        total_days+=1
        pool=None
        for lv in levels:
            p=fl(s,lv)
            if len(p)>8: pool=p; break
        if not pool: continue
        for x in pool: x['sc']=score_fn(x)
        pool.sort(key=lambda x: -x['sc'])
        all_days.append(pool[0])
    
    total=len(all_days)
    rate=sum(1 for d in all_days if d['nh']>=2.5)/total*100 if total else 0
    r30=sum(1 for d in all_days[-30:] if d['nh']>=2.5)/min(30,total)*100 if total else 0 if min(30,total)>0 else 0
    r80=sum(1 for d in all_days[-80:] if d['nh']>=2.5)/min(80,total)*100 if total else 0 if min(80,total)>0 else 0
    return rate, r30, r80, all_days

# 真实涨日 - 试权重组合
print("真实涨日评分网格:")
best_r,best_r30,best_r80=None,None,None
best_fn=None;best_label=''
for pw in [0.8,1.0,1.2,1.5]:
    for clw in [0.05,0.1,0.2]:
        for macd_w in [0.3,0.5]:
            for ma5_b in [0,2,3]:
                for cl_bonus in [0,2]:
                    for cl_pen in [0,-1,-3]:
                        for overdraft in [-5,-8,-10]:
                            def fn(pw=pw,clw=clw,mw=macd_w,ma5=ma5_b,cb=cl_bonus,cp=cl_pen,od=overdraft):
                                def f(stock):
                                    s=stock
                                    ms=0
                                    if s['mg'] and s['dif']>0.5: ms=10
                                    elif s['mg'] and s['dif']>0.2: ms=8
                                    elif s['mg']: ms=6
                                    elif s['dif']>0.5: ms=4
                                    elif s['dif']>0: ms=2
                                    ps2=min(10,max(1,11-s['buy_c']/10)) if s['buy_c'] else 0
                                    sc=s['p']*pw+s['cl']*clw+ps2*0.3+ms*mw
                                    sc+=(ma5 if s['a5'] else 0)
                                    if cb and 65<=s['cl']<=83: sc+=cb
                                    if cp and 70<=s['cl']<80: sc+=cp
                                    if s['p']>5 and s['cl']>80: sc+=od
                                    if s['dif']>0.5: sc+=3
                                    if s['mg']: sc+=3
                                    return round(sc,1)
                                return f
                            lbl=f"p{pw}_cl{clw}_m{macd_w}_m5{ma5_b}_b{cl_bonus}_p{cl_pen}_od{overdraft}"
                            r,r30,r80,dl=run_test('real_up',fn(pw,clw,macd_w,ma5_b,cl_bonus,cl_pen,overdraft),lbl)
                            if best_r is None or r30>best_r30:
                                best_r, best_r30, best_r80 = r,r30,r80
                                best_fn=fn(pw,clw,macd_w,ma5_b,cl_bonus,cl_pen,overdraft)
                                best_label=lbl
                                print(f"  新最佳: 全{r:.1f}% 30{r30:.1f}% 80{r80:.1f}% {lbl}")

print(f"\n真实涨日最优: {best_label}")
print(f"  全量: {best_r:.1f}%  30天: {best_r30:.1f}%  80天: {best_r80:.1f}%")
_,_,_,dl=run_test('real_up',best_fn,'')
print("\n最近30天:")
for d in dl[-30:]:
    t='✅' if d['nh']>=2.5 else '❌'
    print(f"  {d['nm']:<10} 今涨{d['p']:+.1f}% 买入{d['buy_c']:>8.2f} 次日最高{d['nh']:+.1f}% {t}")
