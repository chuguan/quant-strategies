"""深入分析：WR/资金/箱体为何降胜率 + 调优比例公式"""
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
    if not os.path.exists(fp): return 0, 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is not None and idx+1 < len(kdata):
            bc = kdata[idx]['close']
            high_n = (kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
            close_n = (kdata[idx+1]['close']/bc-1)*100 if bc>0 else 0
            return high_n, close_n
    except: return 0, 0

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
        wr_today = (h14-c)/(h14-l14)*100 if h14!=l14 else 50
        # 昨天WR
        if idx-1 < 14:
            wr_yest = 50
        else:
            h14_y = max(k['high'] for k in kdata[idx-14:idx])
            l14_y = min(k['low'] for k in kdata[idx-14:idx])
            c_y = kdata[idx-1]['close']
            wr_yest = (h14_y-c_y)/(h14_y-l14_y)*100 if h14_y!=l14_y else 50
        return wr_today, wr_yest
    except: return 50, 50

def box_info(code, date):
    """箱体信息：20日高/低/振幅"""
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 0, 0, 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx < 20: return 0, 0, 0
        h20 = max(k['high'] for k in kdata[idx-19:idx+1])
        l20 = min(k['low'] for k in kdata[idx-19:idx+1])
        c = kdata[idx]['close']
        amp = (h20 - l20) / l20 * 100  # 箱体振幅%
        ratio = c / h20  # 收盘/箱顶
        return ratio, amp, c
    except: return 0, 0, 0

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

# ===== 第1步：分析WR不同区间对涨跌幅的影响 =====
print("=== WR区间分析 ===")
wr_buckets = {f'{i}-{i+9}':[] for i in range(0,100,10)}
wr_cross = {'cross_below35':[], 'no_cross':[]}

for dt in target:
    for s in data.get(dt, []):
        code,p=s['code'],s['p']
        if p<p_min or p>p_max: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<vr_min or vr>vr_max: continue
        cl=s.get('cl',0)
        if cl<cl_min or cl>cl_max: continue
        nh, nc = get_nxt(code, dt)
        wr_t, wr_y = calc_wr(code, dt)
        # WR区间
        for i in range(0,100,10):
            if i <= wr_t < i+10:
                wr_buckets[f'{i}-{i+9}'].append(nh)
                break
        # WR下穿35
        if wr_t < 35 and wr_y >= 35:
            wr_cross['cross_below35'].append(nh)
        elif wr_t < 35:
            wr_cross['no_cross'].append(nh)

for k,v in wr_buckets.items():
    if v:
        wr25 = sum(1 for x in v if x>=2.5)
        print(f'  WR {k}: {len(v)}只 均涨{v[sum(1 for _ in v)]/len(v):.2f}% 达2.5%:{wr25*100/len(v):.1f}%')

for k,v in wr_cross.items():
    if v:
        wr25 = sum(1 for x in v if x>=2.5)
        print(f'  WR{k}: {len(v)}只 均{sum(v)/len(v):.2f}% 达2.5%:{wr25*100/len(v):.1f}%')

# ===== 第2步：不同公式调优 =====
print("\n=== 公式调优 ===")

def wr_score_v1(wr_t, wr_y):
    """WR下穿35切分：刚下穿(前日>=35,今日<35)才算"""
    if wr_t >= 35 or wr_y < 35: return 0
    # 下穿：WR从>=35到<35
    depth = 35 - wr_t  # 下穿深度
    return min(5, depth * 5 / 15)  # 下穿15个点封顶

def wr_score_v2(wr_t, wr_y):
    """WR小切口：只在下穿35的瞬间加分"""
    if wr_t >= 35: return 0
    if wr_y >= 35:  # 刚下穿
        return 5  # 直接固定5
    # 已经在下穿区域
    if wr_t < 20: return 0  # 太深了不算
    return 3 * (35 - wr_t) / 15  # 20-35之间给0~3分

def fund_score_v2(vr, is_yang, p):
    """主力资金：量比越高质量越好"""
    if not is_yang: return 0  # 收阴不算流入
    quality = (vr - 0.8) * (p / 5)  # 量比×涨幅倍数
    return min(5, quality * 2)

def box_score_v2(ratio, amp):
    """涨幅大的箱体：振幅越大的箱体突破越强"""
    if ratio <= 0.97: return 0
    # 箱体振幅越大加分越多
    amp_factor = min(1.5, amp / 20)  # 20%振幅封顶1.5倍
    base = (ratio - 0.97) * 100  # 0~3分基础（到1.0得3分）
    return min(5, base * amp_factor)

tests = [
    ('基线', lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11]),
    # V1: WR下穿才加分
    ('WR下穿v1', lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + wr_score_v1(c[14], c[15])),
    # V2: WR小切口
    ('WR小切口v2', lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + wr_score_v2(c[14], c[15])),
    # 资金v2
    ('资金v2', lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + fund_score_v2(c[4], c[13], c[3])),
    # 箱体v2(用振幅)
    ('箱体v2(振幅)', lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + box_score_v2(c[16], c[17])),
    # 两两组合
    ('WR下穿+资金', lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + wr_score_v1(c[14], c[15]) + fund_score_v2(c[4], c[13], c[3])),
    ('WR下穿+箱体', lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + wr_score_v1(c[14], c[15]) + box_score_v2(c[16], c[17])),
    ('资金+箱体', lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + fund_score_v2(c[4], c[13], c[3]) + box_score_v2(c[16], c[17])),
    # 三因子
    ('WR下穿+资金+箱体', lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + wr_score_v1(c[14], c[15]) + fund_score_v2(c[4], c[13], c[3]) + box_score_v2(c[16], c[17])),
    # 试试减权重：各减半
    ('WR+资金+箱体(各半)', lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + wr_score_v1(c[14], c[15])*0.5 + fund_score_v2(c[4], c[13], c[3])*0.5 + box_score_v2(c[16], c[17])*0.5),
    # 试试只加一点：各+2
    ('WR+资金+箱体(各2)', lambda c: c[3]*2 + c[0] + ps(c[7])*0.5 + ms(c[9],c[10])*0.5 + 10*c[11] + wr_score_v1(c[14], c[15])*0.4 + fund_score_v2(c[4], c[13], c[3])*0.4 + box_score_v2(c[16], c[17])*0.4),
]

for label, sort_key in tests:
    wins=0; ndays=0; total_n=0
    for dt in target:
        cand=[]
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
            ratio, amp, _ = box_info(code, dt)
            nh, nc = get_nxt(code, dt)
            cand.append((cl,nm,code,p,vr,hsl,sz,buy,nh,dif,macd_g,above5,is_yang,wr_t,wr_y,ratio,amp))
        if not cand: continue
        cand.sort(key=lambda c: (-sort_key(c), -c[3]))
        ndays+=1
        total_n+=len(cand)
        if cand[0][8]>=2.5: wins+=1
    chg = f' {wins*100/ndays-75:.1f}' if label!='基线' else ''
    print(f'{label:<35}: {wins}/{ndays}({wins*100/ndays:.1f}%){chg} | 均{total_n/ndays:.0f}只')
