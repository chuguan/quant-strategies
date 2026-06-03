#!/usr/bin/env python3
"""
2026年冠军跌的案例 + 4日前股价
"""
import pickle, os, json
from collections import defaultdict

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
JSON_DIR=r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: cache=pickle.load(f)
data_cache=cache['data']
names=cache['names']

MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5
fn=lambda c: c['p']+c['a']*1.5+c.get('dif_val',0)*0.5

# 加载JSON数据（用于获取历史收盘价）
def load_stock_data(code):
    fp=os.path.join(JSON_DIR,f"{code}.json")
    try:
        with open(fp,'rb') as f: return json.loads(f.read().decode('utf-8'))
    except: return None

# 整理2026年数据
data=defaultdict(list)
for dt in data_cache:
    if not dt.startswith('2026'): continue
    for c in data_cache[dt]:
        if c['code'] in ST: continue
        p=c['p']; n=c['n']
        if p is None or not (MIN_CHG <= p < MAX_CHG): continue
        if n is None: continue
        data[dt].append(c)
data={k:v for k,v in data.items() if len(v)>=5}
dates=sorted(data.keys())

print("═══ 2026年冠军跌但前3名里有赢家的案例 ═══")
print()

# 预加载一些热门票的JSON数据（内存缓存）
json_cache={}

def get_price_before(code, target_dt, days_before=4):
    """获取某只股票在指定日期前N天的收盘价"""
    if code not in json_cache:
        json_cache[code]=load_stock_data(code)
    recs=json_cache.get(code)
    if not recs: return None
    
    target_idx=None
    for i,r in enumerate(recs):
        if r['date']==target_dt:
            target_idx=i
            break
    if target_idx is None or target_idx<days_before:
        return None
    
    prices=[]
    for d in range(days_before,0,-1):
        idx=target_idx-d
        prices.append({
            'date':recs[idx]['date'],
            'close':recs[idx]['close'],
            'pct':round((recs[idx]['close']/recs[idx-1]['close']-1)*100,2) if idx>0 else 0
        })
    return prices

count=0
for dt in reversed(dates):
    if count>=4: break  # 只要4个案例
    
    cands=sorted(data[dt], key=fn, reverse=True)
    if len(cands)<3: continue
    c1, c2, c3 = cands[0], cands[1], cands[2]
    
    # 冠军跌(n<2.5且最好是n<0实际跌了)，且前3里有赢家
    if c1['n'] < 2.0 and (c2['n'] >= 2.5 or c3['n'] >= 2.5):
        count+=1
        name1=names.get(c1['code'],'?')
        name2=names.get(c2['code'],'?')
        name3=names.get(c3['code'],'?')
        
        print(f"{'='*80}")
        print(f"【案例{count}】📅 {dt}")
        print(f"{'='*80}")
        
        # 当日Top3对比
        print(f"\n📋 当日评分Top3:")
        print(f"{'':>4} {'名称':<10} {'代码':<14} {'买入价':>7} {'涨跌幅':>6} {'实体':>6} {'上影':>5} {'ATR':>5} {'收盘位':>5} {'评分':>5} {'次日高':>7}")
        print(f"  {'─'*75}")
        for i,(c) in enumerate([c1,c2,c3],1):
            name=names.get(c['code'],'?')
            hit='✅' if c['n']>=2.5 else '❌'
            medal='🥇🥈🥉'[i-1]
            print(f"  {medal:<4} {name:<10} {c['code']:<14} {c['close']:>7.2f} {c['p']:>+5.1f}% {c['b']:>5.1f}% {c['s']:>4.1f}% {c['a']:>4.1f}% {c['cl']:>4.1f}% {fn(c):>4.1f} {c['n']:>+5.1f}% {hit}")
        
        # 4日前股价
        print(f"\n📈 选股日前4天收盘价走势:")
        for c in [c1, c2, c3]:
            prices=get_price_before(c['code'], dt, 4)
            if prices:
                name=names.get(c['code'],'?')
                price_str=' → '.join([f"{p['close']:.2f}({p['pct']:+.1f}%)" for p in prices])
                sel_price=c['close']
                print(f"  {name:<10} {c['code']:<14} {price_str} → 【买入日{sel_price:.2f}】")
        
        print()
        
        # 关键差异总结
        print(f"🔍 关键差异分析（冠军 vs 赢家）：")
        # 找出第2/3名中的赢家
        winners=[(i+1,c) for i,c in enumerate([c2,c3]) if c['n']>=2.5]
        for rank, win in winners:
            name=names.get(win['code'],'?')
            print(f"  赢家🥈: {name}({win['code']}) vs 冠军❌: {name1}")
            print(f"    冠军: 涨{c1['p']:+.1f}% 实体{c1['b']:.1f}% 上影{c1['s']:.1f}% ATR{c1['a']:.1f}% 收盘位{c1['cl']:.1f}% → 次日{c1['n']:+.1f}%")
            print(f"    赢家: 涨{win['p']:+.1f}% 实体{win['b']:.1f}% 上影{win['s']:.1f}% ATR{win['a']:.1f}% 收盘位{win['cl']:.1f}% → 次日{win['n']:+.1f}%")
            
            # 差异点总结
            diffs=[]
            for feat,label in [('p','涨跌幅'),('b','实体'),('s','上影'),('a','ATR'),('cl','收盘位')]:
                d=win[feat]-c1[feat]
                if abs(d)>0.5:
                    dirr='↑' if d>0 else '↓'
                    diffs.append(f"{label}{dirr}{abs(d):.1f}")
            print(f"    差异: {' '.join(diffs)}")
        print()
        
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
