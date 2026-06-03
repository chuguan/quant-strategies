"""v11动态扩大：每日最低选股数"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target = [d for d in dates if d >= '2026-01-01']

def ps(p):return min(10,max(1,11-p/10))

# 标准条件
P1=(5,8); V1=(0.8,2.0); H1=(5,15); C1=(60,90)
# 扩大条件
P2=(4,9); V2=(0.6,2.5); H2=(3,20); C2=(50,95)
SZ=300; JM=100

results=[]
for dt in target:
    stocks=data.get(dt,[])
    if not stocks: continue
    all_p=[x['p'] for x in stocks if 'p' in x]
    avg_mkt=sum(all_p)/len(all_p) if all_p else 0
    if avg_mkt>0.5: mkt='up'
    elif avg_mkt<-0.5: mkt='down'
    else: mkt='flat'
    
    cand=[]
    for s in stocks:
        code,p=s['code'],s['p']
        ri=real.get(code)
        if not ri: continue
        sz2=(ri.get('shizhi',0) or 0)
        if sz2>=SZ: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>JM: continue
        
        # 先用标准条件
        pm=5; pM=8; vm=0.8; vM=2.0; hm=5; hM=15; cm=60; cM=90
        use_expanded=False
        
        vr=s.get('vol_ratio',0) or 0
        hsl=(ri.get('hsl',0) or 0)
        cl=s.get('cl',0)
        
        if p<pm or p>pM:continue
        if vr<vm or vr>vM:continue
        if hsl<hm or hsl>hM:continue
        if cl<cm or cl>cM:continue
        
        cand.append((p,vr,hsl,cl,sz2,nm,code))
    
    # 判断是否需要扩大
    # 简化：只看当前有多少
    n_std=len(cand)
    
    # 扩大后的候选
    cand_widen=[]
    for s in stocks:
        code,p=s['code'],s['p']
        ri=real.get(code)
        if not ri: continue
        sz2=(ri.get('shizhi',0) or 0)
        if sz2>=SZ: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>JM: continue
        vr=s.get('vol_ratio',0) or 0
        hsl=(ri.get('hsl',0) or 0)
        cl=s.get('cl',0)
        
        if p<4 or p>9:continue
        if vr<0.6 or vr>2.5:continue
        if hsl<3 or hsl>20:continue
        if cl<50 or cl>95:continue
        
        cand_widen.append((p,vr,hsl,cl,sz2,nm,code))
    
    n_widen=len(cand_widen) if n_std<3 else n_std
    results.append((dt,mkt,n_std,n_widen,cand_widen[:3] if n_std<3 else cand[:3]))

# 排序
results.sort(key=lambda x: x[3])  # 按扩大后数量排序

print("=== v11每日候选数（从少到多）===", flush=True)
print(f"{'日期':<12} {'行情':>4} {'标准':>5} {'最终':>5} {'Top3':<30}", flush=True)
print('-'*60, flush=True)

min_std=999; min_wid=999; min_std_dt=''; min_wid_dt=''
for dt,mkt,n_std,n_wid,top3 in results:
    if n_std<min_std: min_std=n_std; min_std_dt=dt
    if n_wid<min_wid: min_wid=n_wid; min_wid_dt=dt
    t3=' '.join([x[5][:6] for x in top3[:3]])
    print(f"{dt:<12} {mkt:>4} {n_std:>5} {n_wid:>5} {t3:<30}", flush=True)

print(f"\n标准条件最少: {min_std}只 ({min_std_dt})", flush=True)
print(f"扩大后最少: {min_wid}只 ({min_wid_dt})", flush=True)

# 统计
std_lt3=sum(1 for r in results if r[2]<3)
wid_lt3=sum(1 for r in results if r[3]<3)
wid_lt10=sum(1 for r in results if r[3]<10)
wid_lt5=sum(1 for r in results if r[3]<5)
print(f"\n标准条件<3只: {std_lt3}天", flush=True)
print(f"扩大后<3只: {wid_lt3}天 | <5只: {wid_lt5}天 | <10只: {wid_lt10}天", flush=True)
print(f"0候选: {sum(1 for r in results if r[2]==0)}天(标准) -> {sum(1 for r in results if r[3]==0)}天(扩大)", flush=True)
