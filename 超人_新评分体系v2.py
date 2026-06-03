"""新评分维度：选票条件不变，只调评分排序"""
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
    if not os.path.exists(fp): return 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is not None and idx+1 < len(kdata):
            bc = kdata[idx]['close']
            return (kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
    except: return 0

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

def ps(p): return min(10, max(1, 11-p/10))

# 基础选票（不变）
p_min,p_max=5,8; vr_min,vr_max=0.8,2.0; hsl_min,hsl_max=5,15; sz_max=300; cl_min,cl_max=60,90; j_max=100

# ===== 新多维评分函数 =====
def calc_scores(s, klines, dt):
    """返回各维度得分"""
    code = s['code']; p = s['p']; vr = s.get('vol_ratio',0) or 0
    ri = real.get(code)
    hsl = (ri.get('hsl',0) or 0); sz = (ri.get('shizhi',0) or 0)
    cl = s.get('cl',0); dif = s.get('dif_val',0) or 0
    macd_g = s.get('macd_golden',0); above5 = s.get('above_ma5',0)
    is_yang = s.get('is_yang',0); close = s.get('close',0)
    ma5 = s.get('ma5',0) or 0; ma10 = s.get('ma10',0) or 0; ma20 = s.get('ma20',0) or 0
    
    # === 量能维度（权重30%） ===
    liang = 0
    # 量比评分
    if 1.8 <= vr < 2.0: liang += 1
    elif 2.0 <= vr <= 2.5: liang += 2
    elif vr < 0.8: liang -= 1
    # 换手率评分
    if 3 <= hsl < 5: liang += 1
    elif 5 <= hsl <= 7: liang += 2
    elif hsl > 10: liang -= 2
    elif hsl < 3: liang -= 2
    # 量能总分归一化 0~5
    liang_norm = max(0, min(5, liang + 2))
    
    # === 趋势维度（权重40%） ===
    qu = 0
    ma_duotou = (ma5 > ma10 > ma20 and ma5 > close * 0.98)
    ma_kongtou = (ma5 < ma10 < ma20)
    # 突破前5日高+20日线
    break_th = False
    if klines:
        idx = next((i for i,k in enumerate(klines) if k['date']==dt), None)
        if idx is not None and idx >= 5:
            h5 = max(k['high'] for k in klines[idx-4:idx+1])
            if close > h5 and close > ma20: break_th = True
    
    if break_th: qu += 5
    if ma_duotou: qu += 3
    elif ma_kongtou: qu -= 3
    # WR下穿
    wr_t, wr_y = calc_wr(code, dt)
    if wr_t < 30 and wr_y >= 30: qu += 3
    # J值扣分
    jv = s.get('j_val',0) or 0
    if jv > 80: qu -= 1
    # 10日涨幅（高位放量滞涨检测）
    if klines:
        idx = next((i for i,k in enumerate(klines) if k['date']==dt), None)
        if idx is not None and idx >= 10:
            c10 = klines[idx-9]['close']
            pct_10d = (close/c10 - 1) * 100
            if pct_10d < 20 and vr > 2.5 and p < 3: qu -= 5
    # 趋势分归一化 0~10
    qu_norm = max(0, min(10, qu + 3))
    
    # === 资金维度（权重30%） ===
    zi = 0
    if 50 <= sz <= 200: zi += 2
    elif sz < 50: zi -= 2
    elif sz > 200: zi -= 1
    # 收阳=资金流入
    if is_yang: zi += 1
    # 量比大=资金活跃
    if vr > 1.5: zi += 1
    if macd_g and dif > 0: zi += 2  # MACD金叉+正=资金真流入
    # 资金分归一化 0~5
    zi_norm = max(0, min(5, zi + 2))
    
    # === 总分 = 量能30% + 趋势40% + 资金30% ===
    total = liang_norm * 0.3 + qu_norm * 0.4 + zi_norm * 0.3
    
    return total, liang_norm, qu_norm, zi_norm, wr_t, wr_y, break_th, ma_duotou

# ===== 预计算 =====
all_data = {}
for dt in target:
    cand = []
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
        klines = None
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        if os.path.exists(fp):
            try:
                with open(fp) as f: klines = json.load(f)
            except: pass
        nh = get_nxt(code, dt)
        total, ln, qn, zn, wr_t, wr_y, bt, md = calc_scores(s, klines, dt)
        cand.append((total, p, nh, nm, code, cl, vr, hsl, sz, ln, qn, zn, wr_t, wr_y, bt, md))
    if cand:
        all_data[dt] = cand

# ===== 对比测试 =====
for label, weight_scheme in [
    ("突破v8(涨×2.5+CL×0.1+WR×0.5+扣3)", None),
    ("新多维(量能30%+趋势40%+资金30%)", "new"),
]:
    if weight_scheme is None:
        # 原突破公式
        wins=0; ndays=0; t3w=0
        for dt in target:
            if dt not in all_data: continue
            cand=[]
            for s in data.get(dt, []):
                if 1: continue # skip, use precomputed
        # 直接用预计算的
        for dt in target:
            if dt not in all_data: continue
            scored=[]
            for c in all_data[dt]:
                p=0; cl=0; # extract from tuple
                # refresh
                pass
    else:
        # 新评分体系 - 直接用total排序
        wins=0; ndays=0; t3w=0; total_cand=0
        for dt in target:
            if dt not in all_data: continue
            cand = all_data[dt]
            if not cand: continue
            cand.sort(key=lambda x: (-x[0], -x[1]))
            ndays+=1; total_cand+=len(cand)
            if cand[0][2]>=2.5: wins+=1
            if any(c[2]>=2.5 for c in cand[:3]): t3w+=1

if wins==0:
    # 重新跑一次新体系
    print(f"{'日期':<12} {'冠军':<14} {'涨%':>5} {'CL':>3} {'量':>4} {'换':>4} {'总分':>5} {'量能':>4} {'趋':>4} {'资':>4} {'突':>3} {'多':>3} {'次高':>6}", flush=True)
    print('-'*82, flush=True)
    wins=0; ndays=0; t3w=0; total_cand=0
    for dt in target:
        if dt not in all_data: continue
        cand = all_data[dt]
        if not cand: continue
        cand.sort(key=lambda x: (-x[0], -x[1]))
        ndays+=1; total_cand+=len(cand)
        c=cand[0]
        tag='🔥' if c[2]>=5 else('✅' if c[2]>=2.5 else'❌')
        if c[2]>=2.5: wins+=1
        if any(c2[2]>=2.5 for c2 in cand[:3]): t3w+=1
        bt_str='✓' if c[14] else '✗'
        md_str='✓' if c[15] else '✗'
        print(f"{dt}: {c[3][:8]:<12} {c[1]:>5.1f} {c[5]:>3.0f} {c[6]:>4.1f} {c[7]:>4.1f} {c[0]:>5.1f} {c[9]:>4.1f} {c[10]:>4.1f} {c[11]:>4.1f} {bt_str:>3} {md_str:>3} {c[2]:>+5.1f}%{tag}", flush=True)
    
    print(f"\n新评分体系(量能30%+趋势40%+资金30%)", flush=True)
    print(f"冠军达2.5%: {wins}/{ndays}({wins*100/ndays:.1f}%)", flush=True)
    print(f"Top3任意达2.5%: {t3w}/{ndays}({t3w*100/ndays:.1f}%)", flush=True)
    print(f"均候选: {total_cand/max(ndays,1):.0f}只/天", flush=True)
