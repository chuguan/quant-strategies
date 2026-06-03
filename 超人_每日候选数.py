"""查看动态扩大后每日候选数量"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target = [d for d in dates if d >= '2026-01-01']

P1,P2=5,8; VR1,VR2=0.8,2.0; H1,H2=5,15; SZ=300; C1,C2=60,90; J=100
P1B,P2B=4,9; VR1B,VR2B=0.6,2.5; H1B,H2B=3,20; C1B,C2B=50,95

def count_cand(dt, relaxed=False):
    p1,p2=P1,P2; vr1,vr2=VR1,VR2; h1,h2=H1,H2; c1,c2=C1,C2
    if relaxed:
        p1,p2=P1B,P2B; vr1,vr2=VR1B,VR2B; h1,h2=H1B,H2B; c1,c2=C1B,C2B
    
    cand=0
    for s in data.get(dt,[]):
        code,p=s['code'],s['p']
        if p<p1 or p>p2: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<vr1 or vr>vr2: continue
        ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<h1 or hsl>h2: continue
        sz=(ri.get('shizhi',0) or 0)
        if sz>=SZ: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>J: continue
        cl=s.get('cl',0)
        if cl<c1 or cl>c2: continue
        cand+=1
    return cand

print(f"{'日期':<12} {'标准候选':>6} {'扩大候选':>6} {'是否扩大':>6}", flush=True)
print('-'*36, flush=True)

total_std=0; total_exp=0; expand_count=0; std_counts=[]; exp_counts=[]
for dt in target:
    std=count_cand(dt, relaxed=False)
    exp=count_cand(dt, relaxed=True)
    total_std+=std; total_exp+=exp
    std_counts.append(std); exp_counts.append(exp)
    
    if std<3:
        expand=True
        expand_count+=1
        tag='✅扩大'
    else:
        expand=False
        tag='—'
    
    if std<3 or std>30:
        print(f"{dt}: {std:>6} {exp:>6} {tag:>6}", flush=True)

print(f"\n=== 统计 ===", flush=True)
print(f"标准: 均{total_std/len(target):.1f}只/天, 中位数{sorted(std_counts)[len(std_counts)//2]}只", flush=True)
print(f"扩大: 均{total_exp/len(target):.1f}只/天, 中位数{sorted(exp_counts)[len(exp_counts)//2]}只", flush=True)
print(f"需扩大天数: {expand_count}/{len(target)}", flush=True)
print(f"候选0天: {sum(1 for x in std_counts if x==0)}/{len(target)}", flush=True)
print(f"候选1~2天: {sum(1 for x in std_counts if 1<=x<=2)}/{len(target)}", flush=True)
print(f"候选3~5天: {sum(1 for x in std_counts if 3<=x<=5)}/{len(target)}", flush=True)
print(f"候选6~10天: {sum(1 for x in std_counts if 6<=x<=10)}/{len(target)}", flush=True)
print(f"候选>10天: {sum(1 for x in std_counts if x>10)}/{len(target)}", flush=True)
