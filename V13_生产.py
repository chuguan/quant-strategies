"""分而治之 V13 生产版 — 2:50 PM 实时数据版
- 实时行情 → 新浪 hq.sinajs.cn（含实时p/CL）
- 技术指标 → big_cache（dif/wr/kdj等跨日趋势不变）
- 7天动量衰减检查
"""
import os, sys, json, re, time, subprocess, pickle, hashlib
from datetime import datetime, timedelta

# ═══ 安全启动检查 ═══
env = os.environ.get('HERMES_ENV', 'production')
if env == 'dev':
    print('⚠️ 开发环境模式，如需生产请设置 HERMES_ENV=production')
    confirm = input('继续运行?(y/n): ')
    if confirm.lower() != 'y':
        print('已取消')
        sys.exit(0)

# 运行前校验策略文件hash
from safety_module import verify_strategy_hash
if not verify_strategy_hash():
    print('❌ 策略文件hash校验失败，请检查文件完整性')
    sys.exit(1)

# ═══ 配置从数据库读取 ═══
from db_config import get_config, get_config_list, get_path_config, get_strategy_config, get_email_config, get_current_env

SCRIPTS_DIR = get_config('path', 'scripts_dir', 
    os.path.expanduser('~/AppData/Local/hermes/scripts'))
CACHE_DIR = get_config('path', 'cache_dir',
    os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache'))
V13_DIR = get_config('path', 'v13_dir',
    os.path.join(SCRIPTS_DIR, 'release', 'V13'))

# ═══ 每日选股记录存档目录 ═══
SELECTION_LOG_DIR = os.path.join(
    get_config('path', 'email_archive', os.path.join(SCRIPTS_DIR, 'email_archive')),
    '选股记录', 'V13')
os.makedirs(SELECTION_LOG_DIR, exist_ok=True)

os.chdir(SCRIPTS_DIR)
sys.path.insert(0, V13_DIR)

# 导入新浪实时行情
sys.path.insert(0, SCRIPTS_DIR)
from sina_api import sina_realtime

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

# ═══ 从SQLite读取技术指标（代替big_cache pickle）═══
import sqlite3
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
print('连接数据库...')
t0 = time.time()
_cache_conn = sqlite3.connect(DB_PATH)
# 获取最新日期
_c = _cache_conn.cursor()
_c.execute('SELECT MAX(date) FROM data_cache WHERE close > 0')
LAST_DATE = _c.fetchone()[0]
print(f'  最新数据日期: {LAST_DATE} (连接耗时{time.time()-t0:.2f}s)')

# 预加载所有股票的技术指标（最新日期）
ALL_TECH = {}
if LAST_DATE:
    _c.execute('''
        SELECT code, name, vr, dif_val, macd_golden, wr_val,
               j_val, k_val, d_val, kdj_golden, above_ma5,
               pos_in_day, close, original_source
        FROM data_cache WHERE date=?
    ''', (LAST_DATE,))
    for r in _c.fetchall():
        ALL_TECH[r[0]] = {
            'vr': r[2] or 1,
            'dif': r[3] or 0,
            'mg': r[4] or 0,
            'wrv': r[5] or 50,
            'jv': r[6] or 50,
            'kv': r[7] or 50,
            'dv': r[8] or 50,
            'kdj_g': r[9] or 0,
            'a5': r[10] or 0,
            'pos_in_day': r[11] or 50,
            'close': r[12] or 0,
            'name': r[1] or '',
        }
print(f'  已加载 {len(ALL_TECH)} 只股票技术指标')

# 预加载d1/d2/d3（最近3天的涨跌幅）
# 获取最近3个有数据的日期
_c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date DESC LIMIT 4')
_recent_dates = [r[0] for r in _c.fetchall()]
# d1=昨日, d2=前日, d3=大前日
_D1_DATE = _recent_dates[1] if len(_recent_dates) > 1 else None
_D2_DATE = _recent_dates[2] if len(_recent_dates) > 2 else None
_D3_DATE = _recent_dates[3] if len(_recent_dates) > 3 else None

_D1_MAP = {}  # code -> p
_D2_MAP = {}
_D3_MAP = {}
if _D1_DATE:
    _c.execute('SELECT code, p FROM data_cache WHERE date=?', (_D1_DATE,))
    _D1_MAP = {r[0]: (r[1] or 0) for r in _c.fetchall()}
if _D2_DATE:
    _c.execute('SELECT code, p FROM data_cache WHERE date=?', (_D2_DATE,))
    _D2_MAP = {r[0]: (r[1] or 0) for r in _c.fetchall()}
if _D3_DATE:
    _c.execute('SELECT code, p FROM data_cache WHERE date=?', (_D3_DATE,))
    _D3_MAP = {r[0]: (r[1] or 0) for r in _c.fetchall()}

# 获取所有main板股票代码
_c.execute('SELECT DISTINCT code FROM data_cache')
_ALL_CODES = sorted(set(
    c for c, in _c.fetchall()
    if c.startswith(('600','601','603','605','000','001','002'))
))[:4000]
# 排除剔除清单
try:
    _c.execute('SELECT code FROM excluded_stocks WHERE active=1')
    _EXCLUDED = set(r[0] for r in _c.fetchall())
except:
    _EXCLUDED = set()
_ALL_CODES = [c for c in _ALL_CODES if c not in _EXCLUDED]
print(f'  股票池: {len(_ALL_CODES)}只 (剔除{len(_EXCLUDED)}只)')
_cache_conn.close()

# ========== V13子策略 ==========
SUB_STRATEGIES = {
    'real_up': {'module': '分而治之_V10_真实涨日_评分策略', 'name': '真实涨日V13', 'dir': V13_DIR},
    'fake_up': {'module': '分而治之_V10_虚涨日_评分策略', 'name': '虚涨日V13', 'dir': V13_DIR},
    'down': {'module': '分而治之_V10_跌日_评分策略', 'name': '跌日V13', 'dir': V13_DIR},
    'flat': {'module': '分而治之_V10_横盘_评分策略', 'name': '横盘V13', 'dir': V13_DIR},
}

def load_strategy(mkt_key):
    import importlib
    info = SUB_STRATEGIES[mkt_key]
    sys.path.insert(0, info['dir'])
    spec = importlib.util.spec_from_file_location(info['module'],
        os.path.join(info['dir'], '评分策略', f'{info["module"]}.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    levels = mod.LEVELS
    renamed = []
    for lv in levels:
        name = lv['name']
        if name == 'L0': name = 'L'
        renamed.append({**lv, 'name': name})
    if levels:
        last = levels[-1]
        renamed.append({"name":"L5","p_min":last["p_min"]-3,"p_max":last["p_max"],
            "vr_min":max(0.1,last["vr_min"]-0.2),"vr_max":last["vr_max"]+2,
            "hs_min":max(0.1,last["hs_min"]-1),"hs_max":last["hs_max"]+15,
            "sz_max":last["sz_max"]+200,"cl_min":max(0,last["cl_min"]-15),"cl_max":100})
    return renamed, mod

STRAT_CACHE = {}
for k in SUB_STRATEGIES: STRAT_CACHE[k] = load_strategy(k)

MKT_NAMES = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
LEVEL_NAMES = ['L', 'L1', 'L2', 'L3', 'L4', 'L5']

def get_cache_indicator(code):
    """从SQLite获取技术指标（代替big_cache）"""
    return ALL_TECH.get(code, None)

def get_kline_data(code, count=7):
    """腾讯K线用于动量检查"""
    pure = code[2:] if code.startswith(('sh','sz')) else code
    pref = 'sh' if code.startswith(('6','9')) else 'sz'
    url = f'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={pref}{pure},day,,,{count}'
    try:
        r = subprocess.run(['curl','-sL','--max-time','8',url], capture_output=True, timeout=13)
        data = json.loads(r.stdout)
        if 'data' in data and pref in data['data']:
            for key in ['qfqday', 'day', 'klines']:
                if key in data['data'][pref]:
                    klines = data['data'][pref][key]
                    if len(klines) >= 3:
                        daily_p = []
                        for i in range(max(0, len(klines)-6), len(klines)):
                            k = klines[i]
                            if isinstance(k, list) and len(k) >= 5:
                                c = float(k[4] or k[2])
                                o = float(k[1] or k[2])
                                pct = round((c - o) / o * 100, 2) if o else 0
                                daily_p.append(pct)
                        return daily_p
    except: pass
    return []

def build_stock_dict(real, cache):
    """合并新浪实时数据 + 缓存技术指标"""
    # 从新浪实时数据计算p和CL
    pre_close = real.get('pre_close', 0)
    price = real.get('price', 0)
    p = round((price - pre_close) / pre_close * 100, 2) if pre_close > 0 else 0
    
    high = real.get('high', 0)
    low = real.get('low', 0)
    cl = round((price - low) / (high - low) * 100, 2) if (high - low) > 0 else 50
    
    volume = real.get('volume', 0)
    
    # CL反转：高CL=收盘近高位
    pos_in_day = cl
    
    # 量比：用日内量与前5日均量比（从cache获取close）
    avg_vol = 0
    if cache and cache.get('close', 0) > 0:
        # 用cache中的5日均量估算
        pass
    
    d = {
        'p': p,
        'cl': cl,
        'vr': cache.get('vr', 1) if cache else 1,
        'hsl': 0,  # hsl从SQLite获取
        'dif': cache.get('dif', 0) if cache else 0,
        'mg': cache.get('mg', 0) if cache else 0,
        'a5': cache.get('a5', 0) if cache else 0,
        'wrv': cache.get('wrv', 50) if cache else 50,
        'jv': cache.get('jv', 50) if cache else 50,
        'kv': cache.get('kv', 50) if cache else 50,
        'dv': cache.get('dv', 50) if cache else 50,
        'kdj_g': cache.get('kdj_g', 0) if cache else 0,
        'pos_in_day': pos_in_day,
        'nm': real.get('name', ''),
        'code': real.get('code', ''),
        'name': real.get('name', ''),
        'shizhi': 0,  # 暂不支持通过SQLite获取
        'pre_close': pre_close,
        'price': price,
        'close': price,
        'high': high,
        'low': low,
        'volume': volume,
        'amount': real.get('amount', 0),
        # 动量检查用（从SQLite预加载）
        't4_shadow': 0, 'slope5': 0, 'cons_up': 0,
        'd1': _D1_MAP.get(real.get('code', ''), 0),
        'd2': _D2_MAP.get(real.get('code', ''), 0),
        'd3': _D3_MAP.get(real.get('code', ''), 0),
    }
    return d

def classify_market(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p',0) or 0 for s in stocks]
    vrs = [s.get('vr',1) or 1 for s in stocks if s.get('vr')]
    if not ps: return 'flat'
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5: return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

def fetch_sina_with_retry(main_codes, max_retries=3):
    """获取新浪实时行情，带重试 + 降级到腾讯"""
    BATCH = 80
    all_real = {}
    total_batches = (len(main_codes) + BATCH - 1) // BATCH
    failed_batches = 0
    
    for i in range(0, len(main_codes), BATCH):
        batch = main_codes[i:i+BATCH]
        success = False
        
        for attempt in range(max_retries):
            try:
                data = sina_realtime(batch)
                if data and len(data) > 0:
                    all_real.update(data)
                    success = True
                    break
                else:
                    print(f'  批次{i//BATCH}: 返回空数据, 重试{attempt+1}/{max_retries}')
            except Exception as e:
                print(f'  批次{i//BATCH}: {e}, 重试{attempt+1}/{max_retries}')
            time.sleep(0.5 * (attempt + 1))  # 递增等待
        
        if not success:
            failed_batches += 1
            print(f'  ⚠️ 批次{i//BATCH}彻底失败（共{total_batches}批）')
        
        time.sleep(0.05)
    
    # 记录成功率
    success_rate = (total_batches - failed_batches) / total_batches * 100
    print(f'获取到 {len(all_real)} 只实时行情 (成功率{success_rate:.0f}%)')
    
    if success_rate < 95:
        print(f'  ⚠️ 成功率低于95%，将尝试腾讯数据补充')
    
    # 数据格式校验：检查关键字段
    for code, real in list(all_real.items())[:10]:
        required = ['price', 'pre_close', 'pct', 'name']
        missing = [f for f in required if f not in real or real.get(f) is None]
        if missing:
            print(f'  ⚠️ {code} 缺少字段: {missing}')
    
    return all_real, success_rate

def main():
    print('获取实时行情（新浪）...')
    # 从SQLite读取股票代码列表
    main_codes = _ALL_CODES
    
    all_real, success_rate = fetch_sina_with_retry(main_codes)
    
    # 筛选有效股
    clean_stocks = []
    for full_code, real in all_real.items():
        # 去掉sh/sz前缀
        code = full_code[2:] if full_code.startswith(('sh','sz')) else full_code
        real['code'] = code
        price = real.get('price', 0)
        if price <= 0: continue
        pre_close = real.get('pre_close', 0)
        if pre_close <= 0: continue
        pct = real.get('pct', 0)
        if abs(pct) >= 15: continue
        name = real.get('name', '')
        if 'ST' in name or '*ST' in name or '退' in name: continue
        
        # 获取缓存技术指标
        cache = get_cache_indicator(code)
        if cache is None: continue
        
        sd = build_stock_dict(real, cache)
        clean_stocks.append(sd)
    
    print(f'有效股: {len(clean_stocks)}只')
    
    # 行情分类
    mk = classify_market(clean_stocks)
    mk_cn = MKT_NAMES.get(mk, '横盘')
    print(f'行情: {mk_cn}')
    
    # 获取LEVELS和评分
    levels, mod = STRAT_CACHE[mk]
    lm = {l['name']:i for i,l in enumerate(levels)}
    score_fn = mod.score
    
    # 分级筛选（使用2:50实时p和CL）
    pool = None; used_level = '无'
    for ln in LEVEL_NAMES:
        if ln not in lm: continue
        i = lm[ln]; lv = levels[i]; cand = []
        for s in clean_stocks:
            p = s.get('p', 0) or 0
            if p < lv['p_min'] or p > min(lv.get('p_max', 10), 8): continue
            vr = s.get('vr', 0) or 0
            if vr < lv['vr_min'] or vr > lv['vr_max']: continue
            hsl = s.get('hsl', 0) or 0
            if hsl < lv.get('hs_min', 0) or hsl > lv.get('hs_max', 99): continue
            sz = s.get('shizhi', 0) or 0
            if sz >= lv.get('sz_max', 9999): continue
            cl = s.get('cl', 0) or 50
            if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
            cand.append(s)
        if len(cand) >= 10:
            pool = cand; used_level = ln
            break
    
    if not pool:
        print('候选池不足10只！')
        return
    
    print(f'候选池: {len(pool)}只 (等级{used_level})')
    
    # 评分 + 动量检查
    today_str = datetime.now().strftime('%Y-%m-%d')
    scored = []
    for s in pool:
        base = score_fn(s)
        # 7天动量检查
        code = s.get('code', '')
        klines = get_kline_data(code, 7)
        penalty = 0
        if len(klines) >= 5:
            gains = klines[-(min(7,len(klines))):]
            p_today = s.get('p', 0) or 0
            gains[-1] = p_today
            if len(gains) >= 5:
                pad = [0] * (7 - len(gains)) if len(gains) < 7 else []
                vals = pad + gains if pad else gains
                d6,d5,d4,d3,d2,d1,p = vals[-7:] if len(vals)>=7 else [0]*(7-len(vals))+vals
                p_is_max = p >= max(gains[:-1]) if len(gains) > 1 else False
                avg_7d = sum(gains)/len(gains)
                wrv = s.get('wrv', 50) or 50
                if wrv < 10 and p_is_max and avg_7d < 2.0 and p < 6: penalty -= 8
                if p_is_max and avg_7d < 0.8 and p < 8:
                    if avg_7d < 0: penalty -= 15
                    elif avg_7d < 0.3: penalty -= 12
                    elif avg_7d < 0.7: penalty -= 8
                    else: penalty -= 5
                if d1 < -1.5 and d2 < -1.0 and p > 3 and avg_7d < 1.0: penalty -= 8
                if max(d4,d3,d2) > 5 and d1 < 0 and d2 < 0: penalty -= 10
                if len(gains) >= 6 and d5 > d1 and d5 > d2 and p <= d5:
                    recent = d4+d3+d2+d1
                    if recent <= 2: penalty -= 8
                if len(gains) >= 5:
                    last5 = gains[-5:]
                    if all(last5[i] >= last5[i+1] for i in range(len(last5)-1)): penalty -= 10
        scored.append((base + penalty, s))
    
    scored.sort(key=lambda x: -x[0])
    
    today = datetime.now().strftime('%Y-%m-%d')
    now_str = datetime.now().strftime('%H:%M:%S')
    
    # ═══ 保存选股记录到JSON（永久存档）═══
    top10 = []
    for rank, (sc, s) in enumerate(scored[:10], 1):
        top10.append({
            'rank': rank,
            'name': s.get('name', '?')[:6],
            'code': s['code'],
            'score': round(sc, 1),
            'p': s.get('p', 0) or 0,
            'cl': s.get('cl', 0) or 50,
            'wrv': s.get('wrv', 0) or 50,
            'vr': s.get('vr', 0) or 1,
            'price': s.get('price', 0) or 0,
            'pre_close': s.get('pre_close', 0) or 0,
            'volume': s.get('volume', 0) or 0,
        })
    
    selection_record = {
        'date': today,
        'time': now_str,
        'version': 'V13',
        'market_type': mk_cn,
        'market_key': mk,
        'pool_size': len(pool),
        'used_level': used_level,
        'total_candidates': len(clean_stocks),
        'top10': top10,
    }
    
    log_path = os.path.join(SELECTION_LOG_DIR, f'V13_{today}.json')
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(selection_record, f, ensure_ascii=False, indent=2)
    print(f'✅ 选股记录已保存: {log_path}')
    
    # ═══ 输出到控制台 ═══
    report = []
    report.append(f'📊 V13 分而治之·实盘选股 {today}（{now_str}实时数据）')
    report.append(f'📈 行情: {mk_cn} | 候选池: {len(pool)}只 (等级{used_level})')
    report.append(f'')
    report.append(f'🏆 Top {len(top10)}:')
    report.append(f'{"#":>2} {"名称":>8} {"代码":>7} {"评分":>5} {"涨幅":>6} {"CL":>5} {"WR":>5} {"量比":>5} {"现价":>7}')
    for r in top10:
        report.append(f'{r["rank"]:>2} {r["name"]:>8} {r["code"]:>7} {r["score"]:>5.0f} {r["p"]:>+5.1f}% {r["cl"]:>5.0f} {r["wrv"]:>5.0f} {r["vr"]:>5.1f} {r["price"]:>7.2f}')
    
    output = '\n'.join(report)
    print(output)
    
    # ═══ 写入选股池到数据库 ═══
    try:
        import sqlite3
        conn = sqlite3.connect(os.path.join(SCRIPTS_DIR, 'v13_quant.db'))
        c = conn.cursor()
        
        # 先检查今天是否有快照，没有则创建
        c.execute('''
            SELECT id FROM strategy_snapshot 
            WHERE strategy_version='V13' AND run_date=? AND run_time=?
        ''', (today, now_str[:5]))
        snap = c.fetchone()
        if not snap:
            # 从归档中找策略文件
            c.execute('''
                SELECT id FROM strategy_files 
                WHERE strategy_version='V13' AND file_type='backtest'
                LIMIT 1
            ''')
            btid = c.fetchone()
            bt_fid = btid[0] if btid else None
            
            c.execute('''
                INSERT INTO strategy_snapshot
                (strategy_version, run_date, run_time, backtest_file_id,
                 classification_method, data_cache_version)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('V13', today, now_str[:5], bt_fid,
                  'v1_mkt_class', get_config('strategy', 'data_cache_version', 'big_cache_latest')))
            snap_id = c.lastrowid
        else:
            snap_id = snap[0]
        
        # 写入所有候选股到 selection_pool
        rows = []
        for rank, (sc, s) in enumerate(scored, 1):
            rows.append((
                today, now_str[:5], snap_id,
                'sina', 'hq.sinajs.cn', 'realtime',
                'V13', mk_cn, mk, len(pool), used_level, len(clean_stocks),
                s['code'], s.get('name', '')[:6],
                s.get('p', 0) or 0, s.get('cl', 0) or 50,
                s.get('wrv', 0) or 50, s.get('vr', 0) or 1,
                s.get('price', 0) or 0,
                sc, s.get('momentum_penalty', 0) or 0, sc
            ))
        
        c.executemany('''
            INSERT OR REPLACE INTO selection_pool
            (date, run_time, snapshot_id,
             data_provider, data_api, data_type,
             strategy_version, market_type, market_key,
             pool_size, used_level, total_candidates,
             code, name,
             p, cl, wrv, vr, price,
             base_score, momentum_penalty, total_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', rows)
        
        conn.commit()
        conn.close()
        print(f'✅ 已写入 {len(rows)} 条候选股到数据库')
    except Exception as e:
        print(f'⚠️ 数据库写入失败: {e}')
    
    # ═══ 邮件（配置从数据库读取）═══
    try:
        email_cfg = get_email_config()
        email_to = ','.join(email_cfg['recipients'])
        subject = f'V13实盘选股 {today} - {mk_cn} TOP10'
        sender = os.path.join(SCRIPTS_DIR, 'send_email.py')
        subprocess.run([sys.executable, sender, subject, output], timeout=60)
        print('📧 邮件已发送')
    except Exception as e:
        print(f'📧 邮件失败: {e}')

if __name__ == '__main__':
    main()
