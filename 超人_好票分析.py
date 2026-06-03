"""分析：好票为什么没被推上去？找被低估的票的共同特征"""
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
        wr_t = (h14-c)/(h14-l14)*100 if h14!=l14 else 50
        if idx < 15: return wr_t, 50
        h14_y = max(k['high'] for k in kdata[idx-14:idx])
        l14_y = min(k['low'] for k in kdata[idx-14:idx])
        c_y = kdata[idx-1]['close']
        wr_y = (h14_y-c_y)/(h14_y-l14_y)*100 if h14_y!=l14_y else 50
        return wr_t, wr_y
    except: return 50, 50

def box_break(code, date):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 0, 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx < 20: return 0, 0
        h20 = max(k['high'] for k in kdata[idx-19:idx+1])
        l20 = min(k['low'] for k in kdata[idx-19:idx+1])
        c = kdata[idx]['close']
        return c/h20, (h20-l20)/l20*100
    except: return 0, 0

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

# 对每一天，选出"好票"（第二天>=2.5%），看它们在评分中的排名
all_missed = []  # 评分低但实际涨得好的
all_ranked = []  # 评分高
all_good_stocks = []

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
        dif=s.get('dif_val',0) or 0
        macd_g=s.get('macd_golden',0)
        above5=s.get('above_ma5',0)
        is_yang=s.get('is_yang',0)
        wr_t, wr_y = calc_wr(code, dt)
        ratio, amp = box_break(code, dt)
        nh, nc = get_nxt(code, dt)
        
        # 基线评分
        base_score = p*2 + cl + ps(buy)*0.5 + ms(dif,macd_g)*0.5 + 10*above5
        # 新因子评分
        wr_s = 5 * (35-wr_t)/35 if wr_t < 35 and wr_y >= 35 else 0
        fund_s = min(5, (vr-0.8)*(p/5)*2) if is_yang and vr>0.8 else 0
        box_s = min(5, (ratio-0.97)*100*amp/15) if ratio>0.97 else 0
        cl_s = min(5, (cl-75)*0.5) if cl>75 else 0
        
        cand.append({
            'nm': nm, 'code': code, 'p': p, 'cl': cl, 'vr': vr, 'hsl': hsl,
            'buy': buy, 'nh': nh, 'nc': nc, 'dif': dif, 'macd_g': macd_g,
            'above5': above5, 'is_yang': is_yang, 'wr': wr_t, 'wr_y': wr_y,
            'ratio': ratio, 'amp': amp, 'jv': jv,
            'base': base_score, 'wr_s': wr_s, 'fund_s': fund_s, 'box_s': box_s, 'cl_s': cl_s,
            'total': base_score + wr_s + fund_s + box_s + cl_s
        })
    
    if not cand: continue
    # 按总分排序
    cand.sort(key=lambda x: (-x['total'], -x['p']))
    
    # 记录排名信息
    for i, c in enumerate(cand):
        rank = i + 1
        is_good = c['nh'] >= 2.5
        if is_good:
            all_good_stocks.append(c)
            if rank > 5:
                all_missed.append(c)
        if rank == 1:
            all_ranked.append(c)

print(f"总天数: {len(target)}")
print(f"冠军达2.5%: {sum(1 for c in all_ranked if c['nh']>=2.5)}/{len(all_ranked)}")
print(f"所有好票数(次日>=2.5%): {len(all_good_stocks)}")
print(f"被低估(排名>5但实际好): {len(all_missed)}")
print()

# ===== 分析被低估票的特征 =====
if all_missed:
    print("=== 被低估票的特征分析 ===")
    print(f"数量: {len(all_missed)}")
    print(f"平均次日涨: {sum(c['nh'] for c in all_missed)/len(all_missed):.2f}%")
    print(f"平均排名: {sum(c['rank'] if 'rank' in c else 6 for c in all_missed):.0f}")
    print()
    
    # 分析因子分布
    factors = ['p','cl','vr','wr','wr_y','ratio','amp','is_yang','above5','macd_g']
    factor_names = ['涨幅%','CL%','量比','WR','WR前日','箱体比','振幅%','收阳','站上5日','MACD金']
    print("被低估票 因子均值:")
    for f, fn in zip(factors, factor_names):
        vals = [c[f] for c in all_missed]
        print(f"  {fn}: {sum(vals)/len(vals):.2f}")
    
    print()
    print("冠军票 因子均值:")
    for f, fn in zip(factors, factor_names):
        vals = [c[f] for c in all_ranked]
        print(f"  {fn}: {sum(vals)/len(vals):.2f}")
    
    print()
    print("所有好票 因子均值:")
    for f, fn in zip(factors, factor_names):
        vals = [c[f] for c in all_good_stocks]
        print(f"  {fn}: {sum(vals)/len(vals):.2f}")
    
    # 分析评分差异
    print()
    print("=== 评分结构对比 ===")
    for label, pool in [("冠军",all_ranked),("被低估",all_missed),("所有好票",all_good_stocks)]:
        print(f"\n{label}({len(pool)}只):")
        print(f"  基线分: {sum(c['base'] for c in pool)/len(pool):.1f}")
        for sname in ['wr_s','fund_s','box_s','cl_s']:
            vals = [c[sname] for c in pool]
            print(f"  {sname}: {sum(vals)/len(vals):.2f} (非零率: {sum(1 for v in vals if v>0)/len(vals)*100:.0f}%)")
        print(f"  总分: {sum(c['total'] for c in pool)/len(pool):.1f}")

    # ===== 找共同特征：当公式低估时，什么因子被忽略了 =====
    print()
    print("=== 被低估票的规律挖掘 ===")
    # 检查特定信号组合
    for cond_name, cond_fn in [
        ("WR<35+收阳", lambda c: c['wr']<35 and c['is_yang']),
        ("WR下穿35", lambda c: c['wr']<35 and c['wr_y']>=35),
        ("箱体突破+收阳", lambda c: c['ratio']>0.98 and c['is_yang']),
        ("CL>80+放量", lambda c: c['cl']>80 and c['vr']>1.2),
        ("资金流入+CL>75", lambda c: c['is_yang'] and c['vr']>1.2 and c['cl']>75),
        ("MACD金叉+收阳", lambda c: c['macd_g'] and c['is_yang']),
        ("站上5日+收阳+放量", lambda c: c['above5'] and c['is_yang'] and c['vr']>1.2),
        ("WR下穿+箱体突破", lambda c: c['wr']<35 and c['wr_y']>=35 and c['ratio']>0.97),
    ]:
        miss_hit = sum(1 for c in all_missed if cond_fn(c))
        champ_hit = sum(1 for c in all_ranked if cond_fn(c))
        all_hit = sum(1 for c in all_good_stocks if cond_fn(c))
        print(f"{cond_name:<22}: 被低估{miss_hit}({miss_hit*100/len(all_missed):.0f}%) | 冠军{champ_hit}({champ_hit*100/len(all_ranked):.0f}%) | 好票{all_hit}({all_hit*100/len(all_good_stocks):.0f}%)")

print()
print("=== 具体被低估的例子(部分) ===")
for c in all_missed[:15]:
    print(f"{c['nm']:<8}({c['code']}) 涨{c['p']:.1f}% CL{c['cl']:.0f}% 量{c['vr']:.2f} "
          f"WR{c['wr']:.0f}/{c['wr_y']:.0f} 箱{c['ratio']:.2f}/{c['amp']:.1f}% "
          f"基线{c['base']:.0f} → 次日{c['nh']:.1f}% 基底+{c['wr_s']:.1f}+{c['fund_s']:.1f}+{c['box_s']:.1f}+{c['cl_s']:.1f}={c['total']:.0f}")
