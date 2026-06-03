"""V13 30天回测 — 对比两种VR: 默认1.0 vs Volume计算"""
import sqlite3, os, sys, importlib, math
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
sys.path.insert(0, V13_DIR)

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

def run_backtest(vr_mode='default', N=30):
    """vr_mode: 'default' (DB值) 或 'calc' (从volume算)"""
    dates_n = all_dates[-N:]
    extended = all_dates[all_dates.index(dates_n[0])-6:all_dates.index(dates_n[-1])+1]
    
    data = {}
    for dt in extended:
        c.execute('SELECT * FROM data_cache WHERE date=?', (dt,))
        cols = [desc[0] for desc in c.description]
        data[dt] = [dict(zip(cols, row)) for row in c.fetchall()]
    
    # 计算VR（如果需要）
    if vr_mode == 'calc':
        for dt in dates_n:
            for s in data.get(dt, []):
                code = s['code']
                c.execute('SELECT volume FROM data_cache WHERE code=? AND date<? AND volume>0 ORDER BY date DESC LIMIT 5', (code, dt))
                vols = [r[0] for r in c.fetchall()]
                avg_vol = sum(vols)/len(vols) if vols else 1
                today_vol = s.get('volume', 0) or 0
                s['_calc_vr'] = round(today_vol/avg_vol, 2) if avg_vol > 0 else 1.0
    
    features = {}
    for dt in dates_n:
        c.execute('SELECT * FROM features_cache WHERE date=?', (dt,))
        fcols = [desc[0] for desc in c.description]
        for row in c.fetchall():
            f = dict(zip(fcols, row))
            features[(f['code'], dt)] = f
    
    c.execute('SELECT code, hsl, shizhi FROM data_stock_info')
    stock_info = {r[0]: {'hsl': r[1] or 0, 'shizhi': r[2] or 0} for r in c.fetchall()}
    
    MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
    LO = ['L0','L1','L2','L3','L4']
    
    def mkt_class(ss):
        ps=[s.get('p',0) or 0 for s in ss if abs(s.get('p',0) or 0)<15]
        vrs=[s.get('_calc_vr' if vr_mode=='calc' else 'vr',1) or 1 for s in ss if s.get('vr',0)]
        if not ps: return 'flat'
        ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0; hot=sum(1 for p in ps if 5<=p<=8)
        if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
        if ap<-0.5: return 'down'
        return 'flat'
    
    def exhausted(s,code,dt):
        ft=features.get((code,dt),{}); sl5=ft.get('slope5',0); t4s=ft.get('t4_shadow',0)
        cu=ft.get('cons_up',0); pk=ft.get('peak_decay',0); pv=s.get('p',0) or 0
        for ck in [(sl5>8 and t4s>25),(sl5>10 and t4s>18),(cu>=5 and sl5>15),(pk>5 and sl5>5 and pv<6),(sl5>5 and t4s>30),(cu>=4 and sl5>10 and pv<7)]:
            if ck: return True
        return False
    
    def penalty(code,dt,p_today):
        ad=sorted(data.keys())
        try: idx=ad.index(dt)
        except: return 0
        prev=ad[max(0,idx-6):idx]
        g=[]
        for pd in prev:
            f=False
            for s in data.get(pd,[]):
                if s['code']==code: g.append(s.get('p',0) or 0); f=True; break
            if not f: g.append(0)
        g.append(p_today); n=len(g)
        if n<5: return 0
        short=g[-7:] if n>=7 else [0]*(7-n)+g[-n:]
        d6,d5,d4,d3,d2,d1,p_=short if n>=7 else [0]*(7-len(short))+short
        pm=p_>=max(g[:-1]); a7=sum(g)/n; pen=0; w=50
        for s in data.get(dt,[]):
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
    
    def v10_score(s,code,dt,mk_cn):
        mod=STRATS[mk_cn]; stock={}
        stock['p']=s.get('p',0) or 0; stock['cl']=s.get('cl',50)
        stock['vr'] = s.get('_calc_vr',1) if vr_mode=='calc' else (s.get('vr',1) or s.get('vol_ratio',1))
        stock['dif']=s.get('dif_val',0) or s.get('dif',0)
        stock['mg']=s.get('macd_golden',0) or s.get('mg',0)
        stock['wrv']=s.get('wr_val',0) or s.get('wrv',50)
        stock['jv']=s.get('j_val',0) or s.get('jv',50)
        stock['kv']=s.get('k_val',0) or s.get('kv',50)
        stock['dv']=s.get('d_val',0) or s.get('dv',50)
        stock['a5']=s.get('above_ma5',0); stock['kdj_g']=s.get('kdj_golden',0) or s.get('kdj_g',0)
        stock['pos_in_day']=s.get('pos_in_day',50); stock['nm']=s.get('name','') or ''
        si=stock_info.get(code,{}); stock['hsl']=si.get('hsl',0) or 0
        ft=features.get((code,dt),{})
        for k in ['t4_shadow','slope5','cons_up','d1','d2','d3']: stock[k]=ft.get(k,0) if ft else 0
        return round(mod.score(stock)+penalty(code,dt,s.get('p',0) or 0),1)
    
    wi=ta=cta=0
    mk_s={k:[0,0] for k in ['real_up','fake_up','down','flat']}
    
    for dt in reversed(dates_n):
        ss=data.get(dt,[]); ss=[s for s in ss if abs(s.get('p',0) or 0)<15]
        if not ss: continue
        mk=mkt_class(ss); mk_cn=MK_MAP.get(mk,'横盘')
        mod=STRATS[mk_cn]; levels=mod.LEVELS
        lm={l['name']:i for i,l in enumerate(levels)}
        pool=None
        for ln in LO:
            if ln not in lm: continue
            i=lm[ln]; lv=levels[i]; cand=[]
            for s in ss:
                p=s.get('p',0) or 0
                if p<lv['p_min'] or p>min(lv.get('p_max',10),8): continue
                vr = s.get('_calc_vr',1) if vr_mode=='calc' else (s.get('vr',0) or 0)
                if vr<lv['vr_min'] or vr>lv['vr_max']: continue
                si=stock_info.get(s['code'],{}); hsl=si.get('hsl',0) or 0
                if hsl<lv.get('hs_min',0) or hsl>lv.get('hs_max',99): continue
                if (si.get('shizhi',0) or 0)>=lv.get('sz_max',9999): continue
                nm=s.get('name','')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl=s.get('cl',0)
                if cl<lv.get('cl_min',0) or cl>lv.get('cl_max',100): continue
                if exhausted(s,s['code'],dt): continue
                cand.append(s)
            if len(cand)>=10: pool=cand; break
        if not pool: continue
        scored=[(v10_score(s,s['code'],dt,mk_cn),s) for s in pool]
        scored.sort(key=lambda x:-x[0])
        champ=scored[0][1]; nh=champ.get('n',0) or 0
        hn=(dt!=dates_n[-1]); mk_s[mk][1]+=1
        if hn:
            win='✅' if nh>=2.5 else '❌'
            if win=='✅': wi+=1; mk_s[mk][0]+=1
            cta+=1
    
    return wi, cta, mk_s

print('V13 回测对比: 默认VR vs Volume计算VR')
print('='*50)

for N, label in [(30,'30天'),(55,'55天')]:
    w1, t1, mk1 = run_backtest('default', N)
    w2, t2, mk2 = run_backtest('calc', N)
    p1 = w1*100/t1 if t1 else 0
    p2 = w2*100/t2 if t2 else 0
    diff = p2 - p1
    print(f'\n{label}:')
    print(f'  默认VR(DB): {w1}/{t1} = {p1:.1f}%')
    print(f'  计算VR(vol): {w2}/{t2} = {p2:.1f}%')
    print(f'  差异: {diff:+.1f}% {"↑ 更好" if diff > 0 else "↓ 更差" if diff < 0 else "= 持平"}')
    
    # 按行情细分
    mk_names={'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
    for mk in ['real_up','fake_up','down','flat']:
        w1m, t1m = mk1[mk]
        w2m, t2m = mk2[mk]
        if t1m:
            print(f'  {mk_names[mk]}: 默认{p1:.1f}% → 计算{100*w2m/t2m:.1f}%')

conn.close()
