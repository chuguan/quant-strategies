#!/usr/bin/env python3
"""1170 每日选股报告 — V50增强版+行业一票否决"""

import sys, os, json, re, time, subprocess, pickle
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from selection_log_db import log_selection_to_db

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
V50_DIR = os.path.join(SCRIPTS_DIR, 'release', '1170')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
sys.path.insert(0, V50_DIR); sys.path.insert(0, SCRIPTS_DIR)

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

# ===== 加载V50策略模块 =====
import importlib
STRATS = {}
for n in ['真实涨日','虚涨日','跌日','横盘']:
    fp = os.path.join(V50_DIR, '评分策略', f'分而治之_V10_{n}_评分策略.py')
    spec = importlib.util.spec_from_file_location(n, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    STRATS[n] = m

LO = ['L0','L1','L2','L3','L4']
MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}

# ═══ 加载行业映射（一票否决用）═══
INDUSTRY_MAP = {}
ind_path = os.path.join(V50_DIR, 'industry_map.pkl')
if os.path.exists(ind_path):
    with open(ind_path, 'rb') as f:
        INDUSTRY_MAP = pickle.load(f)
    print(f'🏭 行业映射: {len(INDUSTRY_MAP)}只股票', flush=True)

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
    # V50需要：ma5_slope = 5日均线斜率
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

# ═══ 新规则：动量透支 + 跌日HSL + 行业追高 ═══
def check_extra_risks(p, hsl, vr, mk_cn, ind_avg, slope5, gains_7d):
    """返回 (否决, 扣分, [风险标签])"""
    risks = []
    veto = False
    penalty = 0
    
    # 规则1：动量透支否决 — 7天累计>12%且slope5>15
    if slope5 > 15 and gains_7d > 12:
        veto = True
        risks.append('🔴动量透支')
    elif slope5 > 12 and gains_7d > 15:
        veto = True
        risks.append('🔴动量透支')
    
    # 规则2：跌日HSL惩罚 — 跌日/虚涨日高换手=出货
    if mk_cn in ('跌日', '虚涨日'):
        if hsl > 15:
            veto = True
            risks.append('🔴跌日高换手')
        elif hsl > 12:
            penalty -= 10
            risks.append('🟡换手偏高')
    
    # 规则3：行业过热警告 — 行业均>1.5%追高风险
    if ind_avg and ind_avg > 1.5:
        risks.append('🟡行业过热')
        penalty -= 5
    
    return veto, penalty, risks

def calc_probability(mk_cn, p=0, hsl=0, ma5_s=0, ind_rel=0, g7_total=0, stock_code=None, stock_history=None):
    """计算个股明日冲高概率（基于行情+特征+公司历史）
    
    算法: 基础概率(行情) + 特征修正 + 公司历史
    
    Args:
        mk_cn: 行情类型 (真实涨日/虚涨日/跌日/横盘)
        p: 当日涨幅%
        hsl: 换手率%
        ma5_s: 5日均线斜率
        ind_rel: 跑赢行业幅度%
        g7_total: 7天累计涨幅%
        stock_code: 股票代码（用于查历史记录）
        stock_history: {code: (wins, total, name)} 历史冠军记录
    """
    # 1. 行情基础概率（近30天为准）
    base_rates = {'真实涨日': 71, '虚涨日': 55, '跌日': 72, '横盘': 75}
    prob = base_rates.get(mk_cn, 65)
    
    # 2. 特征修正
    # 涨幅修正
    if p > 5: prob += 3      # 大涨>5% = 动量强
    elif p > 4: prob += 1    # 正常涨幅
    elif p < 3: prob -= 3    # 涨幅不足 = 动能弱
    
    # 换手修正
    if 5 <= hsl <= 12: prob += 3      # 理想换手
    elif hsl > 15: prob -= 5          # 高换手=抛压
    elif hsl < 3: prob -= 2           # 低换手=不活跃
    
    # 斜率修正（ma5_s = 5日均线斜率）
    if ma5_s > 12: prob += 4          # 斜率大=趋势强
    elif ma5_s > 8: prob += 1         # 正常斜率
    elif ma5_s < 5 and ma5_s > 0: prob -= 2  # 斜率弱
    elif ma5_s <= 0: prob -= 5        # 斜率为负
    
    # 行业跑赢修正
    if ind_rel > 5: prob += 3         # 大幅跑赢=优质
    elif ind_rel > 3: prob += 1
    elif ind_rel < 0: prob -= 2       # 跑输行业
    
    # 7天累计修正（透支检查）
    if g7_total > 20: prob -= 8       # 严重透支
    elif g7_total > 15: prob -= 4     # 轻度透支
    elif g7_total > 12: prob -= 2
    elif g7_total < 8: prob += 3      # 空间充足
    
    # 3. 公司历史修正
    if stock_code and stock_history:
        hist = stock_history.get(stock_code)
        if hist and hist[1] >= 2:  # 至少被选为冠军2次
            hist_rate = hist[0] * 100 / hist[1]
            # 历史表现加权：历史率与当前概率取平均
            prob = (prob + hist_rate) // 2
    
    return max(30, min(98, prob))  # 限幅30%~98%

# ===== 实时选股 =====
def pick_today():
    print('🚀 V50 实时选股...', flush=True)
    stocks = get_live_stocks()
    mk = classify_market(stocks)
    mk_cn = MK_MAP.get(mk, '横盘')
    print(f'📊 行情: {mk_cn}', flush=True)
    
    mod = STRATS[mk_cn]
    LEVELS = mod.LEVELS
    lm = {l['name']:i for i,l in enumerate(LEVELS)}
    
    # ═══ 计算实时行业均值（用于一票否决）═══
    from collections import defaultdict
    ind_prices = defaultdict(list)
    for code, s in stocks.items():
        ind = INDUSTRY_MAP.get(code, '')
        if ind:
            ind_prices[ind].append(s['p'])
    live_ind_avg = {k: sum(v)/len(v) for k,v in ind_prices.items() if v}
    vetoed_stocks = 0
    
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
            # 停牌检查：p=0且成交量≤股价（volume被填充为price）= 无真实交易
            if p == 0 and s.get('vol', 0) <= s.get('price', 0): continue
            cl_v = ind['cl']
            if cl_v < lv.get('cl_min',0) or cl_v > lv.get('cl_max',100): continue
            if not check_momentum(code, ind, s): continue
            # ═══ 行业一票否决 ═══
            code_ind = INDUSTRY_MAP.get(code, '')
            if code_ind and live_ind_avg.get(code_ind, 0) < -2.0:
                vetoed_stocks += 1
                continue
            # 相对强度否决：个股跑输行业>3%
            if code_ind:
                sp = s['p']
                ia = live_ind_avg.get(code_ind, 0)
                if sp - ia < -3.0:
                    vetoed_stocks += 1
                    continue
            # ═══ 新规则：动量透支 + 跌日HSL + 行业追高 ═══
            risk_ia = ia if code_ind else 0
            extra_veto, extra_penalty, extra_risks = check_extra_risks(
                s['p'], s['hsl'], s['vol_ratio'], mk_cn, risk_ia, ind.get('ma5_slope', 0), 0
            )
            if extra_veto:
                vetoed_stocks += 1
                continue
            cand.append((code,s,ind,extra_risks,extra_penalty))
        if len(cand) >= 10:
            pool = cand; used_level = ln; break
    
    if not pool:
        print('❌ 候选池不足')
        return None
    
    # 评分
    scored = []
    for code, s, ind, extra_risks, extra_penalty in pool:
        stock = {
            'p': s['p'], 'cl': ind['cl'], 'vr': s['vol_ratio'],
            'dif': ind['dif'], 'mg': ind['macd_golden'],
            'wrv': ind['wr'], 'jv': ind['j_val'], 'kv': ind['k_val'], 'dv': ind['d_val'],
            'a5': 1, 'kdj_g': ind['kdj_golden'], 'pos_in_day': 50,
            'nm': s['name'], 'hsl': s['hsl'],
            'ma5_slope': ind.get('ma5_slope', 0),  # V50需要
            't4_shadow': 0, 'slope5': 0, 'cons_up': 0,
            'd1': 0, 'd2': 0, 'd3': 0,
        }
        sc = mod.score(stock) + extra_penalty
        scored.append((sc, s, ind, code, extra_risks))
    scored.sort(key=lambda x:-x[0])
    if vetoed_stocks > 0:
        print(f'🗑️ 行业否决: {vetoed_stocks}只', flush=True)
    
    # ═══ 四维补充分析：基本面+均线+行业+买入建议 ═══
    for i, (sc, s, ind, code, extra_risks) in enumerate(scored[:10]):
        s['risks'] = extra_risks
        # 均线计算（从缓存K线读取）
        try:
            prefix = 'sh' if code.startswith(('6','9')) else 'sz'
            kf = os.path.join(CACHE_DIR, f'{prefix}{code}.json')
            if os.path.exists(kf) and time.time() - os.path.getmtime(kf) < 7200:
                with open(kf) as _fk:
                    kl = json.load(_fk)
                closes = [r['close'] for r in kl]
                price = s['price']
                ma5 = round(sum(closes[-5:])/5, 2) if len(closes)>=5 else price
                ma10 = round(sum(closes[-10:])/10, 2) if len(closes)>=10 else price
                ma20 = round(sum(closes[-20:])/20, 2) if len(closes)>=20 else price
                s['ma5'] = ma5; s['ma10'] = ma10; s['ma20'] = ma20
                # 均线位置描述
                pos = []
                if price > ma5: pos.append('↑5日线')
                else: pos.append('↓5日线')
                if price > ma10: pos.append('↑10日线')
                else: pos.append('↓10日线')
                if price > ma20: pos.append('↑20日线')
                else: pos.append('↓20日线')
                s['ma_pos'] = ' '.join(pos)
                # 均线乖离率
                s['ma5_dev'] = round((price-ma5)/ma5*100, 1)
                s['ma10_dev'] = round((price-ma10)/ma10*100, 1) if ma10 else 0
        except:
            s['ma5'] = s['ma10'] = s['ma20'] = 0
            s['ma_pos'] = '—'
            s['ma5_dev'] = 0
        
        # 行业态势详情
        code_ind = INDUSTRY_MAP.get(code, '')
        if code_ind and live_ind_avg:
            ia = live_ind_avg.get(code_ind, 0)
            short_ind = code_ind.split(' ', 1)[-1] if ' ' in code_ind else code_ind
            s['ind_name'] = short_ind[:12]
            s['ind_avg'] = round(ia, 1)
            s['ind_rel'] = round(s['p'] - ia, 1)
        else:
            s['ind_name'] = '—'; s['ind_avg'] = 0; s['ind_rel'] = 0
        
        # ═══ 全维度风险/利好分析 ═══
        score_total = sc
        bullish = []
        risk_pts = []
        p = s['p']; hsl = s.get('hsl', 0) or 0
        vr = s.get('vol_ratio', 1) or 1
        wr = ind.get('wr', 50) if ind else 50
        ma5_d = s.get('ma5_dev', 0) or 0
        ia = s.get('ind_avg', 0) or 0
        ir = s.get('ind_rel', 0) or 0
        pe = s.get('pe', 0) or 0
        cl_val = ind.get('cl', 50) if ind else 50
        jv = ind.get('jv', 50) if ind else 50
        
        # 技术面利好
        if p > 4: bullish.append(('强势', f'{p:+.1f}%'))
        if 5 <= hsl <= 12: bullish.append(('健康换手', f'{hsl:.1f}%'))
        if 0 < ma5_d < 5: bullish.append(('多头排列', ''))
        if wr < 15: bullish.append(('WR强势', f'WR{wr:.0f}'))
        if 1.2 <= vr <= 2.0: bullish.append(('量价配合', f'VR{vr:.2f}'))
        if ind and ind.get('macd_golden', 0): bullish.append(('MACD金叉', ''))
        if s.get('above_ma10', 0) and s.get('above_ma20', 0): bullish.append(('站上均线', ''))
        if cl_val < 40: bullish.append(('低位启动', f'CL{cl_val:.0f}'))
        
        # 技术面风险
        if p < 3: risk_pts.append(('动能弱', f'{p:+.1f}%'))
        if hsl > 15: risk_pts.append(('换手过高', f'{hsl:.1f}%'))
        elif hsl < 3: risk_pts.append(('交投清淡', f'{hsl:.1f}%'))
        if ma5_d > 8: risk_pts.append(('乖离过大', f'{ma5_d:.1f}%'))
        if vr > 2.5: risk_pts.append(('量比异常', f'{vr:.2f}'))
        if cl_val > 90: risk_pts.append(('高位盘整', f'CL{cl_val:.0f}'))
        if jv > 100: risk_pts.append(('J值超买', f'J{jv:.0f}'))
        if extra_risks:
            for r in extra_risks: risk_pts.append((r, ''))
        
        # 行业面
        if ir > 3: bullish.append(('跑赢行业', f'{ir:+.1f}%'))
        if ia > 0.3: bullish.append(('行业热门', f'{ia:+.1f}%'))
        if ir < -1: risk_pts.append(('跑输行业', f'{ir:+.1f}%'))
        if ia < -0.8: risk_pts.append(('行业低迷', f'{ia:+.1f}%'))
        
        # 基本面
        if 0 < pe < 50: bullish.append(('估值合理', f'PE{pe:.0f}'))
        if pe > 100: risk_pts.append(('估值偏高', f'PE{pe:.0f}'))
        
        # 大盘面
        if mk_cn == '真实涨日': bullish.append(('大盘配合', '涨日行情'))
        if mk_cn == '跌日': risk_pts.append(('大盘承压', '跌日行情'))
        if mk_cn == '虚涨日': risk_pts.append(('大盘虚涨', '注意风险'))
        
        s['bullish'] = bullish[:5]
        s['risk_pts'] = risk_pts[:5]
        
        # 综合判断
        if len(bullish) >= 3 and len(risk_pts) <= 1:
            tip = f'推荐买入'
            if risk_pts: tip += f' | 注意: {risk_pts[0][0]}'
            s['buy_advice'] = f'✅ {tip}'
        elif len(bullish) >= len(risk_pts):
            tip = f'谨慎关注'
            if risk_pts: tip += f' | 风险: {risk_pts[0][0]}'
            s['buy_advice'] = f'⚠️ {tip}'
        else:
            rnames = ' '.join(r[0] for r in risk_pts[:2])
            s['buy_advice'] = f'❌ 风险偏高 | {rnames}'
    
    return scored[:10], mk_cn, used_level, stocks, indicators, live_ind_avg

# ===== 历史回测（V50用自己big_cache_full.pkl，含ma5_slope） =====
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
                     'ma5_slope':0,'t4_shadow':0,'slope5':0,'cons_up':0,'d1':0,'d2':0,'d3':0}
            scored.append((mod.score(stock), s))
        scored.sort(key=lambda x: -x[0])
        champ = scored[0][1]
        nh = champ.get('n', 0) or 0
        ta += 1
        if nh >= 2.5: wi += 1; mk_s[mk][0] += 1
        mk_s[mk][1] += 1
        result = '✅' if nh >= 2.5 else '❌'
        top3.append({'dt':dt,'mk':mk,'c_name':str(champ.get('code','')),'c_code':champ.get('code',''),'nh':nh,'score':scored[0][0],'result':result})
    rows = [f'{"✅" if r["nh"]>=2.5 else "❌"} {r["dt"]} {r["mk"]:>5} {r["c_name"]:>8} nh={r["nh"]:+.1f}%' for r in top3]
    return wi, ta, mk_s, rows, top3, recent[-1] if recent else ''

# ===== 生成HTML =====
def build_html(top10_result, bt_result, prod_result, today_str, data_date_str, buy_date_str, mk_cn, level, ver_id='V50', bt_50=None, bt_100=None, live_ind_avg=None):
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
    for rank, (sc, s, ind, code, extra_risks) in enumerate(top10_result[:3]):
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
        # 风险/利好标签（最前面显眼显示）
        risk_badges = ''
        bullish_tags = ''
        if s.get('risk_pts'):
            risks = s['risk_pts']
            risk_badges = '<div style="margin-top:3px">' + ''.join(f'<span style="font-size:10px;padding:1px 5px;border-radius:3px;background:#ffe0e0;color:#c0392b;margin-right:3px">🔴 {r[0]}</span>' for r in risks[:3]) + '</div>'
        if s.get('bullish'):
            bulls = s['bullish']
            bullish_tags = '<div style="margin-top:2px">' + ''.join(f'<span style="font-size:10px;padding:1px 5px;border-radius:3px;background:#e8f5e9;color:#2e7d32;margin-right:3px">🟢 {b[0]}</span>' for b in bulls[:3]) + '</div>'
        
        # 行业全天表现
        ind_line = ''
        if live_ind_avg and code in INDUSTRY_MAP:
            full_ind = INDUSTRY_MAP[code]
            ia_day = live_ind_avg.get(full_ind, 0)
            if ia_day != 0:
                rel = pct - ia_day
                day_tag = '🔥' if ia_day>0.8 else ('↑' if ia_day>0.3 else ('→' if ia_day>-0.3 else ('↓' if ia_day>-0.8 else '❄️')))
                short_ind = full_ind.split(' ', 1)[-1] if ' ' in full_ind else full_ind
                short_ind = short_ind[:10]
                ind_line = f'<div style="font-size:11px;color:#7f8c8d;margin-top:2px">🏭 {short_ind} 全天{day_tag}{ia_day:+.1f}% 跑赢{rel:+.1f}%</div>'
        # 个股概率（基于行情+特征+公司历史）
        win_rate = calc_probability(
            mk_cn, 
            p=s['p'], 
            hsl=s.get('hsl', 0) or 0,
            ma5_s=s.get('ma5_dev', 0) or 0,
            ind_rel=s.get('ind_rel', 0) or 0,
            g7_total=0,
            stock_code=code,
            stock_history=None
        )
        win_rate_bar = '█' * int(win_rate/5) + '░' * (20 - int(win_rate/5))
        win_rate_line = f'<div style="font-size:11px;color:#7f8c8d;margin-top:1px">📈 个股冲高概率 {win_rate_bar} {win_rate}%</div>'
        # 均线+PE+换手
        extra_line = ''
        extra = []
        pe = s.get('pe', 0) or 0
        hs = s.get('hsl', 0) or 0
        if pe: extra.append(f'PE{pe:.0f}')
        if hs: extra.append(f'换手{hs:.1f}%')
        ma_pos = s.get('ma_pos', '')
        if ma_pos and ma_pos != '—':
            extra.append(ma_pos)
        if extra:
            extra_line = f'<div style="font-size:11px;color:#7f8c8d;margin-top:2px">📊 {" | ".join(extra[:4])}</div>'
        advice = s.get('buy_advice', '')
        if advice:
            extra_line += f'<div style="font-size:11px;margin-top:1px">{advice}</div>'
        bg = '#fff8e1' if rank == 0 else '#f5f6fa'
        
        top3_cards += f'''
    <div style="display:grid;grid-template-columns:40px 1fr;background:{bg};border-radius:6px;padding:8px;align-items:center">
      <div style="font-size:20px;text-align:center">{medal}</div>
      <div>
        <div style="font-weight:bold;font-size:14px">{nm}({code}){price_warn}</div>
        {risk_badges}
        {bullish_tags}
        <div style="font-size:12px;color:#95a5a6">
          买入价<b style="font-size:16px;color:#2c3e50">¥{price}</b>
          &nbsp;| 当日<span style="color:{pct_c};font-weight:bold">{pct_s}</span>
          &nbsp;| 评分<span style="font-weight:bold">{sc:.1f}</span>
          &nbsp;| {trend_str}
        </div>
        {ind_line}
        {win_rate_line}
        {extra_line}
        {risk_badges}
      </div>
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
    
    rank_rows = f'''
<tr><td style="font-size:18px">🥇 冠军</td><td style="color:#e74c3c;font-weight:bold;font-size:16px">{champ_w*100//n if n else 0}%</td><td>{champ_w}/{n}</td><td>评分第1名</td></tr>'''
    
    # 生产验证逐日表
    prod_daily = ''
    if prod_result:
        for r in top3_pr:
            nh = r.get('nh', 0) or 0
            nh_c = '#e74c3c' if nh>=2.5 else '#27ae60'
            mark = '&#9989;' if nh>=2.5 else '&#10060;'
            prod_daily += f'<tr><td>{r["dt"][5:]}</td><td>{r["mk"]}</td><td>{r["c_name"]}</td><td style="color:{nh_c};font-weight:bold">{nh:+.1f}%</td><td>{r.get("score",0):.0f}</td><td>{mark}</td></tr>'
    else:
        prod_daily = '<tr><td colspan="6" style="color:#95a5a6">暂无生产验证数据（V50刚上线，等待明日D+1）</td></tr>'
    
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
        champ = top10_result[0][1]
        if champ['price'] > 100 and len(top10_result) > 1:
            s2 = top10_result[1][1]
            price_tip = f'💡 冠军{champ["name"]}¥{champ["price"]:.2f}价格偏高，预算有限可考虑亚军{s2["name"]}¥{s2["price"]:.2f}'
    
    champ_pct = wi_bt*100//ta_bt if ta_bt else 0
    title_ver = f'1170 分而治之 · 每日选股报告 (历史回测{champ_pct}%版)'
    
    # ═══ 行业热点板块变动 ═══
    ind_heatmap_rows = ''
    # 先读取上次快照（计算尾盘涌入），再存当前快照
    snap_path = os.path.normpath(os.path.join(
        os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache'), 
        '..', 'industry_snapshot.json'
    ))
    ind_30min_surge = {}
    try:
        if os.path.exists(snap_path):
            with open(snap_path) as f:
                snap = json.load(f)
            snap_stocks = snap.get('stocks', {})
            snap_time = snap.get('time', '')
            snap_ind_avg = snap.get('ind_avg', {})
            # 计算尾盘20分钟各行业价格变动
            if snap_ind_avg and live_ind_avg and snap_time:
                for ind, snap_avg in snap_ind_avg.items():
                    now_avg = live_ind_avg.get(ind, 0)
                    surge = round(now_avg - snap_avg, 2)
                    if abs(surge) > 0.05:  # 只记录有意义的变化
                        ind_30min_surge[ind] = surge
    except Exception as e:
        ind_30min_surge = {}
    
    # ═══ 存当前快照（给下次用） ═══
    try:
        snap_stocks = {}
        for code, s in stocks_all.items():
            if 'p' in s:
                snap_stocks[code] = {'pct': s['p']}
        snap_data = {
            'time': datetime.now().strftime('%H:%M'),
            'stocks': snap_stocks,
            'ind_avg': live_ind_avg
        }
        os.makedirs(os.path.dirname(snap_path), exist_ok=True)
        with open(snap_path, 'w') as f:
            json.dump(snap_data, f)
    except:
        pass
    
    if live_ind_avg:
        sorted_inds = sorted(live_ind_avg.items(), key=lambda x: -x[1])
        hot = [(ind, avg) for ind, avg in sorted_inds if avg > 0.3][:6]
        cold = [(ind, avg) for ind, avg in sorted(sorted_inds, key=lambda x: x[1]) if avg < -0.3][:4]
        show_inds = hot + cold
        for ind, avg in show_inds:
            cnt = len([c for c, v in INDUSTRY_MAP.items() if v == ind])
            parts = str(ind).split(' ', 1)
            iname = parts[1][:12] if len(parts) >= 2 else ind
            tag = '🔥' if avg > 0.8 else ('↑' if avg > 0.3 else ('↓' if avg > -0.8 else '❄️'))
            bar = '█' * int(abs(avg)*6) + '░' * (20 - int(abs(avg)*6)) if abs(avg) < 3.4 else '████████████████████'
            ind_heatmap_rows += f'<tr><td>{"🔥" if avg>0 else "🔻"}</td><td style="text-align:left;padding-left:8px">{iname}</td><td style="color:{"#e74c3c" if avg>0 else "#27ae60"}">{avg:+.2f}%</td><td>{cnt}只</td><td>{tag} {bar}</td></tr>'
        if not show_inds:
            ind_heatmap_rows = '<tr><td colspan="5" style="color:#95a5a6">行业数据计算中...</td></tr>'
    else:
        ind_heatmap_rows = '<tr><td colspan="5" style="color:#95a5a6">暂无行业数据</td></tr>'
    
    # ═══ 尾盘20分钟资金涌入（从ind_30min_surge数据生成）═══
    tail_surge_html = ''
    if ind_30min_surge:
        sorted_surge = sorted(ind_30min_surge.items(), key=lambda x: -x[1])[:6]
        if sorted_surge and any(abs(v) > 0.1 for _, v in sorted_surge):
            surge_rows = ''
            for rank, (ind, surge) in enumerate(sorted_surge, 1):
                parts = str(ind).split(' ', 1)
                iname = parts[1][:12] if len(parts) >= 2 else ind
                trend = '🚀涌入' if surge > 0.3 else ('📈微涨' if surge > 0 else '📉微跌' if surge > -0.3 else '🔻出逃')
                surge_rows += f'<tr><td>{rank}</td><td style="text-align:left;padding-left:8px">{iname}</td><td style="color:{"#e74c3c" if surge>0 else "#27ae60"}">{surge:+.2f}%</td><td>{trend}</td></tr>'
            tail_surge_html = f'''
<div style="font-size:12px;font-weight:bold;color:#2c3e50;margin-top:10px;margin-bottom:4px">⚡ 尾盘20分钟资金涌入 (14:30~14:50)</div>
<div style="font-size:10px;color:#95a5a6;margin-bottom:4px">基于14:25/14:43价格快照与14:50实时价的差值计算</div>
<div style="overflow-x:auto"><table style="width:100%;font-size:11px"><thead><tr><th>排名</th><th>板块</th><th>尾盘涌入%</th><th>趋势</th></tr></thead><tbody>{surge_rows}</tbody></table></div>'''
    
    # ═══ 全量排名清单 ═══
    full_rank_rows = ''
    # 热门板块标记（行业均涨>0.3%为🔥, 跌<-0.8%为❄️）
    hot_inds = set()
    cold_inds = set()
    if live_ind_avg:
        for ind, avg in live_ind_avg.items():
            if avg > 0.3: hot_inds.add(ind)
            elif avg < -0.8: cold_inds.add(ind)
    for rank, (sc, s, ind, code, extra_risks) in enumerate(top10_result[:10], 1):
        pct_s = f'+{s["p"]:.1f}%' if s['p'] >= 0 else f'{s["p"]:.1f}%'
        pct_c = '#e74c3c' if s['p'] >= 0 else '#27ae60'
        full_ind = INDUSTRY_MAP.get(code, '')
        iname = ''
        ind_avg_str = '—'
        hot_tag = ''
        if full_ind:
            parts = str(full_ind).split(' ', 1)
            iname = parts[1][:10] if len(parts) >= 2 else str(full_ind)[:10]
            ia = live_ind_avg.get(full_ind, 0) if live_ind_avg else 0
            if ia != 0:
                ind_avg_str = f'{ia:+.1f}%'
            if full_ind in hot_inds:
                hot_tag = '🔥'
                iname = f'🔥{iname}'
            elif full_ind in cold_inds:
                hot_tag = '❄️'
                iname = f'❄️{iname}'
        # 利好/风险标签
        bullish_str = ''
        risk_str = ''
        if s.get('bullish'):
            bulls = s['bullish'][:2]
            bullish_str = ' '.join(f'🟢{b[0]}' for b in bulls)
        if s.get('risk_pts'):
            rps = s['risk_pts'][:2]
            risk_str = ' '.join(f'🔴{r[0]}' for r in rps)
        if not risk_str:
            risk_str = ' '.join(extra_risks) if extra_risks else '—'
        bg = '#fff8e1' if rank <= 3 else ('#fafafa' if rank <=5 else '')
        bg = '#fff5e6' if hot_tag == '🔥' and rank > 3 else bg  # 热门板块高亮
        full_rank_rows += f'<tr style="background:{bg}"><td>{"🥇" if rank==1 else "🥈" if rank==2 else "🥉" if rank==3 else str(rank)}</td><td style="text-align:left;padding-left:6px">{s["name"]}</td><td>{code}</td><td>¥{s["price"]:.2f}</td><td style="color:{pct_c}">{pct_s}</td><td>{sc:.0f}</td><td style="font-size:10px;text-align:left;padding-left:4px">{iname}</td><td style="font-size:10px">{ind_avg_str}</td><td style="font-size:9px;color:#2e7d32;text-align:left;padding-left:4px">{bullish_str[:30]}</td><td style="font-size:9px;color:#c0392b;text-align:left;padding-left:4px">{risk_str[:30]}</td><td style="font-size:9px">{s.get("buy_advice","")[:16]}</td></tr>'
    
    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>1170每日选股报告 {today_str}</title>
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
  V50 分而治之 · 每日选股报告 (30天{champ_pct}%版)
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

<!-- ═══ 行业热点板块变动 ═══ -->
<div class="card">
<h3>🔥 全天行业热度 (09:30~14:50)</h3>
<div style="font-size:11px;color:#7f8c8d;margin-bottom:4px">📊 时间周期: 早盘开盘至尾盘14:50（基于现价-昨收计算）</div>
<div style="overflow-x:auto;margin:8px 0">
<table style="min-width:800px"><thead><tr><th>排名</th><th>板块</th><th>全天均(09:30~14:50)</th><th>活跃数</th><th>热度条</th></tr></thead><tbody>
{ind_heatmap_rows}
</tbody></table>
</div>
<!-- 尾盘20分钟资金涌入（由Python生成，非JS） -->
{tail_surge_html}
</div>

<!-- ═══ 全量排名清单（完整信息） ═══ -->
<div class="card">
<h3>📋 全量候选排名 (#1~#10)</h3>
<div style="font-size:11px;color:#7f8c8d;margin-bottom:4px">📊 数据时间: 尾盘14:50实时行情 | 🏭 行业表现为板块全天均(09:30~14:50)</div>
<div class="scroll">
<table><thead><tr><th>#</th><th>名称</th><th>代码</th><th>买入价</th><th>当日%</th><th>评分</th><th>所属板块</th><th>板块表现</th><th>利好</th><th>风险</th><th>建议</th></tr></thead><tbody>
{full_rank_rows}
</tbody></table>
</div>
</div>

<div class="footer">
1170 分而治之 · 尾盘选股 {today_str} | {mk_cn} | 共{len(top10_result)}只候选
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
        update_py = os.path.join(V50_DIR, 'update_data_cache.py')
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
    
    print(f'🚀 V50 每日选股报告 | {today_str}', flush=True)
    print(f'📡 数据来源: {data_label} ({data_date})', flush=True)
    print(f'🎯 建议买入: {buy_date} 尾盘', flush=True)
    
    # 实时选今天（返回: scored[:10], mk_cn, used_level, stocks, indicators）
    top10_raw = pick_today()
    top10 = top10_raw[:3] if top10_raw else None  # 保持向后兼容
    
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
        # 📊 模拟盘：记录冠军买入
        try:
            champ = top10_raw[0][0]
            champ_code = champ[3]  # code
            champ_s = champ[1]     # stock dict
            from _paper_core import add_position
            pos = add_position(
                code=champ_code,
                name=champ_s['name'],
                buy_price=champ_s['price'],
                buy_pct=champ_s.get('p', 0) or 0,
                market_type=top10[1]
            )
            print(f'💰 模拟买入: {champ_s["name"]}({champ_code}) {champ_s["price"]:.2f}元 '
                  f'回望:从+3%回落0.3%卖', flush=True)
        except Exception as e:
            print(f'⚠️ 模拟盘记录失败: {e}', flush=True)

        live_ind_avg = top10_raw[5] if len(top10_raw) > 5 else {}
        html = build_html(top10[0], bt, None, today_str, f'{data_label}({data_date})', buy_date, top10[1], top10[2], bt_50=bt_50, bt_100=bt_100, live_ind_avg=live_ind_avg)
        
        # 存档
        arch = os.path.join(SCRIPTS_DIR, 'email_archive')
        os.makedirs(arch, exist_ok=True)
        fp = os.path.join(arch, f'{today_str}_V50_报告.html')
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'📁 已存档: {fp}', flush=True)
        
        # 发邮件（收件人从DB读取）
        try:
            sender = os.path.join(V50_DIR, 'send_email.py')
            subj = f'1170每日选股 {today_str} - {top10[1]} - 冠军{top10[0][0][1]["name"]}[{top10[0][0][1]["price"]:.2f}]'
            env = os.environ.copy()
            env['PYTHONPATH'] = SCRIPTS_DIR + os.pathsep + env.get('PYTHONPATH', '')
            r = subprocess.run([sys.executable, sender, subj, html, '--html', '--force'], timeout=60, capture_output=True, text=True, env=env)
            print(f'📧 {r.stdout.strip()}', flush=True)
        except Exception as e:
            print(f'❌ 邮件失败: {e}', flush=True)
        
        # 写入数据库日志
        try:
            log_selection_to_db('V50', today_str, top10[1], top10[2], len(top10[0]), top10[0])
        except Exception as e:
            print(f'⚠️ 数据库日志写入失败: {e}', flush=True)
        
        # 输出摘要到stdout
        print(f'\\n=== 1170 选股摘要 ===')
        print(f'今日推荐 ({top10[1]} {top10[2]}级):')
        for rank, (sc, s, ind, code, extra_risks) in enumerate(top10[0][:3], 1):
            ind_name = s.get('ind_name', '')
            ma_pos = s.get('ma_pos', '')
            advice = s.get('buy_advice', '')
            extras = []
            if ind_name: extras.append(f'行业{ind_name}')
            if ma_pos: extras.append(f'均线{ma_pos[:12]}')
            if advice: extras.append(advice[:30])
            extra_str = ' | '.join(extras)
            print(f'  {rank}. {s["name"]}({code}) ¥{s["price"]:.2f} 当日{s["p"]:+.1f}% 评分{sc:.0f}')
            if extra_str:
                print(f'     {extra_str}')
        import sqlite3
        _db = sqlite3.connect(os.path.join(SCRIPTS_DIR, 'v13_quant.db'), timeout=10)
        _c = _db.execute('SELECT COUNT(*) FROM selection_candidates WHERE version=?', ('V50',))
        _prod_cnt = _c.fetchone()[0] or 0
        _db.close()
        print(f'📊 历史回测30天: {bt[0]}/{bt[1]} = {bt[0]*100/bt[1]:.1f}%' if bt[1] else '📊 历史回测30天: 暂无')
        if bt_50: print(f'📊 历史回测50天: {bt_50[0]}/{bt_50[1]} = {bt_50[0]*100/bt_50[1]:.1f}%')
        if bt_100: print(f'📊 历史回测100天: {bt_100[0]}/{bt_100[1]} = {bt_100[0]*100/bt_100[1]:.1f}%')
        print(f'📊 V50生产记录总数: {_prod_cnt}条')
    else:
        print('❌ 选股失败')