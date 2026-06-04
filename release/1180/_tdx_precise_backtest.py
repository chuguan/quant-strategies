#!/usr/bin/env python3
"""
精确回测: 用通达信5分钟K线数据,模拟回望-0.3%策略
比日最高价模拟更精确 — 每5分钟跟踪一次价格
"""
import pickle, os, sys, importlib, time, json
from pytdx.hq import TdxHq_API
from collections import defaultdict
from datetime import datetime, timedelta

DIR = 'C:/Users/12546/AppData/Local/hermes/scripts/release/1180'
STRATEGY_DIR = os.path.join(DIR, '评分策略')
PKL = 'C:/Users/12546/AppData/Local/hermes/scripts/big_cache_full.pkl'
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')

# 加载big_cache获取冠军数据
with open(PKL, 'rb') as f:
    d = pickle.load(f)
data, real, names = d['data'], d.get('real',{}), d.get('names',{})

all_dates = sorted(k for k in data.keys())

# ===== 加载评分策略(和之前的回测一样) =====
def load_mod(name):
    fp = os.path.join(STRATEGY_DIR, f'分而治之_V10_{name}_评分策略.py')
    spec = importlib.util.spec_from_file_location('m', fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
STRATS = {}
for n in ['真实涨日','虚涨日','跌日','横盘']:
    STRATS[n] = load_mod(n)
MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4']

def mkt_class(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p',0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if ap > 0.5: return 'fake_up' if hot < 15 or av < 0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

def is_momentum_exhausted(s, code, dt):
    feats = precomputed.get((code, dt), {})
    if not feats: return False
    sl5 = feats.get('slope5',0); t4s = feats.get('t4_shadow',0)
    cu = feats.get('cons_up',0); pk = feats.get('peak_decay',0)
    pv = s.get('p',0) or 0
    if sl5 > 8 and t4s > 25: return True
    if sl5 > 10 and t4s > 18: return True
    if cu >= 5 and sl5 > 15: return True
    if pk > 5 and sl5 > 5 and pv < 6: return True
    if sl5 > 5 and t4s > 30: return True
    if cu >= 4 and sl5 > 10 and pv < 7: return True
    return False

def compute_7day_decay_penalty(code, dt, p_today):
    all_dates = sorted(data.keys())
    idx = all_dates.index(dt); prev = all_dates[max(0,idx-6):idx]
    gains = []
    for pd in prev:
        found = False
        for s in data[pd]:
            if s['code'] == code:
                gains.append(s.get('p',0) or 0); found = True; break
        if not found: gains.append(0)
    gains.append(p_today); n = len(gains)
    if n < 5: return 0
    d6,d5,d4,d3,d2,d1,p = gains[-7:] if n>=7 else [0]*(7-n)+gains
    penalty = 0; p_is_max = p >= max(gains[:-1]) if len(gains)>1 else True
    avg_7d = sum(gains)/n; wrv = 50
    for s in data.get(dt,[]):
        if s['code'] == code: wrv = s.get('wr_val',50) or s.get('wrv',50); break
    if wrv<10 and p_is_max and avg_7d<2.0 and p<6: penalty -= 8
    if p_is_max and avg_7d<0.8 and p<8:
        if avg_7d<0: penalty-=15
        elif avg_7d<0.3: penalty-=12
        elif avg_7d<0.7: penalty-=8
        else: penalty-=5
    if d1<-1.5 and d2<-1.0 and p>3 and avg_7d<1.0: penalty-=8
    if max(d4,d3,d2)>5 and d1<0 and d2<0: penalty-=10
    return penalty

with open(os.path.join(DIR, 'features_30d.pkl'), 'rb') as f:
    precomputed = pickle.load(f)

def v10_score(s, code, dt, mk_cn):
    mod = STRATS[mk_cn]
    stock = {}
    stock['p'] = s.get('p',0) or 0; stock['cl'] = s.get('cl',50)
    stock['vr'] = s.get('vol_ratio',1) or s.get('vr',1)
    stock['dif'] = s.get('dif_val',0) or s.get('dif',0)
    stock['mg'] = s.get('macd_golden',0) or s.get('mg',0)
    stock['wrv'] = s.get('wr_val',0) or s.get('wrv',50)
    stock['jv'] = s.get('j_val',0) or s.get('jv',50)
    stock['kv'] = s.get('k_val',0) or s.get('kv',50)
    stock['dv'] = s.get('d_val',0) or s.get('dv',50)
    stock['a5'] = s.get('above_ma5',0); stock['kdj_g'] = s.get('kdj_golden',0) or s.get('kdj_g',0)
    stock['pos_in_day'] = s.get('pos_in_day',50)
    stock['nm'] = s.get('nm','') or names.get(s['code'],'')
    ri = real.get(s['code'],{}); stock['hsl'] = ri.get('hsl',0) or 0
    feats = precomputed.get((code, dt), {})
    stock['t4_shadow'] = feats.get('t4_shadow',0); stock['slope5'] = feats.get('slope5',0)
    stock['cons_up'] = feats.get('cons_up',0); stock['d1'] = feats.get('d1',0)
    stock['d2'] = feats.get('d2',0); stock['d3'] = feats.get('d3',0)
    stock['ma5_slope'] = feats.get('ma5_slope',0)
    sp = compute_7day_decay_penalty(code, dt, s.get('p',0) or 0)
    return round(mod.score(stock) + sp, 1)

# ===== 跑冠军 =====
champs = []
for dt in all_dates[-100:]:
    ss = data.get(dt,[]); ss = [s for s in ss if (s.get('p',0) or 0) < 15]
    if not ss: continue
    mk = mkt_class(ss); mk_cn = MK_MAP.get(mk,'横盘')
    mod = STRATS.get(mk_cn)
    if not mod: continue
    LEVELS = getattr(mod, 'LEVELS', None)
    if not LEVELS: continue
    lm = {l['name']:i for i,l in enumerate(LEVELS)}
    pool = None
    for ln in LO:
        if ln not in lm: continue
        lv = LEVELS[lm[ln]]; cand = []
        for s in ss:
            p = s.get('p',0) or 0
            if p < lv['p_min'] or p > min(lv.get('p_max',10),8): continue
            vr = s.get('vol_ratio',0) or 0
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            ri = real.get(s['code'],{}); hsl = ri.get('hsl',0) or 0
            if hsl < lv.get('hs_min',0) or hsl > lv.get('hs_max',99): continue
            nm = names.get(s['code'],'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl = s.get('cl',0)
            if cl < lv.get('cl_min',0) or cl > lv.get('cl_max',100): continue
            if is_momentum_exhausted(s, s['code'], dt): continue
            cand.append(s)
        if len(cand) >= 10: pool = cand; break
    if not pool: continue
    scored = [(v10_score(s, s['code'], dt, mk_cn), s) for s in pool]
    scored.sort(key=lambda x:-x[0])
    champ = scored[0][1]
    champs.append({
        'dt': dt, 'code': champ['code'], 'name': names.get(champ['code'],'?'),
        'p': champ.get('p',0) or 0,
        'close': champ.get('close',0) or 0,
        'd1h': champ.get('d1h',0) or 0,
        'nl': champ.get('nl',0) or 0,
        'n': champ.get('n',0) or 0,
    })

c30 = champs[-30:]
print(f'共{len(c30)}笔冠军, 获取通达信5分钟K线模拟回望...\n')

# ===== 获取5分钟K线数据 =====
api = TdxHq_API()
api.connect('110.41.147.114', 7709)

# 对每笔冠军,获取下一交易日5分钟K线数据
minute_cache = {}  # 缓存key: (code, date_str) → [bars]

def get_minute_data(code, target_date_str):
    """获取历史分时数据(每分钟1个价格, 9:30~15:00共240条)"""
    key = (code, target_date_str)
    if key in minute_cache:
        return minute_cache[key]
    
    market = 1 if code.startswith(('6','9')) else 0
    date_int = int(target_date_str.replace('-', ''))
    
    try:
        bars = api.get_history_minute_time_data(market, code, date_int)
        if not bars or len(bars) == 0:
            minute_cache[key] = []
            return []
        
        # bars是按顺序的(9:30到15:00)
        # 每个bar: {'price': xxx, 'vol': xxx}
        minute_cache[key] = bars
        return bars
    except:
        minute_cache[key] = []
        return []

def simulate_trailing(bars, buy_price, trail_pct=0.3):
    """在分钟级分时数据上模拟回望-0.3%策略
    每分钟检查一次,精确模拟条件单触发
    """
    if not bars:
        return None
    
    buy_price = float(buy_price)
    if buy_price <= 0:
        return None
    
    peak_price = buy_price
    trailing_activated = False
    sell_price = None
    sell_idx = None
    
    # 找到14:50的分钟作为买入参考
    # 分时数据240根对应9:30~14:50实际是200根(9:30~11:30=120, 13:00~14:50=110)
    # 但具体索引要看API返回
    # 9:30 = 索引0, 9:31=索引1, ... 14:50=索引200
    
    for i, b in enumerate(bars):
        price = float(b['price'])
        if price <= 0:
            continue
        
        cur_pct = (price - buy_price) / buy_price * 100
        
        # 更新最高价
        peak_price = max(peak_price, price)
        
        if not trailing_activated:
            if cur_pct >= 3.0:
                trailing_activated = True
                # 更新peak为当前价
                peak_price = max(peak_price, price)
        
        if trailing_activated:
            # 从最高点回落0.3%
            drop_from_peak = (peak_price - price) / peak_price * 100
            if drop_from_peak >= trail_pct:
                sell_price = price
                sell_idx = i
                break
    
    # 如果没触发,用最后价格
    if sell_price is None:
        last_price = float(bars[-1]['price']) if bars else buy_price
        ret = (last_price - buy_price) / buy_price * 100
        return {
            'activated': trailing_activated,
            'sold': False,
            'sell_price': round(last_price, 2),
            'return_pct': round(ret, 1),
            'sell_reason': '收盘清仓',
            'peak': round((peak_price - buy_price) / buy_price * 100, 1),
        }
    else:
        ret = (sell_price - buy_price) / buy_price * 100
        return {
            'activated': trailing_activated,
            'sold': True,
            'sell_price': round(sell_price, 2),
            'return_pct': round(ret, 1),
            'sell_reason': f'回望(sell_idx={sell_idx})',
            'peak': round((peak_price - buy_price) / buy_price * 100, 1),
        }

# ===== 逐笔模拟 =====
results = []
success = 0
fail = 0
total_ret_sum = 0

print(f'{"天":>3} {"日期":>12} {"票":>10} {"分时数据":>8} {"峰值":>5} {"收益":>6} {"操作"}')
print('-'*60)

for i, c in enumerate(c30):
    dt = c['dt']
    code = c['code']
    name = c['name']
    
    # 下一交易日
    try:
        idx = all_dates.index(dt)
        if idx + 1 >= len(all_dates):
            continue
        next_date = all_dates[idx + 1]
    except:
        continue
    
    # 获取历史分时数据
    bars = get_minute_data(code, next_date)
    if not bars:
        print(f'{i+1:>3} {dt:>12} {name:>10} {"⏳ 无数据":>20}')
        fail += 1
        continue
    
    # 买入价=big_cache里的close
    buy_price = c['close']
    
    # 模拟回望
    result = simulate_trailing(bars, buy_price, trail_pct=0.3)
    if result:
        results.append({'idx': i, 'date': dt, 'name': name, 'code': code, **result})
        emoji = '✅' if result['return_pct'] >= 2 else ('💸' if result['return_pct'] < 0 else '⏸️')
        peak_str = f'+{result["peak"]:.1f}%' if result['peak'] > 0 else '0%'
        ret_str = f'{result["return_pct"]:+.1f}%'
        print(f'{i+1:>3} {dt:>12} {name:>10} {len(bars):>3}根 {peak_str:>6} {ret_str:>6} {emoji} {result["sell_reason"]}')
        
        if result['return_pct'] >= 2:
            success += 1
        
        total_ret_sum += result['return_pct'] or 0
    else:
        print(f'{i+1:>3} {dt:>12} {name:>10} {"模拟失败":>20}')
        fail += 1
    
    # 慢点请求,别被封
    time.sleep(0.3)

api.disconnect()

# ===== 结果汇总 =====
print(f'\n{"="*60}')
print(f'📊 通达信5分钟K线精确回测: 回望-0.3%')
print(f'{"="*60}')
print(f'成功模拟: {len(results)}笔')
print(f'无数据: {fail}笔')
wins = sum(1 for r in results if r['return_pct'] >= 2)
print(f'止盈(>+2%): {wins}笔')
print(f'回望激活: {sum(1 for r in results if r.get("activated"))}笔')
print(f'触发卖出: {sum(1 for r in results if r.get("sold"))}笔')

# 复利计算
cap = 30000
for r in results:
    cap *= (1 + (r['return_pct'] or 0)/100)
print(f'\n3万复利30天: ¥{cap:,.0f} (+{(cap/30000-1)*100:.1f}%)')

# 与日最高价模拟对比
print(f'\n对比日最高价模拟(d1h-0.3%):')
cap_old = 30000
for c in c30:
    if c['d1h'] >= 3.0:
        ret = c['d1h'] - 0.3
    else:
        ret = c['nl'] if c['nl'] > -7 else -7
    cap_old *= (1 + ret/100)
print(f'  日最高价模拟: ¥{cap_old:,.0f} (+{(cap_old/30000-1)*100:.1f}%)')
print(f'  5分钟K线模拟: ¥{cap:,.0f} (+{(cap/30000-1)*100:.1f}%)')
