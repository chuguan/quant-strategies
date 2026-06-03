"""
回测运行器 — 跑任意V13版本的回测并存入 strategy_runs + strategy_run_details
用法: python run_backtest_save.py V13
      python run_backtest_save.py V13C
"""
import os, sys, pickle, json, sqlite3, importlib.util
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

def main():
    if len(sys.argv) < 2:
        print("用法: python run_backtest_save.py <版本> [天数]")
        print("       python run_backtest_save.py <版本> --start YYYY-MM-DD --end YYYY-MM-DD")
        print("示例: python run_backtest_save.py V13C 30")
        print("       python run_backtest_save.py V13 --start 2026-04-08 --end 2026-05-22")
        sys.exit(1)
    
    version = sys.argv[1]
    
    # 检查是否指定窗口
    start_date = None
    end_date = None
    max_days = 30
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--start' and i+1 < len(sys.argv):
            start_date = sys.argv[i+1]
            i += 2
        elif sys.argv[i] == '--end' and i+1 < len(sys.argv):
            end_date = sys.argv[i+1]
            i += 2
        else:
            max_days = int(sys.argv[i])
            i += 1

    V13_DIR = os.path.join(SCRIPTS_DIR, 'release', version)
    if not os.path.isdir(V13_DIR):
        print(f"❌ 版本目录不存在: {V13_DIR}")
        sys.exit(1)
    
    # ── 加载big_cache ──
    print(f'加载 big_cache_full.pkl...')
    with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
        d = pickle.load(f)
    BIG_DATA = d['data']
    names_dict = d.get('names', {})
    real_dict = d.get('real', {})
    ALL_DATES = sorted(BIG_DATA.keys())
    print(f'  共 {len(ALL_DATES)} 天数据 ({ALL_DATES[0]} ~ {ALL_DATES[-1]})')
    
    # ── 加载features ──
    features_path = os.path.join(V13_DIR, 'features_30d.pkl')
    precomputed = {}
    if os.path.exists(features_path):
        with open(features_path, 'rb') as f:
            pkl = pickle.load(f)
            pk = pkl if isinstance(pkl, dict) else {}
            for k, v in pk.items():
                if isinstance(k, tuple) and len(k) == 2:
                    precomputed[k] = v if isinstance(v, dict) else {}
        print(f'  加载 features: {len(precomputed)} 条')
    
    # ── 加载评分策略 ──
    STRAT_DIR = os.path.join(V13_DIR, '评分策略')
    def load_strat(mk):
        names = {'real_up': '真实涨日', 'fake_up': '虚涨日', 'down': '跌日', 'flat': '横盘'}
        fname = f'分而治之_V10_{names[mk]}_评分策略.py'
        spec = importlib.util.spec_from_file_location(mk, os.path.join(STRAT_DIR, fname))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    
    STRATS = {k: load_strat(k) for k in ['real_up','fake_up','down','flat']}
    MARKET_CN = {'real_up': '真实涨日', 'fake_up': '虚涨日', 'down': '跌日', 'flat': '横盘'}
    
    # ── 工具函数 ──
    def classify_market(dt, stocks):
        ps = [s.get('p', 0) or 0 for s in stocks]
        avg_p = sum(ps)/len(ps) if ps else 0
        vrs = [s.get('vol_ratio', 1) or 1 for s in stocks if s.get('vol_ratio')]
        avg_vr = sum(vrs)/len(vrs) if vrs else 0
        hot = sum(1 for p in ps if 5 <= p <= 8)
        if avg_p > 0.5:
            return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
        if avg_p < -0.5:
            return 'down'
        return 'flat'
    
    def get_feats(code, dt):
        return precomputed.get((code, dt), {})
    
    def is_momentum_exhausted(s, code, dt):
        fe = get_feats(code, dt)
        if not fe:
            return False
        sl5 = fe.get('slope5', 0) or 0
        t4s = fe.get('t4_shadow', 0) or 0
        cu = fe.get('cons_up', 0) or 0
        pk = fe.get('peak_decay', 0) or 0
        pv = s.get('p', 0) or 0
        
        if sl5 > 8 and t4s > 25: return True    # R1: 假动能
        if sl5 > 10 and t4s > 18: return True   # R1b: 轻度假动能
        if cu >= 5 and sl5 > 15: return True    # R2: 连涨透支
        if pk > 5 and sl5 > 5 and pv < 6: return True   # R3: 高位衰减
        if sl5 > 5 and t4s > 30: return True    # R4: T-4抛压
        if cu >= 4 and sl5 > 10 and pv < 7: return True  # R5: 连涨透支4天
        return False
    
    # ═══ 7天动量衰减检查 ═══
    def compute_7day_decay_penalty(all_dates, big_data, code, dt, p_today):
        idx = all_dates.index(dt)
        prev = all_dates[max(0,idx-6):idx]
        gains = []
        for pd in prev:
            found = False
            for s in big_data[pd]:
                if s['code'] == code:
                    gains.append(s.get('p', 0) or 0)
                    found = True
                    break
            if not found:
                gains.append(0)
        gains.append(p_today)
        n = len(gains)
        if n < 5: return 0
        d6,d5,d4,d3,d2,d1,p = gains[-7:] if n >= 7 else [0]*(7-n) + gains
        p_is_max = p >= max(gains[:-1]) if len(gains) > 1 else True
        avg_7d = sum(gains) / n
        penalty = 0
        wrv = 50
        for s in big_data.get(dt, []):
            if s['code'] == code:
                wrv = s.get('wr_val', 50) or s.get('wrv', 50)
                break
        if wrv < 10 and p_is_max and avg_7d < 2.0 and p < 6:
            penalty -= 8
        if p_is_max and avg_7d < 0.8 and p < 8:
            if avg_7d < 0: penalty -= 15
            elif avg_7d < 0.3: penalty -= 12
            elif avg_7d < 0.7: penalty -= 8
            else: penalty -= 5
        if d1 < -1.5 and d2 < -1.0 and p > 3 and avg_7d < 1.0:
            penalty -= 8
        if max(d4, d3, d2) > 5 and d1 < 0 and d2 < 0:
            penalty -= 10
        if n >= 5 and d5 > d1 and d5 > d2 and p <= d5:
            recent_sum = (d4+d3+d2+d1) if n >= 6 else (d3+d2+d1)
            if recent_sum <= 2: penalty -= 8
        if n >= 5:
            last5 = gains[-5:]
            if all(last5[i] >= last5[i+1] for i in range(len(last5)-1)):
                penalty -= 10
        return penalty
    
    def v10_score(s, code, dt, mk_cn):
        # 中文→英文映射
        mk_map = {'真实涨日': 'real_up', '虚涨日': 'fake_up', '跌日': 'down', '横盘': 'flat'}
        mk_key = mk_map.get(mk_cn, 'flat')
        mod = STRATS[mk_key]
        P = mod.PARAMS
        stock = {
            'p': s.get('p', 0) or 0,
            'cl': s.get('cl', 50),
            'vr': s.get('vol_ratio', 1) or s.get('vr', 1),
            'dif': s.get('dif_val', 0) or s.get('dif', 0),
            'mg': s.get('macd_golden', 0) or s.get('mg', 0),
            'wrv': s.get('wr_val', 0) or s.get('wrv', 50),
            'jv': s.get('j_val', 0) or s.get('jv', 50),
            'kv': s.get('k_val', 0) or s.get('kv', 50),
            'dv': s.get('d_val', 0) or s.get('dv', 50),
            'a5': s.get('above_ma5', 0),
            'kdj_g': s.get('kdj_golden', 0) or s.get('kdj_g', 0),
            'pos_in_day': s.get('pos_in_day', 50),
            'nm': s.get('nm', '') or s.get('name', '') or names_dict.get(s['code'], ''),
        }
        ri = real_dict.get(s['code'], {})
        stock['hsl'] = ri.get('hsl', 0) or 0
        fe = get_feats(code, dt)
        stock['t4_shadow'] = fe.get('t4_shadow', 0)
        stock['slope5'] = fe.get('slope5', 0)
        stock['cons_up'] = fe.get('cons_up', 0)
        stock['d1'] = fe.get('d1', 0)
        stock['d2'] = fe.get('d2', 0)
        stock['d3'] = fe.get('d3', 0)
        # 7天动量衰减扣分（独立于评分模块）
        seven_day_penalty = compute_7day_decay_penalty(ALL_DATES, BIG_DATA, code, dt, s.get('p', 0) or 0)
        return round(mod.score(stock) + seven_day_penalty, 1)
    
    # ── 主回测 ──
    ta = wi = 0
    details = []  # [(date, mk, level, pool_size, [(rank, stock, score)], champ)]
    
    # 选择日期范围
    if start_date and end_date:
        if start_date in ALL_DATES and end_date in ALL_DATES:
            si = ALL_DATES.index(start_date)
            ei = ALL_DATES.index(end_date)
            test_dates = ALL_DATES[si:ei+1]
            print(f'  指定窗口: {test_dates[0]} ~ {test_dates[-1]} = {len(test_dates)}天')
        else:
            print(f'  ⚠️ 指定窗口日期不在数据中, 回退到最近{max_days}天')
            test_dates = ALL_DATES[-max_days:] if max_days <= len(ALL_DATES) else ALL_DATES
    else:
        test_dates = ALL_DATES[-max_days:] if max_days <= len(ALL_DATES) else ALL_DATES
    
    for idx, dt in enumerate(test_dates):
        stocks = BIG_DATA.get(dt, [])
        if not stocks or len(stocks) < 10:
            continue
        
        mk = classify_market(dt, stocks)
        mk_cn = MARKET_CN[mk]
        mod = STRATS[mk]
        LEVELS = mod.LEVELS
        
        # 入池
        LEVEL_NAMES = ['L0', 'L1', 'L2', 'L3', 'L4', 'L5']
        lm = {l['name']: i for i, l in enumerate(LEVELS)}
        pool = []
        pool_level = '无'
        eliminated = 0
        for ln in LEVEL_NAMES:
            if ln not in lm: continue
            i = lm[ln]
            lv = LEVELS[i]
            cand = []
            for s in stocks:
                p = s.get('p', 0) or 0
                if p < lv['p_min'] or p > min(lv.get('p_max', 10), 8): continue
                vr = s.get('vol_ratio', 0) or 0
                if vr < lv['vr_min'] or vr > lv['vr_max']: continue
                nm = s.get('name', '') or names_dict.get(s['code'], '')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl = s.get('cl', 0)
                if cl < lv.get('cl_min', 0) or cl > lv.get('cl_max', 100): continue
                # HSL
                ri = real_dict.get(s['code'], {})
                hsl = ri.get('hsl', 0) or 0
                if hsl < lv.get('hs_min', 0) or hsl > lv.get('hs_max', 99): continue
                sz = ri.get('shizhi', 0) or 0
                if sz >= lv.get('sz_max', 9999): continue
                # 动量过滤
                if is_momentum_exhausted(s, s['code'], dt):
                    eliminated += 1
                    continue
                cand.append(s)
            if len(cand) >= 10:
                pool = cand
                pool_level = ln
                break
        
        if not pool:
            continue
        
        # 评分 + 排名
        scored = [(v10_score(s, s['code'], dt, mk_cn), s) for s in pool]
        scored.sort(key=lambda x: -x[0])
        
        # D+1 — 直接从当前记录读取（big_cache自带next_high/next_close/next_low）
        for sc_s in scored:
            sc, s = sc_s
            nh_val = s.get('n', 0) or 0
            if sc_s is scored[0]:
                nh = nh_val
                if nh >= 2.5:
                    wi += 1
                ta += 1
                sta = 'OK' if nh >= 2.5 else 'FAIL'
                print(f'{dt} {mk_cn:>5} {names_dict.get(s["code"], s["code"]):>10} p={s.get("p",0):.1f}% sc={sc:.0f} nh={nh:+.1f}% {sta}')
        
        # 记录所有候选股明细
        day_records = []
        for rank, (sc, s) in enumerate(scored):
            nh_val = s.get('n', 0) or 0
            next_h_pct = s.get('next_high', nh_val) or 0
            next_c_pct = s.get('next_close', 0) or 0
            next_l_pct = s.get('next_low', s.get('nl', 0)) or 0
            prev_c = s.get('close', 0) or 0
            next_h_price = round(prev_c * (1 + next_h_pct/100), 2) if prev_c else 0
            next_c_price = round(prev_c * (1 + next_c_pct/100), 2) if prev_c else 0
            next_l_price = round(prev_c * (1 + next_l_pct/100), 2) if prev_c else 0
            
            day_records.append({
                'rank': rank + 1,
                'code': s['code'],
                'name': s.get('name', '') or names_dict.get(s['code'], ''),
                'market_type': mk_cn,
                'used_level': pool_level,
                'buy_price': s.get('close', 0) or 0,
                'buy_pct': s.get('p', 0) or 0,
                'cl': s.get('cl', 50) or 50,
                'vr': s.get('vol_ratio', 1) or s.get('vr', 1),
                'total_score': sc,
                'base_score': 0,
                'momentum_penalty': 0,
                'next_high': next_h_price,
                'next_high_pct': next_h_pct,
                'next_low': next_l_price,
                'next_low_pct': next_l_pct,
                'next_close': next_c_price,
                'next_close_pct': next_c_pct,
                'is_win': 1 if next_h_pct >= 2.5 else 0,
                'is_champion': 1 if rank == 0 else 0,
            })
        
        details.append({
            'date': dt,
            'mk': mk_cn,
            'level': pool_level,
            'pool_size': len(pool),
            'champ': day_records[0],
            'records': day_records,
        })
    
    print(f'\n{version} {max_days}天: {wi}/{ta} = {wi*100/max(ta,1):.1f}%')
    
    # ── 存入数据库 ──
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 写strategy_runs
    params_json = json.dumps({mk: STRATS[mk].PARAMS for mk in STRATS}, ensure_ascii=False, indent=2)
    levels_json = json.dumps({mk: STRATS[mk].LEVELS for mk in STRATS}, ensure_ascii=False, indent=2)
    
    now = datetime.now()
    run_id = None
    
    c.execute('''INSERT INTO strategy_runs
        (strategy_version, run_type, run_date, run_time,
         backtest_start, backtest_end, total_days, win_days, win_rate,
         market_types, used_levels, avg_pool_size,
         champion_code, champion_name, champion_score,
         params_snapshot, levels_snapshot, notes)
        VALUES (?,?,?,?, ?,?,?,?,?, ?,?,?, ?,?,?, ?,?,?)''', (
        version, 'backtest',
        now.strftime('%Y-%m-%d'), now.strftime('%H:%M'),
        details[0]['date'] if details else '',
        details[-1]['date'] if details else '',
        ta, wi, round(wi*100/max(ta,1), 1),
        json.dumps([d['mk'] for d in details], ensure_ascii=False),
        json.dumps([d['level'] for d in details], ensure_ascii=False),
        round(sum(d['pool_size'] for d in details)/max(len(details),1), 1),
        details[-1]['champ']['code'] if details else '',
        details[-1]['champ']['name'] if details else '',
        details[-1]['champ']['total_score'] if details else 0,
        params_json, levels_json,
        f'回测{max_days}天，使用big_cache_full.pkl + features_30d.pkl'
    ))
    run_id = c.lastrowid
    print(f'\n📝 strategy_runs id={run_id} 已创建')
    
    # 写strategy_run_details
    batch = []
    for d in details:
        for r in d['records'][:30]:  # 最多存前30名
            batch.append((
                run_id, d['date'], r['rank'], r['code'], r['name'],
                r['market_type'], r['used_level'],
                r['buy_price'], r['buy_pct'], r['cl'], r['vr'],
                r['total_score'], r['base_score'], r['momentum_penalty'],
                r['next_high'], r['next_high_pct'],
                r['next_low'], r['next_low_pct'],
                r['next_close'], r['next_close_pct'],
                r['is_win'], r['is_champion'],
            ))
    
    c.executemany('''INSERT INTO strategy_run_details
        (run_id, date, rank, code, name,
         market_type, used_level,
         buy_price, buy_pct, cl, vr,
         total_score, base_score, momentum_penalty,
         next_high, next_high_pct,
         next_low, next_low_pct,
         next_close, next_close_pct,
         is_win, is_champion)
        VALUES (?,?,?,?,?, ?,?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?,?,?)''', batch)
    
    conn.commit()
    conn.close()
    print(f'📝 strategy_run_details: {len(batch)} 条记录已存入')
    print(f'\n✅ 完成! 查询方式:')
    print(f'  -- 查运行日志:   SELECT * FROM strategy_runs WHERE id={run_id};')
    print(f'  -- 查明细:       SELECT * FROM strategy_run_details WHERE run_id={run_id} ORDER BY date DESC, rank;')
    print(f'  -- 查某日冠军:   SELECT * FROM strategy_run_details WHERE run_id={run_id} AND is_champion=1 ORDER BY date;')

if __name__ == '__main__':
    main()
