"""
V13 2:50 PM 回测 — 使用AkShare 5分钟K线数据
流程:
  1. 用daily数据跑V13完整流程，记录每天候选股
  2. 对候选股逐个下载5分钟K线，获取14:50真实价格/高/低/量
  3. 用2:50数据重算p/CL/量比
  4. V13评分+冠亚军 → 次日验证
"""
import os, sys, pickle, json, time
from datetime import datetime, timedelta

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
sys.path.insert(0, V13_DIR)

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'
LEVEL_NAMES = ['L', 'L1', 'L2', 'L3', 'L4', 'L5']

# 加载big_cache
print('加载缓存数据...')
with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
BIG_DATA, BIG_REAL, BIG_NAMES = d['data'], d.get('real',{}), d['names']
ALL_DATES = sorted(BIG_DATA.keys())

# 加载V13评分策略
import importlib

def load_strategy(mkt_key):
    info = {
        'real_up': {'module': '分而治之_V10_真实涨日_评分策略'},
        'fake_up': {'module': '分而治之_V10_虚涨日_评分策略'},
        'down': {'module': '分而治之_V10_跌日_评分策略'},
        'flat': {'module': '分而治之_V10_横盘_评分策略'},
    }[mkt_key]
    spec = importlib.util.spec_from_file_location(info['module'],
        os.path.join(V13_DIR, '评分策略', f'{info["module"]}.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    levels = mod.LEVELS
    renamed = []
    for lv in levels:
        name = lv['name']
        if name == 'L0': name = 'L'
        renamed.append({**lv, 'name': name})
    if levels:
        last = levels[-1]
        renamed.append({"name":"L5","p_min":last["p_min"]-3,"p_max":last["p_max"],
            "vr_min":max(0.1,last["vr_min"]-0.2),"vr_max":last["vr_max"]+2,
            "hs_min":max(0.1,last["hs_min"]-1),"hs_max":last["hs_max"]+15,
            "sz_max":last["sz_max"]+200,"cl_min":max(0,last["cl_min"]-15),"cl_max":100})
    return renamed, mod, mod.score

STRATS = {k: load_strategy(k) for k in ['real_up','fake_up','down','flat']}

# 5分钟K线缓存
MIN5_CACHE = {}

def get_min5(code):
    """获取5分钟K线（缓存+下载）"""
    if code in MIN5_CACHE:
        return MIN5_CACHE[code]
    try:
        import akshare as ak
        sym = f"{PREFIX(code)}{code}"
        df = ak.stock_zh_a_minute(symbol=sym, period='5')
        MIN5_CACHE[code] = df
        return df
    except Exception as e:
        MIN5_CACHE[code] = None
        return None

def calc_250_metrics(code, date_str, prev_close):
    """从5分钟K线计算2:50指标"""
    df = get_min5(code)
    if df is None or len(df) == 0:
        return None
    
    # 当天所有bars
    day_bars = df[df['day'].str.startswith(date_str)]
    if len(day_bars) == 0:
        return None
    
    # 找到14:50的bar及其之前的全部bars
    bars_250 = day_bars[day_bars['day'] <= f"{date_str} 14:50:00"]
    if len(bars_250) == 0:
        return None
    
    # 14:50 bar
    h250_bar = bars_250.iloc[-1]
    # 价格
    price_250 = float(h250_bar['close'])
    # 截至14:50的日内高/低
    high_250 = float(bars_250['high'].max())
    low_250 = float(bars_250['low'].min())
    # 截至14:50的成交量
    vol_250 = float(bars_250['volume'].sum())
    # 开盘价
    open_250 = float(day_bars.iloc[0]['open'])
    
    # 转成可用的特征值
    p_250 = round((price_250 - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0
    cl_250 = round((price_250 - low_250) / (high_250 - low_250) * 100, 2) if (high_250 - low_250) > 0 else 50
    
    return {
        'p': p_250,
        'cl': cl_250,
        'price': price_250,
        'high': high_250,
        'low': low_250,
        'volume': vol_250,
        'open': open_250,
        'high_ratio': cl_250,  # same as CL
    }

def build_250_stock_dict(s, dt, m250):
    """用2:50数据替换当日部分指标"""
    from copy import deepcopy
    d = deepcopy(s) if isinstance(s, dict) else {}
    
    # 用2:50数据替换
    d['p'] = m250['p']
    d['cl'] = m250['cl']
    
    # 其他指标保持daily数据（dif/wr/j等）
    return d

def classify_market(dt, stocks):
    if not stocks: return 'flat'
    ps = [s.get('p',0) or 0 for s in stocks]
    avg_p = sum(ps)/len(ps) if ps else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    vrs = [s.get('vr',1) or 1 for s in stocks if s.get('vr')]
    avg_vr = sum(vrs)/len(vrs) if vrs else 0
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

def run_250_backtest():
    """主回测函数"""
    # 可用的日期范围（需有5分钟数据）
    print('检查5分钟数据可用日期范围...')
    test_df = None
    try:
        import akshare as ak
        test_df = ak.stock_zh_a_minute(symbol='sh600519', period='5')
    except:
        print('akshare 不可用')
        return
    
    min_dates = sorted(test_df[test_df['day'].str.contains('14:50')]['day'].str[:10].unique())
    print(f'可用日期范围: {min_dates[0]} ~ {min_dates[-1]} ({len(min_dates)}个交易日)')
    
    # 只回测这些日期（需前一天作为prev_close参考）
    bt_dates = [d for d in ALL_DATES if d in min_dates]
    if not bt_dates:
        print('日期不匹配！')
        return
    
    print(f'将回测 {len(bt_dates)} 天')
    
    results = {
        'close_based': {'win': 0, 'total': 0},  # 原始close回测
        'at_250': {'win': 0, 'total': 0},        # 2:50调整后
        'champion_diff': [],  # 冠军变化追踪
    }
    
    for idx, dt in enumerate(bt_dates):
        if idx == 0: continue  # 跳过第一天（无prev_close数据支持）
        
        # 获取当天数据
        if dt not in BIG_DATA: continue
        day_stocks = BIG_DATA[dt]
        if not day_stocks: continue
        
        # 行情分类
        mk = classify_market(dt, day_stocks)
        levels, mod, score_fn = STRATS[mk]
        lm = {l['name']:i for i,l in enumerate(levels)}
        
        # CLOSE-BASED: 原始V13
        pool_close = []
        for ln in LEVEL_NAMES:
            if ln not in lm: continue
            i = lm[ln]; lv = levels[i]
            for s in day_stocks:
                p = s.get('p', 0) or 0
                if p < lv['p_min'] or p > min(lv.get('p_max', 10), 8): continue
                vr = s.get('vol_ratio', 0) or s.get('vr', 0) or 0
                if vr < lv['vr_min'] or vr > lv['vr_max']: continue
                nm = s.get('name', '') or BIG_NAMES.get(s['code'], '')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl = s.get('cl', 0) or 50
                if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
                pool_close.append(s)
            if len(pool_close) >= 10:
                break
        
        if len(pool_close) < 10:
            continue
        
        # 2:50调整：对每个候选股下载5分钟数据
        pool_250 = []
        for s in pool_close:
            code = s['code']
            prev_close = s.get('pre_close', 0) or 0
            # 上一交易日收盘价
            if idx > 0:
                prev_dt = bt_dates[idx-1]
                for ps in BIG_DATA.get(prev_dt, []):
                    if ps['code'] == code:
                        prev_close = ps.get('close', 0) or ps.get('p', 0) or 0
                        break
            
            m250 = calc_250_metrics(code, dt, prev_close)
            if m250 is None:
                # 无5分钟数据则跳过这只
                continue
            
            # 重新检查LEVELS（用2:50的p/cl）
            p_250 = m250['p']
            cl_250 = m250['cl']
            
            # 找到第一个能过的level
            passed = False
            for ln in LEVEL_NAMES:
                if ln not in lm: continue
                i = lm[ln]; lv = levels[i]
                if p_250 < lv['p_min'] or p_250 > min(lv.get('p_max', 10), 8): continue
                if cl_250 < lv.get('cl_min', 0) or cl_250 > lv.get('cl_max', 100): continue
                passed = True
                break
            
            if not passed:
                continue
            
            # 重算评分
            sd = {
                'code': code,
                'p': p_250,
                'cl': cl_250,
                'vr': s.get('vr', 1),  # VR用daily close的（5分钟里不好算）
                'hsl': s.get('hsl', 0),
                'dif': s.get('dif_val', 0) or s.get('dif', 0),
                'mg': s.get('macd_golden', 0) or s.get('mg', 0),
                'a5': s.get('above_ma5', 0) or 0,
                'wrv': s.get('wr_val', 0) or s.get('wrv', 50),
                'jv': s.get('j_val', 0) or s.get('jv', 50),
                'pos_in_day': m250['high_ratio'],  # 用2:50CL代替
                'nm': s.get('name', '') or BIG_NAMES.get(code, ''),
            }
            base = score_fn(sd)
            pool_250.append((base, code, p_250, m250))
        
        if len(pool_250) < 3:
            continue
        
        pool_250.sort(key=lambda x: -x[0])
        
        # 验证D+1
        next_dt = None
        for nd in ALL_DATES:
            if nd > dt:
                next_dt = nd
                break
        
        if next_dt and next_dt in BIG_DATA:
            next_stocks = {s['code']: s for s in BIG_DATA[next_dt]}
            
            # Close-based冠军
            scored_close = [(score_fn({
                'p': s.get('p',0), 'cl': s.get('cl',50), 'vr': s.get('vr',1),
                'hsl': s.get('hsl',0), 'dif': s.get('dif_val',0) or s.get('dif',0),
                'mg': s.get('macd_golden',0) or s.get('mg',0),
                'a5': s.get('above_ma5',0) or 0,
                'wrv': s.get('wr_val',0) or s.get('wrv',50),
                'jv': s.get('j_val',0) or s.get('jv',50),
                'pos_in_day': s.get('pos_in_day',50),
                'nm': s.get('name','') or BIG_NAMES.get(s['code'],''),
            }), s) for s in pool_close]
            scored_close.sort(key=lambda x: -x[0])
            champ_close = scored_close[0][1]
            
            # Close-based outcome
            if champ_close['code'] in next_stocks:
                ns = next_stocks[champ_close['code']]
                nh = float(ns.get('n', 0) or 0)
                if nh >= 2.5:
                    results['close_based']['win'] += 1
                results['close_based']['total'] += 1
            
            # 2:50冠军
            champ_250 = pool_250[0]
            if champ_250[1] in next_stocks:
                ns = next_stocks[champ_250[1]]
                nh = float(ns.get('n', 0) or 0)
                if nh >= 2.5:
                    results['at_250']['win'] += 1
                results['at_250']['total'] += 1
            
            # 冠军是否不同
            if champ_close['code'] != champ_250[1]:
                results['champion_diff'].append((dt, champ_close['code'], champ_250[1]))
        
        if (idx+1) % 5 == 0:
            cb = results['close_based']
            a2 = results['at_250']
            print(f"  [{idx+1}/{len(bt_dates)}] close:{cb['win']}/{cb['total']}={cb['win']/max(cb['total'],1)*100:.0f}% "
                  f"2:50:{a2['win']}/{a2['total']}={a2['win']/max(a2['total'],1)*100:.0f}% "
                  f"冠军不同:{len(results['champion_diff'])}天")
    
    # 最终结果
    print('\n' + '='*60)
    print('V13 2:50 PM 回测结果')
    print('='*60)
    cb = results['close_based']
    a2 = results['at_250']
    print(f'\n基于close的冠军胜率: {cb["win"]}/{cb["total"]} = {cb["win"]/max(cb["total"],1)*100:.1f}%')
    print(f'基于2:50的冠军胜率:  {a2["win"]}/{a2["total"]} = {a2["win"]/max(a2["total"],1)*100:.1f}%')
    if cb['total'] > 0 and a2['total'] > 0:
        diff = a2['win']/max(a2['total'],1) - cb['win']/max(cb['total'],1)
        print(f'差异: {diff*100:+.1f}%')
    
    print(f'\n冠军不同的天数: {len(results["champion_diff"])}/{a2["total"]}')
    if results['champion_diff']:
        print('冠军变化样本:')
        for dt, old, new in results['champion_diff'][:5]:
            print(f'  {dt}: close冠军={old} → 2:50冠军={new}')
    
    return results

if __name__ == '__main__':
    run_250_backtest()
