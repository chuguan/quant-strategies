"""分析：为什么近28天(4月~5月)胜率远高于1月~3月"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
early = [d for d in dates if '2026-01' <= d <= '2026-03']
late = [d for d in dates if d >= '2026-04-10']  # 近28天

def get_nxt(code, date):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 0, 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is not None and idx+1 < len(kdata):
            bc = kdata[idx]['close']
            return ((kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0,
                    (kdata[idx+1]['close']/bc-1)*100 if bc>0 else 0)
    except: return 0, 0

p_min,p_max=5,8; vr_min,vr_max=0.8,2.0; hsl_min,hsl_max=5,15; sz_max=300; cl_min,cl_max=60,90; j_max=100

print("=" * 80)
print("对比：1~3月（低胜率期） vs 4~5月（高胜率期）")
print("=" * 80)

for label, period in [("1~3月(低胜率)", early), ("4~5月(高胜率)", late)]:
    # 1. 候选池规模
    total_cand = 0
    total_days = 0
    nxt_highs = []
    nxt_closes = []
    p_vals = []; cl_vals = []; vr_vals = []; hsl_vals = []
    
    for dt in period:
        cand = 0
        for s in data.get(dt, []):
            code,p=s['code'],s['p']
            if p<p_min or p>p_max: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<vr_min or vr>vr_max: continue
            ri=real.get(code)
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<hsl_min or hsl>hsl_max: continue
            sz=(ri.get('shizhi',0) or 0)
            if sz>=sz_max: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            jv=s.get('j_val',0) or 0
            if jv>j_max: continue
            cl=s.get('cl',0)
            if cl<cl_min or cl>cl_max: continue
            nh, nc = get_nxt(code, dt)
            cand += 1
            nxt_highs.append(nh)
            nxt_closes.append(nc)
            p_vals.append(p); cl_vals.append(cl); vr_vals.append(vr); hsl_vals.append(hsl)
        total_days += 1
        total_cand += cand
    
    # 候选池分析
    avg_per_day = total_cand / total_days if total_days else 0
    
    # 所有候选的次日表现
    hit_25 = sum(1 for x in nxt_highs if x >= 2.5)
    hit_5 = sum(1 for x in nxt_highs if x >= 5)
    avg_nh = sum(nxt_highs) / len(nxt_highs) if nxt_highs else 0
    
    # 涨跌幅分布
    gt_10 = sum(1 for x in nxt_highs if x >= 10)
    
    print(f"\n{'─'*60}")
    print(f"【{label}】{total_days}天")
    print(f"{'─'*60}")
    print(f"  候选池: 共{total_cand}只, 均{avg_per_day:.1f}只/天")
    print(f"  候选池次日:")
    print(f"    达2.5%: {hit_25}/{len(nxt_highs)}({hit_25*100/len(nxt_highs):.1f}%)")
    print(f"    达5%:   {hit_5}/{len(nxt_highs)}({hit_5*100/len(nxt_highs):.1f}%)")
    print(f"    达10%:  {gt_10}/{len(nxt_highs)}({gt_10*100/len(nxt_highs):.1f}%)")
    print(f"    平均:   {avg_nh:.2f}%")
    print(f"  候选特征:")
    if p_vals:
        print(f"    涨幅:  {sum(p_vals)/len(p_vals):.2f}%")
        print(f"    CL:    {sum(cl_vals)/len(cl_vals):.1f}%")
        print(f"    量比:  {sum(vr_vals)/len(vr_vals):.2f}")
        print(f"    换手:  {sum(hsl_vals)/len(hsl_vals):.1f}%")

# 逐月大盘背景分析
print("\n" + "=" * 80)
print("逐月大盘背景 + 候选池质量")
print("=" * 80)

for m in ['2026-01','2026-02','2026-03','2026-04','2026-05']:
    m_dates = [d for d in dates if d.startswith(m)]
    if not m_dates: continue
    cand_all = []; nh_all = []
    for dt in m_dates:
        for s in data.get(dt, []):
            code,p=s['code'],s['p']
            if p<p_min or p>p_max: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<vr_min or vr>vr_max: continue
            ri=real.get(code)
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<hsl_min or hsl>hsl_max: continue
            sz=(ri.get('shizhi',0) or 0)
            if sz>=sz_max: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl=s.get('cl',0)
            if cl<cl_min or cl>cl_max: continue
            nh, nc = get_nxt(code, dt)
            cand_all.append((p,cl,nh,nm))
    
    if not cand_all: continue
    avg_nh = sum(c[2] for c in cand_all)/len(cand_all)
    hit25 = sum(1 for c in cand_all if c[2]>=2.5)/len(cand_all)*100
    hit5 = sum(1 for c in cand_all if c[2]>=5)/len(cand_all)*100
    gt10 = sum(1 for c in cand_all if c[2]>=10)
    avg_p = sum(c[0] for c in cand_all)/len(cand_all)
    avg_cl = sum(c[1] for c in cand_all)/len(cand_all)
    print(f"\n{m}: {len(m_dates)}天 {len(cand_all)}只候选")
    print(f"  候选次日: 均+{avg_nh:.2f}% >2.5%:{hit25:.1f}% >5%:{hit5:.1f}% >10%:{gt10}只")
    print(f"  候选特征: 均涨{avg_p:.1f}% CL{avg_cl:.0f}%")
