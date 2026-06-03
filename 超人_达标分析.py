"""超人策略 — 达标vs不达标 深度分析"""
import pickle, json, os
from collections import defaultdict, Counter

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
with open('big_cache.pkl','rb') as f:
    cache = pickle.load(f)
d, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(d.keys())

# 使用v2.2评分
def score_v22(pct, vr, cl, features):
    sc = 10
    if 5 <= pct <= 6.5: sc += 15
    elif 6.5 < pct <= 7: sc += 8
    elif 4.5 <= pct < 5: sc += 5
    if pct > 7: sc -= 15
    if 60 <= cl <= 85: sc += 10
    if cl > 90: sc -= 15
    if 0.8 <= vr <= 1.5: sc += 10
    if vr > 3: sc -= 10
    return sc

def analyze_dt(dt):
    """分析一天的选股"""
    stocks = d.get(dt, [])
    all_scored = []
    for s in stocks:
        pct = s['p']
        if pct < 5 or pct > 8: continue
        vr = s.get('vol_ratio',0) or 0
        if vr < 0.5: continue
        code = s['code']
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > 15: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= 150: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > 80: continue
        cl = s.get('cl',0)
        bp = s.get('close',0)
        
        features = {
            'macd': s.get('macd_golden',0), 'kdj': s.get('kdj_golden',0),
            'ma5': s.get('above_ma5',0), 'yang': s.get('is_yang',0),
        }
        sc = score_v22(pct, vr, cl, features)
        nv = s.get('n',0) or 0
        
        all_scored.append({
            'code':code,'name':nm,'pct':pct,'vr':vr,'cl':cl,'hsl':hsl,
            'sz':sz,'jv':jv,'bp':bp,'sc':sc,'nv':nv,'features':features
        })
    
    if not all_scored: return None
    
    # 按评分排序
    ranked = sorted(all_scored, key=lambda x: (-x['sc'], -x['pct']))
    
    # 冠军（评分最高）
    champ = ranked[0]
    # 当天实际表现最好的（次日最高）
    best_performer = max(all_scored, key=lambda x: x['nv'])
    
    return {
        'dt':dt,
        'total':len(all_scored),
        'champ':champ,
        'best':best_performer,
        'all':ranked,
        'hits':[s for s in all_scored if s['nv'] >= 2.5],
        'misses':[s for s in all_scored if s['nv'] < 2.5],
    }

# ===== 全量分析 =====
all_2026 = [dt for dt in dates if dt.startswith('2026')]
results = []

print('正在分析2026年全部交易日...', flush=True)
for dt in all_2026:
    r = analyze_dt(dt)
    if r: results.append(r)

print(f'分析完成: {len(results)}天\n', flush=True)

# ===== 1. 冠军达标率 =====
champ_hits = sum(1 for r in results if r['champ']['nv'] >= 2.5)
champ_misses = sum(1 for r in results if r['champ']['nv'] < 2.5)
print(f'{"="*70}')
print(f'  一、冠军达标率')
print(f'{"="*70}')
print(f'  总天数: {len(results)}')
print(f'  冠军达标: {champ_hits}天 ({champ_hits/len(results)*100:.1f}%)')
print(f'  冠军未达标: {champ_misses}天 ({champ_misses/len(results)*100:.1f}%)')

# ===== 2. 冠军失败原因分析 =====
print(f'\n{"="*70}')
print(f'  二、冠军失败原因分析（评分最高但次日没达2.5%）')
print(f'{"="*70}')

# 收集所有失败冠军的特征分布
fail_features = defaultdict(list)
for r in results:
    c = r['champ']
    if c['nv'] < 2.5:
        fail_features['pct'].append(c['pct'])
        fail_features['vr'].append(c['vr'])
        fail_features['cl'].append(c['cl'])
        fail_features['hsl'].append(c['hsl'])
        fail_features['sz'].append(c['sz'])
        fail_features['jv'].append(c['jv'])
        fail_features['nv'].append(c['nv'])
        fail_features['sc'].append(c['sc'])

if fail_features['nv']:
    import statistics
    print(f'  失败冠军 {len(fail_features["nv"])}次')
    print(f'\n  特征平均值:')
    print(f'  {"特征":<12} {"失败冠军均值":<16} {"达标冠军均值":<16} {"差异":<10}')
    print(f'  {"":-<55}')
    
    # 达标冠军的均值
    hit_features = defaultdict(list)
    for r in results:
        c = r['champ']
        if c['nv'] >= 2.5:
            for k in ['pct','vr','cl','hsl','sz','jv','nv','sc']:
                hit_features[k].append(c[k])
    
    for k in ['pct','vr','cl','hsl','sz','jv','sc']:
        f_avg = statistics.mean(fail_features[k]) if fail_features[k] else 0
        h_avg = statistics.mean(hit_features[k]) if hit_features[k] else 0
        diff = f_avg - h_avg
        arrow = '↑' if diff > 0 else '↓'
        print(f'  {k:<12} {f_avg:<16.1f} {h_avg:<16.1f} {diff:<+7.1f} {arrow}', flush=True)

# ===== 3. 漏网之鱼分析 =====
print(f'\n{"="*70}')
print(f'  三、漏网之鱼分析（评分低但实际达标的票——为什么没被选中）')
print(f'{"="*70}')

missed_best = 0
total_hits = 0
for r in results:
    hits = r['hits']
    if not hits: continue
    total_hits += len(hits)
    # 最佳表现者不在Top3
    best = r['best']
    # 找best在排名中的位置
    rank = next(i+1 for i, s in enumerate(r['all']) if s['code'] == best['code'])
    if rank > 3:
        missed_best += 1
        # 分析为什么它评分低
        b = best
        sc_breakdown = []
        # 涨幅扣分？
        if b['pct'] > 7: sc_breakdown.append(f'涨>{b["pct"]:.0f}%扣15分')
        if b['pct'] > 6.5: sc_breakdown.append(f'涨{b["pct"]:.1f}%非最佳区间')
        if b['pct'] < 5: sc_breakdown.append(f'涨{b["pct"]:.1f}%低于5%')
        if b['cl'] > 90: sc_breakdown.append(f'CL{b["cl"]:.0f}%>90扣15分')
        if b['cl'] < 60 or b['cl'] > 85: sc_breakdown.append(f'CL{b["cl"]:.0f}%非最佳区间')
        if b['vr'] > 1.5 or b['vr'] < 0.8: 
            if b['vr'] > 3: sc_breakdown.append(f'量比{b["vr"]:.1f}>3扣10分')
            else: sc_breakdown.append(f'量比{b["vr"]:.1f}非最佳区间')
        
        if sc_breakdown:
            print(f'  {r["dt"]}: {b["name"]}({b["code"]}) 评{b["sc"]}分 排第{rank} | 次日最高{b["nv"]:+.1f}%🔥 | 原因: {", ".join(sc_breakdown[:3])}', flush=True)

print(f'\n  漏网Top1: {missed_best}/{total_hits}次最佳票没进Top3')

# ===== 4. 特征对比：达标vs不达标 =====
print(f'\n{"="*70}')
print(f'  四、达标票 vs 不达标票 特征分布（所有候选票）')
print(f'{"="*70}')

all_hit_features = defaultdict(list)
all_miss_features = defaultdict(list)
for r in results:
    for s in r['all']:
        target = all_hit_features if s['nv'] >= 2.5 else all_miss_features
        for k in ['pct','vr','cl','hsl','sz','jv','sc']:
            target[k].append(s[k])

print(f'  {"特征":<10} {"达标均值":<12} {"不达标均值":<12} {"差异":<8} {"结论":<20}')
print(f'  {"":-<65}')
for k in ['pct','vr','cl','hsl','sz','jv','sc']:
    h_avg = statistics.mean(all_hit_features[k]) if all_hit_features[k] else 0
    m_avg = statistics.mean(all_miss_features[k]) if all_miss_features[k] else 0
    diff = h_avg - m_avg
    if k == 'pct': conc = '涨幅高更好' if diff > 0 else '涨幅低更好'
    elif k == 'vr': conc = '量比高更好' if diff > 0 else '量比低更好'
    elif k == 'cl': conc = '收盘位高更好' if diff > 0 else '收盘位低更好'
    elif k == 'hsl': conc = '换手高更好' if diff > 0 else '换手低更好'
    elif k == 'sz': conc = '市值高更好' if diff > 0 else '小盘更好'
    elif k == 'jv': conc = 'J值高更好' if diff > 0 else 'J值低更好'
    elif k == 'sc': conc = '评分有效！' if diff > 0 else '评分失效！'
    print(f'  {k:<10} {h_avg:<12.1f} {m_avg:<12.1f} {diff:>+7.1f} {conc:<20}', flush=True)

# ===== 5. 分区间胜率 =====
print(f'\n{"="*70}')
print(f'  五、关键参数分区间胜率（达标概率）')
print(f'{"="*70}')

# 涨幅区间
pct_bins = [(5,5.5),(5.5,6),(6,6.5),(6.5,7),(7,8)]
print(f'\n  涨幅区间达标率:')
for lo, hi in pct_bins:
    vals = [s['nv'] for r in results for s in r['all'] if lo <= s['pct'] < hi]
    if vals:
        rate = sum(1 for v in vals if v >= 2.5)/len(vals)*100
        avg = sum(vals)/len(vals)
        print(f'    {lo:.1f}~{hi:.1f}%: {rate:.1f}% ({len(vals)}次, 均{avg:.2f}%)', flush=True)

# CL区间
cl_bins = [(0,60),(60,70),(70,80),(80,85),(85,90),(90,100)]
print(f'\n  CL区间达标率:')
for lo, hi in cl_bins:
    if lo == 0: continue
    vals = [s['nv'] for r in results for s in r['all'] if lo <= s['cl'] < hi]
    if vals:
        rate = sum(1 for v in vals if v >= 2.5)/len(vals)*100
        avg = sum(vals)/len(vals)
        print(f'    {lo:.0f}~{hi:.0f}%: {rate:.1f}% ({len(vals)}次, 均{avg:.2f}%)', flush=True)

# 量比区间
vr_bins = [(0.5,0.8),(0.8,1.0),(1.0,1.2),(1.2,1.5),(1.5,2.0),(2.0,2.5),(2.5,3.0),(3,10)]
print(f'\n  量比区间达标率:')
for lo, hi in vr_bins:
    vals = [s['nv'] for r in results for s in r['all'] if lo <= s['vr'] < hi]
    if vals:
        rate = sum(1 for v in vals if v >= 2.5)/len(vals)*100
        avg = sum(vals)/len(vals)
        print(f'    {lo:.1f}~{hi:.1f}: {rate:.1f}% ({len(vals)}次, 均{avg:.2f}%)', flush=True)

# J值区间
j_bins = [(0,30),(30,50),(50,65),(65,80),(80,90),(90,100)]
print(f'\n  J值区间达标率:')
for lo, hi in j_bins:
    vals = [s['nv'] for r in results for s in r['all'] if lo <= s['jv'] < hi]
    if vals:
        rate = sum(1 for v in vals if v >= 2.5)/len(vals)*100
        avg = sum(vals)/len(vals)
        print(f'    {lo:.0f}~{hi:.0f}: {rate:.1f}% ({len(vals)}次, 均{avg:.2f}%)', flush=True)

# ===== 6. 总结 =====
print(f'\n{"="*70}')
print(f'  六、总结与改进建议')
print(f'{"="*70}')
print(f'''
从{len(results)}天数据分析发现：

1. 冠军失败特征：''' + (f'平均涨幅{fail_features["pct"][0]:.1f}%→次日{fail_features["nv"][0]:.2f}%' if fail_features['pct'] else '') + '''
   - 失败冠军的''' + ('CL偏高' if statistics.mean(fail_features['cl']) > statistics.mean(hit_features['cl']) else 'CL偏低') if fail_features['cl'] else ''
)
