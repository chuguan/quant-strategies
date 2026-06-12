#!/usr/bin/env python3
"""V51 每日选股报告 — 实时API + V10同款淡色模板"""

import sys, os, json, re, time, subprocess
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/prod')
sys.path.insert(0, os.path.join(SCRIPTS_DIR, 'lib'))
sys.path.insert(0, SCRIPTS_DIR)

from selection_log_db import log_selection_to_db
from risk_tags import get_risk_tags, risk_tags_html
from v51_analysis import analyze_stock

# SCRIPTS_DIR already set above
V51_DIR = os.path.join(SCRIPTS_DIR, 'strategies', 'V50')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
sys.path.insert(0, V51_DIR); sys.path.insert(0, SCRIPTS_DIR)

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

# ===== 加载V51策略模块 =====
import importlib
STRATS = {}
for n in ['真实涨日','虚涨日','跌日','横盘']:
    fp = os.path.join(V51_DIR, '评分策略', f'分而治之_V10_{n}_评分策略.py')
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

# ===== 个股新闻获取（东方财富API）=====
import urllib.parse

def curl_get_utf8(url, timeout=10):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url],capture_output=True,timeout=timeout+5)
        return r.stdout.decode('utf-8',errors='replace')
    except: return ''

POS_KEYWORDS = ['涨停','大涨','拉升','走强','中标','合同','增持','回购','分红','新高','增长','突破','放量','受益','利好','绩优','盈利','订单','投产','扩张','合作','主力','景气','政策','利润']
NEG_KEYWORDS = ['跌停','大跌','减持','立案','亏损','下跌','风险','利空','下调','索赔','处罚','监管','降级','跌超','走低','回调','出货','警告','警示','st','st']

def fetch_stock_news(name, max_items=5):
    enc = urllib.parse.quote(name)
    url = f'https://search-api-web.eastmoney.com/search/jsonp?cb=jQuery&param=%7B%22uid%22%3A%22%22%2C%22keyword%22%3A%22{enc}%22%2C%22type%22%3A%5B%22cmsArticleWebOld%22%5D%2C%22client%22%3A%22web%22%2C%22clientVersion%22%3A%22curr%22%2C%22param%22%3A%7B%22cmsArticleWebOld%22%3A%7B%22searchScope%22%3A%22default%22%2C%22sort%22%3A%22default%22%2C%22pageIndex%22%3A1%2C%22pageSize%22%3A{max_items}%2C%22preTag%22%3A%22%22%2C%22postTag%22%3A%22%22%7D%7D%7D'
    try:
        text = curl_get_utf8(url, timeout=5)
        text = text.strip().lstrip('\ufeff')
        if text.startswith('jQuery(') and text.endswith(')'):
            text = text[7:-1]
        data = json.loads(text)
        return data.get('result', {}).get('cmsArticleWebOld', [])
    except:
        return []

def fetch_stock_ann(code, max_items=5):
    url = f'https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size={max_items}&page_index=1&ann_type=A&stock_list={code}&f_node=0&s_node=0'
    try:
        text = curl_get_utf8(url, timeout=5)
        data = json.loads(text)
        items = data.get('data', {}).get('list', [])
        skip_keywords = ['管理办法','制度','议事规则','委员会','任命','聘任','秘书']
        filtered = [a for a in items if not any(k in a.get('title','') for k in skip_keywords)]
        for a in filtered:
            a['date'] = a.get('notice_date', '')[:10]
            a['content'] = a.get('title', '')
            a['mediaName'] = '公告'
        return filtered[:max_items] if filtered else []
    except:
        return []

def tag_news_sentiment(articles):
    pos, neg = [], []
    for a in articles:
        t = a.get('title','') + a.get('content','')
        ps = sum(1 for kw in POS_KEYWORDS if kw in t)
        ns = sum(1 for kw in NEG_KEYWORDS if kw in t)
        if ps > ns: pos.append(a)
        elif ns > ps: neg.append(a)
    return pos, neg

# ===== 实时行情拉取 =====
def get_live_stocks():
    t0 = time.time()
    now_hour = datetime.now().hour
    # 预加载data_cache的vr（用上交易日vr，避开API虚假量比）
    cache_vr = {}
    try:
        import sqlite3 as _sq3
        _db = _sq3.connect(os.path.join(SCRIPTS_DIR, 'v13_quant.db'), timeout=5)
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
            _cur = _db.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 AND date<? ORDER BY date DESC LIMIT 1', (datetime.now().strftime('%Y-%m-%d'),))
            _r = _cur.fetchone()
            if _r:
                _dt = _r[0]
                _cur2 = _db.execute('SELECT code, name, p, cl, wr_val, dif_val, vr, close, volume FROM data_cache WHERE date=? AND close>0', (_dt,))
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
                        'vol_ratio': r[6] or 1, 'vol': r[8] or 0,
                        'cl': r[3] or 50, 'wr_val': r[4] or 50, 'dif_val': r[5] or 0,
                        'hsl': _hsl.get(code, 0), 'pe': 0, 'sz': 0
                    }
                print(f'📡 开盘前，从data_cache加载: {len(active)}只 ({_dt})', flush=True)
            _db.close()
        except Exception as e:
            print(f'⚠️  data_cache加载失败: {e}', flush=True)
        if active:
            return active
    
    # ═══ 统一缓存快照（pre_warm_unified）═══
    _snap_path = os.path.normpath(os.path.join(CACHE_DIR, '..', 'unified_snapshot.json'))
    if os.path.exists(_snap_path) and time.time() - os.path.getmtime(_snap_path) < 300:
        try:
            _snap = json.load(open(_snap_path, encoding='utf-8'))
            _stocks = _snap.get('stocks', {})
            if len(_stocks) > 2000:
                for _code, _s in _stocks.items():
                    _s['vol_ratio'] = cache_vr.get(_code, _s.get('vol_ratio', 0))
                print(f'📦 统一缓存快照: {len(_stocks)}只 (ts={_snap.get("time","?")})', flush=True)
                return _stocks
        except Exception as e:
            print(f'⚠️ 统一缓存快照读取失败: {e}', flush=True)
    
    codes = [str(i) for i in range(600000, 606000)] + [f'{i:06d}' for i in range(3000)]
    active = {}
    
    def _fetch_chunk(chunk):
        """并发拉取一个chunk的数据，10s超时"""
        symbols = [f'{PREFIX(c)}{c}' for c in chunk]
        text = curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}', timeout=10)
        chunk_data = {}
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
                vol_r = cache_vr.get(code, float(parts[38])) if parts[38] else 0
                hsl = 0
                try: hsl = float(parts[46]) if parts[46] and float(parts[46])<100 else 0
                except: pass
                pe = float(parts[39]) if parts[39] else 0
                sz = 0
                try: sz = float(parts[44])/1e8 if parts[44] else 0
                except: pass
                chunk_data[code] = {'name':nm,'price':price,'p':pct,'vol_ratio':vol_r,'hsl':hsl,'pe':pe,'sz':sz}
            except:
                pass
        return chunk_data
    
    # 将codes分成chunk，每个chunk 80只，用线程池并发拉取
    chunks = [codes[i:i+80] for i in range(0, len(codes), 80)]
    print(f'📡 并发拉取 {len(codes)}只 ({len(chunks)}个chunk)...', flush=True)
    with ThreadPoolExecutor(max_workers=12) as _ex:
        _futs = {_ex.submit(_fetch_chunk, ch): i for i, ch in enumerate(chunks)}
        for _f in as_completed(_futs):
            try:
                _data = _f.result(timeout=15)
                active.update(_data)
            except:
                _chunk_idx = _futs[_f]
                print(f'  ⏱️ chunk{_chunk_idx}超时跳过', flush=True)
    print(f'📡 实时: {len(active)}只 ({time.time()-t0:.1f}s)', flush=True)
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
    # V51需要：ma5_slope = 5日均线斜率
    ma5_slope = 0
    if n >= 10:
        ma5_today = sum(close[-5:]) / 5
        ma5_yday = sum(close[-6:-1]) / 5
        ma5_slope = (ma5_today - ma5_yday) / ma5_yday * 100 if ma5_yday > 0 else 0
    return {'dif':round(dif,3),'macd_golden':mg,'k_val':round(k_val,1),'d_val':round(d_val,1),
            'j_val':round(j_val,1),'kdj_golden':kdj_g,'wr':round(wr,1),'cl':round(cl,1),
            'ma5_slope':round(ma5_slope,2)}

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
    print('🚀 V51 实时选股...', flush=True)
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
        print(f'  🔍 开始分级过滤...', flush=True)
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
            # 停牌检查：p=0且成交量≤股价（volume被填充为price）= 无真实交易
            if p == 0 and s.get('vol', 0) <= s.get('price', 0): continue
            cl_v = ind['cl']
            if cl_v < lv.get('cl_min',0) or cl_v > lv.get('cl_max',100): continue
            if not check_momentum(code, ind, s): continue
            cand.append((code,s,ind))
        if len(cand) >= 10:
            pool = cand; used_level = ln; break
    
    if not pool:
        print('❌ 候选池不足')
        return None
    

    # 评分 + 失败案例警告
    scored = []
    for code, s, ind in pool:
        stock = {
            'p': s['p'], 'cl': ind['cl'], 'vr': s['vol_ratio'],
            'dif': ind['dif'], 'mg': ind['macd_golden'],
            'wrv': ind['wr'], 'jv': ind['j_val'], 'kv': ind['k_val'], 'dv': ind['d_val'],
            'a5': 1, 'kdj_g': ind['kdj_golden'], 'pos_in_day': 50,
            'nm': s['name'], 'hsl': s['hsl'],
            'ma5_slope': ind.get('ma5_slope', 0),
            't4_shadow': 0, 'slope5': 0, 'cons_up': 0,
            'd1': 0, 'd2': 0, 'd3': 0,
            'close': s.get('close', 0) or s.get('price', 0) or 0,
        }
        sc = mod.score(stock)
        # ═══ V51 失败案例警告标签 ═══
        warnings = []
        cp = stock['close']
        wr = stock['wrv']
        pv = stock['p']
        cl = stock['cl']
        vr = stock['vr']
        # ① 合锻智能模式：超买+放量
        if wr < 10 and vr > 1.8:
            warnings.append('合锻智能6/5(-8.5%): WR超买+VR异常放量')
        # ② 江顺科技模式：高价+大涨
        if cp > 80 and pv > 5 and mk_cn == '跌日':
            warnings.append('江顺科技6/8(-7.8%): 跌日高价大涨')
        # ③ 鹏鼎控股模式：高价+高位
        if cp > 80 and cl > 70 and mk_cn == '跌日':
            warnings.append('鹏鼎控股6/9(-4.4%): 跌日高位高价')
        # ④ 松发股份模式：超高价
        if cp > 150:
            warnings.append('松发股份6/10(待验证): 超高价¥150+')
        # ⑤ 放量不涨：VR>2且p<2
        if vr > 2.0 and 0 < pv < 2:
            warnings.append('放量不涨: VR>2但涨幅<2%，主力出货风险')
        
        scored.append((sc, warnings, s, ind, code))
    scored.sort(key=lambda x:-x[0])
    return scored[:10], mk_cn, used_level, stocks, indicators


# ===== 历史回测（V51用自己big_cache_full.pkl，含ma5_slope） =====
def backtest_30d():
    """从共享big_cache_full.pkl跑回测（含ma5_slope等全字段）"""
    import pickle
    pkl = os.path.join(SCRIPTS_DIR, 'big_cache_full.pkl')
    if not os.path.exists(pkl):
        print(f'⚠️ big_cache_full.pkl不存在: {pkl}')
        # fallback: 用data_cache简单回测
        return _backtest_data_cache_fallback()
    try:
        with open(pkl, 'rb') as f:
            d = pickle.load(f)
    except:
        return _backtest_data_cache_fallback()
    bdata, real, names = d['data'], d['real'], d['names']
    all_dates = sorted(k for k in bdata.keys())
    # 取足够多的天数来确保n填充率≥50%的日有30天
    n_valid_needed = 30
    recent_raw = all_dates[-50:]  # 从最近50天中筛选
    # 过滤掉n填充率不足的日期
    valid_dates = []
    for dt in reversed(recent_raw):
        ss_count = len([s for s in bdata.get(dt, []) if (s.get('p',0) or 0) < 15])
        if ss_count < 20: continue
        n_filled = sum(1 for s in bdata.get(dt, []) if (s.get('n',0) or 0) != 0 and (s.get('p',0) or 0) < 15)
        if n_filled < ss_count * 0.5: continue
        valid_dates.append(dt)
        if len(valid_dates) >= n_valid_needed: break
    valid_dates.reverse()
    if len(valid_dates) < 10:
        # fallback: 直接用最后30天
        valid_dates = all_dates[-30:]
    
    recent = valid_dates
    
    MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
    LO_loc = ['L0','L1','L2','L3','L4']
    
    def mkt_cn(ss):
        ps = [s.get('p',0) or 0 for s in ss if abs(s.get('p',0) or 0) < 15]
        vrs = [s.get('vol_ratio',0) or 0 for s in ss if s.get('vol_ratio',0)]
        ap = sum(ps)/len(ps) if ps else 0
        av = sum(vrs)/len(vrs) if vrs else 0
        hot = sum(1 for p in ps if 5<=p<=8)
        if ap > 0.5: return '虚假涨日' if hot < 15 or av < 0.9 else '真实涨日'
        if ap < -0.5: return '跌日'
        return '横盘'
    
    wi = 0; ta = 0
    mk_s = {'真实涨日':[0,0],'虚涨日':[0,0],'跌日':[0,0],'横盘':[0,0]}
    top3 = []
    for dt in recent:
        ss = [s for s in bdata.get(dt, []) if (s.get('p',0) or 0) < 15]
        if len(ss) < 20: continue
        # 跳过n填充率不足50%的日期（最后1-2天数据不完整）
        n_filled = sum(1 for s in ss if (s.get('n',0) or 0) != 0)
        if n_filled < len(ss) * 0.5:
            continue
        mk = None
        ps_mk = [s.get('p',0) or 0 for s in ss if abs(s.get('p',0) or 0) < 15]
        vrs_mk = [s.get('vol_ratio',0) or 0 for s in ss if s.get('vol_ratio',0)]
        ap_mk = sum(ps_mk)/len(ps_mk) if ps_mk else 0
        av_mk = sum(vrs_mk)/len(vrs_mk) if vrs_mk else 0
        hot_mk = sum(1 for p in ps_mk if 5<=p<=8)
        if ap_mk > 0.5: mk = '虚涨日' if hot_mk < 15 or av_mk < 0.9 else '真实涨日'
        elif ap_mk < -0.5: mk = '跌日'
        else: mk = '横盘'
        
        mod = STRATS.get(mk)
        if not mod: continue
        levels = getattr(mod, 'LEVELS', None)
        if not levels: continue
        lm_loc = {l['name']:i for i,l in enumerate(levels)}
        pool = None
        for ln in LO_loc:
            if ln not in lm_loc: continue
            lv = levels[lm_loc[ln]]
            cand = []
            for s in ss:
                p = s.get('p',0) or 0
                if p < lv['p_min'] or p > min(lv.get('p_max',10),8): continue
                vr = s.get('vol_ratio',1) or 1
                if vr < lv['vr_min'] or vr > lv['vr_max']: continue
                hsl = real.get(s['code'],{}).get('hsl',0) or 0
                if hsl < lv.get('hs_min',0) or hsl > lv.get('hs_max',99): continue
                cl = s.get('cl',50)
                if cl < lv.get('cl_min',0) or cl > lv.get('cl_max',100): continue
                cand.append(s)
            if len(cand) >= 10: pool = cand; break
        if not pool: continue
        
        scored = []
        for s in pool:
            stock = {
                'p': s.get('p',0) or 0, 'cl': s.get('cl',50),
                'vr': s.get('vol_ratio',1) or s.get('vr',1),
                'dif': s.get('dif_val',0) or s.get('dif',0),
                'mg': s.get('macd_golden',0) or s.get('mg',0),
                'wrv': s.get('wr_val',0) or s.get('wrv',50),
                'jv': s.get('j_val',0) or s.get('jv',50),
                'kv': s.get('k_val',0) or s.get('kv',50),
                'dv': s.get('d_val',0) or s.get('dv',50),
                'a5': s.get('above_ma5',0),
                'kdj_g': s.get('kdj_golden',0) or s.get('kdj_g',0),
                'pos_in_day': s.get('pos_in_day',50),
                'nm': names.get(s['code'],''),
                'hsl': real.get(s['code'],{}).get('hsl',0) or 0,
                'buy_c': s.get('close',0) or 0,
                'ma5_slope': s.get('ma5_slope',0) or 0,
                't4_shadow': s.get('t4_shadow',0) or 0,
                'slope5': s.get('slope5',0) or 0,
                'cons_up': s.get('cons_up',0) or 0,
                'peak_decay': s.get('peak_decay',0) or 0,
                'amplitude': s.get('amplitude',0) or 0,
                'body_pct': s.get('body_pct',0) or 0,
                'above_ma10': s.get('above_ma10',0) or 0,
                'above_ma20': s.get('above_ma20',0) or 0,
                'd1': s.get('d1',0) or 0, 'd2': s.get('d2',0) or 0, 'd3': s.get('d3',0) or 0,
            }
            sc = mod.score(stock)
            scored.append((sc, s))
        scored.sort(key=lambda x: -x[0])
        champ = scored[0][1]
        nh = champ.get('n', 0) or 0
        ta += 1
        if nh >= 2.5: wi += 1; mk_s[mk][0] += 1
        mk_s[mk][1] += 1
        result = '✅' if nh >= 2.5 else '❌'
        cname = names.get(champ['code'], str(champ.get('code','')))
        top3.append({'dt':dt,'mk':mk,'c_name':cname,'c_code':champ.get('code',''),'p':champ.get('p',0) or 0,'nh':nh,'score':scored[0][0],'result':result})
    rows = [f'{"✅" if r["nh"]>=2.5 else "❌"} {r["dt"]} {r["mk"]:>5} {r["c_name"]:>8} nh={r["nh"]:+.1f}%' for r in top3]
    return wi, ta, mk_s, rows, top3, recent[-1] if recent else ''

def _backtest_data_cache_fallback():
    """fallback: 从data_cache简单回测（不含ma5_slope）"""
    import sqlite3
    DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')
    c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
    all_dates = [r[0] for r in c.fetchall() if r[0] != today_str]
    conn.close()
    recent = all_dates[-30:]
    if not recent: return None

    # 从big_cache_full.pkl覆盖n值（次日最高涨幅自动刷新）
    PKL = os.path.join(SCRIPTS_DIR, 'big_cache_full.pkl')
    big_n = {}
    if os.path.exists(PKL):
        try:
            import pickle
            big = pickle.load(open(PKL, 'rb'))
            for dt in recent:
                big_d = big['data'].get(dt, [])
                big_n[dt] = {s['code']: (s.get('n', 0) or 0) for s in big_d}
        except:
            pass

    wi = 0; ta = 0; mk_s = {'真实涨日':[0,0],'虚假涨日':[0,0],'跌日':[0,0],'横盘':[0,0]}
    top3 = []
    for dt in recent:
        import sqlite3
        conn2 = sqlite3.connect(DB_PATH, timeout=10)
        c2 = conn2.cursor()
        c2.execute('SELECT code, close, p, vr, cl, wr_val, dif_val, n, k_val, d_val, j_val, kdj_golden, above_ma5, pos_in_day FROM data_cache WHERE date=? AND close>0', (dt,))
        ss = [dict(zip(['code','close','p','vr','cl','wr_val','dif_val','n','k_val','d_val','j_val','kdj_golden','above_ma5','pos_in_day'], r)) for r in c2.fetchall()]
        conn2.close()
        ss = [s for s in ss if (s.get('p',0) or 0) < 8]
        if len(ss) < 20: continue
        
        ps = [s.get('p',0) or 0 for s in ss if abs(s.get('p',0) or 0) < 15]
        ap = sum(ps)/len(ps) if ps else 0
        if ap > 0.5: mk = '虚假涨日'
        elif ap < -0.5: mk = '跌日'
        else: mk = '横盘'
        
        mod = STRATS.get(mk)
        if not mod: continue
        levels = getattr(mod, 'LEVELS', None)
        if not levels: continue
        lm = {l['name']:i for i,l in enumerate(levels)}
        pool = None
        for ln in ['L0','L1','L2','L3','L4']:
            if ln not in lm: continue
            lv = levels[lm[ln]]
            cand = [s for s in ss if (s.get('p',0) or 0) >= lv['p_min'] and (s.get('p',0) or 0) <= min(lv.get('p_max',10),8)
                    and (s.get('vr',1) or 1) >= lv['vr_min'] and (s.get('vr',1) or 1) <= lv['vr_max']
                    and (s.get('cl',50)) >= lv.get('cl_min',0) and (s.get('cl',50)) <= lv.get('cl_max',100)]
            if len(cand) >= 10: pool = cand; break
        if not pool: continue
        
        scored = []
        for s in pool:
            stock = {'p':s.get('p',0),'cl':s.get('cl',50),'vr':s.get('vr',1) or 1,
                     'dif':s.get('dif_val',0) or 0,'mg':1 if (s.get('dif_val',0) or 0)>0 else 0,
                     'wrv':s.get('wr_val',50),'kv':s.get('k_val',50),'dv':s.get('d_val',50),
                     'jv':s.get('j_val',50),'a5':s.get('above_ma5',0) or 0,'kdj_g':s.get('kdj_golden',0) or 0,
                     'pos_in_day':s.get('pos_in_day',50) or 50,'nm':s.get('code',''),'hsl':0,
                     'ma5_slope':0,'t4_shadow':0,'slope5':0,'cons_up':0,'d1':0,'d2':0,'d3':0,
                     'close':s.get('close',0) or 0}
            scored.append((mod.score(stock), s))
        scored.sort(key=lambda x: -x[0])
        champ = scored[0][1]
        # 从big_cache_full.pkl覆盖n值
        _bc_n = big_n.get(dt, {}).get(champ.get('code', ''), 0)
        if _bc_n:
            nh = _bc_n
        else:
            nh = champ.get('n', 0) or 0
        ta += 1
        if nh >= 2.5: wi += 1; mk_s[mk][0] += 1
        mk_s[mk][1] += 1
        result = '✅' if nh >= 2.5 else '❌'
        top3.append({'dt':dt,'mk':mk,'c_name':str(champ.get('code','')),'c_code':champ.get('code',''),'nh':nh,'score':scored[0][0],'result':result})
    rows = [f'{"✅" if r["nh"]>=2.5 else "❌"} {r["dt"]} {r["mk"]:>5} {r["c_name"]:>8} nh={r["nh"]:+.1f}%' for r in top3]
    return wi, ta, mk_s, rows, top3, recent[-1] if recent else ''

# ===== 放量下跌一票否决 =====
# 使用SQLite data_cache表（比加载big_cache快100倍）
_FLCACHE = {}  # 轻量缓存: {code: {date: (pct, vol_ratio)}}
def _load_fangliang_data(codes):
    """只查指定股票的最近2天数据，极快"""
    global _FLCACHE
    if _FLCACHE:
        return
    try:
        import sqlite3
        _db_path = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
        if not os.path.exists(_db_path):
            return
        _conn = sqlite3.connect(_db_path, timeout=5)
        _c = _conn.cursor()
        # 获取最近3个交易日
        _c.execute("SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date DESC LIMIT 3")
        _recent_dates = [r[0] for r in _c.fetchall()]
        if not _recent_dates:
            _conn.close()
            return
        for _code in codes:
            for _dt in _recent_dates:
                _c.execute("SELECT p, vr FROM data_cache WHERE code=? AND date=?", (_code, _dt))
                _row = _c.fetchone()
                if _row:
                    _FLCACHE.setdefault(_code, {})[_dt] = (_row[0] or 0, _row[1] or 1)
        _conn.close()
    except:
        pass

def check_fangliang_veto(code, today_str, all_codes=None):
    """检查某只票过去1-2天是否有放量下跌
    返回 (是否有否决, 原因说明)
    速度: ~5ms/只
    """
    if all_codes:
        _load_fangliang_data(all_codes)
    
    stock_data = _FLCACHE.get(code, {})
    if not stock_data:
        return False, ''
    
    prev_dates = sorted(d for d in stock_data.keys() if d < today_str)
    if not prev_dates:
        return False, ''
    
    reasons = []
    for prev_d in prev_dates[-2:]:
        pct, vr = stock_data[prev_d]
        if pct < 0 and vr >= 1.3:
            reasons.append(f"{prev_d} 跌{pct:.1f}% 量比{vr:.1f}x")
    
    if reasons:
        return True, ' | '.join(reasons)
    return False, ''

# ===== 生成HTML =====
def build_html(top10_result, bt_result, prod_result, today_str, data_date_str, buy_date_str, mk_cn, level, ver_id='V51', bt_50=None, bt_100=None, market_avg_pct=0):
    """V10同款淡色模板，含历史回测+真实数据两个板块"""
    # 历史回测结果
    if bt_result:
        wi_bt, ta_bt, mk_s_bt, daily_rows_bt, top3_bt, last_dt = bt_result
    else:
        wi_bt = ta_bt = 0; mk_s_bt = {}; daily_rows_bt = []; top3_bt = []
    # 真实生产验证结果
    if prod_result:
        wi_pr, ta_pr, mk_s_pr, daily_rows_pr, top3_pr, _ = prod_result
    else:
        wi_pr = ta_pr = 0; mk_s_pr = {}; daily_rows_pr = []; top3_pr = []
    
    now = datetime.now()

    # 50天/100天胜率（从主流程传入的bt_50/bt_100动态计算）
    v50d = f'{bt_50[0]*100//bt_50[1]}%' if bt_50 and bt_50[1] else '—'
    v100d = f'{bt_100[0]*100//bt_100[1]}%' if bt_100 and bt_100[1] else '—'
    
    # 对比表：收盘15:00 vs 尾盘14:50（同一张表，逐日对比）
    # 对比表
    close_pct = wi_bt*100/ta_bt if ta_bt else 0
    champion_pct = wi_bt*100//ta_bt if ta_bt else 0
    
    close_by_dt = {r['dt']: r for r in top3_bt}
    top3_cards = ''
    medals = {0:'🥇',1:'🥈',2:'🥉'}
    for rank, (sc, warnings, s, ind, code, analysis) in enumerate(top10_result[:10]):
        medal = medals.get(rank, f'#{rank+1}')
        nm = s['name']
        price = f'{s["price"]:.2f}'
        pct = s['p']
        pct_s = f'+{pct:.1f}%' if pct >= 0 else f'{pct:.1f}%'
        pct_c = '#e74c3c' if pct >= 0 else '#27ae60'
        vr = s['vol_ratio']
        hsl = s['hsl']
        sz = s['sz']
        price_warn = ' ⚠️ 价格较高' if s['price'] > 100 else ''
        
        # ═══ V51: 风险标签 ═══
        risk_tags = get_risk_tags(s, ind, market_avg_pct)
        risk_html = risk_tags_html(risk_tags)
        trends = []
        if pct > 0 and vr > 1.2: trends.append('放量')
        elif pct > 0: trends.append('正常')
        else: trends.append('缩量')
        if ind and ind['macd_golden']: trends.append('多头')
        elif ind and ind['dif'] > 0: trends.append('偏多')
        else: trends.append('偏弱')
        trend_str = ' | '.join(trends)
        bg = '#fff8e1' if rank == 0 else '#f0f7ff' if rank == 1 else '#f5f5f5' if rank <= 3 else '#fafafa'
        
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
        <div style="margin-top:3px">{risk_html}</div>
        {'<div style="margin-top:4px;padding:4px 6px;background:#fff0f0;border-left:3px solid #e74c3c;border-radius:3px;font-size:11px;color:#c0392b">⚠️ ' + ' | '.join(warnings) + '</div>' if warnings else ''}
      </div>
    </div>
    {'<div style="margin-top:5px;padding:6px;background:#f8f9fa;border-radius:4px;font-size:11px">' +
      ''.join(f'<div style="margin-bottom:2px">[{"✅" if ok else "❌"}] {label} ({val}) → {desc}</div>' for label, ok, val, desc in analysis["checks"]) +
      f'<div style="margin-top:2px;font-weight:bold">= {analysis["score"]}/4 {"👍 建议买入" if analysis["score"]>=3 else "👀 谨慎参考" if analysis["score"]>=2 else "⚠️ 风险偏高"}</div>' +
      ('<div style="margin-top:4px;padding:3px 5px;background:#f0f7ff;border-left:3px solid #3498db;border-radius:3px">🧠 <b>个股IQ:</b> ' + analysis["stock_iq"]["rating"] + ' ' + str(analysis["stock_iq"]["iq"]) + '分 · ' + analysis["stock_iq"]["summary"] + '</div>' if analysis.get("stock_iq") else '') +
      ('<div style="color:#7f8c8d;margin-top:2px">' + '<br>'.join(analysis["details"][:5]) + '</div>' if analysis["details"] else '') +
      ('<div style="color:#e74c3c;margin-top:2px">⚠️ 相似失败案例:' + ' | '.join(analysis["refs"]) + '</div>' if analysis["refs"] else '') +
    '</div>' if analysis else ''}'''

    # ═══ 获取冠亚季军新闻+公告（并行拉取）═══
    top3_news_html = ''
    medals_cn = {0:'🥇 冠军',1:'🥈 亚军',2:'🥉 季军'}
    news_results = {}
    with ThreadPoolExecutor(max_workers=6) as _ex:
        _futs = {}
        for rank, (sc, warnings, s, ind, code) in enumerate(top10_result[:3]):
            nm = s['name']
            _futs[_ex.submit(fetch_stock_news, nm, 5)] = ('news', rank, nm, code)
            _futs[_ex.submit(fetch_stock_ann, code, 5)] = ('ann', rank, nm, code)
        for _f in as_completed(_futs):
            _type, _rank, _nm, _code = _futs[_f]
            try:
                _r = _f.result()
                news_results.setdefault(_rank, {'arts':[], 'anns':[], 'nm':_nm, 'code':_code})
                if _type == 'news':
                    news_results[_rank]['arts'] = _r
                else:
                    news_results[_rank]['anns'] = _r
            except:
                pass
    for _rank in sorted(news_results.keys()):
        _nr = news_results[_rank]
        all_items = list(_nr['arts']) + list(_nr['anns'])
        pos_items, neg_items = tag_news_sentiment(all_items)
        pos_items = pos_items[:2]
        neg_items = neg_items[:2]
        if not pos_items and not neg_items:
            continue
        news_lines = ''
        if pos_items:
            news_lines += '<div style="margin-top:3px">'
            for a in pos_items:
                ttl = a.get('title','')[:50]
                news_lines += f'<span style="display:inline-block;font-size:10px;padding:1px 6px;border-radius:3px;background:#e8f5e9;color:#27ae60;margin-right:4px;margin-top:2px">🟢 {ttl}</span>'
            news_lines += '</div>'
        if neg_items:
            news_lines += '<div style="margin-top:2px">'
            for a in neg_items:
                ttl = a.get('title','')[:50]
                news_lines += f'<span style="display:inline-block;font-size:10px;padding:1px 6px;border-radius:3px;background:#ffebee;color:#e74c3c;margin-right:4px;margin-top:2px">🔴 {ttl}</span>'
            news_lines += '</div>'
        if news_lines:
            top3_news_html += f'''<div style="margin-top:4px;padding:4px 8px;background:#fafafa;border-radius:4px;font-size:11px">
      <div style="font-weight:bold;color:#555;margin-bottom:2px">{medals_cn[_rank]} 资讯速览</div>
      {news_lines}
    </div>'''

    # 30天战绩
    mkt_rows = ''
    total_w = sum(mk_s_bt[k][0] for k in mk_s_bt) if mk_s_bt else 0
    total_t = sum(mk_s_bt[k][1] for k in mk_s_bt) if mk_s_bt else 0
    total_pct = total_w*100/total_t if total_t else 0
    for cn in ['真实涨日','虚涨日','跌日','横盘']:
        w, t = mk_s_bt.get(cn, [0,0])
        if t == 0: continue
        wr_pct = w*100/t
        bar_full = '█' * int(wr_pct/5)
        bar_empty = '░' * (20 - len(bar_full))
        mkt_rows += f'''<tr><td style='font-weight:bold'>{cn}</td><td>{t}天</td><td>{bar_full}{bar_empty}</td><td style='font-weight:bold;color:#e74c3c'>{wr_pct:.1f}%</td><td>{w}/{t}</td></tr>'''
    bar_full = '█' * int(total_pct/5)
    bar_empty = '░' * (20 - len(bar_full))
    mkt_rows += f'''<tr style='font-weight:bold;background:#f5f6fa'><td>总计</td><td>{total_t}天</td><td>{bar_full}{bar_empty}</td><td style='color:#e74c3c'>{total_pct:.1f}%</td><td>{total_w}/{total_t}</td></tr>'''
    
    # 冠亚季军胜率
    valid_results = [r for r in top3_bt] if top3_bt else []
    n = len(valid_results)
    champ_w = sum(1 for r in valid_results if r['nh']>=2.5)
    # V51 no 亚军/季军 data, show as '—'
    second_w = 0
    third_w = 0
    top3_any = champ_w
    
    rank_rows = f'''
<tr><td style="font-size:18px">🥇 冠军</td><td style="color:#e74c3c;font-weight:bold;font-size:16px">{champ_w*100//n if n else 0}%</td><td>{champ_w}/{n}</td><td>评分第1名</td></tr>
<tr><td style="font-size:18px">🥈 亚军</td><td style="color:#b8860b;font-weight:bold;font-size:16px">—</td><td>—</td><td>冠军太贵时的备选</td></tr>
<tr><td style="font-size:18px">🥉 季军</td><td style="color:#b8860b;font-weight:bold;font-size:16px">—</td><td>—</td><td>第三备选</td></tr>
<tr style="background:#f5f6fa;font-weight:bold"><td>🎯 冠军达标</td><td style="color:#e74c3c;font-size:16px">{champ_w*100//n if n else 0}%</td><td>{champ_w}/{n}</td><td>仅统计冠军（无亚军/季军数据）</td></tr>'''
    
    # 逐日战绩（V51 top3_bt 无 cl/vr/hsl/wr/dif，显示'—'）
    daily_table = ''
    for r in reversed(top3_bt):
        pct_c = '#e74c3c' if r.get('p', 0)>=0 else '#27ae60'
        nh = r.get('nh', 0) or 0
        if nh == 0:
            nh_display = '<span style="color:#95a5a6">待确认</span>'
            nh_result = chr(9203)
        else:
            nh_c = '#e74c3c' if nh>=2.5 else '#27ae60'
            nh_display = '<span style="color:{};font-weight:bold">{:+.1f}%</span>'.format(nh_c, nh)
            nh_result = r.get('result', '—')
        daily_table += '<tr><td>{}</td><td>{}</td><td style="font-weight:bold">{}</td><td>{}</td><td style="color:{};font-weight:bold">{:+.1f}%</td><td>{}</td><td style="font-weight:bold">{:.0f}</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>{}</td></tr>'.format(
            r['dt'][5:], r['mk'], r['c_name'], r['c_code'], pct_c, r.get('p', 0),
            nh_display, r.get('score',0), nh_result)
    
    # 生产验证逐日表
    prod_daily = ''
    if prod_result:
        for r in top3_pr:
            nh = r.get('nh', 0) or 0
            nh_c = '#e74c3c' if nh>=2.5 else '#27ae60'
            mark = '&#9989;' if nh>=2.5 else '&#10060;'
            prod_daily += f'<tr><td>{r["dt"][5:]}</td><td>{r["mk"]}</td><td>{r["c_name"]}</td><td style="color:{nh_c};font-weight:bold">{nh:+.1f}%</td><td>{r.get("score",0):.0f}</td><td>{mark}</td></tr>'
    else:
        prod_daily = '<tr><td colspan="6" style="color:#95a5a6">暂无生产验证数据（V51刚上线，等待明日D+1）</td></tr>'
    
    # 动态计算最强/弱行情（历史回测）
    mkt_names_cn = ['真实涨日','虚涨日','跌日','横盘']
    sorted_mkts = sorted([(mk_s_bt[k][0]*100/mk_s_bt[k][1], mk_s_bt[k][0], mk_s_bt[k][1], k) 
                          for k in mkt_names_cn if mk_s_bt.get(k) and mk_s_bt[k][1]>0], reverse=True)
    strongest = [f'{nm}{r:.0f}%🏆' for r,w,t,nm in sorted_mkts[:2]] if sorted_mkts else ['暂无']
    weakest = [f'{nm}{r:.0f}%' for r,w,t,nm in sorted_mkts[-1:]] if sorted_mkts else ['暂无']
    strongest_str = ' | '.join(strongest)
    weakest_str = ' | '.join(weakest)
    

    # 价格提示
    price_tip = ''
    if top10_result and len(top10_result) > 0:
        champ = top10_result[0][2]
        if champ['price'] > 100 and len(top10_result) > 1:
            s2 = top10_result[1][2]
            price_tip = f'💡 冠军{champ["name"]}¥{champ["price"]:.2f}价格偏高，预算有限可考虑亚军{s2["name"]}¥{s2["price"]:.2f}'
    
    champ_pct = wi_bt*100//ta_bt if ta_bt else 0
    title_ver = f'V51 分而治之 · 每日选股报告 (历史回测{champ_pct}%版)'
    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>V51每日选股报告 {today_str}</title>
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
  V51 分而治之 · 每日选股报告 (30天{champ_pct}%版)
</div>

<div style="font-size:12px;color:#95a5a6;text-align:center;margin-bottom:8px">
  📅 {today_str} | 📡 数据: {data_date_str} | 🎯 建议买入: {buy_date_str} 尾盘 | 📌 {mk_cn} | 🔰 {level}
</div>

<div style="background:#f5f6fa;border-radius:8px;padding:12px;margin:12px 0">
  <div style="font-size:16px;font-weight:bold;color:#b8860b;margin-bottom:8px">今日推荐 {today_str} | {mk_cn} | {level}级</div>
  <div style="display:grid;grid-template-columns:1fr;gap:8px">
{top3_cards}
  </div>
{top3_news_html}
</div>

<div class="card">
<h3>📋 V51 版本档案</h3>
<table><thead><tr><th>指标</th><th>数据</th></tr></thead><tbody>
<tr><td>30天胜率</td><td><b>{champ_pct}%</b> ({wi_bt}/{ta_bt}) 动态回测 ✅</td></tr>
<tr><td>50天胜率</td><td>{v50d} (动态回测 ✅)</td></tr>
<tr><td>100天胜率</td><td>{v100d} (动态回测 ✅)</td></tr>
<tr><td>最强行情</td><td>{strongest_str}</td></tr>
<tr><td>短板行情</td><td>{weakest_str}</td></tr>
<tr><td>当前行情</td><td>{mk_cn} | {level}级 | 池{len(top10_result)}只</td></tr>
</tbody></table>
</div>

<div class="card">
<h3>📊 近30天总战绩</h3>
  <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin:8px 0">
  <table style="min-width:500px"><thead><tr><th>行情</th><th>天数</th><th>胜率条</th><th>胜率</th><th>胜/负</th></tr></thead><tbody>
{mkt_rows}
</tbody></table></div>
<div style="font-size:11px;color:#95a5a6;margin-top:5px">
✅ 目标：次日最高涨幅≥2.5% | 最新30天 {wi_bt}/{ta_bt} = {champ_pct}%
</div>
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

<div class="footer">
V51 分而治之 | 30天 {wi_bt}/{ta_bt} = {champ_pct}% | 实战累计中
<p style="font-size:14px;color:#b8860b;font-weight:bold;margin-top:12px">
  🤝 {wi_bt}/{ta_bt} = {champ_pct}%，继续优化全年胜率！
</p>
</div>

</body></html>'''
    return html

# ===== 主流程 =====
if __name__ == '__main__':
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    
    # ═══ 第一步：公共数据刷新（增量补充，所有版本共用）═══
    print('🔄 [通用] 数据刷新...', flush=True)
    try:
        update_py = os.path.join(V51_DIR, 'update_data_cache.py')
        if not os.path.exists(update_py):
            update_py = os.path.join(SCRIPTS_DIR, 'update_data_cache.py')
        if os.path.exists(update_py):
            r = subprocess.run([sys.executable, update_py], timeout=30, capture_output=True, text=True)
            for line in r.stdout.strip().split('\n'):
                if any(k in line for k in ['✅','⚠️','📅','📊','⏱','补充','+','缺失','通用']):
                    print(f'  {line.strip()}', flush=True)
    except Exception as e:
        print(f'⚠️ 数据刷新失败: {e}，继续使用现有缓存', flush=True)
    
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
    
    print(f'🚀 V51 每日选股报告 | {today_str}', flush=True)
    print(f'📡 数据来源: {data_label} ({data_date})', flush=True)
    print(f'🎯 建议买入: {buy_date} 尾盘', flush=True)
    
    # 实时选今天（返回: scored[:10], mk_cn, used_level, stocks, indicators）
    top10_raw = pick_today()
    top10 = top10_raw[:3] if top10_raw else None  # 保持向后兼容
    
    # 计算大盘均值（用于风险标签-超级行情跟风检测）
    market_avg_pct = 0
    if top10_raw and len(top10_raw) > 3:
        _stocks = top10_raw[3]
        if _stocks:
            _ps = [s['p'] for s in _stocks.values() if abs(s['p']) < 15]
            market_avg_pct = sum(_ps)/len(_ps) if _ps else 0
    
    # 2. 保存当天实时数据到data_cache（统一数据源）
    if top10_raw:
        stocks = top10_raw[3]
        indicators = top10_raw[4]
        try:
            from selection_log_db import save_realtime_to_datacache
            save_realtime_to_datacache(today_str, stocks, indicators, 'tencent:1450-v50')
        except Exception as e:
            print(f'⚠️ data_cache写入失败: {e}', flush=True)
    
    # 3. 回测（V50自己的big_cache_full.pkl，含ma5_slope）
    bt = backtest_30d()
    # 再算50天和100天胜率（从同一个big_cache）
    bt_50 = None; bt_100 = None
    try:
        import pickle
        pkl = os.path.join(SCRIPTS_DIR, 'big_cache_full.pkl')
        if os.path.exists(pkl):
            with open(pkl, 'rb') as f: dc = pickle.load(f)
            bd, rr, nn = dc['data'], dc['real'], dc['names']
            ad = sorted(k for k in bd.keys())
            # 复用全局STRATS和LO
            for label, days in [('50',50),('100',100)]:
                if len(ad) < days: continue
                target = ad[-days:]
                wi=ta=0
                for dt in target:
                    ss = [s for s in bd.get(dt,[]) if (s.get('p',0) or 0) < 15]
                    if len(ss)<20: continue
                    n_f = sum(1 for s in ss if (s.get('n',0) or 0)!=0)
                    if n_f<len(ss)*0.5: continue
                    # 简化行情分类
                    ps2=[s.get('p',0) or 0 for s in ss if abs(s.get('p',0) or 0)<15]
                    vrs2=[s.get('vol_ratio',0) or 0 for s in ss if s.get('vol_ratio',0)]
                    ap2=sum(ps2)/len(ps2) if ps2 else 0
                    av2=sum(vrs2)/len(vrs2) if vrs2 else 0
                    hot2=sum(1 for p in ps2 if 5<=p<=8)
                    if ap2>0.5: mk2='虚假涨日' if hot2<15 or av2<0.9 else '真实涨日'
                    elif ap2<-0.5: mk2='跌日'
                    else: mk2='横盘'
                    mod2=STRATS.get(mk2)
                    if not mod2: continue
                    levels2=getattr(mod2,'LEVELS',None)
                    if not levels2: continue
                    lm2={l['name']:i for i,l in enumerate(levels2)}
                    pool2=None
                    for ln in LO:
                        if ln not in lm2: continue
                        lv2=levels2[lm2[ln]]; cand2=[]
                        for s in ss:
                            p=s.get('p',0) or 0
                            if p<lv2['p_min'] or p>min(lv2.get('p_max',10),8): continue
                            vr=s.get('vol_ratio',1) or 1
                            if vr<lv2['vr_min'] or vr>lv2['vr_max']: continue
                            hsl=rr.get(s['code'],{}).get('hsl',0) or 0
                            if hsl<lv2.get('hs_min',0) or hsl>lv2.get('hs_max',99): continue
                            cl=s.get('cl',50)
                            if cl<lv2.get('cl_min',0) or cl>lv2.get('cl_max',100): continue
                            cand2.append(s)
                        if len(cand2)>=10: pool2=cand2; break
                    if not pool2: continue
                    # 评分-简化版
                    scored2=[]
                    for s in pool2:
                        st2={
                            'p':s.get('p',0) or 0,'cl':s.get('cl',50),'vr':s.get('vol_ratio',1) or s.get('vr',1),
                            'dif':s.get('dif_val',0) or s.get('dif',0),'mg':s.get('macd_golden',0) or s.get('mg',0),
                            'wrv':s.get('wr_val',0) or s.get('wrv',50),'jv':s.get('j_val',0) or s.get('jv',50),
                            'kv':s.get('k_val',0) or s.get('kv',50),'dv':s.get('d_val',0) or s.get('dv',50),
                            'a5':s.get('above_ma5',0),'kdj_g':s.get('kdj_golden',0) or s.get('kdj_g',0),
                            'pos_in_day':s.get('pos_in_day',50),'nm':nn.get(s['code'],''),
                            'hsl':rr.get(s['code'],{}).get('hsl',0) or 0,
                            'ma5_slope':s.get('ma5_slope',0) or 0,'t4_shadow':s.get('t4_shadow',0) or 0,
                            'slope5':s.get('slope5',0) or 0,'cons_up':s.get('cons_up',0) or 0,
                            'd1':s.get('d1',0) or 0,'d2':s.get('d2',0) or 0,'d3':s.get('d3',0) or 0,
                        }
                        scored2.append((mod2.score(st2),s))
                    scored2.sort(key=lambda x:-x[0])
                    if scored2 and (scored2[0][1].get('n',0) or 0)>=2.5: wi+=1
                    ta+=1
                if label=='50': bt_50=(wi,ta)
                else: bt_100=(wi,ta)
    except Exception as e:
        print(f'⚠️ 50/100天计算失败: {e}')
    
    if top10 and bt:
        # 丰富分析（先预加载big_cache再开线程）
        from v51_analysis import _ensure_stock_index
        _ensure_stock_index()  # 主线程预加载，避免子线程排队
        def enrich_one(item):
            sc, warnings, s, ind, code = item
            return (sc, warnings, s, ind, code, analyze_stock(s, ind, code, top10[1], market_avg_pct))
        with ThreadPoolExecutor(max_workers=6) as _ex:
            futs = {_ex.submit(enrich_one, item): i for i, item in enumerate(top10[0])}
            enriched_list = [None] * len(top10[0])
            for f in as_completed(futs):
                i = futs[f]
                enriched_list[i] = f.result()
        
        # 用丰富后的数据替换
        top10_enriched = enriched_list
        html = build_html(top10_enriched, bt, None, today_str, f'{data_label}({data_date})', buy_date, top10[1], top10[2], bt_50=bt_50, bt_100=bt_100, market_avg_pct=market_avg_pct)
        
        # 存档
        arch = os.path.join(SCRIPTS_DIR, 'email_archive')
        os.makedirs(arch, exist_ok=True)
        fp = os.path.join(arch, f'{today_str}_V51_报告.html')
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'📁 已存档: {fp}', flush=True)
        
        # 发邮件（全部4人，收件人从config/email_config.yaml统一读取）
        try:
            from send_email import send_email
            subj = f'V51每日选股 {today_str} - {top10[1]} - 冠军{top10[0][0][2]["name"]}[{top10[0][0][2]["price"]:.2f}]'
            r = send_email(subject=subj, body=html, html=True, force=True)
            print(f'📧 {"✅成功" if r else "❌失败"}: {subj}', flush=True)
        except Exception as e:
            print(f'❌ 邮件失败: {e}', flush=True)
        
        # 写入数据库日志
        try:
            log_selection_to_db('V51', today_str, top10[1], top10[2], len(top10[0]), top10[0])
        except Exception as e:
            print(f'⚠️ 数据库日志写入失败: {e}', flush=True)
        
        # 输出摘要到stdout
        print(f'\n=== V51 选股摘要 ===')
        print(f'今日推荐 ({top10[1]} {top10[2]}级):')
        
        # 放量下跌一票否决检查（全部10只，批量查一次）
        veto_map = {}
        _today = today_str
        _all_codes = []
        for item in top10[0]:
            _code = item[2]['code'] if len(item) > 2 else item[1].get('code', '')
            _all_codes.append(_code)
        # 一次批量加载所有代码数据
        _load_fangliang_data(_all_codes)
        for _code in _all_codes:
            _has, _why = check_fangliang_veto(_code, _today)
            if _has:
                veto_map[_code] = _why
        
        # 找没有否决的#1（鹤立鸡群候选人）
        heji_candidate = None
        for rank, item in enumerate(top10[0][:3], 1):
            _sc, _warnings, _s, _ind, _code, _analysis = item
            if _code not in veto_map:
                if heji_candidate is None:
                    heji_candidate = rank
        
        for rank, (sc, warnings, s, ind, code, analysis) in enumerate(top10[0][:3], 1):
            lines = [f'  {rank}. {s["name"]}({code}) ¥{s["price"]:.2f} 当日{s["p"]:+.1f}% 评分{sc:.0f}']
            
            # 🔥🔥🔥 鹤立鸡群 🔥🔥🔥 — #1且没有放量下跌
            if rank == heji_candidate:
                lines[0] += '  🔥🔥🔥 鹤立鸡群 🔥🔥🔥'
            
            # ⚠️ 不建议购买 — 放量下跌一票否决
            if code in veto_map:
                lines.append(f'     ⚠️ 不建议购买（{veto_map[code]}）')
            
            for label, ok, val, desc in analysis["checks"]:
                lines.append(f'     [{"✅" if ok else "❌"}] {label} ({val}) → {desc}')
            lines.append(f'     = {analysis["score"]}/4')
            if analysis.get('stock_iq'):
                si = analysis['stock_iq']
                lines.append(f'     🧠 个股IQ: {si["rating"]} {si["iq"]}分 · {si["summary"]}')
            if analysis.get('details'):
                for d in analysis['details'][:4]:
                    lines.append(f'     {d}')
            if analysis.get('refs'):
                lines.append(f'     ⚠️ 类似:{"; ".join(analysis["refs"])}')
            print('\n'.join(lines))
        import sqlite3
        _db = sqlite3.connect(os.path.join(SCRIPTS_DIR, 'v13_quant.db'), timeout=10)
        _c = _db.execute('SELECT COUNT(*) FROM selection_candidates WHERE version=?', ('V51',))
        _prod_cnt = _c.fetchone()[0] or 0
        _db.close()
        print(f'📊 历史回测30天: {bt[0]}/{bt[1]} = {bt[0]*100/bt[1]:.1f}%' if bt[1] else '📊 历史回测30天: 暂无')
        if bt_50: print(f'📊 历史回测50天: {bt_50[0]}/{bt_50[1]} = {bt_50[0]*100/bt_50[1]:.1f}%')
        if bt_100: print(f'📊 历史回测100天: {bt_100[0]}/{bt_100[1]} = {bt_100[0]*100/bt_100[1]:.1f}%')
        print(f'📊 V51生产记录总数: {_prod_cnt}条')
    else:
        print('❌ 选股失败')