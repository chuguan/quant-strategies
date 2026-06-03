import pickle, os, json, statistics

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
KC = {}
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
all_days = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]

def gk(code):
    if code not in KC:
        fp = os.path.join(CACHE_DIR, code+'.json')
        KC[code] = json.load(open(fp)) if os.path.exists(fp) else None
    return KC[code]

def is_ht(code, dt):
    kd = gk(code)
    if not kd: return False
    for i,d in enumerate(kd):
        if d['date']!=dt: continue
        if i<8: return False
        kw=kd[i-7:i+1]; t=kw[-1]
        for j in range(len(kw)-2,-1,-1):
            prv=kw[j-1] if j>0 else t
            pct=(kw[j]['close']-prv['close'])/prv['close']*100
            if pct>=5:
                rt=len(kw)-j-2
                if 1<=rt<=4:
                    vols=[d['volume'] for d in kw[j+1:-1]]
                    if vols and max(vols)<=kw[j]['volume']*1.3 and t['volume']>=(statistics.mean(vols)or 1)*1.1 and t['close']>t['open']:
                        return True
                break
    return False

def run_eval(p):
    hn,hnv=[],[]
    for dt in all_days:
        pool=[]
        for st in data.get(dt,[]):
            cd,px=st['code'],st['p']
            if px<p['p_min'] or px>p['p_max']: continue
            vr=st.get('vol_ratio',0)or 0
            if vr<p['vr_min'] or vr>p['vr_max']: continue
            ri=real.get(cd)
            if not ri: continue
            hsl=(ri.get('hsl',0)or 0)
            if hsl<p['hsl_min'] or hsl>p['hsl_max']: continue
            if (ri.get('shizhi',0)or 0)>p['sz_max']: continue
            nm=names.get(cd,'')
            if 'ST' in nm or '*ST' in nm: continue
            if (st.get('j_val',0)or 0)>100: continue
            nv=st.get('n',0)or 0
            pool.append((px,nv,cd))
        if not pool: continue
        pool.sort(key=lambda x:-x[0])
        htf=[(x,nv) for x,nv,cd in pool if is_ht(cd,dt)]
        if htf:
            b=max(htf,key=lambda x:x[0])[1]
            hn.append(b); hnv.append(b)
        else:
            hn.append(pool[0][1])
    def stats(nvl):
        n=len(nvl)
        return n, sum(1 for v in nvl if v>=2.5)*100/n, sum(1 for v in nvl if v>=5)*100/n, statistics.mean(nvl) if nvl else 0
    return stats(hn), stats(hnv)

base={'p_min':5,'p_max':7,'vr_min':0.8,'vr_max':1.5,'hsl_min':5,'hsl_max':8,'sz_max':80}

tests = [
    ('市值<80(基准)', dict()),
    ('市值<60', dict(sz_max=60)),
    ('市值<100', dict(sz_max=100)),
    ('换手<10', dict(hsl_max=10)),
    ('换手<12', dict(hsl_max=12)),
    ('涨5~7.5%', dict(p_max=7.5)),
    ('涨5~7.5%+量1.0~1.5', dict(p_max=7.5, vr_min=1.0)),
    ('涨5~7%+量1.0~1.5', dict(vr_min=1.0)),
    ('涨6~7%+量0.8~1.5', dict(p_min=6)),
    ('涨5~7%+换手<10', dict(hsl_max=10)),
    ('涨5~7%+量0.8~2.0', dict(vr_max=2.0)),
    ('涨5~7%+量0.8~2.0+换手<10', dict(vr_max=2.0, hsl_max=10)),
    ('涨5~7%+市值<100+换手<10', dict(sz_max=100, hsl_max=10)),
    ('涨5~7%+市值<60+换手<10', dict(sz_max=60, hsl_max=10)),
    ('涨5~7%+市值<60+量1.0~1.5', dict(sz_max=60, vr_min=1.0)),
]

print('%-40s | %s | %s' % ('参数','双模式','回马枪'))
print('-'*85)
for nm,ch in tests:
    p=dict(base); p.update(ch)
    hy,htv=run_eval(p)
    sig='🔥' if hy[1]>=70 else('✅' if hy[1]>=67 else'')
    print('%s %-38s | %5.1f%% %2d天 | %5.1f%% %2d天' % (sig,nm,hy[1],hy[0],htv[1],htv[0]))
