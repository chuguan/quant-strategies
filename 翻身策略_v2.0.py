"""
翻身策略 v2.0 - 强度评分版
大盘涨(≥0)→涨3~6%, 大盘跌→涨2~5%
强度评分: 涨幅+量比+收盘位分段得分
空仓规则: 候选池胜率<30% -> 空仓
"""
import pickle, os, json

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']

# 大盘
market = {dt: sum(s['p'] for s in data[dt])/len(data[dt]) for dt in data if data[dt]}

def strength_score(p, vr, cl):
    sc = 0
    if 5 <= p <= 6: sc += 3  # 涨幅最佳
    elif 4 <= p < 5: sc += 2
    elif 3 <= p < 4: sc += 1
    if 1.0 <= vr <= 1.2: sc += 3  # 量比最佳
    elif 1.2 < vr <= 1.5: sc += 2
    elif 1.5 < vr <= 2.0: sc += 1
    if 70 <= cl <= 80: sc += 3  # 收盘位最佳
    elif 80 < cl <= 85: sc += 2
    elif 85 < cl <= 95: sc += 1
    return sc

def get_candidates(date):
    stocks = data.get(date, [])
    if not stocks: return []
    mkt = market.get(date, 0)
    pmin, pmax = (3,6) if mkt >= 0 else (2,5)
    
    cand = []
    for s in stocks:
        code = s['code']; p = s['p']
        if p < pmin or p > pmax: continue
        if (s.get('vol_ratio',0) or 0) <= 1: continue
        if s.get('cl',0) < 70 or s.get('cl',0) > 95: continue
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > 15: continue
        sz = (ri.get('shizhi',0) or 0)
        if sz >= 200: continue
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        
        sc = strength_score(p, s['vol_ratio'], s['cl'])
        nv = s.get('n',0) or 0
        cand.append((sc, nm, code, p, s['vol_ratio'], s['cl'], hsl, sz, nv))
    
    cand.sort(key=lambda x:-x[0])
    return cand

if __name__ == '__main__':
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else sorted(data.keys())[-1]
    cand = get_candidates(date)
    
    if not cand:
        print(f'{date}: 无候选')
        exit()
    
    # 空仓检查
    pool_ok = sum(1 for x in cand if x[8] >= 2.5)
    pool_rate = pool_ok / len(cand) * 100
    skip = pool_rate < 30
    
    print(f'{date} | 大盘{market[date]:+.2f}% | 候选{len(cand)}只 | 池胜率{pool_rate:.0f}%', flush=True)
    if skip:
        print(f'🟡 空仓(池胜率<30%)', flush=True)
    else:
        print(f'🟢 操作日', flush=True)
    
    print(f'{"#":<3} {"名称":<10} {"评分":<4} {"涨%":<5} {"量比":<5} {"CL%":<4} {"换手%":<5} {"市值亿":<5} {"次日高%":<7}', flush=True)
    print('-' * 55, flush=True)
    for i, x in enumerate(cand[:10]):
        nstr = f'{x[8]:.2f}%' if x[8] != 0 else 'N/A'
        ok = '✅' if x[8] >= 2.5 else ''
        print(f'{i+1:<3} {x[1][:8]:<10} {x[0]:<4} {x[3]:<5.1f} {x[4]:<5.2f} {x[5]:<4.0f} {x[6]:<5.1f} {x[7]:<5.0f} {nstr:<7} {ok}', flush=True)
