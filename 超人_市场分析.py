"""分析不同市场月份候选池质量"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())

def get_nxt(code, date):
    fp=os.path.join(CACHE_DIR,f'{code}.json')
    if not os.path.exists(fp): return 0
    try:
        with open(fp) as f: kdata=json.load(f)
        idx=next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is not None and idx+1 < len(kdata):
            bc=kdata[idx]['close']
            return (kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
    except: return 0

P_MIN,P_MAX=5,8;VR_MIN,VR_MAX=0.8,2.0;HSL_MIN,HSL_MAX=5,15;SZ_MAX=300;CL_MIN,CL_MAX=60,90;J_MAX=100

print("=== 2026年每月候选池质量 ===", flush=True)
print(f"{'月份':<10} {'天数':>4} {'候选只数':>8} {'均涨%':>6} {'达2.5%':>8} {'达5%':>6}", flush=True)
print('-'*46, flush=True)

for month in ['2026-01','2026-02','2026-03','2026-04','2026-05']:
    mdates=[x for x in dates if x.startswith(month)]
    all_pool=[]
    for dt in mdates:
        for s in data.get(dt,[]):
            code,p=s['code'],s['p']
            if p<P_MIN or p>P_MAX: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<VR_MIN or vr>VR_MAX: continue
            ri=real.get(code)
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<HSL_MIN or hsl>HSL_MAX: continue
            sz=(ri.get('shizhi',0) or 0)
            if sz>=SZ_MAX: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv=s.get('j_val',0) or 0
            if jv>J_MAX: continue
            cl=s.get('cl',0)
            if cl<CL_MIN or cl>CL_MAX: continue
            nh=get_nxt(code,dt)
            if nh>0: all_pool.append(nh)
    
    if all_pool:
        w25=sum(1 for x in all_pool if x>=2.5)*100/len(all_pool)
        w5=sum(1 for x in all_pool if x>=5)*100/len(all_pool)
        avg=sum(all_pool)/len(all_pool)
        print(f"{month:<10} {len(mdates):>4} {len(all_pool):>8} {avg:>6.2f} {w25:>7.1f}% {w5:>5.1f}%", flush=True)

# 看大盘涨跌和候选池质量的关系
print("\n=== 大盘涨跌日 vs 候选池质量 ===", flush=True)
# 简易大盘判断：看当天所有股票的平均涨跌幅
up_days=[]; down_days=[]
for dt in dates:
    if not dt.startswith('2026'): continue
    stocks=data.get(dt,[])
    if not stocks: continue
    avg_p=sum(s.get('p',0) or 0 for s in stocks)/len(stocks)
    
    cand=[]
    P_MIN,P_MAX=5,8;VR_MIN,VR_MAX=0.8,2.0;HSL_MIN,HSL_MAX=5,15;SZ_MAX=300;CL_MIN,CL_MAX=60,90;J_MAX=100
    for s in stocks:
        code,p=s['code'],s['p']
        if p<P_MIN or p>P_MAX: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<VR_MIN or vr>VR_MAX: continue
        ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<HSL_MIN or hsl>HSL_MAX: continue
        sz=(ri.get('shizhi',0) or 0)
        if sz>=SZ_MAX: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>J_MAX: continue
        cl=s.get('cl',0)
        if cl<CL_MIN or cl>CL_MAX: continue
        nh=get_nxt(code,dt)
        if nh>0: cand.append(nh)
    
    if cand:
        w25=sum(1 for x in cand if x>=2.5)*100/len(cand)
        if avg_p > 0:
            up_days.append(w25)
        else:
            down_days.append(w25)

if up_days: print(f"大盘涨日({len(up_days)}天): 候选池达2.5% {sum(up_days)/len(up_days):.1f}%")
if down_days: print(f"大盘跌日({len(down_days)}天): 候选池达2.5% {sum(down_days)/len(down_days):.1f}%")
