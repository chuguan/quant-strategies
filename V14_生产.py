"""
分而治之 V14 生产版 — 带大阳+洗盘因子
"""
import os, sys, json, re, time, subprocess, pickle
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
V14_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V14')
os.chdir(SCRIPTS_DIR)
sys.path.insert(0, V14_DIR)

from sina_api import sina_realtime
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

print('加载缓存数据...')
with open(os.path.join(V14_DIR, 'big_cache_full.pkl'), 'rb') as f:
    d = pickle.load(f)
BIG_DATA, BIG_REAL, BIG_NAMES = d['data'], d.get('real',{}), d['names']
ALL_DATES = sorted(BIG_DATA.keys())
LAST_DATE = ALL_DATES[-1] if ALL_DATES else None

SUB_STRATEGIES = {
    'real_up': {'module': '分而治之_V10_真实涨日_评分策略', 'name': '真实涨日V14', 'dir': V14_DIR},
    'fake_up': {'module': '分而治之_V10_虚涨日_评分策略', 'name': '虚涨日V14', 'dir': V14_DIR},
    'down': {'module': '分而治之_V10_跌日_评分策略', 'name': '跌日V14', 'dir': V14_DIR},
    'flat': {'module': '分而治之_V10_横盘_评分策略', 'name': '横盘V14', 'dir': V14_DIR},
}

def load_strategy(mkt_key):
    import importlib
    info = SUB_STRATEGIES[mkt_key]
    sys.path.insert(0, info['dir'])
    spec = importlib.util.spec_from_file_location(info['module'],
        os.path.join(info['dir'], '评分策略', f'{info["module"]}.py'))
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
    return renamed, mod

STRAT_CACHE = {}
for k in SUB_STRATEGIES: STRAT_CACHE[k] = load_strategy(k)

MKT_NAMES = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LEVEL_NAMES = ['L', 'L1', 'L2', 'L3', 'L4', 'L5']

def get_cache_indicator(code):
    if not LAST_DATE or LAST_DATE not in BIG_DATA:
        return None
    for s in BIG_DATA[LAST_DATE]:
        if s['code'] == code:
            ri = BIG_REAL.get(code, {})
            return {
                'vr': s.get('vol_ratio', 1) or s.get('vr', 1),
                'hsl': ri.get('hsl', 0) or s.get('hsl', 0) or s.get('hs', 0) or 0,
                'dif': s.get('dif_val', 0) or s.get('dif', 0) or 0,
                'mg': s.get('macd_golden', 0) or s.get('mg', 0) or 0,
                'a5': s.get('above_ma5', 0) or 0,
                'wrv': s.get('wr_val', 0) or s.get('wrv', 50) or 50,
                'jv': s.get('j_val', 0) or s.get('jv', 50) or 50,
                'kv': s.get('k_val', 0) or s.get('kv', 50) or 50,
                'dv': s.get('d_val', 0) or s.get('dv', 50) or 50,
                'kdj_g': s.get('kdj_golden', 0) or s.get('kdj_g', 0) or 0,
                'pos_in_day': s.get('pos_in_day', 50) or 50,
                'close': s.get('close', 0),
                'shizhi': s.get('shizhi', 0) or s.get('sz', 0) or 0,
            }
    return None

def build_stock_dict(real, cache):
    """合并新浪实时 + 缓存 + d1/d2/d3"""
    pre_close = real.get('pre_close', 0)
    price = real.get('price', 0)
    p = round((price - pre_close) / pre_close * 100, 2) if pre_close > 0 else 0
    high = real.get('high', 0)
    low = real.get('low', 0)
    cl = round((price - low) / (high - low) * 100, 2) if (high - low) > 0 else 50
    
    d1 = d2 = d3 = 0
    if LAST_DATE and LAST_DATE in BIG_DATA:
        for ss in BIG_DATA.get(LAST_DATE, []):
            if ss['code'] == real.get('code', ''):
                d1 = ss.get('p', 0) or 0
                break
        # 前两天的
        prev_idx = ALL_DATES.index(LAST_DATE) - 1 if LAST_DATE in ALL_DATES else -1
        if prev_idx >= 0:
            for ss in BIG_DATA.get(ALL_DATES[prev_idx], []):
                if ss['code'] == real.get('code', ''):
                    d2 = ss.get('p', 0) or 0
                    break
        prev_idx2 = ALL_DATES.index(LAST_DATE) - 2 if LAST_DATE in ALL_DATES else -1
        if prev_idx2 >= 0:
            for ss in BIG_DATA.get(ALL_DATES[prev_idx2], []):
                if ss['code'] == real.get('code', ''):
                    d3 = ss.get('p', 0) or 0
                    break
    
    return {
        'p': p, 'cl': cl,
        'vr': cache.get('vr', 1) if cache else 1,
        'hsl': cache.get('hsl', 0) if cache else 0,
        'dif': cache.get('dif', 0) if cache else 0,
        'mg': cache.get('mg', 0) if cache else 0,
        'a5': cache.get('a5', 0) if cache else 0,
        'wrv': cache.get('wrv', 50) if cache else 50,
        'jv': cache.get('jv', 50) if cache else 50,
        'kv': cache.get('kv', 50) if cache else 50,
        'dv': cache.get('dv', 50) if cache else 50,
        'kdj_g': cache.get('kdj_g', 0) if cache else 0,
        'pos_in_day': cl,
        'd1': d1, 'd2': d2, 'd3': d3,
        'nm': real.get('name', ''),
        'code': real.get('code', ''),
        'name': real.get('name', ''),
        'shizhi': cache.get('shizhi', 0) if cache else 0,
        'close': price,
    }

def classify_market(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p',0) or 0 for s in stocks]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps)
    hot = sum(1 for p in ps if 5 <= p <= 8)
    vrs = [s.get('vr',1) or 1 for s in stocks if s.get('vr')]
    avg_vr = sum(vrs)/len(vrs) if vrs else 0
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

def main():
    print('获取实时行情（新浪）...')
    main_codes = sorted(set(
        s['code'] for dates in list(BIG_DATA.values())[-5:]
        for s in dates if IS_MAIN(s['code'])
    ))[:4000]
    
    all_real = {}
    for i in range(0, len(main_codes), 80):
        batch = main_codes[i:i+80]
        try:
            all_real.update(sina_realtime(batch))
        except: pass
        time.sleep(0.05)
    print(f'获取到 {len(all_real)} 只')
    
    clean = []
    for full_code, real in all_real.items():
        code = full_code[2:] if full_code.startswith(('sh','sz')) else full_code
        real['code'] = code
        if real.get('price',0) <= 0: continue
        pre_close = real.get('pre_close',0)
        if pre_close <= 0: continue
        pct = real.get('pct',0)
        if abs(pct) >= 15: continue
        nm = real.get('name','')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        cache = get_cache_indicator(code)
        if cache is None: continue
        clean.append(build_stock_dict(real, cache))
    
    print(f'有效: {len(clean)}只')
    mk = classify_market(clean)
    mk_cn = MKT_NAMES.get(mk, '横盘')
    print(f'行情: {mk_cn}')
    
    levels, mod = STRAT_CACHE[mk]
    lm = {l['name']:i for i,l in enumerate(levels)}
    score_fn = mod.score
    
    pool = None; used_level = '无'
    for ln in LEVEL_NAMES:
        if ln not in lm: continue
        i = lm[ln]; lv = levels[i]; cand = []
        for s in clean:
            p = s.get('p', 0) or 0
            if p < lv['p_min'] or p > min(lv.get('p_max', 10), 8): continue
            vr = s.get('vr', 0) or 0
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            hsl = s.get('hsl', 0) or 0
            if hsl < lv.get('hs_min', 0) or hsl > lv.get('hs_max', 99): continue
            sz = s.get('shizhi', 0) or 0
            if sz >= lv.get('sz_max', 9999): continue
            cl = s.get('cl', 0) or 50
            if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
            cand.append(s)
        if len(cand) >= 10:
            pool = cand; used_level = ln
            break
    
    if not pool:
        print('候选池不足10只！')
        return
    
    print(f'候选池: {len(pool)}只 ({used_level})')
    
    scored = []
    for s in pool:
        sc = score_fn(s)
        scored.append((sc, s))
    scored.sort(key=lambda x: -x[0])
    
    today = datetime.now().strftime('%Y-%m-%d')
    report = [f'📊 V14 分而治之·实盘选股 {today}（含大阳+洗盘因子）']
    report.append(f'📈 {mk_cn} | 候选{len(pool)}只 ({used_level})')
    report.append(f'')
    report.append(f'🏆 Top 10:')
    report.append(f'{"#":>2} {"名称":>8} {"代码":>7} {"评分":>5} {"涨幅":>6} {"CL":>5} {"WR":>5} {"量比":>5}')
    for rank, (sc, s) in enumerate(scored[:10], 1):
        nm = s.get('name', '?')[:6]
        report.append(f'{rank:>2} {nm:>8} {s["code"]:>7} {sc:>5.0f} {s.get("p",0):>+5.1f}% {s.get("cl",0):>5.0f} {s.get("wrv",0):>5.0f} {s.get("vr",0):>5.1f}')
    
    output = '\n'.join(report)
    print(output)
    
    try:
        email_to = '1254628314@qq.com,314913203@qq.com'
        subject = f'V14实盘选股 {today} - {mk_cn} TOP10'
        sender = os.path.join(SCRIPTS_DIR, 'send_email.py')
        subprocess.run([sys.executable, sender, email_to, subject, output], timeout=60)
        print('邮件已发送')
    except Exception as e:
        print(f'邮件失败: {e}')

if __name__ == '__main__':
    main()
