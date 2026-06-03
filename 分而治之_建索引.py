"""建索引v3 — 补充hsl/sz字段"""
import pickle, json, os, sys, time
from collections import defaultdict

SCRIPTS_DIR=os.path.expanduser('~/AppData/Local/hermes/scripts')
IDX_FILE=os.path.join(SCRIPTS_DIR,'分而治之_日期索引.pkl')
CACHE_FILE=os.path.join(SCRIPTS_DIR,'release','分而治之','indicator_cache.pkl')

t0=time.time()

# 读缓存
with open(CACHE_FILE,'rb') as f:
    ic=pickle.load(f)['data']
print(f'缓存: {len(ic)}只 ({time.time()-t0:.0f}s)', flush=True)

# 读K线
CACHE_DIR=os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
ck={}
for fn in os.listdir(CACHE_DIR):
    if not fn.endswith('.json'): continue
    cd=fn.replace('sh','').replace('sz','').replace('.json','')
    try:
        with open(os.path.join(CACHE_DIR,fn)) as f:
            k=json.load(f)
        bd={}
        for r in k:
            bd[r['date']]={'h':r['high'],'c':r['close']}
            bd[r['date'].replace('-','')]={'h':r['high'],'c':r['close']}
        ck[cd]=bd
    except: pass
print(f'K线: {len(ck)}只 ({time.time()-t0:.0f}s)', flush=True)

# 读实时缓存（取hsl/sz）
try:
    rt_path=os.path.join(SCRIPTS_DIR,'archive','V2703','cache','realtime_cache.pkl')
    with open(rt_path,'rb') as f:
        rt=pickle.load(f)
    hsl_map=rt.get('hsl',{})
    sz_map=rt.get('sz',{})
except:
    hsl_map={}
    sz_map={}
print(f'实时数据: hsl={len(hsl_map)}, sz={len(sz_map)} ({time.time()-t0:.0f}s)', flush=True)

# 建索引
fm={'p':'p','cl':'cl','vr':'vr','dif':'dif','mg':'mg','a5':'a5',
    'wrv':'wrv','kdj_g':'kdj_g','pos_in_day':'pos_in_day',
    'close':'buy_c','j':'jv','k':'kv','d':'dv'}
daily=defaultdict(list)
cnt=0
for code,sd in ic.items():
    dl=sd['dates']
    hsl_v=hsl_map.get(code,0) or 0
    sz_v=sz_map.get(code,0) or 0
    for i,dt in enumerate(dl):
        cnt+=1
        st={'code':code,'hsl':hsl_v,'sz':sz_v}
        for ck2,sk in fm.items():
            arr=sd.get(ck2)
            st[sk]=arr[i] if arr and i<len(arr) else 0
        daily[dt].append(st)

di={'daily':dict(daily),'dates':sorted(d for d in daily if '2025-01-01'<=d<'2026-06-01'),'kline':ck}
with open(IDX_FILE,'wb') as f: pickle.dump(di,f)
print(f'✅ {len(di["dates"])}天, {cnt}条 ({time.time()-t0:.0f}s)', flush=True)
