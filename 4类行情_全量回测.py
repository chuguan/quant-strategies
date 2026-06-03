"""
4类行情分型 + 虚涨日策略 全量回测
"""
import pickle, os, sys

os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
print("Loading cache...", flush=True)
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, real, names = d['data'], d['real'], d['names']
dates = [x for x in sorted(data.keys()) if '2025-01-01' <= x < '2026-06-01']
print(f"共{len(dates)}天", flush=True)

def classify_market(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    avg_p = sum(ps) / len(ps)
    avg_vr = sum(vrs) / len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5:
        return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

def calc_macd_score(s):
    dif = s.get('dif_val', 0) or 0
    mg = s.get('macd_golden', 0)
    if mg and dif > 0.5: return 10
    if mg and dif > 0.2: return 8
    if mg: return 6
    if dif > 0.5: return 4
    if dif > 0: return 2
    return 0

# 基础过滤函数（所有策略共用）
def base_filter(s, real, names, p_min, p_max, vr_min, vr_max, hs_min, hs_max, sz_max, cl_min, cl_max):
    code = s['code']
    p = s.get('p', 0) or 0
    if p < p_min or p > p_max: return None
    vr = s.get('vol_ratio', 0) or 0
    if vr < vr_min or vr > vr_max: return None
    ri = real.get(code)
    if not ri: return None
    h = (ri.get('hsl', 0) or 0)
    if h < hs_min or h > hs_max: return None
    if (ri.get('shizhi', 0) or 0) >= sz_max: return None
    nm = names.get(code, '')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return None
    cl = s.get('cl', 0)
    if cl < cl_min or cl > cl_max: return None
    nh = s.get('n', 0) or 0
    if nh <= 0: return None
    return {
        'code': code, 'name': nm, 'p': p, 'vr': vr, 'cl': cl,
        'nh': nh, 'buy': s.get('close', 0) or 0,
        'hsl': h, 'sz': ri.get('shizhi', 0) or 0,
        'dif': s.get('dif_val', 0) or 0, 'mg': s.get('macd_golden', 0),
        'a5': s.get('above_ma5', 0) or 0,
        'iy': s.get('is_yang', 0) or 0,
        'jv': s.get('j_val', 0) or 0,
    }

# 各策略评分
def score_real_up(item):
    """涨日策略：激进追强"""
    ms = calc_macd_score(item)
    ps2 = min(10, max(1, 11 - item['buy'] / 10)) if item['buy'] else 0
    wt = (item.get('wr_t', 50) or 50)
    wr_v = min(5, max(0, (35-wt)*5/35)) if wt < 35 else 0
    hsl_b = 0.6 if 5 <= item['hsl'] <= 7 else 0
    return item['p'] * 3.0 + item['cl'] * 0.1 + ps2 * 0.3 + ms * 0.3 + (3 if item['a5'] else 0) + wr_v * 0.3 + hsl_b * 2

def score_down(item):
    """跌日策略：防守为主"""
    ms = calc_macd_score(item)
    ps2 = min(10, max(1, 11 - item['buy'] / 10)) if item['buy'] else 0
    yp = -3 if item.get('y_p', 0) > 7 else 0
    return item['p'] * 2.0 + item['cl'] * 0.05 + ps2 * 0.3 + ms * 0.3 + yp

def score_flat(item):
    """横盘策略"""
    ms = calc_macd_score(item)
    ps2 = min(10, max(1, 11 - item['buy'] / 10)) if item['buy'] else 0
    yp = -3 if item.get('y_p', 0) > 7 else 0
    hsl_b = 0.6 if 5 <= item['hsl'] <= 7 else 0
    vr_b = 0.3 if item['iy'] and item['vr'] > 1.2 else 0
    return item['p'] * 2.0 + item['cl'] * 0.05 + ps2 * 0.3 + ms * 0.3 + yp + hsl_b * 2 + vr_b

def score_fake_up(item):
    """虚涨日策略：放宽涨幅+低CL+反转"""
    ms = calc_macd_score(item)
    ps2 = min(10, max(1, 11 - item['buy'] / 10)) if item['buy'] else 0
    return item['p'] * 1.0 + item['cl'] * 0.05 + ps2 * 0.3 + ms * 0.5

# ===== 虚涨日策略 =====
FAKE_PARAMS = {'p_min':0,'p_max':6,'vr_min':0.6,'vr_max':2.5,'hs_min':5,'hs_max':20,'sz_max':200,'cl_min':30,'cl_max':95}
# ===== 主策略（涨日/跌日/横盘） =====
MAIN_PARAMS = {'p_min':5,'p_max':8,'vr_min':0.8,'vr_max':2.0,'hs_min':5,'hs_max':15,'sz_max':300,'cl_min':60,'cl_max':90}

def calc_wr(code, date, cache_dir):
    """WR计算（简化版，从已有数据获取）"""
    return 50, 50, 0  # 简化处理

# ===== 回测 =====
CHAMPION_WINS = {'real_up':0,'fake_up':0,'down':0,'flat':0}
CHAMPION_TOTAL = {'real_up':0,'fake_up':0,'down':0,'flat':0}
TOP3_WINS = {'real_up':0,'fake_up':0,'down':0,'flat':0}
TOP3_TOTAL = {'real_up':0,'fake_up':0,'down':0,'flat':0}
RESULTS = []

for dt in dates:
    stocks = data.get(dt, [])
    if not stocks: continue
    mkt = classify_market(stocks)
    
    cand = []
    if mkt == 'fake_up':
        # 虚涨日：用放宽条件
        for s in stocks:
            item = base_filter(s, real, names, **FAKE_PARAMS)
            if not item: continue
            item['score'] = score_fake_up(item)
            cand.append(item)
    else:
        # 正常日：用主策略 + 行情专用评分
        for s in stocks:
            item = base_filter(s, real, names, **MAIN_PARAMS)
            if not item: continue
            if mkt == 'real_up':
                item['score'] = score_real_up(item)
            elif mkt == 'down':
                item['score'] = score_down(item)
            else:  # flat
                item['score'] = score_flat(item)
            cand.append(item)
    
    if not cand:
        RESULTS.append({'date':dt, 'mkt':mkt, '冠军':None, '冠军次收':None, '达标':False, 'top3达标':False, '池':0})
        continue
    
    cand.sort(key=lambda x: (-x['score'], -x['p']))
    
    CHAMPION_TOTAL[mkt] += 1
    TOP3_TOTAL[mkt] += 1
    
    champ = cand[0]
    champ_ok = champ['nh'] >= 2.5
    if champ_ok: CHAMPION_WINS[mkt] += 1
    
    top3 = cand[:3]
    top3_ok = any(c['nh'] >= 2.5 for c in top3)
    if top3_ok: TOP3_WINS[mkt] += 1
    
    tag_c = 'A' if champ['nh'] >= 5 else ('B' if champ_ok else 'C')
    tag_t = 'OK' if top3_ok else '!!'
    
    RESULTS.append({
        'date': dt, 'mkt': mkt,
        '冠军': f"{champ['name'][:8]}({champ['code']})",
        '冠军涨': champ['p'],
        '冠军次收': champ['nh'],
        '达标': champ_ok,
        'top3达标': top3_ok,
        '池': len(cand),
        '冠军cl': champ['cl'],
        '冠军vr': champ['vr'],
        '冠军hsl': champ['hsl'],
    })

# ===== 输出结果 =====
total = len(RESULTS)
champ_all = sum(CHAMPION_WINS.values())
total_all = sum(CHAMPION_TOTAL.values())
top3_all = sum(TOP3_WINS.values())
top3_total_all = sum(TOP3_TOTAL.values())

print(f"\n{'='*60}")
print("4行情分型+虚涨日策略 全量回测")
print(f"{'='*60}")
print(f"日期范围: {dates[0]} ~ {dates[-1]}")
print(f"交易日数: {total}")
print(f"\n【总胜率】")
print(f"  冠军达标(≥2.5%): {champ_all}/{total_all}={champ_all*100/total_all:.1f}%")
print(f"  Top3任意达标:    {top3_all}/{top3_total_all}={top3_all*100/top3_total_all:.1f}%")

print(f"\n【分行情胜率】")
for mkt in ['real_up','fake_up','down','flat']:
    if CHAMPION_TOTAL[mkt] > 0:
        cr = CHAMPION_WINS[mkt]*100/CHAMPION_TOTAL[mkt]
        tr = TOP3_WINS[mkt]*100/TOP3_TOTAL[mkt]
        name = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}[mkt]
        print(f"  {name}: {CHAMPION_TOTAL[mkt]}天 | 冠军{cr:.1f}% | Top3{tr:.1f}%")

# 对比：旧版（不加虚涨日分类）
print(f"\n{'='*60}")
print("【对比】旧版（不加虚涨日识别，全归入涨日策略）")
old_champ = 0
old_top3 = 0
for dt in dates:
    stocks = data.get(dt, [])
    if not stocks: continue
    mkt = classify_market(stocks)
    # 旧版：不管real_up/fake_up全当涨日处理
    cand = []
    for s in stocks:
        item = base_filter(s, real, names, **MAIN_PARAMS)
        if not item: continue
        item['score'] = score_real_up(item)
        cand.append(item)
    if not cand: continue
    cand.sort(key=lambda x: (-x['score'], -x['p']))
    if cand[0]['nh'] >= 2.5: old_champ += 1
    if any(c['nh'] >= 2.5 for c in cand[:3]): old_top3 += 1

print(f"  旧版冠军: {old_champ}/{total_all}={old_champ*100/total_all:.1f}%")
print(f"  旧版Top3: {old_top3}/{top3_total_all}={old_top3*100/top3_total_all:.1f}%")
print(f"  新版冠军: {champ_all}/{total_all}={champ_all*100/total_all:.1f}%（+{champ_all-old_champ}天）")

# 输出失败明细
print(f"\n{'='*60}")
print("失败日明细:")
for r in RESULTS:
    if not r['冠军']: continue
    if not r['达标']:
        print(f"  {r['date']} [{r['mkt']}] {r['冠军']} 涨{r['冠军涨']:+.1f}% CL{r['冠军cl']:.0f}% 量{r['冠军vr']:.2f} -> +{r['冠军次收']:.1f}% ❌ 池{r['池']}只")
