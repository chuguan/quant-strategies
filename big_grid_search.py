#!/usr/bin/env python3
"""
全维度搜索：新big_cache + 新10个维度
"""
import pickle, os
from collections import defaultdict
import sys

sys.stdout.reconfigure(line_buffering=True)

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']
names=cache['names']

MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5

def filter_data(yr):
    by_date=defaultdict(list)
    for dt in data_cache:
        if not dt.startswith(yr): continue
        for c in data_cache[dt]:
            if c['code'] in ST: continue
            p=c['p']; n=c['n']
            if p is None or not (MIN_CHG <= p < MAX_CHG): continue
            if n is None: continue
            by_date[dt].append(c)
    return {k:v for k,v in by_date.items() if len(v)>=5}

data25=filter_data('2025')
data26=filter_data('2026')
print(f"📅 2025: {len(data25)}天, 2026: {len(data26)}天")

# 对比用：旧M1(严格)的p+a冠军胜率
old_cache_path=r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"
with open(old_cache_path,'rb') as f: old=pickle.load(f)
def old_filter(yr):
    by_date=defaultdict(list)
    for dt in old['data']:
        if not dt.startswith(yr): continue
        for c in old['data'][dt]:
            if c['code'] in ST: continue
            p=c['p']; n=c['n']
            if p is None or not (MIN_CHG <= p < MAX_CHG): continue
            if n is None: continue
            by_date[dt].append(c)
    return {k:v for k,v in by_date.items() if len(v)>=5}
old25=old_filter('2025'); old26=old_filter('2026')
old_w25=sum(1 for dt in sorted(old25.keys()) if max(old25[dt], key=lambda c:c['p']+c['a'])['n']>=TARGET)/max(len(old25),1)*100
old_w26=sum(1 for dt in sorted(old26.keys()) if max(old26[dt], key=lambda c:c['p']+c['a'])['n']>=TARGET)/max(len(old26),1)*100
print(f"\n📊 旧M1(严格)+p+a: {old_w25:.1f}% / {old_w26:.1f}% / 平均{(old_w25+old_w26)/2:.1f}%")

# 新M1(放宽)+p+a基准
fn_bench=lambda c: c['p']+c['a']
b25=sum(1 for dt in sorted(data25.keys()) if max(data25[dt], key=fn_bench)['n']>=TARGET)/max(len(data25),1)*100
b26=sum(1 for dt in sorted(data26.keys()) if max(data26[dt], key=fn_bench)['n']>=TARGET)/max(len(data26),1)*100
print(f"📊 新M1(放宽)+p+a: {b25:.1f}% / {b26:.1f}% / 平均{(b25+b26)/2:.1f}%")

# 新M1+p+a的Top3理论
t3_25=sum(1 for dt in sorted(data25.keys()) if any(c['n']>=TARGET for c in sorted(data25[dt],key=fn_bench,reverse=True)[:3]))/max(len(data25),1)*100
t3_26=sum(1 for dt in sorted(data26.keys()) if any(c['n']>=TARGET for c in sorted(data26[dt],key=fn_bench,reverse=True)[:3]))/max(len(data26),1)*100
print(f"📊 新M1+p+a Top3: {t3_25:.1f}% / {t3_26:.1f}% / 平均{(t3_25+t3_26)/2:.1f}%")

# ═══ 各新维度独立测试 ═══
print("\n═══ 各维度独立预测力（单一维度选冠军） ═══")
print(f"{'维度':<15} {'2025':>8} {'2026':>8} {'平均':>8}")
print("-"*42)

dims=[
    ('p(涨跌幅)','p'), ('b(实体)','b'), ('s(上影)','s'),
    ('a(ATR)','a'), ('cl(收盘位)','cl'), ('量比','vol_ratio'),
    ('KJJ-J','j_val'), ('MA5斜率','ma5_slope'), ('DIF值','dif_val'),
    ('振幅','amplitude'), ('成交量','vol'), ('阳线','is_yang'),
    ('站MA5','above_ma5'), ('站MA10','above_ma10'), ('站MA20','above_ma20'),
]
dim_results=[]
for name, key in dims:
    for dirr, dname in [(1, '↑'), (-1, '↓')]:
        fn=lambda c, k=key, d=dirr: c.get(k,0)*d
        w25=sum(1 for dt in sorted(data25.keys()) if max(data25[dt], key=fn)['n']>=TARGET)/max(len(data25),1)*100
        w26=sum(1 for dt in sorted(data26.keys()) if max(data26[dt], key=fn)['n']>=TARGET)/max(len(data26),1)*100
        avg=(w25+w26)/2
        dim_results.append((avg, w25, w26, f"{dname}{name}"))

dim_results.sort(key=lambda x:x[0], reverse=True)
for i,(avg,w25,w26,name) in enumerate(dim_results,1):
    print(f"{i:<2} {name:<15} {w25:>7.1f}% {w26:>7.1f}% {avg:>7.1f}%")

# ═══ 2-3维最优组合 ═══
print("\n═══ 2-3维最优组合搜索 ═══")
best_so_far=0
results=[]

# p + a 是基础，加第3个维度
third_dims=[('量比','vol_ratio'),('KJJ-J','j_val'),('MA5斜率','ma5_slope'),
            ('DIF值','dif_val'),('振幅','amplitude'),('阳线','is_yang'),
            ('站MA5','above_ma5'),('站MA10','above_ma10'),('站MA20','above_ma20'),
            ('实体','b'),('上影','s'),('收盘位','cl')]

for w_p in [1, 1.5, 2]:
    for w_a in [1, 1.5, 2]:
        for name3, key3 in third_dims:
            for w3 in [0, 0.1, 0.2, 0.5, 1, 2]:
                fn=lambda c, w1=w_p, w2=w_a, w3v=w3, k3=key3: c['p']*w1+c['a']*w2+c.get(k3,0)*w3v
                w25=sum(1 for dt in sorted(data25.keys()) if max(data25[dt], key=fn)['n']>=TARGET)/max(len(data25),1)*100
                w26=sum(1 for dt in sorted(data26.keys()) if max(data26[dt], key=fn)['n']>=TARGET)/max(len(data26),1)*100
                avg=(w25+w26)/2
                if avg>best_so_far:
                    best_so_far=avg
                    print(f"  🥇 {avg:.1f}% = p×{w_p}+a×{w_a}+{name3}×{w3} (2025={w25:.1f}%, 2026={w26:.1f}%)")
                results.append((avg, w25, w26, f"p×{w_p}+a×{w_a}+{name3}×{w3}"))

results.sort(key=lambda x:x[0], reverse=True)
print(f"\n🏆 2-3维最优 TOP5:")
for i,(avg,w25,w26,name) in enumerate(results[:5],1):
    print(f"  {i}. {avg:.1f}% = {name}")

# ═══ 全维度搜索（5维以内） ═══
print("\n═══ 4-5维组合搜索（精华版） ═══")
# 选取前几轮最优的几个维度: p, a, cl, vol_ratio, ma5_slope
best4=0
results4=[]
for w_p in [1, 1.5]:
    for w_a in [1, 1.5, 2]:
        for w_cl in [0, 0.01, 0.03, 0.05]:
            for w_vr in [0, 0.1, 0.2, 0.5]:
                for w_ms in [0, 0.1, 0.2, 0.5]:
                    if w_cl==0 and w_vr==0 and w_ms==0: continue
                    fn=lambda c,wp=w_p,wa=w_a,wcl=w_cl,wvr=w_vr,wms=w_ms: c['p']*wp+c['a']*wa+c['cl']*wcl+c.get('vol_ratio',0)*wvr+c.get('ma5_slope',0)*wms
                    w25=sum(1 for dt in sorted(data25.keys()) if max(data25[dt], key=fn)['n']>=TARGET)/max(len(data25),1)*100
                    w26=sum(1 for dt in sorted(data26.keys()) if max(data26[dt], key=fn)['n']>=TARGET)/max(len(data26),1)*100
                    avg=(w25+w26)/2
                    if avg>best4:
                        best4=avg
                        print(f"  🥇 {avg:.1f}% = p×{w_p}+a×{w_a}+cl×{w_cl}+量比×{w_vr}+斜率×{w_ms} (25={w25:.1f}%, 26={w26:.1f}%)")
                    results4.append((avg, w25, w26, f"p×{w_p}+a×{w_a}+cl×{w_cl}+vr×{w_vr}+ms×{w_ms}"))

results4.sort(key=lambda x:x[0], reverse=True)
print(f"\n🏆 4-5维最优 TOP5:")
for i,(avg,w25,w26,name) in enumerate(results4[:5],1):
    print(f"  {i}. {avg:.1f}% = {name}")

# ═══ 再试放宽MA硬过滤条件 ═══
print("\n═══ 再试：不加站MA10/MA20过滤 ═══")
# 新缓存已取消阳线/站MA5硬过滤，变成"above_ma5"评分项
# 看看加"以上评分"的效果
for name, key in [('站MA5(+1)', 'above_ma5'), ('站MA10(+1)', 'above_ma10'), ('站MA20(+1)', 'above_ma20'), ('阳线(+1)', 'is_yang')]:
    fn=lambda c, k=key: c['p']+c['a']+c.get(k,0)*2
    w25=sum(1 for dt in sorted(data25.keys()) if max(data25[dt], key=fn)['n']>=TARGET)/max(len(data25),1)*100
    w26=sum(1 for dt in sorted(data26.keys()) if max(data26[dt], key=fn)['n']>=TARGET)/max(len(data26),1)*100
    avg=(w25+w26)/2
    print(f"  p+a+{name}×2: {avg:.1f}% (25={w25:.1f}%, 26={w26:.1f}%)")
