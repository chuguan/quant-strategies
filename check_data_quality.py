"""数据质量检查：n字段覆盖情况"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']

dates=[x for x in sorted(data.keys()) if x>='2025-01-01']
print(f"2025-01 ~ 2026-05共{len(dates)}个交易日", flush=True)

# 检查n字段在各月的情况
print(f"\n{'月份':<10} {'天数':>4} {'总股数':>6} {'有n':>6} {'n>0%':>6} {'n均值':>6} {'n中位':>6}", flush=True)
print('-'*50, flush=True)

for month in sorted(set(d[:7] for d in dates)):
    mdates=[d for d in dates if d.startswith(month)]
    total_stocks=0; has_n=0; n_pos=0; n_vals=[]
    for dt in mdates:
        for s in data.get(dt,[]):
            total_stocks+=1
            n=s.get('n',0) or 0
            if n!=0: has_n+=1
            if n>0: n_pos+=1
            if n!=0: n_vals.append(n)
    
    avg_n=sum(n_vals)/len(n_vals) if n_vals else 0
    med_n=sorted(n_vals)[len(n_vals)//2] if n_vals else 0
    n_rate=has_n*100/total_stocks if total_stocks else 0
    n_pos_rate=n_pos*100/has_n if has_n else 0
    print(f"{month:<10} {len(mdates):>4} {total_stocks:>6} {has_n:>6} {n_rate:>5.0f}% {avg_n:>+5.1f}% {med_n:>+5.1f}%", flush=True)

# 看看我们的选股条件下，n字段的可用性
print(f"\n=== 选股条件后n字段有效性 ===", flush=True)
import time
P_MIN,P_MAX=5,8;VR_MIN,VR_MAX=0.8,2.0;HSL_MIN,HSL_MAX=5,15;SZ_MAX=300;CL_MIN,CL_MAX=60,90;J_MAX=100

for month in ['2025-01','2025-02','2025-03','2025-04','2025-08','2025-12','2026-05']:
    mdates=[d for d in dates if d.startswith(month)]
    cand_days=0; has_n_days=0
    for dt in mdates:
        cand=[]
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
            n=s.get('n',0) or 0
            cand.append((code,p,cl,n))
        
        if cand:
            cand_days+=1
            nz=sum(1 for c in cand if c[3]!=0)
            if nz>0: has_n_days+=1
    
    print(f"{month}: {cand_days}天有候选, {has_n_days}天有n数据", flush=True)
