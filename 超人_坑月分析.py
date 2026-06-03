"""分析低潮月份（8月/10月）与好月份差异——找提胜率方向"""
import pickle, json, os
CACHE_DIR=os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

P_MIN,P_MAX=5,8;VR_MIN,VR_MAX=0.8,2.0;HSL_MIN,HSL_MAX=5,15;SZ_MAX=300;CL_MIN,CL_MAX=60,90;J_MAX=100

def get_candidates(dt):
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
        cand.append(s)
    return cand

# 比较好月份vs差月份
bad_months=['2025-08','2025-10','2025-06']
good_months=['2025-02','2026-04','2026-05']

print("=== 好月份 vs 差月份 候选池特征对比 ===", flush=True)
print(f"\n{'指标':<20} {'好月均':>10} {'差月均':>10} {'差异':>8}",flush=True)
print('-'*50,flush=True)

metrics=['p','cl','vr','dif_val','j_val']
mnames=['涨幅%','CL%','量比','DIF','J值']
for met,mn in zip(metrics,mnames):
    good_vals=[]; bad_vals=[]
    for dt in dates:
        month=dt[:7]
        cand=get_candidates(dt)
        for s in cand:
            v=s.get(met,0) or 0
            if month in good_months: good_vals.append(v)
            elif month in bad_months: bad_vals.append(v)
    if good_vals and bad_vals:
        ga=sum(good_vals)/len(good_vals)
        ba=sum(bad_vals)/len(bad_vals)
        diff=ga-ba
        print(f"{mn:<20} {ga:>10.2f} {ba:>10.2f} {diff:>+8.2f}",flush=True)

# 再看胜出的票有什么特征
print(f"\n=== 差月份中 赢的票 vs 输的票 差异 ===",flush=True)
print(f"{'指标':<20} {'赢家均':>10} {'输家均':>10} {'差异':>8}",flush=True)
print('-'*50,flush=True)

win_vals={m:[] for m in metrics}
lose_vals={m:[] for m in metrics}
win_nl=[]; lose_nl=[]

for dt in dates:
    month=dt[:7]
    if month not in bad_months: continue
    cand=get_candidates(dt)
    if not cand: continue
    
    all_p=[x['p'] for x in data.get(dt,[]) if 'p' in x]
    avg_mkt=sum(all_p)/len(all_p) if all_p else 0
    mkt='up' if avg_mkt>0.5 else ('down' if avg_mkt<-0.5 else 'flat')
    
    for s in cand:
        n=s.get('n',0) or 0
        if n>=2.5:
            for m in metrics: win_vals[m].append(s.get(m,0) or 0)
        else:
            for m in metrics: lose_vals[m].append(s.get(m,0) or 0)

for met,mn in zip(metrics,mnames):
    if win_vals[met] and lose_vals[met]:
        wa=sum(win_vals[met])/len(win_vals[met])
        la=sum(lose_vals[met])/len(lose_vals[met])
        diff=wa-la
        print(f"{mn:<20} {wa:>10.2f} {la:>10.2f} {diff:>+8.2f}",flush=True)

# 看看差月份大盘环境
print(f"\n=== 差月份大盘环境 ===",flush=True)
for month in bad_months:
    mdates=[d for d in dates if d.startswith(month)]
    mkt_days={'up':0,'down':0,'flat':0}
    for dt in mdates:
        all_p=[x['p'] for x in data.get(dt,[]) if 'p' in x]
        avg=sum(all_p)/len(all_p) if all_p else 0
        if avg>0.5: mkt_days['up']+=1
        elif avg<-0.5: mkt_days['down']+=1
        else: mkt_days['flat']+=1
    print(f"{month}: 涨{mkt_days['up']}天 跌{mkt_days['down']}天 横{mkt_days['flat']}天",flush=True)

# 差月份里，赢的票的CL、量比、涨幅分布
print(f"\n=== 差月份赢家的特征分布 ===",flush=True)
win_cl=[]; win_vr=[]; win_p=[]; win_hsl=[]; win_sz=[]
for dt in dates:
    month=dt[:7]
    if month not in bad_months: continue
    for s in get_candidates(dt):
        n=s.get('n',0) or 0
        if n>=2.5:
            win_cl.append(s.get('cl',0))
            win_vr.append(s.get('vol_ratio',0) or 0)
            win_p.append(s['p'])
            ri=real.get(s['code'])
            if ri:
                win_hsl.append(ri.get('hsl',0) or 0)
                win_sz.append(ri.get('shizhi',0) or 0)

if win_cl:
    print(f"CL: 均{sum(win_cl)/len(win_cl):.1f}% 中{sorted(win_cl)[len(win_cl)//2]:.1f}%",flush=True)
    print(f"涨幅: 均{sum(win_p)/len(win_p):.1f}%",flush=True)
    print(f"量比: 均{sum(win_vr)/len(win_vr):.2f} 中{sorted(win_vr)[len(win_vr)//2]:.2f}",flush=True)
    print(f"换手: 均{sum(win_hsl)/len(win_hsl):.1f}%",flush=True)
    print(f"市值: 均{sum(win_sz)/len(win_sz):.0f}亿",flush=True)
    
    # CL分段胜率
    for cl_range in [(60,70),(70,80),(80,90)]:
        r=[x for x in win_cl if cl_range[0]<=x<cl_range[1]]
        print(f"  CL{cl_range[0]}~{cl_range[1]}: {len(r)}只 均{sum(r)/len(r):.1f}%" if r else "",flush=True)
