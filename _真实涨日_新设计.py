"""
真实涨日重新设计 - 追强势策略
L1: p[5,7] 排MACD金叉 → 63.8%质量
L2: p[4,7] 排MACD金叉 → 57.9%
L3: p[3,7] 正常
L4: p[2,7] 保底
"""
import pickle, sys, os
sys.stdout.reconfigure(line_buffering=True)

with open(os.path.join(os.path.dirname(__file__), 'big_cache_full.pkl'), 'rb') as f:
    cache = pickle.load(f)
data = cache['data']
real_data = cache.get('real', {})
names = cache.get('names', {})

dates = sorted(x for x in data.keys() if '2025-06-01' <= x < '2026-06-01')
def cm(s):
    ps=[x.get('p',0) or 0 for x in s]
    if not ps: return ''
    ap=sum(ps)/len(ps)
    vrs=[x.get('vol_ratio',0) or 0 for x in s if x.get('vol_ratio',0)]
    av=sum(vrs)/len(vrs) if vrs else 0
    ht=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'real_up' if ht>=15 and av>=0.9 else ''
    return ''

real_sl=[data.get(dt,[]) for dt in dates if cm(data.get(dt,[]))=='real_up']

def check(s_list, p1,p2,v1,v2,c1,c2,h1,h2,sz,no_macd):
    pool=[];ok=tn=tq=0
    for sl in s_list:
        day_pool=[]
        for sx in sl:
            code=sx.get('code','')
            p=(sx.get('p',0) or 0)
            if p<p1 or p>p2: continue
            if p>=8: continue
            vr=(sx.get('vol_ratio',0) or 0)
            if vr<v1 or vr>v2: continue
            cl=(sx.get('cl',0) or 0)
            if cl<c1 or cl>c2: continue
            ri=real_data.get(code)
            if ri:
                hsl=(ri.get('hsl',0) or 0)
                if hsl<h1 or hsl>h2: continue
                szv=ri.get('shizhi',0) or 0
                if isinstance(szv,(int,float)) and szv>1: szv*=1e-8
                if szv>=sz: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            nh=(sx.get('n',0) or 0)
            if nh<=0: continue
            if no_macd and (sx.get('macd_golden',0) or 0)>=1: continue
            day_pool.append(nh)
        if len(day_pool)>8:
            ok+=1
            tn+=len(day_pool)
            tq+=sum(1 for nh in day_pool if nh>=2.5)
    return tq/tn*100 if tn else 0, tn/ok if ok else 0, ok, len(s_list)

# 新级别
levels = [
    ('L1(强势)', 5,7, 0.6,3.0, 50,95, 5,20,200, 1),
    ('L2(中强)', 4,7, 0.5,3.0, 40,95, 3,25,300, 1),
    ('L3(中等)', 3,7, 0.5,3.5, 30,98, 3,30,400, 0),
    ('L4(保底)', 2,7, 0.4,5.0, 20,100, 2,40,500, 0),
    ('L5(极限)', 0,7, 0.2,10, 10,100, 1,50,5000, 0),
]

total=len(real_sl)
print('真实涨日 新级别设计:')
for name, *params in levels:
    rate, avg, ok, _ = check(real_sl, *params)
    pct=ok/total*100
    print(f'  {name}: 质量{rate:5.1f}%  日均{avg:3.0f}只  出票{ok}/{total}天({pct:.0f}%)')

# 分级模拟
print(f'\n分级选股结果:')
day_r=[]
for sl in real_sl:
    sel=None
    used=None
    for name, *params in levels:
        p1,p2,v1,v2,c1,c2,h1,h2,sz,no_macd=params
        pool=[]
        for sx in sl:
            code=sx.get('code','')
            p=(sx.get('p',0) or 0)
            if p<p1 or p>p2: continue
            if p>=8: continue
            vr=(sx.get('vol_ratio',0) or 0)
            if vr<v1 or vr>v2: continue
            cl=(sx.get('cl',0) or 0)
            if cl<c1 or cl>c2: continue
            ri=real_data.get(code)
            if ri:
                hsl=(ri.get('hsl',0) or 0)
                if hsl<h1 or hsl>h2: continue
                szv=ri.get('shizhi',0) or 0
                if isinstance(szv,(int,float)) and szv>1: szv*=1e-8
                if szv>=sz: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            nh=(sx.get('n',0) or 0)
            if nh<=0: continue
            if no_macd and (sx.get('macd_golden',0) or 0)>=1: continue
            pool.append(nh)
        if len(pool)>8:
            sel=pool; used=name; break
    if sel:
        q=sum(1 for nh in sel if nh>=2.5)
        day_r.append({'n':len(sel),'qual':q,'lvl':used})
    else:
        day_r.append({'n':0,'qual':0,'lvl':'弃权'})

tn=sum(d['n'] for d in day_r)
tq=sum(d['qual'] for d in day_r)
rate=tq/tn*100 if tn else 0
iss=sum(1 for d in day_r if d['n']>0)
lu={}
for d in day_r:
    lu[d['lvl']]=lu.get(d['lvl'],0)+1
avg_cand=tn/iss if iss else 0
print(f'  最终池质量: {rate:.1f}% ({tq}/{tn})')
print(f'  平均出票: {avg_cand:.0f}只/天')
print(f'  出票率: {iss}/{total}天 ({iss/total*100:.0f}%)')
for l in ['L1(强势)','L2(中强)','L3(中等)','L4(保底)','弃权']:
    if l in lu:
        print(f'    {l}: {lu[l]}天')
