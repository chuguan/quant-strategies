"""新评分体系测试：量能×30% + 趋势×40% + 资金×30% + 风险过滤"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target = [d for d in dates if d >= '2026-04-10']

def get_klines(code):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return None
    try:
        with open(fp) as f: return json.load(f)
    except: return None

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

# ===== 基础选票条件（用户原条件不变） =====
P_MIN, P_MAX = 5, 8
VR_MIN, VR_MAX_OLD = 0.8, 2.0
HSL_MIN, HSL_MAX_OLD = 5, 15
SZ_MAX = 300
CL_MIN, CL_MAX = 60, 90
J_MAX = 100

# ===== 新评分体系测试 =====
# 硬性风险过滤（可实现的）
# 量比1.8~2.5，换手3~10%，均线多头，突破压力位

def apply_new_scoring(dt, stock_list):
    """用新评分体系打分"""
    cand = []
    for s in stock_list:
        code, p = s['code'], s['p']
        if p < P_MIN or p > P_MAX: continue
        vr = s.get('vol_ratio', 0) or 0
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl', 0) or 0)
        sz = (ri.get('shizhi', 0) or 0)
        if sz >= SZ_MAX: continue
        nm = names.get(code, '')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv = s.get('j_val', 0) or 0
        cl = s.get('cl', 0)
        buy = s.get('close', 0)
        dif = s.get('dif_val', 0) or 0
        macd_g = s.get('macd_golden', 0)
        above5 = s.get('above_ma5', 0)
        
        # 获取K线分析
        klines = get_klines(code)
        
        # ===== 量能维度（可得分0~5） =====
        # 量比分
        vr_score = 0
        if 1.8 <= vr <= 2.5:
            if 1.8 <= vr < 2.0: vr_score = 1
            elif 2.0 <= vr <= 2.5: vr_score = 2
        else:
            vr_score = -1
        
        # 换手率分
        hsl_score = 0
        if 3 <= hsl <= 10:
            if 3 <= hsl < 5: hsl_score = 1
            elif 5 <= hsl <= 7: hsl_score = 2
            elif 7 < hsl <= 10: hsl_score = 1
        else:
            hsl_score = -2
        
        # 量能总分（0~5）
        liangneng = vr_score + hsl_score
        
        # ===== 趋势维度（可得分0~10） =====
        qu_shi = 0
        ma5 = s.get('ma5', 0) or 0
        ma10 = s.get('ma10', 0) or 0
        ma20 = s.get('ma20', 0) or 0
        close = s.get('close', 0) or 0
        
        # 均线多头排列
        ma_duotou = (ma5 > ma10 > ma20 and ma5 > ma5*0.99)  # 5>10>20且5日线上扬
        ma_kongtou = (ma5 < ma10 < ma20)
        
        # 突破前5日高点+20日均线
        break_through = False
        if klines:
            idx = next((i for i,k in enumerate(klines) if k['date']==dt), None)
            if idx is not None and idx >= 5:
                h5 = max(k['high'] for k in klines[idx-4:idx+1])
                if close > h5 and close > ma20:
                    break_through = True
                    qu_shi += 3
                elif not break_through:
                    # 检查是否在下降通道
                    if ma_kongtou:
                        qu_shi -= 5
        
        # 均线多头
        if ma_duotou:
            qu_shi += 3
        elif ma_kongtou:
            qu_shi -= 5
        
        # WR下穿
        wr_t, wr_y = calc_wr(code, dt)
        if wr_t < 35 and wr_y >= 35:
            qu_shi += 2
        
        # ===== 资金维度（可得分0~5） =====
        # 只有市值可参考
        zi_jin = 0
        if 50 <= sz <= 200:
            zi_jin += 1
        elif sz < 50 or sz > 200:
            zi_jin -= 3
        
        # 收阳提示资金流入
        if s.get('is_yang', 0):
            zi_jin += 1
        
        # ===== 新风险过滤（硬性） =====
        # 量比1.8~2.5
        if vr < 1.8 or vr > 2.5:
            continue
        # 换手3~10%
        if hsl < 3 or hsl > 10:
            continue
        # 均线空头 → 排除
        if ma_kongtou:
            continue
        # 未突破压力位（前5日高+20日线）
        if not break_through:
            continue
        # 市值极端排除
        if sz < 50:
            continue
        
        # ===== 高位放量滞涨检查 =====
        if klines:
            idx = next((i for i,k in enumerate(klines) if k['date']==dt), None)
            if idx is not None and idx >= 10:
                c10 = klines[idx-9]['close']
                pct_10d = (close/c10 - 1) * 100
                if pct_10d < 20 and vr > 2.5 and p < 3:
                    qu_shi -= 5  # 出货信号
        
        # ===== 总分 = 量能30% + 趋势40% + 资金30% =====
        # 归一化到0~10
        total = liangneng * 0.3 + qu_shi * 0.4 + zi_jin * 0.3
        
        nh = get_nxt(code, dt)
        cand.append((total, p, nh, nm, code, cl, vr, hsl, sz, liangneng, qu_shi, zi_jin, wr_t, wr_y))
    
    return cand

# ===== 回测 =====
wins=0; ndays=0; t3w=0; total_cand=0
print(f"{'日期':<12} {'冠军':<14} {'涨%':>5} {'CL':>3} {'量':>4} {'换':>4} {'总分':>5} {'量能':>4} {'趋势':>4} {'资金':>4} {'次高':>6} {'结果':>2}", flush=True)
print('-' * 85, flush=True)

for dt in target:
    cand = apply_new_scoring(dt, data.get(dt, []))
    if not cand: 
        # 如果没有候选（过滤太严），回退到原评分
        print(f"{dt}: 无候选(风险过滤)", flush=True)
        continue
    cand.sort(key=lambda x: (-x[0], -x[1]))
    ndays+=1; total_cand+=len(cand)
    c=cand[0]
    tag='🔥' if c[2]>=5 else('✅' if c[2]>=2.5 else'❌')
    if c[2]>=2.5: wins+=1
    if any(c2[2]>=2.5 for c2 in cand[:3]): t3w+=1
    print(f"{dt}: {c[3][:8]:<12} {c[1]:>5.1f} {c[5]:>3.0f} {c[6]:>4.1f} {c[7]:>4.1f} {c[0]:>5.1f} {c[9]:>4.0f} {c[10]:>4.0f} {c[11]:>4.0f} {c[2]:>+5.1f}%{tag:>2}", flush=True)

print(f"\n总天数: {ndays}", flush=True)
print(f"冠军达2.5%: {wins}/{ndays}({wins*100/ndays:.1f}%)", flush=True)
print(f"Top3任意达2.5%: {t3w}/{ndays}({t3w*100/ndays:.1f}%)", flush=True)
print(f"均候选: {total_cand/max(ndays,1):.0f}只/天", flush=True)
