"""检查2025年数据质量"""
import pickle, json, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d['real'], d['names']
CACHE = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

# 1. K线数据范围
with open(os.path.join(CACHE, 'sh600000.json')) as f:
    kd = json.load(f)
print(f"K线数据: {len(kd)}条, {kd[0]['date']} ~ {kd[-1]['date']}")

# 2. 几个2025年日期，看候选数和次日数据
P_MIN,P_MAX=5,8; VR_MIN,VR_MAX=0.8,2.0
dates = ['2025-01-02','2025-03-03','2025-06-02','2025-09-01','2025-12-01']
for dt in dates:
    stocks = data.get(dt, [])
    cand = []
    nh_ok = 0
    for s in stocks:
        code,p=s['code'],s['p']
        if p<P_MIN or p>P_MAX: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<VR_MIN or vr>VR_MAX: continue
        fp=os.path.join(CACHE,f'{code}.json')
        if not os.path.exists(fp): continue
        with open(fp) as f: kdata=json.load(f)
        idx=next((i for i,k in enumerate(kdata) if k['date']==dt), None)
        if idx is not None and idx+1 < len(kdata):
            bc=kdata[idx]['close']
            nh=(kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
            if abs(nh) < 50:  # 过滤异常
                cand.append(nh)
                if nh >= 2.5: nh_ok += 1
    
    if cand:
        print(f"\n{dt}: {len(cand)}只候选有次高, 达2.5%:{nh_ok}({nh_ok*100/len(cand):.1f}%)")
        print(f"  涨幅范围: {min(cand):.1f}%~{max(cand):.1f}% 均{sum(cand)/len(cand):.2f}%")
    else:
        print(f"\n{dt}: 无候选(数据问题)")

# 3. 2026年对比
print("\n=== 2026年对比 ===")
for dt in ['2026-05-06','2026-05-15']:
    stocks = data.get(dt, [])
    cand = []
    for s in stocks:
        code,p=s['code'],s['p']
        if p<P_MIN or p>P_MAX: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<VR_MIN or vr>VR_MAX: continue
        fp=os.path.join(CACHE,f'{code}.json')
        if not os.path.exists(fp): continue
        with open(fp) as f: kdata=json.load(f)
        idx=next((i for i,k in enumerate(kdata) if k['date']==dt), None)
        if idx is not None and idx+1 < len(kdata):
            bc=kdata[idx]['close']
            nh=(kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
            if abs(nh) < 50:
                cand.append(nh)
    if cand:
        ok=sum(1 for x in cand if x>=2.5)
        print(f"{dt}: {len(cand)}只, 达2.5%:{ok}({ok*100/len(cand):.1f}%) 均{sum(cand)/len(cand):.2f}%")
