"""
V51 全方位信息面板 — 形态历史胜率 + 板块热度 + 资金流向 + 有利/有害因素

使用：
  from v51_analysis import analyze_stock, get_hot_sectors
  result = analyze_stock(stock_dict, mk_cn)
  
返回：
  {
    'warnings': [...],  # 形态警告+历史胜率
    'positives': [...], # 有利因素
    'negatives': [...], # 有害因素
    'industry': '...',  # 所属行业
    'is_hot_sector': True/False,  # 是否热门板块
  }
"""

import os, json, subprocess, urllib.parse, re

# ===== 形态历史胜率（从200天回测得出） =====
PATTERN_STATS = {
    '超买放量':       {'total': 0, 'win': 0, 'wr': '0%', 'note': '极罕见'},
    '超高价¥150+':    {'total': 5, 'win': 3, 'wr': '60%', 'note': '低于基准-10%'},
    '跌日高价大涨':   {'total': 3, 'win': 3, 'wr': '100%', 'note': '极高胜率'},
    '跌日高位高价':   {'total': 6, 'win': 5, 'wr': '83%', 'note': '高于基准'},
    '放量不涨':       {'total': 0, 'win': 0, 'wr': '0%', 'note': '极罕见'},
}
BASELINE_WR = '69.7%'


def curl_get(url, timeout=8):
    """获取URL内容（UTF-8）"""
    try:
        r = subprocess.run(['curl', '-s', '--max-time', str(timeout), url],
                          capture_output=True, timeout=timeout+3)
        return r.stdout.decode('utf-8', errors='replace')
    except:
        return ''


def curl_get_gbk(url, timeout=8):
    """获取URL内容（GBK）"""
    try:
        r = subprocess.run(['curl', '-s', '--max-time', str(timeout), url],
                          capture_output=True, timeout=timeout+3)
        return r.stdout.decode('gbk', errors='replace')
    except:
        return ''


# ── 行业/板块数据缓存 ──
_industry_cache = {}
_hot_sectors_cache = None

def get_stock_industry(code, name=''):
    """从本地DB获取股票行业"""
    global _industry_cache
    if code in _industry_cache:
        return _industry_cache[code]
    
    try:
        import sqlite3
        db = os.path.expanduser('~/AppData/Local/hermes/prod/data/v13_quant.db')
        c = sqlite3.connect(db, timeout=5)
        row = c.execute('SELECT industry FROM stock_industry WHERE code=?', (code,)).fetchone()
        c.close()
        if row:
            _industry_cache[code] = row[0]
            return row[0]
    except:
        pass
    _industry_cache[code] = name[:6] if name else '其他'
    return _industry_cache[code]


def get_hot_sectors(top_n=10):
    """获取今日热门板块（东方财富板块涨幅排名）"""
    global _hot_sectors_cache
    if _hot_sectors_cache is not None:
        return _hot_sectors_cache
    
    hot = []
    try:
        url = 'https://push2.eastmoney.com/api/qt/clist/get?cb=&pn=1&pz=20&po=1&np=1&fields=f2,f3,f4,f12,f14&fid=f3&fs=m:90+t:2'
        text = curl_get(url)
        if text and 'diff' in text:
            import json as _json
            text = text.strip().lstrip('\ufeff')
            data = _json.loads(text)
            for item in data.get('data', {}).get('diff', []):
                name = item.get('f14', '')
                pct = item.get('f3', 0)
                if pct is None: pct = 0
                hot.append({'name': name, 'pct': pct})
    except:
        pass
    _hot_sectors_cache = hot[:top_n]
    return _hot_sectors_cache[:top_n]


def get_capital_flow(code):
    """获取个股主力资金流向"""
    try:
        url = f'https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get?secid=0.{code[2:] if code.startswith("0") else "1."+code if code.startswith(("3","6","9")) else "0."+code}&fields=f1,f2,f3,f7,f8,f9,f10,f11&lmt=1'
        text = curl_get(url)
        if text and 'data' in text:
            import json
            data = json.loads(text)
            kl = data.get('data', {}).get('klines', [])
            if kl:
                parts = kl[0].split(',')
                # f2=主力净流入, f3=小单净流入
                main_in = float(parts[1]) if len(parts) > 1 else 0
                small_in = float(parts[2]) if len(parts) > 2 else 0
                return {'main_net': round(main_in/10000, 1), 'small_net': round(small_in/10000, 1)}
    except:
        pass
    return None


# ═══════════════════════════════════════════
# 板块热度 — 从big_cache数据直接计算
# ═══════════════════════════════════════════

_industry_map_cache = None
_hot_sectors_cache_local = None
_STOCK_INDUSTRY_CODE_PREFIX = re.compile(r'^\d+')

def _strip_industry_code(name):
    """去掉行业名前缀数字编码，如'39计算机...' → '计算机...'"""
    return _STOCK_INDUSTRY_CODE_PREFIX.sub('', name) if name else '其他'

def _get_industry_map():
    """从本地DB加载股票→行业映射（缓存）"""
    global _industry_map_cache
    if _industry_map_cache is not None:
        return _industry_map_cache
    try:
        import sqlite3
        _db = sqlite3.connect(os.path.join(os.path.expanduser('~/AppData/Local/hermes/prod'), 'data', 'v13_quant.db'), timeout=5)
        _rows = _db.execute('SELECT code, industry FROM stock_industry').fetchall()
        _db.close()
        _industry_map_cache = {r[0]: r[1] for r in _rows}
    except:
        _industry_map_cache = {}
    return _industry_map_cache

def get_hot_sectors_from_cache(top_n=10):
    """
    从big_cache数据直接计算板块热度
    返回 [{name, avg_pct, rank, count, avg_vr}, ...]
    比外部API更稳定，且数据与回测一致
    """
    global _hot_sectors_cache_local
    if _hot_sectors_cache_local is not None:
        return _hot_sectors_cache_local[:top_n]
    
    _cp = os.path.join(os.path.expanduser('~/AppData/Local/hermes/prod'), 'data', 'big_cache_full.pkl')
    if not os.path.exists(_cp):
        return []
    
    try:
        import pickle as _pkl
        from collections import defaultdict as _dd
        with open(_cp, 'rb') as _f:
            _c = _pkl.load(_f)
        _data = _c.get('data', {})
        _dkeys = sorted(_data.keys())
        _stocks = _data.get(_dkeys[-1], [])
        
        _im = _get_industry_map()
        _groups = _dd(lambda: {'pcts': [], 'vrs': [], 'codes': set()})
        
        for _s in _stocks:
            if not isinstance(_s, dict): continue
            _cd = _s.get('code')
            _p = _s.get('p', 0) or 0
            _vr = _s.get('vol_ratio', 1) or 1
            if abs(_p) > 15: continue
            _ind = _im.get(_cd, '其他')
            _groups[_ind]['pcts'].append(_p)
            _groups[_ind]['vrs'].append(_vr)
            _groups[_ind]['codes'].add(_cd)
        
        _sectors = []
        for _n, _g in _groups.items():
            if len(_g['codes']) < 3: continue
            _sectors.append({
                'name': _strip_industry_code(_n),
                'avg_pct': round(sum(_g['pcts'])/len(_g['pcts']), 2),
                'avg_vr': round(sum(_g['vrs'])/len(_g['vrs']), 2),
                'count': len(_g['codes']),
            })
        
        _sectors.sort(key=lambda x: -x['avg_pct'])
        for _i, _s in enumerate(_sectors):
            _s['rank'] = _i + 1
        
        _hot_sectors_cache_local = _sectors[:30]
    except:
        _hot_sectors_cache_local = []
    return _hot_sectors_cache_local[:top_n]


# ═══════════════════════════════════════════
# 个股IQ评分 — 全年走势·涨停活跃度·趋势分析
# 只用于解读，不参与选股排名
# ═══════════════════════════════════════════

import pickle as _pickle
from collections import defaultdict as _defaultdict

_stock_iq_cache = None

def _ensure_stock_index():
    """懒加载big_cache的个股历史索引，只加载一次"""
    global _stock_iq_cache
    if _stock_iq_cache is not None:
        return _stock_iq_cache
    
    _cache_path = os.path.join(os.path.expanduser('~/AppData/Local/hermes/prod'), 'data', 'big_cache_full.pkl')
    if not os.path.exists(_cache_path):
        _stock_iq_cache = {}
        return {}
    
    try:
        with open(_cache_path, 'rb') as _f:
            _c = _pickle.load(_f)
        _data, _names, _dkeys = _c.get('data',{}), _c.get('names',{}), sorted(_c.get('data',{}).keys())
        
        _sh = _defaultdict(list)
        for _d in _dkeys:
            for _s in _data.get(_d, []):
                if isinstance(_s, dict):
                    _cd = _s.get('code')
                    if _cd:
                        _sh[_cd].append({
                            'date': _d, 'close': _s.get('close',0) or 0,
                            'p': _s.get('p',0) or 0,
                        })
        _stock_iq_cache = {'history': dict(_sh), 'names': _names}
    except:
        _stock_iq_cache = {}
    return _stock_iq_cache

def compute_stock_iq(code):
    """
    个股IQ评分：看走势趋势、涨停活跃度、多波上涨、死猫跳检测
    
    返回 dict 含:
      iq: 0-100
      rating: 🟢好票/✅良好/👀一般/⚠️偏弱/🔴弱势
      summary: 一句话描述
      total_return, r60d, r30d, zt, up_ratio
    """
    _idx = _ensure_stock_index()
    _hist = _idx.get('history', {}).get(code, [])
    if len(_hist) < 15:
        return None
    
    _n = len(_hist)
    _fc, _lc = _hist[0]['close'], _hist[-1]['close']
    _tr = (_lc / _fc - 1) * 100 if _fc else 0
    
    # 近期表现
    _r60 = _hist[-60:] if _n >= 60 else _hist
    _r30 = _hist[-30:] if _n >= 30 else _hist
    _r60r = (_r60[-1]['close'] / _r60[0]['close'] - 1) * 100 if _r60[0]['close'] else 0
    _r30r = (_r30[-1]['close'] / _r30[0]['close'] - 1) * 100 if _r30[0]['close'] else 0
    
    # 涨停
    _zt = sum(1 for h in _hist if h['p'] >= 9.5)
    
    # 近期涨跌比
    _r30_p = [h['p'] for h in _r30]
    _up_r = sum(1 for p in _r30_p if p > 0) / max(len(_r30_p), 1)
    
    # 趋势一致 - 每20天切片
    _cs = 20
    _chunks = [_hist[i:i+_cs] for i in range(0, _n, _cs)]
    _crs = [(c[-1]['close'] / c[0]['close'] - 1) * 100 for c in _chunks if len(c) >= 5 and c[0]['close']]
    _pos_c = sum(1 for cr in _crs if cr > 0)
    _cons = _pos_c / max(len(_crs), 1)
    
    # 多波上涨(≥15%算一波)
    _waves = sum(1 for cr in _crs if cr > 15)
    
    # 死猫跳: 前70%跌>15% + 后30%涨>20%
    _sp = int(_n * 0.7)
    _early_t = (_hist[_sp]['close'] / _hist[0]['close'] - 1) * 100 if _hist[0]['close'] else 0
    _late_s = (_hist[-1]['close'] / _hist[_sp]['close'] - 1) * 100 if _hist[_sp]['close'] else 0
    _dc = _early_t < -15 and _late_s > 20
    
    # === 评分 [基础35分] ===
    def _score(val, *thresholds):
        for t, s in thresholds:
            if val >= t: return s
        return thresholds[-1][1]
    
    _s_tr = _score(_tr, (80,15), (30,10), (0,5), (-15,-3), (-999,-8))
    _s_r60 = _score(_r60r, (15,12), (5,7), (-5,3), (-15,-5), (-999,-10))
    _s_r30 = _score(_r30r, (8,10), (3,6), (-3,2), (-8,-4), (-999,-8))
    _s_zt = _score(_zt, (8,12), (4,8), (2,5), (1,2), (0,-3))
    _s_ur = _score(_up_r, (0.6,8), (0.5,4), (0.4,0), (0.3,-5), (0,-8))
    _s_cw = 10 if _cons >= 0.65 and _waves >= 2 else (
             6 if _cons >= 0.6 else 2 if _cons >= 0.5 else -2 if _cons >= 0.4 else -6)
    _s_dc = -20 if _dc else 0
    
    _total = 35 + _s_tr + _s_r60 + _s_r30 + _s_zt + _s_ur + _s_cw + _s_dc
    _iq = max(0, min(100, _total))
    
    # 评级
    if _iq >= 78:  _rating = '🟢好票'
    elif _iq >= 62: _rating = '✅良好'
    elif _iq >= 46: _rating = '👀一般'
    elif _iq >= 30: _rating = '⚠️偏弱'
    else:           _rating = '🔴弱势'
    
    # 一句话描述
    _d = []
    if _dc: _d.append('⚠️警惕死猫跳')
    if _r30r > 5 and _r60r > 10: _d.append('📈近期强势')
    elif _r30r > 0: _d.append('↗️近期偏强')
    elif _r30r > -5: _d.append('➡️近期平淡')
    else: _d.append('📉近期下跌')
    if _tr > 0: _d.append(f'累计涨{_tr:.0f}%')
    else: _d.append(f'累计跌{_tr:.1f}%')
    if _zt >= 8: _d.append(f'涨停{_zt}次🔥')
    elif _zt >= 3: _d.append(f'涨停{_zt}次')
    
    return {
        'iq': _iq, 'rating': _rating,
        'summary': ' · '.join(_d),
        'total_return': round(_tr, 1),
        'r60d': round(_r60r, 1),
        'r30d': round(_r30r, 1),
        'zt': _zt,
        'up_ratio': round(_up_r, 2),
        'waves': _waves,
        'dead_cat': _dc,
    }

# ═══ 254次冠军(341天)真实数据 ═══
# 涨幅p: p<4%胜率51% | p≥4%胜率69% | 差距-18%（最强区分因子）
# 位置CL: CL≥75胜率62% | CL<75胜率75% | 差距-13%（阈值75非85）
# 超买WR: WR<10胜率61% | WR15~30胜率72% | 差距-11%
# 换手HSL: HSL<8%胜率58% | HSL≥8%胜率66% | 差距-8%
# 量比VR>2.0反更高75%，不做扣分项
# 股价各区间56~67%，差距不大，不做主判断

def check_p(pv):
    ok = pv >= 4
    wr_str = "69%" if ok else "51%"
    diff = "(+18%)" if ok else "(-18%)"
    return (ok, f'p={pv:+.1f}%', f'{"≥4%" if ok else "<4%"} 历史{wr_str}胜率{diff}')

def check_cl(cl):
    ok = cl < 75
    return (ok, f'CL={cl:.0f}', f'{"安全<75" if ok else "高位≥75"} 历史:{"75%" if ok else "62%"}胜率{"(+13%)" if ok else "(-13%)"}')

def check_wr(wr):
    ok = wr >= 15
    return (ok, f'WR={wr:.0f}', f'{"安全≥15" if ok else "偏低<15"} 历史:{"72%" if ok else "60%"}胜率{"(+12%)" if ok else "(-12%)"}')

def check_hsl(hsl):
    """换手活跃"""
    ok = hsl >= 8
    return (ok, f'HSL={hsl:.1f}%', f'{"活跃≥8%" if ok else "偏低<8%"} 历史:{"66%" if ok else "58%"}胜率{"(+8%)" if ok else "(-8%)"}')

def check_vr(vr, pv):
    if vr > 2.0:
        return ('info', f'VR={vr:.1f}x', f'放量不是风险(历史75%胜率)')
    elif vr < 0.6:
        return ('info', f'VR={vr:.1f}x', f'缩量不明显')
    return None

def check_price(price):
    if price > 120:
        return ('info', f'¥{price:.0f}', f'高价但非主要风险(历史67%胜率)')
    elif price > 80:
        return ('info', f'¥{price:.0f}', f'偏高但非主要风险(历史67%胜率)')
    return None


# 智商评分配置（254次冠军341天数据）
BASE_SCORE = 62  # 基准分 = 平均胜率62.2%
SCORE_MAP = {
    'p':    {True: 7, False: -11},   # ≥4%:+7, <4%:-11
    'cl':   {True: 13, False: 0},    # <75:+13, ≥75:0
    'wr':   {True: 10, False: -2},   # ≥15:+10, <15:-2
    'hsl':  {True: 4, False: -4},    # ≥8%:+4, <8%:-4
}

def get_rating(iq_score):
    if iq_score >= 82: return ('🟢优秀', '放心买')
    if iq_score >= 72: return ('✅良好', '可考虑')
    if iq_score >= 62: return ('👀一般', '谨慎参考')
    if iq_score >= 52: return ('⚠️偏低', '建议观望')
    return ('🔴较差', '不推荐')


def analyze_stock(s, ind, code, mk_cn, market_avg_pct=0):
    """
    4项✅/❌数据驱动判断 + 综合智商评分
    返回: {checks:[], details:[], score:int, iq_score:int, rating:str, advice:str, refs:[]}
    """
    pv = s.get('p', 0) or 0
    close_price = s.get('close', 0) or s.get('price', 0) or 0
    wr = s.get('wrv', 50) or (ind.get('wr', 50) if ind else 50)
    cl = s.get('cl', 50) or (ind.get('cl', 50) if ind else 50)
    vr = s.get('vol_ratio', 1) or 1
    hsl = s.get('hsl', 0) or 0
    dif = s.get('dif', 0) or (ind.get('dif', 0) if ind else 0)
    mg = s.get('mg', 0) or (ind.get('macd_golden', 0) if ind else 0)
    name = s.get('name', s.get('nm', ''))
    
    checks = []
    details = []
    refs = []
    iq_score = BASE_SCORE
    
    # ═══ 4项核心判断（带分数贡献） ═══
    for label, key, fn, val in [('涨幅','p', check_p, pv), ('位置','cl', check_cl, cl), 
                                 ('超买','wr', check_wr, wr), ('换手','hsl', check_hsl, hsl)]:
        ok, v, desc = fn(val)
        pts = SCORE_MAP[key][ok]
        iq_score += pts
        checks.append((label, ok, v, f'{desc} [{pts:+d}分]'))
    
    rating, advice = get_rating(iq_score)
    
    # 额外参考信息（不影响分数）
    vr_info = check_vr(vr, pv)
    if vr_info:
        details.append(f'💡 {vr_info[2]}')
    price_info = check_price(close_price)
    if price_info:
        details.append(f'💡 {price_info[2]}')
    
    # ═══ 详细信息 ═══
    clean_ind = _strip_industry_code(get_stock_industry(code, name) or '其他')
    details.append(f'🏭 {clean_ind}')
    if mg: details.append('📊 MACD金叉')
    if dif > 0: details.append(f'📈 DIF+{dif:.2f}')
    
    flow = get_capital_flow(code)
    if flow:
        mn = flow['main_net']
        if abs(mn) > 50: details.append(f'💰主力{"+%d万" % mn if mn>0 else "%d万" % mn}')
    
    # ═══ 板块热度（从big_cache本地计算）═══
    hot_sectors = get_hot_sectors_from_cache(top_n=15)
    industry = get_stock_industry(code, name)
    if industry and hot_sectors:
        for hs in hot_sectors:
            if hs['name'] in clean_ind or clean_ind in hs['name']:
                details.append(f'🔥{hs["name"]} #{hs["rank"]} 今日{hs["avg_pct"]:+.1f}%({hs["count"]}只)')
                break
    
    # 失败案例参考
    if wr < 10 and vr > 1.8: refs.append('合锻智能6/5(-8.5%)')
    if mk_cn == '跌日' and close_price > 80 and pv > 5: refs.append('江顺科技6/8(-7.8%)')
    if mk_cn == '跌日' and close_price > 80 and cl > 70: refs.append('鹏鼎控股6/9(-4.4%)')
    if close_price > 150: refs.append('松发股份6/10(待验证)')
    if vr > 2.0 and 0 < pv < 2: refs.append('放量不涨风险')
    
    # ═══ 个股IQ评分 ═══
    stock_iq = compute_stock_iq(code)
    
    return {
        'checks': checks,
        'details': details[:5],
        'score': len([c for c in checks if c[1]]),  # ✅数量
        'iq_score': iq_score,
        'rating': rating,
        'advice': advice,
        'refs': refs,
        'stock_iq': stock_iq,  # 个股IQ评分
    }
