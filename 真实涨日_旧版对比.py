"""旧版v10切换策略 vs 新版4类分型 - 真实涨日对比"""
import pickle, os, sys

os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
print("Loading...", flush=True)
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, real, names = d['data'], d['real'], d['names']
dates = [x for x in sorted(data.keys()) if '2025-01-01' <= x < '2026-06-01']

def classify_market(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    if avg_p<-0.5: return 'down'
    return 'flat'

def calc_macd(dif, mg):
    if mg and dif > 0.5: return 10
    if mg and dif > 0.2: return 8
    if mg: return 6
    if dif > 0.5: return 4
    if dif > 0: return 2
    return 0

def filter_stock(s, p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz_max,cl_min,cl_max):
    code=s['code']; p=s.get('p',0) or 0
    if p<p_min or p>p_max: return None
    vr=s.get('vol_ratio',0) or 0
    if vr<vr_min or vr>vr_max: return None
    ri=real.get(code)
    if not ri: return None
    hsl=(ri.get('hsl',0) or 0)
    if hsl<hs_min or hsl>hs_max: return None
    if (ri.get('shizhi',0) or 0)>=sz_max: return None
    nm=names.get(code,'')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return None
    cl=s.get('cl',0)
    if cl<cl_min or cl>cl_max: return None
    nh=s.get('n',0) or 0
    if nh<=0: return None
    return {
        'nm':nm[:12],'code':code,'p':p,'cl':cl,'vr':vr,'nh':nh,
        'buy':s.get('close',0) or 0,
        'dif':s.get('dif_val',0) or 0,'mg':s.get('macd_golden',0),
        'a5':s.get('above_ma5',0) or 0,'iy':s.get('is_yang',0) or 0
    }

MAIN_PARAMS = {'p_min':5,'p_max':8,'vr_min':0.8,'vr_max':2.0,'hs_min':5,'hs_max':15,'sz_max':300,'cl_min':60,'cl_max':90}

# 找出所有真实涨日
real_up_dates = []
for dt in dates:
    stocks = data.get(dt,[])
    if not stocks: continue
    mkt = classify_market(stocks)
    if mkt == 'real_up': real_up_dates.append(dt)

print(f"真实涨日共{len(real_up_dates)}天")
print()

# ===== 方案A: 旧版v10涨日策略（涨×3.0 + CL×0.1 + MACD + MA5） =====
def score_v10_up(x):
    ms = calc_macd(x['dif'], x['mg'])
    ps2 = min(10, max(1, 11 - x['buy'] / 10)) if x['buy'] else 0
    return x['p'] * 3.0 + x['cl'] * 0.1 + ps2 * 0.3 + ms * 0.3 + (3 if x['a5'] else 0)

# ===== 方案B: 旧版v10跌/横盘策略（涨×2.0 + CL×0.05 + MACD） =====
def score_v10_down(x):
    ms = calc_macd(x['dif'], x['mg'])
    ps2 = min(10, max(1, 11 - x['buy'] / 10)) if x['buy'] else 0
    return x['p'] * 2.0 + x['cl'] * 0.05 + ps2 * 0.3 + ms * 0.3

tests = [
    ("旧版v10涨:涨x3+CLx0.1+MACD+MA5", score_v10_up),
    ("保守涨x1+CLx0.1:降涨升CL", lambda x: x['p']*1.0 + x['cl']*0.1),
    ("保守涨x0.5+CLx0.15:降涨升CL更多", lambda x: x['p']*0.5 + x['cl']*0.15),
    ("涨x2+CLx0.05:降CL", lambda x: x['p']*2.0 + x['cl']*0.05),
    ("用跌日策略:涨x2+CLx0.05+MACD", score_v10_down),
    ("涨x1+CLx0.05+MACD:复制虚涨日", lambda x: x['p']*1.0 + x['cl']*0.05 + min(10,max(1,11-x['buy']/10))*0.3 + calc_macd(x['dif'],x['mg'])*0.5),
    ("涨x1.5+CLx0.08+MACD", lambda x: x['p']*1.5 + x['cl']*0.08 + calc_macd(x['dif'],x['mg'])*0.3),
    ("涨x2+CLx0.08+MACD+MA5", lambda x: x['p']*2.0 + x['cl']*0.08 + calc_macd(x['dif'],x['mg'])*0.3 + (3 if x['a5'] else 0)),
    ("涨x2.5+CLx0.05+MACD+MA5", lambda x: x['p']*2.5 + x['cl']*0.05 + calc_macd(x['dif'],x['mg'])*0.3 + (3 if x['a5'] else 0)),
]

for name, score_fn in tests:
    wins = 0
    for dt in real_up_dates:
        stocks = data.get(dt, [])
        cand = []
        for s in stocks:
            x = filter_stock(s, **MAIN_PARAMS)
            if not x: continue
            x['score'] = score_fn(x)
            cand.append(x)
        if cand:
            cand.sort(key=lambda x: (-x['score'], -x['p']))
            if cand[0]['nh'] >= 2.5: wins += 1
    print(f"  {wins}/{len(real_up_dates)}={wins*100/len(real_up_dates):.1f}% | {name}")

# 再试试放宽选股条件
print(f"\n{'='*60}")
print("真实涨日 - 放宽选股范围")
print(f"{'='*60}")

alt_params = [
    ("原范围:涨5-8量0.8-2.0CL60-90", 5,8,0.8,2.0,5,15,300,60,90),
    ("窄:涨5-7量0.8-2.0CL65-90", 5,7,0.8,2.0,5,15,300,65,90),
    ("低CL:涨5-8量0.8-2.0CL50-80", 5,8,0.8,2.0,5,15,300,50,80),
    ("宽量:涨5-8量1.0-2.5CL60-90", 5,8,1.0,2.5,5,15,300,60,90),
    ("小市值:涨5-8量0.8-2.0CL60-90sz<200", 5,8,0.8,2.0,5,15,200,60,90),
]

for name,p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz_max,cl_min,cl_max in alt_params:
    wins = 0
    for dt in real_up_dates:
        stocks = data.get(dt, [])
        cand = []
        for s in stocks:
            x = filter_stock(s,p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz_max,cl_min,cl_max)
            if not x: continue
            x['score'] = score_v10_up(x)
            cand.append(x)
        if cand:
            cand.sort(key=lambda x: (-x['score'], -x['p']))
            if cand[0]['nh'] >= 2.5: wins += 1
    print(f"  {wins}/{len(real_up_dates)}={wins*100/len(real_up_dates):.1f}% | {name}")
