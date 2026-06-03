"""
V46 选股 + 尾盘形态标注
"""
import os, sys, pickle, importlib
from collections import defaultdict

SCRIPTS_DIR = r'C:\Users\12546\AppData\Local\hermes\scripts'
RELEASE_DIR = os.path.join(SCRIPTS_DIR, 'release')

def load_strats(vdir):
    strats = {}
    for f in sorted(os.listdir(os.path.join(vdir, '评分策略'))):
        if f.endswith('.py') and '评分策略' in f:
            modname = f.replace('.py','')
            spec = importlib.util.spec_from_file_location(modname, os.path.join(vdir, '评分策略', f))
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            strats[getattr(m, 'MARKET', 'unk')] = m
    return strats

v46s = load_strats(os.path.join(RELEASE_DIR, 'V46'))
v42s = load_strats(os.path.join(RELEASE_DIR, 'V42'))

with open(os.path.join(RELEASE_DIR, 'V46', 'big_cache_full.pkl'), 'rb') as f:
    cache = pickle.load(f)
with open(os.path.join(RELEASE_DIR, 'V46', 'features_30d.pkl'), 'rb') as f:
    feats = pickle.load(f)

names = cache.get('names', {})
data = cache['data']
dates = sorted(data.keys())
print(f'数据: {len(dates)}个交易日')

d1_map = {}
for (code, dt), fv in feats.items():
    d1_map[(str(code), dt)] = fv.get('d1', 0)

def cls(p, vr):
    if p < -0.5: return 'down'
    if p > 1.5: return 'real_up'
    if p > 0.5 and vr < 0.85: return 'fake_up'
    return 'flat'

def tail_label(s):
    """返回尾盘形态标注文字"""
    p = s.get('p', 0) or 0
    cl = s.get('cl', 50) or 50
    vr = s.get('vr', 0) or 0
    wr = s.get('wrv', 50) or 50
    tags = []
    if -1 < p < 1 and cl < 40:
        tags.append('弱反弹⚠️')
    if p > 2 and cl > 70:
        tags.append('强收📈')
        if vr > 2 and p > 3:
            tags.append('抢筹🔥')
    if p > 2 and cl > 60 and wr < 40:
        tags.append('资金进场💹')
    return ' '.join(tags) if tags else '—'

mk_cn = {'down':'跌日','flat':'横盘','real_up':'真实涨日','fake_up':'虚涨日'}

# 用最新200天跑
recent = [d for d in dates if d >= '2025-11-01']
print(f'近200天: {len(recent)}个交易日\n')

v46w, v46t = 0, 0
v42w, v42t = 0, 0

for d in recent:
    pool = data.get(d, [])
    if not isinstance(pool, list): continue
    
    v46c, v42c = [], []
    for s in pool:
        if not isinstance(s, dict): continue
        code = str(s.get('code',''))
        p = s.get('p', 0) or 0
        vr = s.get('vol_ratio', 0) or 1.0
        s['p'] = p; s['vr'] = vr
        mk = cls(p, vr)
        
        st46 = v46s.get(mk)
        if st46:
            if code in names: s['nm'] = names[code]
            sc = st46.score(s)
            if sc > 0: v46c.append((code, sc, s, mk))
        
        st42 = v42s.get(mk)
        if st42:
            if code in names: s['nm'] = names[code]
            sc2 = st42.score(s)
            if sc2 > 0: v42c.append((code, sc2, s, mk))
    
    if len(v46c) < 3 or len(v42c) < 3: continue
    
    v46c.sort(key=lambda x: x[1], reverse=True)
    v42c.sort(key=lambda x: x[1], reverse=True)
    
    c46 = v46c[0]; c42 = v42c[0]
    d1_46 = d1_map.get((c46[0], d), 0)
    d1_42 = d1_map.get((c42[0], d), 0)
    if d1_46 >= 2.5: v46w += 1
    v46t += 1
    if d1_42 >= 2.5: v42w += 1
    v42t += 1

print(f'V46 #1: {v46w}/{v46t} = {v46w*100/v46t:.1f}%')
print(f'V42 #1: {v42w}/{v42t} = {v42w*100/v42t:.1f}%')
print()

# ===== 逐日展示带尾盘形态标注 =====
print('=' * 120)
print(f'  V46逐日选股（带尾盘形态标注）')
print('=' * 120)
print(f'  {"日期":<12} {"行情":<6} {"#":<3} {"名称":<12} {"代码":<8} {"p%":>6} {"CL":>4} {"WR":>4} {"VR":>4} {"尾盘形态":<20} {"D+1":>6}')
print(f'  {"-"*12} {"-"*6} {"-"*3} {"-"*12} {"-"*8} {"-"*6} {"-"*4} {"-"*4} {"-"*4} {"-"*20} {"-"*6}')

count = 0
for d in recent[-30:]:
    pool = data.get(d, [])
    if not isinstance(pool, list): continue
    v46c = []
    for s in pool:
        if not isinstance(s, dict): continue
        code = str(s.get('code',''))
        p = s.get('p', 0) or 0
        vr = s.get('vol_ratio', 0) or 1.0
        s['p'] = p; s['vr'] = vr
        mk = cls(p, vr)
        st = v46s.get(mk)
        if not st: continue
        # 注入名称（big_cache的name在names_map中）
        if code in names:
            s['nm'] = names[code]
        sc = st.score(s)
        if sc <= 0: continue
        s['_code'] = code
        v46c.append((code, sc, s, mk))
    if len(v46c) < 3: continue
    v46c.sort(key=lambda x: x[1], reverse=True)
    
    for j, (code, sc, s, mk) in enumerate(v46c[:3], 1):
        d1 = d1_map.get((code, d), s.get('d1', 0) or 0)
        nm = names.get(code, '')
        tl = tail_label(s)
        p_v = s.get('p', 0) or 0
        cl_v = s.get('cl', 50) or 50
        wr_v = s.get('wrv', 50) or 50
        vr_v = s.get('vr', 0) or 0
        hit = '✅' if d1 >= 2.5 else '❌'
        print(f'  {d:<12} {mk_cn.get(mk,mk):<6} {j:<3} {nm:<12} {code:<8} {p_v:>+5.1f}% {cl_v:>3.0f} {wr_v:>3.0f} {vr_v:>3.1f} {tl:<20} {d1:>+5.1f}%{hit}')
        count += 1
        if count >= 90: break
    if count >= 90: break

print()
print('尾盘形态标注说明:')
print('  弱反弹⚠️  = -1<p<1 且 CL<40 → 弱反弹形态（扣分）')
print('  强收📈    = p>2 且 CL>70 → 强势收盘（加分）')
print('  抢筹🔥    = 强收 + vr>2 + p>3 → 放量抢筹（再加分）')
print('  资金进场💹 = p>2 + CL>60 + WR<40 → 资金买入未超买（加分）')
print('  —         = 无尾盘形态信号')
