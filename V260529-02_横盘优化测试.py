"""
V260529-02 横盘评分优化测试
"""
import pickle, os, sys, importlib

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR); sys.path.insert(0, SCRIPTS_DIR)

d = pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates = sorted(x for x in data.keys() if '2025-01-01' <= x < '2026-06-01')

mod = importlib.import_module('大道至简_横盘_评分策略')
lv = {**mod.LEVELS[0], 'name':'L'}

def classify_mkt(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p',0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

def run_backtest(fn_scale, max_days=None):
    test_dates = dates[-max_days:] if max_days else dates
    r30={'w':0,'t':0}; r80={'w':0,'t':0}; ra={'w':0,'t':0}
    for dt in test_dates:
        stocks = data.get(dt,[])
        if not stocks: continue
        if classify_mkt(stocks) != 'flat': continue
        pool=[]
        for s in stocks:
            code=s.get('code',''); p=s.get('p',0) or 0
            if p<lv['p_min'] or p>lv['p_max']: continue
            if p>=8: continue
            vr=s.get('vol_ratio',0) or 0
            if vr<lv['vr_min'] or vr>lv['vr_max']: continue
            ri=real.get(code)
            if not ri: continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<lv['hs_min'] or hsl>lv['hs_max']: continue
            if (ri.get('shizhi',0) or 0)>=lv['sz_max']: continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl=s.get('cl',0)
            if cl<lv['cl_min'] or cl>lv['cl_max']: continue
            if (s.get('n',0) or 0)<=0: continue
            pool.append(s)
        if len(pool)<=8: continue
        
        scored=[]
        for s in pool:
            sd={'p':s.get('p',0) or 0,'cl':s.get('cl',0),'vr':s.get('vol_ratio',0) or 0,
                'hsl':(real.get(s['code'],{}).get('hsl',0) or 0),
                'dif':s.get('dif_val',0) or 0,'mg':s.get('macd_golden',0),
                'a5':s.get('above_ma5',0) or 0,'wrv':0,
                'jv':s.get('j_val',0) or 0,'kv':s.get('k_val',0) or 0,
                'dv':s.get('d_val',0) or 0,'kdj_g':s.get('kdj_golden',0) or 0,
                'buy_c':s.get('close',0) or 0}
            sc=fn_scale(sd)
            nh=s.get('n',0) or 0
            scored.append({'sc':sc,'nh':nh})
        if not scored: continue
        scored.sort(key=lambda x:(-x['sc']))
        ra['t']+=1
        if scored[0]['nh']>=2.5: ra['w']+=1
        idx=test_dates.index(dt)
        df=len(test_dates)-1-idx
        if df<30: r30['t']+=1; 
        if scored[0]['nh']>=2.5 and df<30: r30['w']+=1
        if df<80: r80['t']+=1; 
        if scored[0]['nh']>=2.5 and df<80: r80['w']+=1
    return r30, r80, ra

def fmt(r): return f"{r['w']*100/r['t']:.1f}%({r['w']}/{r['t']})" if r['t'] else '—'

# ===== 评分变体 =====
def baseline(s):
    p=s['p'];cl=s['cl'];vr=s['vr'];hsl=s['hsl'];dif=s['dif'];mg=s['mg'];a5=s['a5']
    jv=s['jv'];kv=s['kv'];dv=s['dv'];kdj_g=s['kdj_g'];bc=s['buy_c']
    ms=0
    if mg and dif>0.5:ms=10
    elif mg and dif>0.2:ms=8
    elif mg:ms=6
    elif dif>0.5:ms=4
    elif dif>0:ms=2
    ps2=min(10,max(1,11-bc/10)) if bc else 0
    sc=p*1.5+cl*0.05+ps2*0.3+ms*0.3
    sc+=(2 if a5 else 0)
    sc+=(1*1.5 if 1.0<=vr<=1.5 else 0)
    sc+=(0.3*2 if 5<=hsl<=7 else 0)
    sc+=(2 if 20<=jv<=40 else 0)
    sc+=(2 if kdj_g else 0)
    return sc

def vA(s):
    """A: +V260528加分"""
    sc=baseline(s)
    if s['p']>5 and s['cl']>80: sc-=8
    if s['dif']>0.5: sc+=3
    if s['mg']: sc+=3
    return sc

def vB(s):
    """B: p_w=2.0"""
    sc=baseline(s)
    sc+=s['p']*0.5  # p_w 1.5→2.0
    return sc

def vC(s):
    """C: p_w=1.0 + 加强vr"""
    sc=baseline(s)
    sc-=s['p']*0.5  # p_w 1.5→1.0
    sc+=(3 if s['vr']>1.2 else 0)  # 放量加分加强
    return sc

def vD(s):
    """D: 加WR超卖(wrv>75→+3)"""
    sc=baseline(s)
    sc+=(3 if s['wrv']>75 else 0)
    return sc

def vE(s):
    """E: KDJ加分加强"""
    sc=baseline(s)
    sc+=(1 if s['kdj_g'] else 0)  # KDJ金叉从+2→+3
    return sc

def vF(s):
    """F: p_w=2.0 + V260528加分"""
    sc=baseline(s)
    sc+=s['p']*0.5
    if s['p']>5 and s['cl']>80: sc-=8
    if s['dif']>0.5: sc+=3
    if s['mg']: sc+=3
    return sc

def vG(s):
    """G: p_w=2.0 + WR超卖"""
    sc=baseline(s)
    sc+=s['p']*0.5
    sc+=(3 if s['wrv']>75 else 0)
    return sc

def vH(s):
    """H: 去掉j_low, 加WR+KDJ加强"""
    sc=baseline(s)
    sc-=(2 if 20<=s['jv']<=40 else 0)  # 去掉j_low
    sc+=(3 if s['wrv']>75 else 0)
    sc+=(1 if s['kdj_g'] else 0)  # KDJ金叉+2→+3
    return sc

tests = [
    ('基线(原始)', baseline),
    ('A_V260528加分', vA),
    ('B_p_w=2.0', vB),
    ('C_p_w=1.0+放量', vC),
    ('D_WR超卖+3', vD),
    ('E_KDJ加强', vE),
    ('F_p_w2.0+加分', vF),
    ('G_p_w2.0+WR', vG),
    ('H_去j改WR+KDJ', vH),
]

print("="*70)
print("V260529-02 横盘评分优化测试")
print("="*70)
print(f"{'变体':<18} {'30天':<16} {'80天':<16} {'全量':<16}")
print("-"*70)
for name, fn in tests:
    r30,r80,ra=run_backtest(fn)
    print(f"{name:<18} {fmt(r30):<16} {fmt(r80):<16} {fmt(ra):<16}")
