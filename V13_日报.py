#!/usr/bin/env python3
"""V13 每日选股报告 — 实时API + V10同款淡色模板"""

import sys, os, json, re, time, subprocess
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from selection_log_db import log_selection_to_db

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
sys.path.insert(0, V13_DIR); sys.path.insert(0, SCRIPTS_DIR)

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

# ===== 加载V13策略模块 =====
import importlib
STRATS = {}
for n in ['真实涨日','虚涨日','跌日','横盘']:
    fp = os.path.join(V13_DIR, '评分策略', f'分而治之_V10_{n}_评分策略.py')
    spec = importlib.util.spec_from_file_location(n, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    STRATS[n] = m

LO = ['L0','L1','L2','L3','L4']
MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}

def curl_get(url, timeout=10):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url],capture_output=True,timeout=timeout+5)
        return r.stdout.decode('gbk',errors='replace')
    except: return ''

# ===== 实时行情拉取 =====
def get_live_stocks():
    t0 = time.time()
    now_hour = datetime.now().hour
    # 预加载data_cache的vr（用上交易日vr，避开API虚假量比）
    cache_vr = {}
    try:
        import sqlite3 as _sq3
        _db = _sq3.connect(os.path.join(SCRIPTS_DIR, 'v13_quant.db'), timeout=5)
        # 取上交易日vr（今天被save_realtime_api写了错误的量比）
        _today = datetime.now().strftime('%Y-%m-%d')
        _cur = _db.execute('SELECT DISTINCT date FROM data_cache WHERE vr>0 AND date<? ORDER BY date DESC LIMIT 1', (_today,))
        _last = _cur.fetchone()
        if _last:
            _last_date = _last[0]
            _cur2 = _db.execute('SELECT code, vr FROM data_cache WHERE date=? AND vr>0', (_last_date,))
            cache_vr = {r[0]: r[1] for r in _cur2.fetchall()}
            print(f'📊 量比数据源: {_last_date} ({len(cache_vr)}只)', flush=True)
        _db.close()
    except:
        pass
    # 开盘前（<9:30）直接从data_cache加载，确保和回测数据一致
    if now_hour < 9 or (now_hour == 9 and datetime.now().minute < 30):
        active = {}
        try:
            import sqlite3 as _sq3
            _db = _sq3.connect(os.path.join(SCRIPTS_DIR, 'v13_quant.db'), timeout=5)
            _last_date = datetime.now().strftime('%Y-%m-%d') if False else ''
            _cur = _db.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 AND date<? ORDER BY date DESC LIMIT 1', (datetime.now().strftime('%Y-%m-%d'),))
            _r = _cur.fetchone()
            if _r:
                _dt = _r[0]
                _cur2 = _db.execute('SELECT code, name, p, cl, wr_val, dif_val, vr, close FROM data_cache WHERE date=? AND close>0', (_dt,))
                # 加载HSL
                _hsl = {}
                try:
                    _hsl_cur = _db.execute('SELECT code, hsl FROM data_stock_info')
                    _hsl = {r[0]: r[1] or 0 for r in _hsl_cur.fetchall()}
                except:
                    pass
                for r in _cur2.fetchall():
                    code = r[0]
                    active[code] = {
                        'name': r[1] or '', 'price': r[7], 'p': r[2] or 0,
                        'vol_ratio': r[6] or 1,
                        'cl': r[3] or 50, 'wr_val': r[4] or 50, 'dif_val': r[5] or 0,
                        'hsl': _hsl.get(code, 0), 'pe': 0, 'sz': 0
                    }
                print(f'📡 开盘前，从data_cache加载: {len(active)}只 ({_dt})', flush=True)
            _db.close()
        except Exception as e:
            print(f'⚠️  data_cache加载失败: {e}', flush=True)
        if active:
            return active
    
    codes = [str(i) for i in range(600000, 606000)] + [f'{i:06d}' for i in range(3000)]
    active = {}
    for i in range(0, len(codes), 80):
        chunk = codes[i:i+80]
        symbols = [f'{PREFIX(c)}{c}' for c in chunk]
        text = curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}', timeout=8)
        for line in text.split('\n'):
            if '~' not in line: continue
            parts = line.split('~')
            if len(parts) < 40: continue
            try:
                nm = parts[1]; code = parts[2]
                if not nm or 'ST' in nm or '*ST' in nm or '退' in nm: continue
                if not IS_MAIN(code): continue
                price = float(parts[3]); prev_c = float(parts[4])
                pct = round((price/prev_c-1)*100,2) if prev_c else 0
                # 量比优先从data_cache读取（和回测保持一致）
                vol_r = cache_vr.get(code, float(parts[38])) if parts[38] else 0
                hsl = 0
                try: hsl = float(parts[46]) if parts[46] and float(parts[46])<100 else 0
                except: pass
                pe = float(parts[39]) if parts[39] else 0
                sz = 0
                try: sz = float(parts[44])/1e8 if parts[44] else 0
                except: pass
                active[code] = {'name':nm,'price':price,'p':pct,'vol_ratio':vol_r,'hsl':hsl,'pe':pe,'sz':sz}
            except: pass
    print(f'📡 实时: {len(active)}只 ({time.time()-t0:.0f}s)', flush=True)
    return active

# ===== K线获取+指标计算 =====
def fetch_kline(code):
    mkt = PREFIX(code)
    kf = os.path.join(CACHE_DIR, f'{mkt}{code}.json')
    if os.path.exists(kf) and time.time()-os.path.getmtime(kf)<3600:
        try: return json.load(open(kf))
        except: pass
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt}{code},day,,,300,qfq'
    try:
        text = curl_get(url)
        d = json.loads(text) if text.strip().startswith('{') else {}
        sd = d.get('data',{}).get(f'{mkt}{code}',{})
        k = sd.get('qfqday',[])
        if not k:
            for key in sd:
                if isinstance(sd[key],list) and sd[key] and isinstance(sd[key][0],list): k=sd[key]; break
        if not k or len(k)<80: return None
        recs=[{'date':x[0],'open':float(x[1]),'close':float(x[2]),'high':float(x[3]),'low':float(x[4]),'volume':float(x[5])} for x in k]
        os.makedirs(CACHE_DIR, exist_ok=True); json.dump(recs,open(kf,'w'))
        return recs
    except: return None

def calc_indicators(recs, idx):
    n = len(recs[:idx+1]); df = recs[:idx+1]
    if n<60: return None
    close = [r['close'] for r in df]; high = [r['high'] for r in df]; low = [r['low'] for r in df]
    ema12=close[-1]; ema26=close[-1]
    for i in range(n-2,max(n-27,-1),-1):
        ema12=close[i]*2/13+ema12*11/13; ema26=close[i]*2/27+ema26*25/27
    dif=ema12-ema26; mg=1 if dif>0 else 0
    k_val=d_val=j_val=50; kdj_g=0
    if n>=9:
        h9=max(high[-9:]); l9=min(low[-9:])
        rsv=(close[-1]-l9)/(h9-l9+1e-10)*100
        k_val=rsv*2/3+50/3; d_val=k_val*2/3+50/3; j_val=3*k_val-2*d_val
        kdj_g=1 if k_val>d_val else 0
    wr=50
    if n>=21:
        h21=max(high[-21:]); l21=min(low[-21:])
        wr=100*(h21-close[-1])/(h21-l21+1e-10)
    cl=50
    if n>=20:
        h20=max(high[-20:]); l20=min(low[-20:])
        cl=(close[-1]-l20)/(h20-l20+1e-10)*100
    return {'dif':round(dif,3),'macd_golden':mg,'k_val':round(k_val,1),'d_val':round(d_val,1),
            'j_val':round(j_val,1),'kdj_golden':kdj_g,'wr':round(wr,1),'cl':round(cl,1)}

def classify_market(stocks_all):
    ps=[s['p'] for c,s in stocks_all.items() if abs(s['p'])<15]
    vrs=[s['vol_ratio'] for c,s in stocks_all.items() if s['vol_ratio']>0]
    if not ps: return 'flat'
    avg_p=sum(ps)/len(ps); avg_vr=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    if avg_p<-0.5: return 'down'
    return 'flat'

# ===== 动量检查（简化版，只用K线数据计算） =====
def check_momentum(code, ind, s):
    wr = ind['wr']; cl = ind['cl']; p = s['p']
    if wr < 10 and cl > 60 and 2 < p < 5: return False
    if wr < 15 and p > 5: return False
    if cl > 95 and s['vol_ratio'] < 0.8: return False
    return True

# ===== 实时选股 =====
def pick_today():
    print('🚀 V13 实时选股...', flush=True)
    stocks = get_live_stocks()
    mk = classify_market(stocks)
    mk_cn = MK_MAP.get(mk, '横盘')
    print(f'📊 行情: {mk_cn}', flush=True)
    
    mod = STRATS[mk_cn]
    LEVELS = mod.LEVELS
    lm = {l['name']:i for i,l in enumerate(LEVELS)}
    
    # 多线程计算技术指标（开盘前从data_cache加载的已有指标就跳过）
    codes = list(stocks.keys())
    indicators = {}
    has_precomputed = 'cl' in next(iter(stocks.values())) if stocks else False
    if has_precomputed:
        for code, s in stocks.items():
            if 'cl' in s and 'wr_val' in s:
                indicators[code] = {
                    'dif': s.get('dif_val', 0) or 0,
                    'macd_golden': 1 if (s.get('dif_val', 0) or 0) > 0 else 0,
                    'k_val': 50, 'd_val': 50, 'j_val': 50,
                    'kdj_golden': 1, 'wr': s.get('wr_val', 50) or 50,
                    'cl': s.get('cl', 50) or 50
                }
        print(f'📊 指标: {len(indicators)}/{len(codes)} (来自data_cache)', flush=True)
    else:
        def calc_one(code):
            kl = fetch_kline(code)
            if not kl: return None
            ind = calc_indicators(kl, len(kl)-1)
            if not ind: return None
            return code, ind
        with ThreadPoolExecutor(max_workers=10) as ex:
            for f in as_completed({ex.submit(calc_one,c):c for c in codes}):
                try:
                    r = f.result()
                    if r: indicators[r[0]] = r[1]
                except: pass
        print(f'📊 指标: {len(indicators)}/{len(codes)}', flush=True)
    
    # 分级过滤
    pool = None; used_level = '无'
    for ln in LO:
        if ln not in lm: continue
        i = lm[ln]; lv = LEVELS[i]
        cand = []
        for code, s in stocks.items():
            p = s['p']
            if p < lv['p_min'] or p > min(lv.get('p_max',10),8): continue
            vr = s['vol_ratio']
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            hsl = s['hsl']
            if hsl < lv.get('hs_min',0) or hsl > lv.get('hs_max',99): continue
            if s['sz'] >= lv.get('sz_max',9999): continue
            if 'ST' in s['name'] or '*ST' in s['name']: continue
            ind = indicators.get(code)
            if not ind: continue
            cl_v = ind['cl']
            if cl_v < lv.get('cl_min',0) or cl_v > lv.get('cl_max',100): continue
            if not check_momentum(code, ind, s): continue
            cand.append((code,s,ind))
        if len(cand) >= 10:
            pool = cand; used_level = ln; break
    
    if not pool:
        print('❌ 候选池不足')
        return None
    
    # 评分
    scored = []
    for code, s, ind in pool:
        stock = {
            'p': s['p'], 'cl': ind['cl'], 'vr': s['vol_ratio'],
            'dif': ind['dif'], 'mg': ind['macd_golden'],
            'wrv': ind['wr'], 'jv': ind['j_val'], 'kv': ind['k_val'], 'dv': ind['d_val'],
            'a5': 1, 'kdj_g': ind['kdj_golden'], 'pos_in_day': 50,
            'nm': s['name'], 'hsl': s['hsl'],
            't4_shadow': 0, 'slope5': 0, 'cons_up': 0,
            'd1': 0, 'd2': 0, 'd3': 0,
        }
        sc = mod.score(stock)
        scored.append((sc, s, ind, code))
    scored.sort(key=lambda x:-x[0])
    return scored[:10], mk_cn, used_level, stocks, indicators

# ===== 双轨回测：收盘15:00 vs 尾盘14:50 =====
def backtest_30d():
    """返回 (收盘结果, 2:50结果, last_cache_date)"""
    import sqlite3
    DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    
    # 加载所有交易日
    today_str = datetime.now().strftime('%Y-%m-%d')
    c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
    all_dates_raw = [r[0] for r in c.fetchall()]
    all_dates = []
    for d in all_dates_raw:
        try:
            wd = datetime.strptime(d, '%Y-%m-%d').weekday()
            if wd < 5 and d != today_str:
                all_dates.append(d)
        except:
            pass
    recent = all_dates[-30:]
    extended = all_dates[max(0, all_dates.index(recent[0])-6):all_dates.index(recent[-1])+1]
    
    # 加载data_cache数据（收盘价）
    data = {}
    for dt in extended:
        c.execute('SELECT * FROM data_cache WHERE date=?', (dt,))
        cols = [d[0] for d in c.description]
        data[dt] = [dict(zip(cols, row)) for row in c.fetchall()]
    
    # 加载data_sina 2:50价格
    c.execute('SELECT DISTINCT date FROM data_sina WHERE price>0')
    sina_dates = set(r[0] for r in c.fetchall())
    p250 = {}
    for dt in recent:
        if dt in sina_dates:
            c.execute('SELECT code, price FROM data_sina WHERE date=? AND price>0', (dt,))
            sina_prices = {r[0]: r[1] for r in c.fetchall()}
            prev_idx = max(0, all_dates.index(dt) - 1)
            prev_dt = all_dates[prev_idx]
            for s in data.get(dt, []):
                code = s['code']
                price_250 = sina_prices.get(code)
                if price_250 and price_250 > 0:
                    pre_close = None
                    for ps in data.get(prev_dt, []):
                        if ps['code'] == code:
                            pre_close = ps.get('close', 0)
                            break
                    if pre_close and pre_close > 0:
                        p250[(code, dt)] = round((price_250 / pre_close - 1) * 100, 2)
    
    # 加载特征
    features = {}
    for dt in recent:
        c.execute('SELECT * FROM features_cache WHERE date=?', (dt,))
        fcols = [d[0] for d in c.description]
        for row in c.fetchall():
            f = dict(zip(fcols, row))
            features[(f['code'], dt)] = f
    
    # 股票信息(hsl/市值)
    c.execute('SELECT code, hsl, shizhi FROM data_stock_info')
    stock_info = {r[0]: {'hsl': r[1] or 0, 'shizhi': r[2] or 0} for r in c.fetchall()}
    conn.close()
    
    def mkt_class(ss):
        if not ss: return 'flat'
        ps=[s.get('p',0) or 0 for s in ss]
        vrs=[s.get('vr',0) or 1 for s in ss if s.get('vr',0)]
        ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0
        hot=sum(1 for p in ps if 5<=p<=8)
        if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
        if ap<-0.5: return 'down'
        return 'flat'
    
    def is_momentum_exhausted(s,code,dt):
        feats=features.get((code,dt),{})
        if not feats: return False
        sl5=feats.get('slope5',0); t4s=feats.get('t4_shadow',0); cu=feats.get('cons_up',0)
        pk=feats.get('peak_decay',0); pv=s.get('p',0) or 0
        if sl5>8 and t4s>25: return True
        if sl5>10 and t4s>18: return True
        if cu>=5 and sl5>15: return True
        if pk>5 and sl5>5 and pv<6: return True
        if sl5>5 and t4s>30: return True
        if cu>=4 and sl5>10 and pv<7: return True
        return False
    
    def compute_7day_penalty(code,dt,p_today):
        ad=sorted(data.keys())
        try: idx=ad.index(dt)
        except: return 0
        prev=ad[max(0,idx-6):idx]
        gains=[]
        for pd in prev:
            found=False
            for s in data.get(pd,[]):
                if s['code']==code: gains.append(s.get('p',0) or 0); found=True; break
            if not found: gains.append(0)
        gains.append(p_today)
        n=len(gains)
        if n<5: return 0
        d6,d5,d4,d3,d2,d1,p=gains[-7:] if n>=7 else [0]*(7-n)+gains[-n:]
        p_is_max=p>=max(gains[:-1]); avg_7d=sum(gains)/n
        penalty=0; wrv=50
        for s in data.get(dt,[]):
            if s['code']==code: wrv=s.get('wr_val',50) or s.get('wrv',50); break
        if wrv<10 and p_is_max and avg_7d<2.0 and p<6: penalty-=8
        if p_is_max and avg_7d<0.8 and p<8:
            if avg_7d<0: penalty-=15
            elif avg_7d<0.3: penalty-=12
            elif avg_7d<0.7: penalty-=8
            else: penalty-=5
        if d1<-1.5 and d2<-1.0 and p>3 and avg_7d<1.0: penalty-=8
        if max(d4,d3,d2)>5 and d1<0 and d2<0: penalty-=10
        if n>=5 and d5>d1 and d5>d2 and p<=d5:
            recent_sum=(d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
            if recent_sum<=2: penalty-=8
        if n>=5:
            last5=gains[-5:]
            if all(last5[i]>=last5[i+1] for i in range(len(last5)-1)): penalty-=10
        return penalty
    
    def run_single_backtest(use_250=False):
        """跑单次回测，use_250=True则用2:50价格"""
        def get_p(s, code, dt):
            if use_250:
                return p250.get((code, dt), s.get('p',0) or 0)
            return s.get('p',0) or 0
        
        def v10_score(s,code,dt,mk_cn):
            mod=STRATS[mk_cn]; stock={}
            p_v = get_p(s, code, dt)
            stock['p']=p_v; stock['cl']=s.get('cl',50)
            stock['vr']=s.get('vr',1) or s.get('vol_ratio',1)
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
            feats=features.get((code,dt),{})
            stock['t4_shadow']=feats.get('t4_shadow',0); stock['slope5']=feats.get('slope5',0)
            stock['cons_up']=feats.get('cons_up',0)
            stock['d1']=feats.get('d1',0); stock['d2']=feats.get('d2',0); stock['d3']=feats.get('d3',0)
            penalty=compute_7day_penalty(code,dt,p_v)
            return round(mod.score(stock)+penalty,1)
        
        wi=0; ta=0; daily_rows=[]; mk_s={'real_up':[0,0],'fake_up':[0,0],'down':[0,0],'flat':[0,0]}
        top3_results=[]; p250_days=0
        
        for dt in recent:
            ss=data.get(dt,[]); ss=[s for s in ss if (get_p(s,s['code'],dt) or 0)<15]
            if not ss: continue
            mk=mkt_class(ss); mk_cn=MK_MAP.get(mk,'横盘')
            mod=STRATS[mk_cn]; levels=mod.LEVELS
            lm={l['name']:i for i,l in enumerate(levels)}
            pool=None
            for ln in LO:
                if ln not in lm: continue
                i=lm[ln]; lv=levels[i]; cand=[]
                for s in ss:
                    code=s['code']
                    p_v=get_p(s,code,dt)
                    if p_v<lv['p_min'] or p_v>min(lv.get('p_max',10),8): continue
                    vr=s.get('vr',0) or s.get('vol_ratio',0) or 0
                    if vr<lv['vr_min'] or vr>lv['vr_max']: continue
                    si=stock_info.get(code,{}); hsl=si.get('hsl',0) or 0
                    if hsl<lv.get('hs_min',0) or hsl>lv.get('hs_max',99): continue
                    if (si.get('shizhi',0) or 0)>=lv.get('sz_max',9999): continue
                    nm=s.get('name','')
                    if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                    cl=s.get('cl',0)
                    if cl<lv.get('cl_min',0) or cl>lv.get('cl_max',100): continue
                    if is_momentum_exhausted(s,code,dt): continue
                    cand.append(s)
                if len(cand)>=10: pool=cand; break
            if not pool: continue
            scored=[(v10_score(s,s['code'],dt,mk_cn),s) for s in pool]
            scored.sort(key=lambda x:-x[0])
            champ=scored[0][1]; nh=champ.get('n',0) or 0
            if use_250 and (champ['code'], dt) in p250: p250_days+=1
            has_next = nh != 0 or any((s.get('n',0) or 0)!=0 for s in ss)
            if has_next: ta+=1; mk_s[mk][1]+=1
            t3=[scored[i][1] for i in range(min(3,len(scored)))]
            
            cname=champ.get('name','') or champ.get('nm','')
            if not has_next:
                daily_rows.append(f'⏳ {dt} {mk_cn:>5} {cname:>8} nh=待确认')
                result_mark = '⏳'
            elif nh>=2.5:
                wi+=1; mk_s[mk][0]+=1
                daily_rows.append(f'✅ {dt} {mk_cn:>5} {cname:>8} nh={nh:+.1f}%')
                result_mark = '✅'
            else:
                daily_rows.append(f'❌ {dt} {mk_cn:>5} {cname:>8} nh={nh:+.1f}%')
                result_mark = '❌'
            
            si2=stock_info.get(champ['code'],{})
            top3_results.append({
                'dt':dt,'mk':mk_cn,'c_name':cname,'c_code':champ['code'],
                'p':get_p(champ,champ['code'],dt),'nh':nh,'score':scored[0][0],
                'cl':champ.get('cl',0),'vr':champ.get('vr',0) or champ.get('vol_ratio',0),
                'hsl':si2.get('hsl',0),
                'wr':champ.get('wr_val',0) or champ.get('wrv',50),
                'dif':champ.get('dif_val',0) or champ.get('dif',0),
                'result': result_mark,
                's_name':t3[1].get('name','?') if len(t3)>1 else '—',
                's_code':t3[1]['code'] if len(t3)>1 else '',
                's_nh':t3[1].get('n',0) or 0 if len(t3)>1 else 0,
                't_name':t3[2].get('name','?') if len(t3)>2 else '—',
                't_code':t3[2]['code'] if len(t3)>2 else '',
                't_nh':t3[2].get('n',0) or 0 if len(t3)>2 else 0,
            })
        
        return (wi, ta, mk_s, daily_rows, top3_results, recent[-1], p250_days)
    
    close_res = run_single_backtest(use_250=False)
    p250_res = run_single_backtest(use_250=True)
    return close_res, p250_res, len(recent)

# ===== 生成HTML =====
def build_html(top10_result, bt_result, today_str, data_date_str, buy_date_str, mk_cn, level, ver_id='V13'):
    """V10同款淡色模板"""
    close_res, p250_res, total_days = bt_result
    wi, ta, mk_s, daily_rows, top3_results, last_cache_date, _ = close_res
    p250_wi, p250_ta, p250_mk_s, _, p250_top3, _, p250_days = p250_res
    now = datetime.now()

    # 从数据库读版本战绩
    import sqlite3
    v50d = '—'; v100d = '—'
    try:
        db = sqlite3.connect(DB_PATH, timeout=10)
        cur = db.execute("SELECT rate_50d, rate_100d FROM version_results WHERE version LIKE ? ORDER BY rowid DESC", (f'{ver_id}%',))
        r = cur.fetchone()
        if r:
            v50d = f'{r[0]:.0f}%' if r[0] else '—'
            v100d = f'{r[1]:.0f}%' if r[1] else '—'
        db.close()
    except: pass
    
    # 对比表：收盘15:00 vs 尾盘14:50（同一张表，逐日对比）
    p250_pct = p250_wi*100/p250_ta if p250_ta else 0
    close_pct = wi*100/ta if ta else 0
    
    # 构建对比逐日表
    compare_rows = ''
    close_by_dt = {r['dt']: r for r in top3_results}
    p250_by_dt = {r['dt']: r for r in p250_top3}
    all_dts = sorted(set(list(close_by_dt.keys()) + list(p250_by_dt.keys())), reverse=True)
    match_count = 0
    for dt in all_dts:
        cr = close_by_dt.get(dt)
        pr = p250_by_dt.get(dt)
        if not cr or not pr: continue
        
        # 收盘冠军
        c_pct_c = '#e74c3c' if cr['p']>=0 else '#27ae60'
        c_nh = cr.get('nh', 0) or 0
        if c_nh == 0 and cr['dt'] >= last_cache_date:
            c_nh_disp = '<span style="color:#95a5a6">待确认</span>'
        else:
            c_nh_c = '#e74c3c' if c_nh>=2.5 else '#27ae60'
            c_nh_disp = f'<span style="color:{c_nh_c};font-weight:bold">{c_nh:+.1f}%</span>'
        c_pct_s = f'<span style="color:{c_pct_c};font-weight:bold">{cr["p"]:+.1f}%</span>'
        
        # 14:50冠军
        p_pct_c = '#e74c3c' if pr['p']>=0 else '#27ae60'
        p_nh = pr.get('nh', 0) or 0
        if p_nh == 0 and pr['dt'] >= last_cache_date:
            p_nh_disp = '<span style="color:#95a5a6">待确认</span>'
        else:
            p_nh_c = '#e74c3c' if p_nh>=2.5 else '#27ae60'
            p_nh_disp = f'<span style="color:{p_nh_c};font-weight:bold">{p_nh:+.1f}%</span>'
        p_pct_s = f'<span style="color:{p_pct_c};font-weight:bold">{pr["p"]:+.1f}%</span>'
        
        compare_rows += f'<tr><td>{dt[5:]}</td><td>{cr["mk"]}</td><td>{cr["c_name"]}</td><td>{c_pct_s}</td><td>{c_nh_disp}</td><td>{pr["c_name"]}</td><td>{p_pct_s}</td><td>{p_nh_disp}</td></tr>'
    
    # 一致率统计
    match_count = sum(1 for dt in all_dts if close_by_dt.get(dt) and p250_by_dt.get(dt) and close_by_dt[dt]['c_code'] == p250_by_dt[dt]['c_code'])
    
    match_total = len(all_dts)
    match_pct = match_count*100/match_total if match_total else 0
    

    top3_cards = ''
    medals = {0:'🥇',1:'🥈',2:'🥉'}
    for rank, (sc, s, ind, code) in enumerate(top10_result[:3]):
        medal = medals[rank]
        nm = s['name']
        price = f'{s["price"]:.2f}'
        pct = s['p']
        pct_s = f'+{pct:.1f}%' if pct >= 0 else f'{pct:.1f}%'
        pct_c = '#e74c3c' if pct >= 0 else '#27ae60'
        vr = s['vol_ratio']
        hsl = s['hsl']
        sz = s['sz']
        price_warn = ' ⚠️ 价格较高' if s['price'] > 100 else ''
        trends = []
        if pct > 0 and vr > 1.2: trends.append('放量')
        elif pct > 0: trends.append('正常')
        else: trends.append('缩量')
        if ind and ind['macd_golden']: trends.append('多头')
        elif ind and ind['dif'] > 0: trends.append('偏多')
        else: trends.append('偏弱')
        trend_str = ' | '.join(trends)
        bg = '#fff8e1' if rank == 0 else '#f5f6fa'
        
        top3_cards += f'''
    <div style="display:grid;grid-template-columns:40px 1fr;background:{bg};border-radius:6px;padding:8px;align-items:center">
      <div style="font-size:20px;text-align:center">{medal}</div>
      <div>
        <div style="font-weight:bold;font-size:14px">{nm}({code}){price_warn}</div>
        <div style="font-size:12px;color:#95a5a6">
          买入价<b style="font-size:16px;color:#2c3e50">¥{price}</b>
          &nbsp;| 当日<span style="color:{pct_c};font-weight:bold">{pct_s}</span>
          &nbsp;| 评分<span style="font-weight:bold">{sc:.1f}</span>
          &nbsp;| {trend_str}
        </div>
      </div>
    </div>'''
    
    # 30天战绩
    mkt_names = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
    mkt_rows = ''
    total_w = sum(mk_s[k][0] for k in mk_s)
    total_t = sum(mk_s[k][1] for k in mk_s)
    for k, cn in mkt_names.items():
        w, t = mk_s[k]
        if t == 0: continue
        wr_pct = w*100/t
        bar_full = '█' * int(wr_pct/5)
        bar_empty = '░' * (20 - len(bar_full))
        mkt_rows += f'''<tr><td style='font-weight:bold'>{cn}</td><td>{t}天</td><td>{bar_full}{bar_empty}</td><td style='font-weight:bold;color:#e74c3c'>{wr_pct:.1f}%</td><td>{w}/{t}</td></tr>'''
        total_pct = total_w*100/total_t if total_t else 0
        # 更新静态胜率文字为动态数据
        static_30d_text = f'{total_w}/{total_t} = {total_pct:.1f}%'
    bar_full = '█' * int(total_pct/5)
    bar_empty = '░' * (20 - len(bar_full))
    mkt_rows += f'''<tr style='font-weight:bold;background:#f5f6fa'><td>总计</td><td>{total_t}天</td><td>{bar_full}{bar_empty}</td><td style='color:#e74c3c'>{total_pct:.1f}%</td><td>{total_w}/{total_t}</td></tr>'''
    
    # 冠亚季军胜率
    champ_w = sum(1 for r in top3_results if r['nh']>=2.5)
    second_w = sum(1 for r in top3_results if r['s_nh']>=2.5)
    third_w = sum(1 for r in top3_results if r['t_nh']>=2.5)
    top3_any = sum(1 for r in top3_results if r['nh']>=2.5 or r['s_nh']>=2.5 or r['t_nh']>=2.5)
    n = len(top3_results)
    
    rank_rows = f'''
<tr><td style="font-size:18px">🥇 冠军</td><td style="color:#e74c3c;font-weight:bold;font-size:16px">{champ_w*100//n}%</td><td>{champ_w}/{n}</td><td>评分第1名，主力推荐</td></tr>
<tr><td style="font-size:18px">🥈 亚军</td><td style="color:#b8860b;font-weight:bold;font-size:16px">{second_w*100//n}%</td><td>{second_w}/{n}</td><td>冠军太贵时的备选</td></tr>
<tr><td style="font-size:18px">🥉 季军</td><td style="color:#b8860b;font-weight:bold;font-size:16px">{third_w*100//n}%</td><td>{third_w}/{n}</td><td>第三备选</td></tr>
<tr style="background:#f5f6fa;font-weight:bold"><td>🎯 Top3任一达标</td><td style="color:#e74c3c;font-size:16px">{top3_any*100//n}%</td><td>{top3_any}/{n}</td><td>三只票买任意一只，{n}天中{top3_any}天有票达标</td></tr>'''
    
    # 逐日战绩
    daily_table = ''
    for r in reversed(top3_results):
        pct_c = '#e74c3c' if r['p']>=0 else '#27ae60'
        # 无下一日数据时显示待确认
        if r['nh'] == 0 and r['dt'] >= last_cache_date:
            nh_display = '<span style="color:#95a5a6">待确认</span>'
            nh_result = chr(9203)  # ⏳
        else:
            nh_c = '#e74c3c' if r['nh']>=2.5 else '#27ae60'
            nh_display = '<span style="color:{};font-weight:bold">{:+.1f}%</span>'.format(nh_c, r['nh'])
            nh_result = r['result']
        daily_table += '<tr><td>{}</td><td>{}</td><td style="font-weight:bold">{}</td><td>{}</td><td style="color:{};font-weight:bold">{:+.1f}%</td><td>{}</td><td style="font-weight:bold">{:.0f}</td><td>{:.0f}</td><td>{:.2f}</td><td>{:.1f}</td><td>{:.0f}</td><td>{:.2f}</td><td>{}</td></tr>'.format(
            r['dt'][5:], r['mk'], r['c_name'], r['c_code'], pct_c, r['p'],
            nh_display, r['score'], r['cl'], r['vr'], r['hsl'], r['wr'], r['dif'], nh_result)
    
    # 价格提示
    price_tip = ''
    if top10_result and top10_result[0][1]['price'] > 100:
        s2 = top10_result[1][1] if len(top10_result) > 1 else None
        if s2:
            price_tip = f'💡 冠军{top10_result[0][1]["name"]}¥{top10_result[0][1]["price"]:.2f}价格偏高，预算有限可考虑亚军{s2["name"]}¥{s2["price"]:.2f}'
    
    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>V13每日选股报告 {today_str}</title>
<style>
body{{margin:0;padding:15px;background:#ffffff;font-family:-apple-system,'微软雅黑','PingFang SC',sans-serif;color:#2c3e50;font-size:13px;line-height:1.5}}
h2{{color:#b8860b;border-bottom:2px solid #b8860b;padding-bottom:5px;margin:20px 0 10px}}
h3{{color:#2c3e50;margin:15px 0 8px}}
table{{width:100%;border-collapse:collapse;margin:10px 0;font-size:12px}}
th{{background:#f0f0f0;padding:5px 3px;text-align:center;border-bottom:2px solid #dfe6e9;font-size:11px;position:sticky;top:0}}
td{{padding:3px 2px;text-align:center;border-bottom:1px solid #f0f0f0}}
.card{{background:#f5f6fa;border-radius:8px;padding:12px;margin:10px 0}}
.footer{{text-align:center;font-size:11px;color:#95a5a6;margin:15px 0}}
.scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:8px 0}}
.scroll table{{min-width:920px}}
</style></head><body>

<div style="font-size:22px;font-weight:bold;color:#b8860b;text-align:center;margin:10px 0;background:linear-gradient(135deg,#fff8e1,#ffecb3);padding:12px;border-radius:8px;border-bottom:3px solid #b8860b">
  {ver_id} 分而治之 · 每日选股报告 (近{p250_ta}天{p250_wi*100//p250_ta}%版 ｜ 14:50真实买点)
</div>

<div style="font-size:12px;color:#95a5a6;text-align:center;margin-bottom:8px">
  📅 {today_str} | 📡 数据: {data_date_str} | 🎯 建议买入: {buy_date_str} 尾盘 | 📌 {mk_cn} | 🔰 {level}
</div>

<div style="background:#f5f6fa;border-radius:8px;padding:12px;margin:12px 0">
  <div style="font-size:16px;font-weight:bold;color:#b8860b;margin-bottom:8px">今日推荐 {today_str} | {mk_cn} | {level}级</div>
  <div style="display:grid;grid-template-columns:1fr;gap:8px">
{top3_cards}
  </div>
</div>

<div class="card">
<h3>📋 V13 版本档案</h3>
<table><thead><tr><th>指标</th><th>数据</th></tr></thead><tbody>
<tr><td>30天胜率</td><td><b>{wi*100//ta}%</b> ({wi}/{ta}) 动态回测 ✅</td></tr>
<tr><td>50天胜率</td><td>{v50d} (数据库)</td></tr>
<tr><td>100天胜率</td><td>{v100d} (数据库)</td></tr>
<tr><td>核心武器</td><td>动量衰竭6规则 + 7天衰减扣分 + WR超买惩罚</td></tr>
<tr><td>最强行情</td><td>真实涨日 ~79%</td></tr>
<tr><td>短板行情</td><td>横盘 ~56% | 虚涨日 ~20%</td></tr>
<tr><td>选它理由</td><td>🔥 经典动量过滤体系，30天爆发力最强，经验证最可靠</td></tr>
</tbody></table>
</div>

<div class="card">
<h3>📊 近30天总战绩</h3>
  <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin:8px 0">
  <table style="min-width:500px"><thead><tr><th>行情</th><th>天数</th><th>胜率条</th><th>胜率</th><th>胜/负</th></tr></thead><tbody>
{mkt_rows}
</tbody></table></div>
<div style="font-size:11px;color:#95a5a6;margin-top:5px">
✅ 目标：次日最高涨幅≥2.5% | 最新30天 {wi}/{ta} = {wi*100//ta}%
</div>
</div>

<div class="card" style="border-left:4px solid #b8860b;border-top:2px solid #b8860b">
<div class="card" style="border-left:4px solid #b8860b;border-top:2px solid #b8860b">
<h3>📊 按时间段区分回测结果</h3>
<p style="font-size:12px;color:#2c3e50;background:#f8f8f8;padding:6px 8px;border-radius:4px">
<b>近{ta}天</b> ｜ 
📊 <b>15:00收盘回测</b> 胜率 <span style="color:#e74c3c;font-weight:bold;font-size:15px">{close_pct:.1f}%</span> ({wi}/{ta}) ｜ 
🕐 <b>14:50尾盘回测</b>（真实买点）胜率 <span style="color:#e74c3c;font-weight:bold;font-size:15px">{p250_pct:.1f}%</span> ({p250_wi}/{p250_ta}) ｜ 
🏆 一致率 {match_pct:.0f}%
</p>
<div class="scroll">
<table style="min-width:1000px"><thead><tr>
<th rowspan="2">日期</th><th rowspan="2">行情</th>
<th colspan="3" style="background:#fff8e1;border-bottom:2px solid #b8860b">📊 15:00收盘</th>
<th colspan="3" style="background:#f0f8ff;border-bottom:2px solid #4a90d9">🕐 14:50尾盘</th>
</tr><tr>
<th style="background:#fff8e1">冠军</th><th style="background:#fff8e1">当日%</th><th style="background:#fff8e1">次日高</th>
<th style="background:#f0f8ff">冠军</th><th style="background:#f0f8ff">当日%</th><th style="background:#f0f8ff">次日高</th>
</tr></thead><tbody>
{compare_rows}
</tbody></table>
</div>
<p style="font-size:11px;color:#95a5a6;margin-top:4px">
✅ 一致=同时段选出同一只股 ｜ ❌ 不一致=两个时点选了不同的股 ｜ 价差=同一只股14:50%-收盘%
</p>
</div>

<div class="card">
<h3>🏆 冠亚季军历史胜率（{n}天）</h3>
<table><thead><tr><th>排名</th><th>胜率</th><th>天数</th><th>说明</th></tr></thead><tbody>
{rank_rows}
</tbody></table>
{price_tip}
</div>

<div class="card">
<h3>📜 近{n}天逐日战绩</h3>
<div class="scroll">
<table><thead><tr>
<th>日期</th><th>行情</th><th>冠军</th><th>编码</th><th>当日%</th><th>次日最高%</th><th>评分</th><th>CL</th><th>量比</th><th>换手%</th><th>WR</th><th>DIF</th><th>结果</th>
</tr></thead><tbody>
{daily_table}
</tbody></table>
</div>
</div>

<div class="card">
<h3>⚙️ 分析流程 (V13)</h3>
<pre style="font-size:11px;background:#f8f8f8;padding:8px;border-radius:4px;white-space:pre-wrap">
1. 腾讯实时API → 全市场3043只实时行情（含HSL换手率/PE/市值）
2. K线API → MACD/KDJ/WR/CL等技术指标计算
3. 行情分类（均价涨幅>0.5%→真实涨日/虚涨日，<-0.5%→跌日，其余→横盘）
4. L0→L4分级筛选（硬门槛逐级放宽至≥10只候选池）
5. <b>V13评分</b> — 各行情独立封顶打分 + 动量衰竭6规则预过滤 + 7天衰减扣分 + WR超买惩罚
6. 淡色HTML输出 → 存档 + 邮件3人 + 微信推送</pre>
</pre>
</div>

<div class="card">
<h3>📋 V13 vs V42 对比</h3>
<table><thead><tr><th>指标</th><th>V13</th><th>V42</th></tr></thead><tbody>
<tr><td>最新30天胜率</td><td style="color:#e74c3c;font-weight:bold">{wi*100//ta}% ({wi}/{ta})</td><td style="color:#e74c3c;font-weight:bold">93.3% (28/30)</td></tr>
<tr><td>50天胜率</td><td>68% (回测)</td><td><b>82%</b> 🏆 (回测)</td></tr>
<tr><td>100天胜率</td><td>61% (回测)</td><td><b>77%</b> 🏆 (回测)</td></tr>
<tr><td>核心武器</td><td>动量衰竭6规则+7天衰减扣分</td><td>横盘CL<88混合评分+冲顶惩罚+HSL否决</td></tr>
<tr><td>最强行情</td><td>真实涨日~79%</td><td>虚涨日100% 🏆 横盘78% 🏆 跌日78% 🏆</td></tr>
<tr><td>短板行情</td><td>横盘~56% 虚涨日~20%</td><td>真实涨日~72%</td></tr>
</tbody></table>
</div>

<div class="footer">
V13 分而治之 | 30天 {wi}/{ta} = {wi*100//ta}% | 全年69.2%
<p style="font-size:14px;color:#b8860b;font-weight:bold;margin-top:12px">
  🤝 {wi}/{ta} = {wi*100//ta}%，继续优化全年胜率！
</p>
</div>

</body></html>'''
    return html

# ===== 主流程 =====
if __name__ == '__main__':
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    
    # 确定数据日期
    if now.hour < 9:
        data_date = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        while datetime.strptime(data_date,'%Y-%m-%d').weekday()>=5:
            data_date = (datetime.strptime(data_date,'%Y-%m-%d')-timedelta(days=1)).strftime('%Y-%m-%d')
        data_label = '昨日收盘'
    elif now.hour < 15:
        data_date = today_str
        data_label = f'盘中{now.hour}:{now.minute:02d}'
    else:
        data_date = today_str
        data_label = '今日收盘'
    
    buy_date = today_str
    if now.hour >= 15:
        buy_date = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        while datetime.strptime(buy_date,'%Y-%m-%d').weekday()>=5:
            buy_date = (datetime.strptime(buy_date,'%Y-%m-%d')+timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f'🚀 V13 每日选股报告 | {today_str}', flush=True)
    print(f'📡 数据来源: {data_label} ({data_date})', flush=True)
    print(f'🎯 建议买入: {buy_date} 尾盘', flush=True)
    
    # 1. 实时选今天（返回: scored[:10], mk_cn, used_level, stocks, indicators）
    top10_raw = pick_today()
    top10 = top10_raw[:3] if top10_raw else None  # 保持向后兼容
    
    # 2. 保存当天实时数据到data_cache（统一数据源）
    if top10_raw:
        stocks = top10_raw[3]
        indicators = top10_raw[4]
        try:
            from selection_log_db import save_realtime_to_datacache
            save_realtime_to_datacache(today_str, stocks, indicators, 'tencent:1448-v13')
        except Exception as e:
            print(f'⚠️ data_cache写入失败: {e}', flush=True)
    
    # 3. 缓存回测30天
    bt = backtest_30d()
    
    if top10 and bt:
        html = build_html(top10[0], bt, today_str, f'{data_label}({data_date})', buy_date, top10[1], top10[2])
        
        # 存档
        arch = os.path.join(SCRIPTS_DIR, 'email_archive')
        os.makedirs(arch, exist_ok=True)
        fp = os.path.join(arch, f'{today_str}_V13_报告.html')
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'📁 已存档: {fp}', flush=True)
        
        # 发邮件
        try:
            sender = os.path.join(SCRIPTS_DIR, 'send_email.py')
            email_to = '1254628314@qq.com,314913203@qq.com,2603672569@qq.com'
            subj = f'V13每日选股 {today_str} - {top10[1]} - 冠军{top10[0][0][1]["name"]}[{top10[0][0][1]["price"]:.2f}]'
            r = subprocess.run([sys.executable, sender, subj, html, '--html'], timeout=60, capture_output=True, text=True)
            print(f'📧 {r.stdout.strip()}', flush=True)
        except Exception as e:
            print(f'❌ 邮件失败: {e}', flush=True)
        
        # 发邮件B（潘永俊）
        try:
            subj_b = f'V13每日选股 {today_str} - {top10[1]} - 冠军{top10[0][0][1]["name"]}[{top10[0][0][1]["price"]:.2f}]'
            r = subprocess.run([sys.executable, sender, subj_b, html, '--html', '--config', 'B'], timeout=60, capture_output=True, text=True)
            print(f'📧B {r.stdout.strip()}', flush=True)
        except Exception as e:
            print(f'⚠️ B邮件失败: {e}', flush=True)
        
        # 写入数据库日志
        try:
            log_selection_to_db('V13', today_str, top10[1], top10[2], len(top10[0]), top10[0])
        except Exception as e:
            print(f'⚠️ 数据库日志写入失败: {e}', flush=True)
        
        # 输出摘要到stdout
        print(f'\n=== V13 选股摘要 ===')
        print(f'今日推荐 ({top10[1]} {top10[2]}级):')
        for rank, (sc, s, ind, code) in enumerate(top10[0][:3], 1):
            print(f'  {rank}. {s["name"]}({code}) ¥{s["price"]:.2f} 当日{s["p"]:+.1f}% 评分{sc:.0f}')
        close_res, p250_res, total_days = bt
        c_wi, c_ta = close_res[0], close_res[1]
        p_wi, p_ta = p250_res[0], p250_res[1]
        print(f'📊 收盘回测: {c_wi}/{c_ta} = {c_wi*100/c_ta:.1f}%')
        print(f'🕐 14:50回测: {p_wi}/{p_ta} = {p_wi*100/p_ta:.1f}%')
    else:
        print('❌ 选股失败')
