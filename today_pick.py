#!/usr/bin/env python3
"""今日选股 — 带股票名称+当天涨幅"""
import json, os, time, sys, urllib.request, re
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\.cand_cache.json"
CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
TODAY = "2026-05-21"

# ═══ 加载候选缓存（秒级） ═══
print("📡 加载缓存..."); t0=time.time()
with open(CACHE_FILE,'rb') as f: cache=json.loads(f.read().decode('utf-8'))
cands = cache[f'cands_{TODAY[:4]}']
data = defaultdict(list)
for c in cands:
    data[c['d']].append(c)
print(f"✅ {TODAY}: {len(data.get(TODAY,[]))}只, {time.time()-t0:.1f}秒")

# ═══ 加载原始JSON获取涨幅 ═══
print("📡 加载K线数据算涨幅...")
all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and 
             (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]

# 只加载有候选的股票（加速）
cand_codes = set(c['c'] for c in data.get(TODAY,[]))
code_data = {}
for fn in all_files:
    code = fn.replace('.json','')
    if code not in cand_codes: continue
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        di = next((i for i,r in enumerate(recs) if r['date']==TODAY), None)
        if di is None: continue
        prev_close = recs[di-1]['close'] if di>0 else recs[di]['open']
        pct = round((recs[di]['close']/prev_close-1)*100, 2)
        code_data[code] = {'pct': pct, 'close': recs[di]['close'],
                           'open': recs[di]['open'], 'high': recs[di]['high']}
    except: pass
print(f"✅ {len(code_data)}只有涨幅数据")

# ═══ 获取股票名称（从sina批量获取） ═══
print("📡 获取股票名称...")
codes_list = list(code_data.keys())
names = {}
batch_size = 50
for i in range(0, len(codes_list), batch_size):
    batch = codes_list[i:i+batch_size]
    # sina格式: 沪市sh, 深市sz
    sina_codes = []
    for c in batch:
        if c.startswith('sh'): sina_codes.append(f"sh{c[2:]}")
        elif c.startswith('sz'): sina_codes.append(f"sz{c[2:]}")
    if not sina_codes: continue
    url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
    try:
        req = urllib.request.Request(url, headers={'Referer':'https://finance.sina.com.cn'})
        resp = urllib.request.urlopen(req, timeout=5)
        text = resp.read().decode('gbk')
        for line in text.strip().split('\n'):
            m = re.search(r'var hq_str_(sh\d+|sz\d+)="([^,]+)', line)
            if m:
                code_key = m.group(1)
                name = m.group(2)
                orig_code = f"sh{code_key[2:]}" if code_key.startswith('sh') else f"sz{code_key[2:]}"
                names[orig_code] = name
    except:
        pass
    if (i+1) % 200 == 0:
        print(f"  {len(names)}/{len(codes_list)}")

print(f"✅ {len(names)}只有名称")

# ═══ 今日选股（v14评分） ═══
cands_today = data.get(TODAY, [])
if not cands_today:
    print("❌ 今日无候选（无数据）")
    sys.exit(0)

for c in cands_today:
    sh = max(0, 35 - c['s'] * 1.2) if c['s'] < 30 else 0
    ba = min(c['b']*3, 25) + min(c['a']*2, 16)
    c['total'] = round(sh + ba, 1)
    c['shadow_score'] = round(sh, 1)
    c['body_score'] = round(min(c['b']*3,25), 1)
    c['atr_score'] = round(min(c['a']*2,16), 1)

cands_today.sort(key=lambda x: x['total'], reverse=True)

print(f"\n{'='*110}")
print(f"📅 {TODAY} CG-07 v14 选股 — 共{len(cands_today)}只候选")
print(f"{'='*110}")
print(f"{'排名':<4} {'名称':<8} {'代码':<10} {'总分':>5} {'上影分':>6} {'实体分':>6} {'ATR分':>5} {'实体%':>6} {'上影%':>6} {'涨跌幅':>7} {'次日':>6}")
print("-"*75)

for rank, c in enumerate(cands_today[:20], 1):
    code = c['c']
    name = names.get(code, '—')
    pct = code_data.get(code, {}).get('pct', '—')
    pct_str = f"{pct:+.2f}%" if isinstance(pct, (int,float)) else pct
    next_str = f"{c['n']:+.1f}%" if c['n'] else "N/A"
    mk = "🏆" if rank == 1 else ""
    print(f"{rank:<4} {name:<8} {code:<10} {c['total']:>5.1f} {c['shadow_score']:>6.1f} {c['body_score']:>6.1f} {c['atr_score']:>5.1f} {c['b']:>5.2f}% {c['s']:>5.1f}% {pct_str:>7} {next_str:>6} {mk}")

# 冠军详情
if cands_today:
    champ = cands_today[0]
    code = champ['c']
    name = names.get(code, '—')
    pct = code_data.get(code, {}).get('pct')
    close = code_data.get(code, {}).get('close')
    print(f"\n{'='*110}")
    print(f"🏆 冠军: {name}({code})")
    print(f"   总分: {champ['total']}分")
    print(f"   当日涨幅: {pct:+.2f}%" if pct else "   当日涨幅: N/A")
    print(f"   收盘价: {close}" if close else "")
    print(f"   实体: {champ['b']:.2f}% (分{champ['body_score']})")
    print(f"   上影: {champ['s']:.1f}% (分{champ['shadow_score']})")
    print(f"   ATR: {champ['a']:.2f}% (分{champ['atr_score']})")
    print(f"   次日最高: {champ['n']:+.1f}%" if champ['n'] else "   次日最高: 无数据")

print(f"\n⏱ {time.time()-t0:.1f}秒")
