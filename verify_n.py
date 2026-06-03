"""验证缓存n字段是否准确"""
import pickle, json, os, sys, subprocess
sys.path.insert(0, os.path.dirname(__file__))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPTS_DIR)

# 从缓存读数据
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, names = d['data'], d['names']
dates = sorted(data.keys())

# 选近30天里胜率低的某天，逐只检查n值是否合理
# 2026-04-20: 真实涨日 冠军金瑞矿业 n=1.4%
dt = '2026-04-20'
stocks = data.get(dt, [])
print(f'=== {dt} 缓存数据 ===')
print(f'总股票: {len(stocks)}只')

# 找当天涨幅在3-6%的股票，检查它们的n值
candidates = []
for s in stocks:
    p = s.get('p', 0) or 0
    if 3 <= p <= 6:
        n = s.get('n', 0) or 0
        code = s.get('code', '')
        nm = names.get(code, '?')
        candidates.append((code, nm, p, n))

candidates.sort(key=lambda x: -x[3])
print(f'涨3-6%的票: {len(candidates)}只')
print(f'其中n>2.5%的: {sum(1 for c in candidates if c[3] >= 2.5)}只')
print()
print('Top 15 按n排序:')
for code, nm, p, n in candidates[:15]:
    print(f'  {nm}({code[-4:]}) p={p:.1f}% n={n:.1f}%')

# 找一个具体股票，看看它的K线JSON里n是否正确
print()
print('=== 验证K线JSON ===')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
verify_codes = ['600714']  # 金瑞矿业
for code in verify_codes:
    mkt = 'sh' if code.startswith(('6','9')) else 'sz'
    fp = os.path.join(CACHE_DIR, f'{mkt}{code}.json')
    if not os.path.exists(fp):
        print(f'{code}: JSON文件不存在')
        continue
    with open(fp) as f:
        kdata = json.load(f)
    # 找2026-04-20
    idx = next((i for i, k in enumerate(kdata) if k.get('date') == dt), None)
    if idx is None:
        print(f'{code}: 找不到{dt}')
        continue
    buy_c = kdata[idx]['close']
    if idx + 1 < len(kdata):
        next_high = (kdata[idx+1]['high'] / buy_c - 1) * 100
        next_close = (kdata[idx+1]['close'] / buy_c - 1) * 100
        print(f'{code} {dt}: 收盘{buy_c}')
        print(f'  D+1 {kdata[idx+1]["date"]}: 最高{kdata[idx+1]["high"]} ({next_high:.1f}%) 收盘{kdata[idx+1]["close"]} ({next_close:.1f}%)')
        # 对比缓存里的n
        for s in stocks:
            if s['code'] == code:
                print(f'  缓存n={s.get("n",0):.1f}%')
                break
    else:
        print(f'{code}: 没有下一天的数据')
