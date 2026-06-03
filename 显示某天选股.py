"""显示V13某天所有选股结果"""
import sqlite3, os, sys, importlib
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
sys.path.insert(0, V13_DIR)

TARGET_DATE = sys.argv[1] if len(sys.argv) > 1 else '2026-05-29'

STRATS = {}
for n in ['真实涨日','虚涨日','跌日','横盘']:
    fp = os.path.join(V13_DIR, '评分策略', f'分而治之_V10_{n}_评分策略.py')
    spec = importlib.util.spec_from_file_location(n, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    STRATS[n] = m

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
all_dates = [r[0] for r in c.fetchall()]
if TARGET_DATE not in all_dates:
    print(f'{TARGET_DATE} 不在交易日中')
    conn.close(); exit()

idx = all_dates.index(TARGET_DATE)
prev_dates = []
for offset in range(1, 8):
    if idx-offset >= 0: prev_dates.append(all_dates[idx-offset])

# 加载当日数据
c.execute('SELECT code, name, p, cl, vr, n, dif_val, macd_golden, wr_val, j_val, k_val, d_val, pos_in_day, above_ma5, kdj_golden, close FROM data_cache WHERE date=?', (TARGET_DATE,))
cols = ['code','name','p','cl','vr','n','dif_val','macd_golden','wr_val','j_val','k_val','d_val','pos_in_day','above_ma5','kdj_golden','close']
stocks = [dict(zip(cols, row)) for row in c.fetchall()]

# 前7天数据
prev_data = {}
for dt in prev_dates:
    c.execute('SELECT code, p FROM data_cache WHERE date=?', (dt,))
    for r in c.fetchall():
        if r[0] not in prev_data: prev_data[r[0]]={}
        prev_data[r[0]][dt] = r[1] or 0

# 特征
features = {}
c.execute('SELECT * FROM features_cache WHERE date=?', (TARGET_DATE,))
fcols = [desc[0] for desc in c.description]
for row in c.fetchall():
    f = dict(zip(fcols, row))
    features[f['code']] = f

c.execute('SELECT code, hsl, shizhi FROM data_stock_info')
stock_info = {r[0]: {'hsl': r[1] or 0, 'shizhi': r[2] or 0} for r in c.fetchall()}

MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LO = ['L0','L1','L2','L3','L4']

def mkt_class(ss):
    ps=[s.get('p',0) or 0 for s in ss if abs(s.get('p',0) or 0)<15]
    vrs=[s.get('vr',0) or 1 for s in ss if s.get('vr',0)]
    if not ps: return 'flat'
    ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

def is_momentum_exhausted(s):
    ft=features.get(s['code'],{})
    if not ft: return False
    sl5=ft.get('slope5',0); t4s=ft.get('t4_shadow',0); cu=ft.get('cons_up',0)
    pk=ft.get('peak_decay',0); pv=s.get('p',0) or 0
    if sl5>8 and t4s>25: return True
    if sl5>10 and t4s>18: return True
    if cu>=5 and sl5>15: return True
    if pk>5 and sl5>5 and pv<6: return True
    if sl5>5 and t4s>30: return True
    if cu>=4 and sl5>10 and pv<7: return True
    return False

def compute_7day_penalty(code, p_today):
    g=[]
    for dt in sorted(prev_dates):
        if code in prev_data and dt in prev_data[code]:
            g.append(prev_data[code][dt])
        else: g.append(0)
    g.append(p_today)
    n=len(g)
    if n<5: return 0
    d6,d5,d4,d3,d2,d1,p_=g[-7:] if n>=7 else [0]*(7-n)+g[-n:]
    pm=p_>=max(g[:-1]); a7=sum(g)/n; pen=0; w=50
    for s in stocks:
        if s['code']==code: w=s.get('wr_val',50) or s.get('wrv',50); break
    if w<10 and pm and a7<2.0 and p_<6: pen-=8
    if pm and a7<0.8 and p_<8:
        pen-=15 if a7<0 else (-12 if a7<0.3 else (-8 if a7<0.7 else -5))
    if n>=6 and d1<-1.5 and d2<-1.0 and p_>3 and a7<1.0: pen-=8
    if len(g)>=7 and max(d4,d3,d2)>5 and d1<0 and d2<0: pen-=10
    if n>=5 and d5>d1 and d5>d2 and p_<=d5:
        rs=(d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
        if rs<=2: pen-=8
    if n>=5 and all(g[-5+i]>=g[-4+i] for i in range(4)): pen-=10
    return pen

def v10_score(s):
    code=s['code']; mk_cn=MK_MAP.get(mk,'横盘')
    mod=STRATS[mk_cn]; stock={}
    stock['p']=s.get('p',0) or 0; stock['cl']=s.get('cl',50)
    stock['vr']=s.get('vr',1) or 1
    stock['dif']=s.get('dif_val',0) or s.get('dif',0)
    stock['mg']=s.get('macd_golden',0) or s.get('mg',0)
    stock['wrv']=s.get('wr_val',0) or s.get('wrv',50)
    stock['jv']=s.get('j_val',0) or s.get('jv',50)
    stock['kv']=s.get('k_val',0) or s.get('kv',50)
    stock['dv']=s.get('d_val',0) or s.get('dv',50)
    stock['a5']=s.get('above_ma5',0); stock['kdj_g']=s.get('kdj_golden',0) or s.get('kdj_g',0)
    stock['pos_in_day']=s.get('pos_in_day',50)
    stock['nm']=s.get('name','') or ''
    si=stock_info.get(code,{}); stock['hsl']=si.get('hsl',0) or 0
    ft=features.get(code,{})
    stock['t4_shadow']=ft.get('t4_shadow',0) if ft else 0
    stock['slope5']=ft.get('slope5',0) if ft else 0
    stock['cons_up']=ft.get('cons_up',0) if ft else 0
    stock['d1']=ft.get('d1',0) if ft else 0
    stock['d2']=ft.get('d2',0) if ft else 0
    stock['d3']=ft.get('d3',0) if ft else 0
    penalty=compute_7day_penalty(code,s.get('p',0) or 0)
    return round(mod.score(stock)+penalty,1), round(penalty,1), round(mod.score(stock),1)

# 行情分类
mk=mkt_class(stocks); mk_cn=MK_MAP.get(mk,'横盘')
mod=STRATS[mk_cn]; levels=mod.LEVELS
lm={l['name']:i for i,l in enumerate(levels)}

print(f'\n📊 {TARGET_DATE} 行情: {mk_cn}')
print('='*80)

pool=None; used_level='无'
for ln in LO:
    if ln not in lm: continue
    i=lm[ln]; lv=levels[i]; cand=[]
    for s in stocks:
        p=s.get('p',0) or 0
        if p<lv['p_min'] or p>min(lv.get('p_max',10),8): continue
        vr=s.get('vr',0) or s.get('vol_ratio',0) or 0
        if vr<lv['vr_min'] or vr>lv['vr_max']: continue
        si=stock_info.get(s['code'],{}); hsl=si.get('hsl',0) or 0
        if hsl<lv.get('hs_min',0) or hsl>lv.get('hs_max',99): continue
        if (si.get('shizhi',0) or 0)>=lv.get('sz_max',9999): continue
        nm=s.get('name','')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        cl=s.get('cl',0)
        if cl<lv.get('cl_min',0) or cl>lv.get('cl_max',100): continue
        if is_momentum_exhausted(s): continue
        cand.append(s)
    if len(cand)>=10: pool=cand; used_level=ln; break

if not pool:
    print('❌ 候选池不足10只')
    conn.close(); exit()

scored=[]
for s in pool:
    total, penalty, base = v10_score(s)
    scored.append((total, penalty, base, s))
scored.sort(key=lambda x:-x[0])

print(f'级别: {used_level} | 候选: {len(pool)}只 | 显示TOP20')
print(f'{"排名":>4} {"名称":>10} {"代码":>6} {"涨":>5} {"CL":>4} {"WR":>5} {"VR":>4} {"HSL":>4} {"基础分":>6} {"衰减":>5} {"总分":>6}')
print('-'*74)
for rank, (total, penalty, base, s) in enumerate(scored[:20], 1):
    p=s.get('p',0) or 0; cl=s.get('cl',0) or 50
    wr=s.get('wr_val',0) or s.get('wrv',50)
    vr=s.get('vr',0) or 1
    si=stock_info.get(s['code'],{}); hsl=si.get('hsl',0) or 0
    nh=s.get('n',0) or 0
    champ_mark = '🏆' if rank==1 else ''
    print(f'{champ_mark}{rank:>3} {s["name"]:>10} {s["code"]:>6} {p:+4.1f}% {cl:>3.0f} {wr:>4.0f} {vr:>3.1f} {hsl:>3.1f} {base:>6.1f} {penalty:>5.1f} {total:>6.1f}')

# 次日高验证
print(f'\n冠军次日高: {nh:+.1f}% → {"✅ 达标(≥2.5%)" if nh>=2.5 else "❌ 未达标" if nh>0 else "⏳ 待验证"}')

conn.close()
