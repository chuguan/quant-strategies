"""
V50最终验证 - 修改后的策略完整回测
"""
import sys, os, importlib, pickle

WORK = os.path.expanduser('~/AppData/Local/hermes/scripts')
V50_DIR = os.path.join(WORK, 'release/V50')
sys.path.insert(0, V50_DIR)
sys.path.insert(0, os.path.join(V50_DIR, '评分策略'))

exec(open(os.path.join(WORK, '_v50_framework.py')).read())

mod_down = importlib.import_module('分而治之_V10_跌日_评分策略')
mod_flat = importlib.import_module('分而治之_V10_横盘_评分策略')
mod_real = importlib.import_module('分而治之_V10_真实涨日_评分策略')
mod_fake = importlib.import_module('分而治之_V10_虚涨日_评分策略')

def run_full(mod, mk):
    sc_fn = mod.score; levels = mod.LEVELS
    date_list = sorted(dates_all)
    periods = [
        ('全量', None),
        ('150天', date_list[-150] if len(date_list) >= 150 else date_list[0]),
        ('100天', date_list[-100] if len(date_list) >= 100 else date_list[0]),
        ('50天',  date_list[-50] if len(date_list) >= 50 else date_list[0]),
        ('30天',  date_list[-30] if len(date_list) >= 30 else date_list[0]),
    ]
    for label, cutoff in periods:
        dts = mkt_dates[mk]
        if cutoff: dts = [x for x in dts if x >= cutoff]
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
        wr=wins/len(nh)*100 if nh else 0
        cp=has_cand/total*100 if total else 0
        avg_nh=sum(nh)/len(nh) if nh else 0
        print(f"  {label:6s} | 胜率 {wr:5.1f}% ({wins}/{len(nh)}) | 出票 {cp:4.1f}% | 均涨幅 {avg_nh:.1f}% | {total}天")

print("=" * 60)
print("V50 最终版 - 全行情回测")
print("=" * 60)

all_wins = {}; all_hits = {}; all_total = {}
date_list = sorted(dates_all)
periods = ['全量', '150天', '100天', '50天', '30天']
cuts = [None, date_list[-150], date_list[-100], date_list[-50], date_list[-30]]

for mk_name, mk, mod in [('跌日','down',mod_down), ('横盘','flat',mod_flat), 
                          ('真实涨日','real_up',mod_real), ('虚涨日','fake_up',mod_fake)]:
    print(f"\n▶ {mk_name}")
    run_full(mod, mk)

# 汇总
print(f"\n{'='*60}")
print("V50 汇总对比")
print(f"{'='*60}")
print(f"{'时间段':8s} | {'跌日':12s} | {'横盘':12s} | {'真实涨日':12s} | {'虚涨日':12s} | {'合计':10s}")
print("-" * 70)

for label, cutoff in zip(periods, cuts):
    total_w = 0; total_h = 0
    line = f"{label:8s}"
    for mk_name, mk, mod in [('跌日','down',mod_down), ('横盘','flat',mod_flat), 
                              ('真实涨日','real_up',mod_real), ('虚涨日','fake_up',mod_fake)]:
        dts = mkt_dates[mk]
        if cutoff: dts = [x for x in dts if x >= cutoff]
        total=0; wins=0; nh=[]
        for dt in dts:
            s = data.get(dt,[]); total+=1; selected=None
            for lv in mod.LEVELS:
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
                    sc=mod.score(stock)
                    nh_=sx.get('n',0) or 0
                    pool.append((sc, nh_, code, nm[:6]))
                if len(pool)>8:
                    pool.sort(key=lambda x:-x[0]); selected=pool[0]; break
            if selected:
                sc,nh_,code,nm=selected; nh.append(nh_)
                if nh_>=2.5: wins+=1
        wr=wins/len(nh)*100 if nh else 0
        line += f" | {wr:5.1f}%({len(nh):2d})"
        total_w += wins; total_h += len(nh)
    total_wr = total_w/total_h*100 if total_h else 0
    line += f" | {total_wr:5.1f}%"
    print(line)
