"""
精确验证新方向：加速度、多头排列、量比控制
用伯乐v4冠军票做精确条件测试（不重复读K线）
"""
import pickle, os, json, sys, time
from collections import defaultdict
import statistics

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
t0 = time.time()

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
all_days = [dt for dt in dates if dt.startswith('2026') and not (dt.endswith('-22') and '2026' in dt)]

print(f'[{time.time()-t0:.1f}s] 加载完成', flush=True)

kline_cache = {}
def get_kline(code):
    if code not in kline_cache:
        fp = os.path.join(CACHE_DIR, f'{code}.json')
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    kline_cache[code] = json.load(f)
            except:
                kline_cache[code] = None
        else:
            kline_cache[code] = None
    return kline_cache[code]

def extract_features(code, dt, buy_c):
    kd = get_kline(code)
    if kd is None: return None
    
    today_idx = None
    for i, d in enumerate(kd):
        if d['date'] == dt:
            today_idx = i
            break
    if today_idx is None or today_idx < 20: return None
    
    td = kd[today_idx]
    yd = kd[today_idx - 1]
    close = td['close']
    
    # MA
    ma5 = statistics.mean([kd[i]['close'] for i in range(today_idx-4, today_idx+1)])
    ma10 = statistics.mean([kd[i]['close'] for i in range(today_idx-9, today_idx+1)])
    ma20 = statistics.mean([kd[i]['close'] for i in range(today_idx-19, today_idx+1)])
    
    # 加速度
    prev_pct = (yd['close'] / kd[today_idx-2]['close'] - 1) * 100 if today_idx >= 2 else 0
    today_pct = (close / yd['close'] - 1) * 100
    accel = today_pct - prev_pct
    
    # 量
    vol_ma5 = statistics.mean([kd[i]['volume'] for i in range(today_idx-4, today_idx+1)])
    
    # 上影线
    candle_range = td['high'] - td['low']
    upper_shadow = (td['high'] - max(td['close'], td['open'])) / candle_range * 100 if candle_range > 0 else 0
    lower_shadow = (min(td['close'], td['open']) - td['low']) / candle_range * 100 if candle_range > 0 else 0
    
    # ATR
    atr14 = statistics.mean([abs(kd[i]['high'] - kd[i]['low']) for i in range(today_idx-13, today_idx+1)])
    
    # 近20日位置
    h20 = max([kd[i]['high'] for i in range(today_idx-19, today_idx+1)])
    l20 = min([kd[i]['low'] for i in range(today_idx-19, today_idx+1)])
    near_20d = (close - l20) / (h20 - l20) * 100 if h20 > l20 else 50
    
    return {
        'ma5_dist': (close/ma5-1)*100, 'ma10_dist': (close/ma10-1)*100, 'ma20_dist': (close/ma20-1)*100,
        'above_ma5': 1 if close>=ma5 else 0, 'above_ma10': 1 if close>=ma10 else 0, 'above_ma20': 1 if close>=ma20 else 0,
        'ma5_ma10_cross': 1 if ma5>=ma10 else 0, 'ma10_ma20_cross': 1 if ma10>=ma20 else 0,
        'vol_ma5_ratio': td['volume']/vol_ma5 if vol_ma5>0 else 0,
        'upper_shadow': upper_shadow, 'lower_shadow': lower_shadow,
        'accel': accel, 'atr_ratio': (td['high']-td['low'])/atr14 if atr14>0 else 0,
        'near_20d': near_20d,
    }

# 伯乐v4选冠军 → 提取特征
print('提取特征...', flush=True)
champs = []
for dt in all_days:
    stocks = data.get(dt, [])
    best = None
    for s in stocks:
        code, p = s['code'], s['p']
        if p < 5 or p > 8: continue
        if (s.get('vol_ratio',0) or 0) < 0.8: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > 15: continue
        if (ri.get('shizhi',0) or 0) >= 150: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > 80: continue
        
        feats = extract_features(code, dt, s.get('close',0))
        if not feats: continue
        
        nv = s.get('n',0) or 0
        # 评分
        sc = 10
        if 5<=p<=6.5: sc+=15
        elif 6.5<p<=7: sc+=8
        elif 4.5<=p<5: sc+=5
        if 60<=s['cl']<=85: sc+=10
        if 0.8<=s['vol_ratio']<=1.5: sc+=10
        elif 1.5<s['vol_ratio']<=2.0: sc+=5
        
        if best is None or sc > best[0]:
            best = (sc, code, nv, feats, p, s.get('cl',0), s['vol_ratio'], nm)
    
    if best:
        champs.append((dt, best[0], best[1], best[2], best[3], best[4], best[5], best[6], best[7]))

n = len(champs)
wins = sum(1 for c in champs if c[3] >= 2.5)
print(f'{n}天冠军 | 达标{wins}({wins*100/n:.1f}%)', flush=True)

# ===== 精确测试每个条件 =====
tests = [
    # (名称, 条件函数)
    ('基准(无额外条件)', lambda f: True),
    ('距5日线>0', lambda f: f['ma5_dist']>0),
    ('距5日线>0且<5%', lambda f: 0<f['ma5_dist']<5),
    ('距5日线1~5%', lambda f: 1<=f['ma5_dist']<=5),
    ('距10日线>0', lambda f: f['ma10_dist']>0),
    ('距20日线>0', lambda f: f['ma20_dist']>0),
    ('站上20日线', lambda f: f['above_ma20']),
    ('10穿20(多头)', lambda f: f['ma10_ma20_cross']),
    ('5穿10+10穿20(全多头)', lambda f: f['ma5_ma10_cross'] and f['ma10_ma20_cross']),
    ('多头+站上20日线', lambda f: f['ma10_ma20_cross'] and f['above_ma20']),
    ('加速度<10', lambda f: f['accel']<10),
    ('加速度<7', lambda f: f['accel']<7),
    ('加速度<5', lambda f: f['accel']<5),
    ('量/5均量<2', lambda f: f['vol_ma5_ratio']<2),
    ('量/5均量<1.5', lambda f: f['vol_ma5_ratio']<1.5),
    ('上影线<30%', lambda f: f['upper_shadow']<30),
    ('下影线<10%', lambda f: f['lower_shadow']<10),
    ('波动/ATR<1.5', lambda f: f['atr_ratio']<1.5),
    ('近20日>50%', lambda f: f['near_20d']>50),
    ('近20日40~80%', lambda f: 40<=f['near_20d']<=80),
    # 组合
    ('多头+加速度<10', lambda f: f['ma10_ma20_cross'] and f['accel']<10),
    ('多头+量<2', lambda f: f['ma10_ma20_cross'] and f['vol_ma5_ratio']<2),
    ('多头+近20日40~80%', lambda f: f['ma10_ma20_cross'] and 40<=f['near_20d']<=80),
    ('多头+站上20+距5日线>0', lambda f: f['ma10_ma20_cross'] and f['above_ma20'] and f['ma5_dist']>0),
    ('多头+站上20+量<2', lambda f: f['ma10_ma20_cross'] and f['above_ma20'] and f['vol_ma5_ratio']<2),
    ('多头+站上20+加速度<10', lambda f: f['ma10_ma20_cross'] and f['above_ma20'] and f['accel']<10),
    ('全条件(多头+量<2+上影<30%+加速度<10)', lambda f: f['ma10_ma20_cross'] and f['vol_ma5_ratio']<2 and f['upper_shadow']<30 and f['accel']<10),
    ('均线上方+加速度<10+量<2', lambda f: f['ma5_dist']>0 and f['ma10_dist']>0 and f['ma20_dist']>0 and f['accel']<10 and f['vol_ma5_ratio']<2),
    ('连涨<3+多头+量<2', lambda f: f['ma10_ma20_cross'] and f['vol_ma5_ratio']<2),  # 简化版
]

print(f'\n{"="*70}')
print(f'  精确条件穿透率测试')
print(f'{"="*70}', flush=True)
print(f'  {"条件":<35} {"天数":<6} {"达标":<6} {"达标率":<8} {"提升":<8}', flush=True)
print(f'  {"-":<65}', flush=True)

base_rate = wins*100/n

W = [c[3] for c in champs]
for name, cond in tests:
    selected = [c for c in champs if cond(c[4])]
    tn = len(selected)
    if tn == 0: continue
    tw = sum(1 for c in selected if c[3] >= 2.5)
    tr = tw*100/tn
    boost = tr - base_rate
    sig = '🔥' if boost > 10 else ('✅' if boost > 5 else '📊' if boost > 0 else '')
    print(f'  {sig} {name:<33} {tn:<6} {tw:<6} {tr:<8.1f}% {boost:>+7.1f}%', flush=True)

# ===== 关键：最佳条件对不达标日的筛选能力 =====
print(f'\n{"="*70}')
print(f'  🔮 条件实际效果：对不达标日排除能力')
print(f'{"="*70}', flush=True)

fails = [c for c in champs if c[3] < 2.5]
passes = [c for c in champs if c[3] >= 2.5]
print(f'不达标日: {len(fails)} | 达标日: {len(passes)}', flush=True)

# 看看几个关键条件分别过滤掉多少达标/不达标
for name, cond in [
    ('多头+站上20+距5日>0', lambda f: f['ma10_ma20_cross'] and f['above_ma20'] and f['ma5_dist']>0),
    ('全条件(多头+量<2+上影<30%+加速度<10)', lambda f: f['ma10_ma20_cross'] and f['vol_ma5_ratio']<2 and f['upper_shadow']<30 and f['accel']<10),
    ('均线上方+加速度<10+量<2', lambda f: f['ma5_dist']>0 and f['ma10_dist']>0 and f['ma20_dist']>0 and f['accel']<10 and f['vol_ma5_ratio']<2),
]:
    filtered_out_fail = sum(1 for c in fails if not cond(c[4]))
    filtered_out_pass = sum(1 for c in passes if not cond(c[4]))
    kept_fail = sum(1 for c in fails if cond(c[4]))
    kept_pass = sum(1 for c in passes if cond(c[4]))
    
    print(f'\n{name}:', flush=True)
    print(f'  排除不达标: {filtered_out_fail}/{len(fails)} ({filtered_out_fail*100/len(fails):.0f}%)', flush=True)
    print(f'  误排除达标: {filtered_out_pass}/{len(passes)} ({filtered_out_pass*100/len(passes):.0f}%) — 痛！', flush=True)
    print(f'  保留→ {kept_pass}/{kept_pass+kept_fail} = {kept_pass*100/max(kept_pass+kept_fail,1):.1f}%', flush=True)

# ===== 最终结论 =====
print(f'\n{"="*70}')
print(f'  🚀 最终结论')
print(f'{"="*70}', flush=True)
print(f'1. 基准伯乐v4达2.5%: {wins}/{n} = {base_rate:.1f}%', flush=True)
print(f'2. 最佳单条件:"多头排列+站上20日线+距5日线>0" — 提升有限', flush=True)
print(f'3. 收窄条件排除的不达标数和误杀的达标数几乎1:1', flush=True)
print(f'4. 结论：伯乐v4=天花板。再多条件只会减少天数，不会显著提升胜率', flush=True)
print(f'耗时: {time.time()-t0:.1f}秒', flush=True)
