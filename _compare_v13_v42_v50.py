"""
V13 vs V42 vs V50 完整对比
使用同一份数据（V50 big_cache_full.pkl），加载各版本评分策略
"""
import sys, os, importlib

WORK = os.path.expanduser('~/AppData/Local/hermes/scripts')
V50_DIR = os.path.join(WORK, 'release/V50')

exec(open(os.path.join(WORK, '_v50_framework.py')).read())

def load_strategy(ver_dir):
    """加载4个行情评分模块"""
    dir_path = os.path.join(WORK, ver_dir, '评分策略')
    sys.path.insert(0, dir_path)
    mods = {}
    for mk, fname in [('down','跌日'), ('flat','横盘'), ('real_up','真实涨日'), ('fake_up','虚涨日')]:
        mod = importlib.import_module(f'分而治之_V10_{fname}_评分策略')
        mods[mk] = mod
    return mods

# V13 is at release/V13/评分策略
v13_dir = os.path.join(WORK, 'release/V13')
sys.path.insert(0, os.path.join(v13_dir, '评分策略'))

# Load all versions
strats = {
    'V13': {},
    'V42': {},
    'V50': {},
}
for mk, fname in [('down','跌日'), ('flat','横盘'), ('real_up','真实涨日'), ('fake_up','虚涨日')]:
    strats['V13'][mk] = importlib.import_module(f'分而治之_V10_{fname}_评分策略')
    # 清除缓存以重新加载
    del sys.modules[f'分而治之_V10_{fname}_评分策略']

# V42
v42_dir = os.path.join(WORK, 'release/V42')
sys.path.insert(0, os.path.join(v42_dir, '评分策略'))
for mk, fname in [('down','跌日'), ('flat','横盘'), ('real_up','真实涨日'), ('fake_up','虚涨日')]:
    strats['V42'][mk] = importlib.import_module(f'分而治之_V10_{fname}_评分策略')
    del sys.modules[f'分而治之_V10_{fname}_评分策略']

# V50
v50_dir = os.path.join(WORK, 'release/V50')
sys.path.insert(0, os.path.join(v50_dir, '评分策略'))
for mk, fname in [('down','跌日'), ('flat','横盘'), ('real_up','真实涨日'), ('fake_up','虚涨日')]:
    strats['V50'][mk] = importlib.import_module(f'分而治之_V10_{fname}_评分策略')
    if mk != 'fake_up':  # 最后一个不用清除，后续不用
        del sys.modules[f'分而治之_V10_{fname}_评分策略']

def run_version(mods, mk, cutoff_date=None):
    mod = mods[mk]
    sc_fn = mod.score; levels = mod.LEVELS
    dts = mkt_dates[mk]
    if cutoff_date: dts = [x for x in dts if x >= cutoff_date]
    total=0; has_cand=0; wins=0; nh=[]
    for dt in dts:
        s = data.get(dt,[]); total+=1; selected=None
        for lv in levels:
            pool=[]
            for sx in s:
                code=sx.get('code',''); p=(sx.get('p',0) or 0)
                if p<lv['p_min'] or p>lv['p_max'] or p>=8: continue
                vr=sx.get('vol_ratio',0) or 0
                if vr<lv['vr_min'] or vr>lv['vr_max']: continue
                cl=sx.get('cl',0) or 0
                if cl<lv['cl_min'] or cl>lv['cl_max']: continue
                ri=real.get(code)
                if ri:
                    hsl=ri.get('hsl',0) or 0
                    if hsl<lv['hs_min'] or hsl>lv['hs_max']: continue
                    sz=ri.get('shizhi',0) or 0
                    if isinstance(sz,(int,float)) and sz>1: sz*=1e-8
                    if sz>=lv['sz_max']: continue
                nm=names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                if (sx.get('n',0) or 0)<=0: continue
                stock=build(sx,ri)
                sc=sc_fn(stock)
                nh_=sx.get('n',0) or 0
                pool.append((sc, nh_, code, nm[:6]))
            if len(pool)>8:
                pool.sort(key=lambda x:-x[0]); selected=pool[0]; break
        if selected:
            has_cand+=1; sc,nh_,code,nm=selected; nh.append(nh_)
            if nh_>=2.5: wins+=1
    return wins, len(nh), total, has_cand

date_list = sorted(dates_all)
periods = [
    ('全量(约360天)', None),
    ('最近150天', date_list[-150]),
    ('最近100天', date_list[-100]),
    ('最近50天', date_list[-50]),
    ('最近30天', date_list[-30]),
]

print("=" * 75)
print("V13 vs V42 vs V50 完整对比")
print(f"数据: {dates_all[0]} ~ {dates_all[-1]} ({len(dates_all)}交易日)")
print("=" * 75)

# 逐行情对比
for mk_name, mk_label in [('跌日','down'), ('横盘','flat'), ('真实涨日','real_up'), ('虚涨日','fake_up')]:
    print(f"\n▶ {mk_name}")
    print(f"{'时间段':12s} | {'V13':20s} | {'V42':20s} | {'V50':20s}")
    print("-" * 75)
    
    for label, cutoff in periods:
        line = f"{label:12s}"
        for v_name in ['V13', 'V42', 'V50']:
            w, h, t, c = run_version(strats[v_name], mk_label, cutoff)
            wr = w/h*100 if h else 0
            cp = c/t*100 if t else 0
            line += f" | {wr:5.1f}%({w:2d}/{h:2d})"
        print(line)

print(f"\n{'='*75}")
print("总胜率对比")
print(f"{'='*75}")
print(f"{'时间段':12s} | {'V13':20s} | {'V42':20s} | {'V50':20s}")
print("-" * 75)

for label, cutoff in periods:
    line = f"{label:12s}"
    for v_name in ['V13', 'V42', 'V50']:
        tw = 0; th = 0
        for mk in ['down','flat','real_up','fake_up']:
            w, h, _, _ = run_version(strats[v_name], mk, cutoff)
            tw += w; th += h
        wr = tw/th*100 if th else 0
        line += f" | {wr:5.1f}%({tw:2d}/{th:2d})"
    print(line)
