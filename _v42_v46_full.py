#!/usr/bin/env python3
"""V42 vs V46 正确回测 - 使用big_cache_full + features_30d"""
import sys, os, pickle, importlib
import numpy as np

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

RELEASE_DIR = os.path.join(SCRIPTS_DIR, 'release')

def load_strats(d, label):
    s = {}
    for n in ['真实涨日','虚涨日','跌日','横盘']:
        fp = os.path.join(d, f'分而治之_V10_{n}_评分策略.py')
        spec = importlib.util.spec_from_file_location(f'{label}_{n}', fp)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        s[n] = m
    return s

v42s = load_strats(os.path.join(RELEASE_DIR, 'V42', '评分策略'), 'V42')
v46s = load_strats(os.path.join(RELEASE_DIR, 'V46', '评分策略'), 'V46')

MK = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}

def cm(ps, vrs):
    ap = sum(ps)/len(ps) if ps else 0
    av = sum(vrs)/len(vrs) if vrs else 0
    h = sum(1 for p in ps if 5<=p<=8)
    if ap > 0.5: return 'fake_up' if h<15 or av<0.9 else 'real_up'
    if ap < -0.5: return 'down'
    return 'flat'

# 加载数据
print('加载 big_cache_full.pkl...')
with open(os.path.join(RELEASE_DIR, 'V42', 'big_cache_full.pkl'), 'rb') as f:
    cache = pickle.load(f)
data = cache['data']
names = cache['names']
real = cache.get('real', {})

print('加载 features_30d.pkl...')
with open(os.path.join(RELEASE_DIR, 'V42', 'features_30d.pkl'), 'rb') as f:
    fdict = pickle.load(f)

dates = sorted(data.keys())
print(f'交易日: {len(dates)}天 ({dates[0]} ~ {dates[-1]})')

# 用最近30天
recent = dates[-30:]
print(f'最近30天: {recent[0]} ~ {recent[-1]}')
print()

v42w=0; v46w=0; v42t=0; v46t=0; td=0

for d in recent:
    day_data = data[d]
    if not day_data: continue
    
    stocks = []
    for st in day_data:
        code = st['code']
        if not code or code not in names: continue
        name = names[code]
        if 'ST' in name or '*ST' in name or '退' in name: continue
        
        p = st.get('p', 0)
        vr = st.get('vol_ratio', 0) or 0
        cl = st.get('cl', 50) or 50
        wr = st.get('wr_val', 50) or 50
        dif = st.get('dif_val', 0) or 0
        mg = st.get('macd_golden', 0) or 0
        jv = st.get('j_val', 50) or 50
        kv = st.get('k_val', 50) or 50
        dv = st.get('d_val', 50) or 50
        a5 = st.get('above_ma5', 0) or 0
        close = st.get('close', 0) or 0
        pos = st.get('pos_in_day', 50) or 50
        n_val = st.get('n', 0) or 0
        target = 1 if n_val >= 2.5 else 0
        
        # 换手率
        hsl = 0
        if code in real and isinstance(real[code], dict):
            hsl = real[code].get('hsl', 0) or 0
        
        # 动量特征 (从features_30d取)
        feat_key = (code, d)
        t4s = 0; sl5 = 0; cu = 0
        if feat_key in fdict:
            f = fdict[feat_key]
            t4s = f.get('t4_shadow', 0) or 0
            sl5 = f.get('slope5', 0) or 0
            cu = f.get('cons_up', 0) or 0
        
        if abs(p) >= 9: continue
        if vr <= 0 or vr >= 10: vr = 0.5
        
        stocks.append({
            'code': code, 'name': name, 'p': p, 'vr': vr, 'cl': cl,
            'wrv': wr, 'dif': dif, 'mg': mg, 'kdj_g': 0,
            'jv': jv, 'kv': kv, 'dv': dv, 'a5': a5, 'close': close,
            'hsl': hsl, 'pos_in_day': pos, 'nm': name,
            't4_shadow': t4s, 'slope5': sl5, 'cons_up': cu,
            'target': target, 'n': n_val
        })
    
    if len(stocks) < 50: continue
    
    # 行情分类
    ps = [s['p'] for s in stocks if abs(s['p'])<15]
    vrs = [s['vr'] for s in stocks if s['vr']>0]
    mk_cn = MK.get(cm(ps, vrs), '横盘')
    
    vm = v42s.get(mk_cn)
    vm2 = v46s.get(mk_cn)
    if not vm or not vm2: continue
    
    v42sc = []
    v46sc = []
    for s in stocks:
        try:
            s1 = vm.score(s)
            s2 = vm2.score(s)
            if s1 > 0: v42sc.append({'n':s['name'],'s':s1,'t':s['target'],'p':s['p']})
            if s2 > 0: v46sc.append({'n':s['name'],'s':s2,'t':s['target'],'p':s['p']})
        except:
            pass
    
    if len(v42sc) < 3 or len(v46sc) < 3: continue
    
    v42sc.sort(key=lambda x: x['s'], reverse=True)
    v46sc.sort(key=lambda x: x['s'], reverse=True)
    
    td += 1
    if v42sc[0]['t']: v42w += 1
    if v46sc[0]['t']: v46w += 1
    if any(x['t'] for x in v42sc[:3]): v42t += 1
    if any(x['t'] for x in v46sc[:3]): v46t += 1
    
    # 打印每天明细
    m42 = '✅' if v42sc[0]['t'] else '❌'
    m46 = '✅' if v46sc[0]['t'] else '❌'
    print(f'{d} {mk_cn:<4} V42:#{v42sc[0]["n"]}({v42sc[0]["p"]:+.1f}%){m42}  V46:#{v46sc[0]["n"]}({v46sc[0]["p"]:+.1f}%){m46}')

print()
print(f'===== 最近{td}天 V42 vs V46 (big_cache完整版) =====')
h1 = '#1冠军胜率'
h2 = 'TOP3至少1达标'
print(f'{"指标":<20}  {"V42":>16}  {"V46":>16}  {"差异":>8}')
print('-'*68)
print(f'{h1:<20}  {v42w:>3}/{td:<3} ={v42w/td*100:>5.1f}%  {v46w:>3}/{td:<3} ={v46w/td*100:>5.1f}%  {v46w/td*100-v42w/td*100:+>+5.1f}%')
print(f'{h2:<20}  {v42t:>3}/{td:<3} ={v42t/td*100:>5.1f}%  {v46t:>3}/{td:<3} ={v46t/td*100:>5.1f}%  {v46t/td*100-v42t/td*100:+>+5.1f}%')
