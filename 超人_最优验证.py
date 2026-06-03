"""验证最优组合：CLw=0.8, 涨w=1.5, WRw=1.0, 资金=0, 箱体=0, CL+=0"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target = [d for d in dates if d >= '2026-04-10']

def get_nxt(code, date):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 0, 0, 0, 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is not None and idx+1 < len(kdata):
            bc = kdata[idx]['close']
            h1 = (kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
            c1 = (kdata[idx+1]['close']/bc-1)*100 if bc>0 else 0
            l1 = (kdata[idx+1]['low']/bc-1)*100 if bc>0 else 0
            # D+2
            h2 = (kdata[idx+2]['high']/bc-1)*100 if idx+2<len(kdata) and bc>0 else 0
            c2 = (kdata[idx+2]['close']/bc-1)*100 if idx+2<len(kdata) and bc>0 else 0
            return h1, c1, l1, h2
    except: return 0, 0, 0, 0

def calc_wr(code, date):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 50, 50
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx < 14: return 50, 50
        h14 = max(k['high'] for k in kdata[idx-13:idx+1])
        l14 = min(k['low'] for k in kdata[idx-13:idx+1])
        c = kdata[idx]['close']
        wr_t = (h14-c)/(h14-l14)*100 if h14!=l14 else 50
        if idx < 15: return wr_t, 50
        h14_y = max(k['high'] for k in kdata[idx-14:idx])
        l14_y = min(k['low'] for k in kdata[idx-14:idx])
        c_y = kdata[idx-1]['close']
        wr_y = (h14_y-c_y)/(h14_y-l14_y)*100 if h14_y!=l14_y else 50
        return wr_t, wr_y
    except: return 50, 50

def ps(price):
    if price<15: return 10
    if price<25: return 9
    if price<35: return 8
    if price<45: return 7
    if price<55: return 5
    if price<70: return 3
    if price<90: return 2
    return 1

def ms(dif, g):
    if g and dif>0.5: return 10
    if g and dif>0.2: return 8
    if g: return 6
    if dif>0.5: return 4
    if dif>0: return 2
    if dif>-0.3: return 0
    if dif>-0.5: return -3
    return -5

p_min,p_max=5,8; vr_min,vr_max=0.8,2.0; hsl_min,hsl_max=5,15; sz_max=300; cl_min,cl_max=60,90; j_max=100

# 最优公式参数
CL_W = 0.8
P_W = 1.5
WR_W = 1.0

# 对比：原基线 vs 新公式
print(f"{'日期':<12} {'原冠军':<16} {'原次日高':>8} {'新冠军':<16} {'新次日高':>8} {'结果':>4}")
print('-' * 70)

wins_new=0; wins_old=0; ndays=0

for dt in target:
    cand_new = []
    cand_old = []
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
        buy=s.get('close',0)
        dif=s.get('dif_val',0) or 0
        macd_g=s.get('macd_golden',0)
        above5=s.get('above_ma5',0)
        is_yang=s.get('is_yang',0)
        wr_t, wr_y = calc_wr(code, dt)
        nh, nc, nl, nh2 = get_nxt(code, dt)
        wr_s = min(5, max(0, (35-wr_t)*5/15)) if wr_t < 35 and wr_y >= 35 else 0
        
        score_new = p*P_W + cl*CL_W + ps(buy)*0.3 + ms(dif,macd_g)*0.3 + 5*above5 + wr_s*WR_W
        score_old = p*2 + cl*1 + ps(buy)*0.5 + ms(dif,macd_g)*0.5 + 10*above5
        
        cand_new.append((nm,code,p,cl,vr,buy,nh,score_new,wr_t,wr_y,wr_s,nh2))
        cand_old.append((nm,code,p,cl,vr,buy,nh,score_old))
    
    if not cand_new or not cand_old: continue
    
    cand_new.sort(key=lambda x: (-x[6], -x[2]))
    cand_old.sort(key=lambda x: (-x[7], -x[2]))
    
    ndays += 1
    n = cand_new[0]; o = cand_old[0]
    nw = 1 if n[6] >= 2.5 else 0
    ow = 1 if o[6] >= 2.5 else 0
    wins_new += nw; wins_old += ow
    
    n_tag = '✅' if n[6]>=2.5 else ('🔥' if n[6]>=5 else '❌')
    o_tag = '✅' if o[6]>=2.5 else ('🔥' if o[6]>=5 else '❌')
    
    print(f"{dt:<12} {o[0][:8]:<12} {o[6]:>+7.1f}%{o_tag:<2} {n[0][:8]:<12} {n[6]:>+7.1f}%{n_tag:<2}", end='')
    
    # 如果不一样显示差异
    if n[0] != o[0]:
        # 新冠军的信息
        print(f" WR{n[8]:.0f}/{n[9]:.0f} WR+{n[10]:.1f} CL{n[3]:.0f}% 涨{n[2]:.1f}%", end='')
    print()

print(f"\n原公式: {wins_old}/{ndays}({wins_old*100/ndays:.1f}%)")
print(f"新公式(CL×{CL_W}+涨×{P_W}+WR×{WR_W}): {wins_new}/{ndays}({wins_new*100/ndays:.1f}%)")
print(f"提升: {wins_new*100/ndays - wins_old*100/ndays:+.1f}个百分点")

# Top3胜率对比
print()
top3_new=0; top3_old=0; top5_new=0
for dt in target:
    cand_new = []
    cand_old = []
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
        buy=s.get('close',0)
        dif=s.get('dif_val',0) or 0
        macd_g=s.get('macd_golden',0)
        above5=s.get('above_ma5',0)
        is_yang=s.get('is_yang',0)
        wr_t, wr_y = calc_wr(code, dt)
        nh, nc, nl, nh2 = get_nxt(code, dt)
        wr_s = min(5, max(0, (35-wr_t)*5/15)) if wr_t < 35 and wr_y >= 35 else 0
        
        score_new = p*P_W + cl*CL_W + ps(buy)*0.3 + ms(dif,macd_g)*0.3 + 5*above5 + wr_s*WR_W
        score_old = p*2 + cl*1 + ps(buy)*0.5 + ms(dif,macd_g)*0.5 + 10*above5
        
        cand_new.append((nm,code,p,cl,vr,buy,nh,score_new,wr_t,wr_y,wr_s,nh2,nc,nl))
        cand_old.append((nm,code,p,cl,vr,buy,nh,score_old))
    
    if not cand_new: continue
    cand_new.sort(key=lambda x: (-x[6], -x[2]))
    cand_old.sort(key=lambda x: (-x[7], -x[2]))
    
    if any(c[6]>=2.5 for c in cand_new[:3]): top3_new+=1
    if any(c[6]>=2.5 for c in cand_old[:3]): top3_old+=1
    if any(c[6]>=2.5 for c in cand_new[:5]): top5_new+=1

print(f"新公式Top3任意达2.5%: {top3_new}/{ndays}({top3_new*100/ndays:.1f}%)")
print(f"原公式Top3任意达2.5%: {top3_old}/{ndays}({top3_old*100/ndays:.1f}%)")
print(f"新公式Top5任意达2.5%: {top5_new}/{ndays}({top5_new*100/ndays:.1f}%)")

# 展示最优组合近10天Top3
print(f"\n=== 近10天Top3(最优公式) ===")
for dt in target[-10:]:
    cand_new = []
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
        buy=s.get('close',0)
        dif=s.get('dif_val',0) or 0
        macd_g=s.get('macd_golden',0)
        above5=s.get('above_ma5',0)
        is_yang=s.get('is_yang',0)
        wr_t, wr_y = calc_wr(code, dt)
        nh, nc, nl, nh2 = get_nxt(code, dt)
        wr_s = min(5, max(0, (35-wr_t)*5/15)) if wr_t < 35 and wr_y >= 35 else 0
        score_new = p*P_W + cl*CL_W + ps(buy)*0.3 + ms(dif,macd_g)*0.3 + 5*above5 + wr_s*WR_W
        cand_new.append((nm,code,p,cl,vr,buy,nh,score_new,wr_s,wr_t,wr_y,nc,nl,nh2))
    
    if not cand_new: continue
    cand_new.sort(key=lambda x: (-x[6], -x[2]))
    ok = any(c[6]>=2.5 for c in cand_new[:3])
    print(f"\n{dt} {'✅' if ok else '❌'}")
    for i,c in enumerate(cand_new[:3]):
        tag = '🔥' if c[6]>=5 else ('✅' if c[6]>=2.5 else '❌')
        wr_tag = f'WR{c[9]:.0f}/{c[10]:.0f}+{c[7]:.1f}' if c[7]>0 else f'WR{c[9]:.0f}'
        print(f"  Top{i+1}: {c[0][:8]:<10} 涨{c[2]:.1f}% CL{c[3]:.0f}% 量{c[4]:.2f} {wr_tag} → {c[6]:+.1f}%{tag} 收{c[11]:+.1f}% 低{c[12]:+.1f}%")
