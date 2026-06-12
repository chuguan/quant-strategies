#!/usr/bin/env python3
"""虚涨日 V9 vs V14 双版全量对比回测 — 用 data_cache + features_cache + stock_info"""

import sqlite3, sys, os, json, copy
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'v13_quant.db')

# ── V9 评分策略 ──
V9_PARAMS = {
    "use_p": 1, "p_w": 0.5,
    "use_cl": 1, "cl_w": 0.05,
    "use_vr": 0,
    "use_macd": 1, "macd_w": 1, "dif_bonus": 2,
    "use_a5": 1, "a5_b": 0,
    "use_wr": 0, "wr_lo": 20, "wr_lo_b": 0,
    "use_kdj": 0, "j_golden_b": 5, "j_zone_b": 5,
    "use_pos": 0, "pos_hi_pen": -20,
    "use_hsl": 0,
    "cl_zones": [], "vr_zones": []
}

# ── V14 评分策略 ──
V14_PARAMS = {
    "use_p": 1, "p_w": 2.0,
    "use_cl": 1, "cl_w": 0.05,
    "use_vr": 0,
    "use_macd": 1, "macd_w": 0.5, "dif_bonus": 3,
    "use_a5": 1, "a5_b": 0,
    "use_wr": 1, "wr_lo": 15, "wr_lo_b": 0, "wr_hi": 50, "wr_hi_b": -5,
    "use_kdj": 0, "j_golden_b": 5, "j_zone_b": 5,
    "use_pos": 0, "pos_hi_pen": -20,
    "use_hsl": 1, "hsl_hi": 12, "hsl_hi_pen": -8,
    "cl_zones": [], "vr_zones": []
}

LEVELS = [
    {"name":"L1","p_min":4,"p_max":7,"vr_min":0.6,"vr_max":2.0,"hs_min":5,"hs_max":20,"sz_max":200,"cl_min":30,"cl_max":90},
    {"name":"L2","p_min":3,"p_max":7,"vr_min":0.5,"vr_max":2.5,"hs_min":3,"hs_max":25,"sz_max":200,"cl_min":20,"cl_max":95},
    {"name":"L3","p_min":2,"p_max":7,"vr_min":0.5,"vr_max":3.0,"hs_min":2,"hs_max":30,"sz_max":300,"cl_min":10,"cl_max":98},
    {"name":"L4","p_min":0,"p_max":7,"vr_min":0.4,"vr_max":4.0,"hs_min":1,"hs_max":40,"sz_max":500,"cl_min":0,"cl_max":100},
    {"name":"L5","p_min":-10,"p_max":7,"vr_min":0.1,"vr_max":10,"hs_min":0.1,"hs_max":100,"sz_max":10000,"cl_min":0,"cl_max":100}
]
LO = ['L0','L1','L2','L3','L4']

def v9_score(s, feats):
    p = PARAMS_HOLDER['v9_p']; p['use_hsl'] = 0
    stock = s.copy()
    score = 0
    if p.get('use_p',1): score += (stock.get('p',0) or 0) * p.get('p_w',1)
    cl = stock.get('cl',50) or 50
    if p.get('use_cl',1):
        score += cl * p.get('cl_w',0.05)
        for z in p.get('cl_zones',[]):
            if len(z)==3 and z[0]<=cl<=z[1]: score+=z[2]
    dif = stock.get('dif_val',0) or stock.get('dif',0) or 0
    mg = stock.get('macd_golden',0) or stock.get('mg',0) or 0
    if p.get('use_macd',1):
        ms = 0
        if mg and dif>0.5: ms=10
        elif mg and dif>0.2: ms=8
        elif mg: ms=6
        elif dif>0.5: ms=4
        elif dif>0: ms=2
        score += ms * p.get('macd_w',0.3)
        if dif > p.get('dif_thresh',0.5): score += p.get('dif_bonus',0)
    if p.get('use_a5',0) and stock.get('above_ma5',0): score += p.get('a5_b',0)
    wrv = stock.get('wr_val',0) or stock.get('wrv',50) or 50
    if p.get('use_wr',0):
        if wrv < p.get('wr_lo',25): score += p.get('wr_lo_b',0)
        if wrv > p.get('wr_hi',75): score += p.get('wr_hi_b',0)
    return round(score,1)

def v14_score(s, feats):
    p = PARAMS_HOLDER['v14_p']
    stock = s.copy()
    score = 0
    if p.get('use_p',1): score += (stock.get('p',0) or 0) * p.get('p_w',1)
    cl = stock.get('cl',50) or 50
    if p.get('use_cl',1):
        score += cl * p.get('cl_w',0.05)
        for z in p.get('cl_zones',[]):
            if len(z)==3 and z[0]<=cl<=z[1]: score+=z[2]
    hsl = stock.get('hsl', 0) or 0
    if p.get('use_hsl', 1) and hsl > p.get('hsl_hi', 15):
        score += p.get('hsl_hi_pen', -5)
    dif = stock.get('dif_val',0) or stock.get('dif',0) or 0
    mg = stock.get('macd_golden',0) or stock.get('mg',0) or 0
    if p.get('use_macd',1):
        ms = 0
        if mg and dif>0.5: ms=10
        elif mg and dif>0.2: ms=8
        elif mg: ms=6
        elif dif>0.5: ms=4
        elif dif>0: ms=2
        score += ms * p.get('macd_w',0.3)
        if dif > p.get('dif_thresh',0.5): score += p.get('dif_bonus',0)
    if p.get('use_a5',0) and stock.get('above_ma5',0): score += p.get('a5_b',0)
    wrv = stock.get('wr_val',0) or stock.get('wrv',50) or 50
    if p.get('use_wr',0):
        if wrv < p.get('wr_lo',25): score += p.get('wr_lo_b',0)
        if wrv > p.get('wr_hi',75): score += p.get('wr_hi_b',0)
    jv = stock.get('j_val',0) or stock.get('jv',50) or 50
    kv = stock.get('k_val',0) or stock.get('kv',50) or 50
    dv = stock.get('d_val',0) or stock.get('dv',50) or 50
    if p.get('use_kdj',0):
        if jv > kv > dv: score += p.get('j_golden_b',0)
        if p.get('j_lo',20) <= jv <= p.get('j_hi',40): score += p.get('j_zone_b',0)
        if jv < p.get('j_super_lo',15): score += p.get('j_super_b',0)
    pos = stock.get('pos_in_day',50) or 50
    if p.get('use_pos',0):
        if pos > p.get('pos_hi',85): score += p.get('pos_hi_pen',-2)
        if pos < p.get('pos_lo',30): score += p.get('pos_lo_b',0)

    # V14 大阳+洗盘信号
    if feats:
        d1 = feats.get('d1',0) or 0
        d2 = feats.get('d2',0) or 0
        d3 = feats.get('d3',0) or 0
        p_today = stock.get('p',0) or 0
        max_4d = max(p_today, d1, d2, d3)
        min_4d = min(d1, d2, d3)
        if min_4d > 0: min_4d = 0
        if max_4d >= 9.5: score += 8
        elif max_4d >= 7.0: score += 5
        elif max_4d >= 5.0: score += 3
        if min_4d <= -7.0: score += 5
        elif min_4d <= -5.0: score += 3
        elif min_4d <= -3.0: score += 1
        cl_val = stock.get('cl',50) or 50
        if 40 <= cl_val <= 75: score += 3
        if p_today > 5.5 and dif < 0: score += 5

    return round(score, 1)

PARAMS_HOLDER = {'v9_p': V9_PARAMS, 'v14_p': V14_PARAMS}

def main():
    conn = sqlite3.connect(DB, timeout=30)
    c = conn.cursor()

    # 1. 交易日
    c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
    all_dates_raw = [r[0] for r in c.fetchall()]
    all_dates = []
    for d in all_dates_raw:
        try:
            if datetime.strptime(d, '%Y-%m-%d').weekday() < 5:
                all_dates.append(d)
        except: pass
    print(f'交易日: {len(all_dates)} ({all_dates[0]} ~ {all_dates[-1]})')

    # 2. 股票信息
    c.execute('SELECT code, hsl, shizhi FROM data_stock_info')
    stock_info = {r[0]: {'hsl': r[1] or 0, 'shizhi': r[2] or 0} for r in c.fetchall()}
    sz_max_global = min(si['shizhi'] for si in stock_info.values() if si['shizhi'] > 0)
    print(f'股票信息: {len(stock_info)} 只 (最低流通市值≈{sz_max_global*1e8:.0f}亿)')

    # 3. 遍历每个交易日
    results_v9 = []
    results_v14 = []
    fake_up_dates = []

    for idx, dt in enumerate(all_dates):
        if idx % 50 == 0:
            print(f'  进度: {idx}/{len(all_dates)} ...', flush=True)

        # 加载当日数据
        c.execute('''
            SELECT code, p, cl, vr, n, dif_val, macd_golden,
                   wr_val, j_val, k_val, d_val, pos_in_day, above_ma5,
                   kdj_golden, close
            FROM data_cache WHERE date=?
        ''', (dt,))
        cols = ['code','p','cl','vr','n','dif_val','macd_golden',
                'wr_val','j_val','k_val','d_val','pos_in_day','above_ma5',
                'kdj_golden','close']
        rows = c.fetchall()
        if not rows: continue
        stocks = [dict(zip(cols, row)) for row in rows]

        # 过滤异常
        stocks = [s for s in stocks if (s.get('p',0) or 0) < 15 and (s.get('p',0) or 0) > -15]
        if not stocks: continue

        # 行情分类
        ps = [(s.get('p',0) or 0) for s in stocks]
        vrs = [(s.get('vr',0) or 1) for s in stocks if (s.get('vr',0) or 0) > 0]
        ap = sum(ps)/len(ps)
        av = sum(vrs)/len(vrs) if vrs else 0
        hot = sum(1 for p in ps if 5 <= p <= 8)
        if ap > 0.5:
            mk = 'fake_up' if (hot < 15 or av < 0.9) else 'real_up'
        elif ap < -0.5:
            mk = 'down'
        else:
            mk = 'flat'

        if mk != 'fake_up':
            continue

        fake_up_dates.append((dt, ap, av, hot))

        # 加载特征
        c.execute('SELECT code, d1, d2, d3, slope5, t4_shadow, cons_up, peak_decay FROM features_cache WHERE date=?', (dt,))
        feats = {}
        for row in c.fetchall():
            feats[row[0]] = {
                'd1': row[1] or 0, 'd2': row[2] or 0, 'd3': row[3] or 0,
                'slope5': row[4] or 0, 't4_shadow': row[5] or 0,
                'cons_up': row[6] or 0, 'peak_decay': row[7] or 0,
            }

        # LEVEL 筛选 + 评分
        scores_v9 = []
        scores_v14 = []
        lm = {l['name']:i for i,l in enumerate(LEVELS)}

        for level_name in LO:
            if level_name not in lm: continue
            i = lm[level_name]
            lv = LEVELS[i]
            candidates = []

            for s in stocks:
                code = s['code']
                p_v = s.get('p',0) or 0
                # LEVEL 过滤
                if p_v < lv['p_min'] or p_v > min(lv.get('p_max',10), 8): continue
                vr_v = s.get('vr',0) or s.get('vol_ratio',0) or 0
                if vr_v < lv['vr_min'] or vr_v > lv['vr_max']: continue
                si = stock_info.get(code, {})
                hsl = si.get('hsl',0) or 0
                if hsl < lv.get('hs_min',0) or hsl > lv.get('hs_max',99): continue
                if (si.get('shizhi',0) or 0) >= lv.get('sz_max',9999): continue
                cl = s.get('cl',0) or 0
                if cl < lv.get('cl_min',0) or cl > lv.get('cl_max',100): continue

                # 跳过动量衰竭
                f = feats.get(code, {})
                sl5 = f.get('slope5',0); t4s = f.get('t4_shadow',0); cu = f.get('cons_up',0)
                pk = f.get('peak_decay',0)
                if (sl5>8 and t4s>25) or (sl5>10 and t4s>18) or (cu>=5 and sl5>15) or (pk>5 and sl5>5 and p_v<6) or (sl5>5 and t4s>30) or (cu>=4 and sl5>10 and p_v<7):
                    continue

                # 计算V9评分
                s9 = v9_score(s, f)
                # 计算V14评分
                s14 = v14_score(s, f)

                candidates.append((code, s9, s14, p_v, s.get('vr',0) or 0, cl, s.get('n',0) or 0))

            if candidates:
                # 只取评分最高的V9冠军和V14冠军
                cand_v9 = max(candidates, key=lambda x: x[1])
                cand_v14 = max(candidates, key=lambda x: x[2])
                scores_v9.append(cand_v9)
                scores_v14.append(cand_v14)
                break  # 找到可用level就停

        if not scores_v9:
            continue

        champion_v9 = max(scores_v9, key=lambda x: x[1])
        champion_v14 = max(scores_v14, key=lambda x: x[2])

        results_v9.append({
            'date': dt, 'code': champion_v9[0], 'score_v9': champion_v9[1],
            'p': champion_v9[3], 'vr': champion_v9[4], 'cl': champion_v9[5],
            'n': champion_v9[6], 'win': champion_v9[6] >= 2.5
        })
        results_v14.append({
            'date': dt, 'code': champion_v14[0], 'score_v14': champion_v14[1],
            'p': champion_v14[3], 'vr': champion_v14[4], 'cl': champion_v14[5],
            'n': champion_v14[6], 'win': champion_v14[6] >= 2.5
        })

    conn.close()

    # ── 输出结果 ──
    print('\n' + '='*80)
    print('═══ 虚涨日 V9 vs V14 全量对比回测结果 ═══')
    print('='*80)
    print(f'\n虚涨日总数: {len(fake_up_dates)} / {len(all_dates)} 天 ({100*len(fake_up_dates)/len(all_dates):.1f}%)')
    print(f'回测覆盖: {len(results_v9)} 天 (有候选池的天数)')
    print()

    if len(results_v9) < 3:
        print('样本太少，无法得出可靠结论')
        print('\n虚涨日明细:')
        for dt, ap, av, hot in fake_up_dates:
            print(f'  {dt}: avg_p={ap:.2f}% av_vr={av:.4f} hot={hot}')
        return

    # V9统计
    v9_wins = sum(1 for r in results_v9 if r['win'])
    v9_avg_n = sum(r['n'] for r in results_v9) / len(results_v9)
    v9_max_n = max(r['n'] for r in results_v9)
    v9_pos_days = sum(1 for r in results_v9 if r['n'] > 0)

    # V14统计
    v14_wins = sum(1 for r in results_v14 if r['win'])
    v14_avg_n = sum(r['n'] for r in results_v14) / len(results_v14)
    v14_max_n = max(r['n'] for r in results_v14)
    v14_pos_days = sum(1 for r in results_v14 if r['n'] > 0)

    print('【V9 最优版】')
    print(f'  总天数:    {len(results_v9)}')
    print(f'  胜率:     {v9_wins}/{len(results_v9)} = {v9_wins/len(results_v9)*100:.1f}%')
    print(f'  正收益比例: {v9_pos_days}/{len(results_v9)} = {v9_pos_days/len(results_v9)*100:.1f}%')
    print(f'  平均次日涨幅: {v9_avg_n:.2f}%')
    print(f'  最大次日涨幅: {v9_max_n:.2f}%')
    print(f'  参数: p_w=0.5, macd_w=1.0, dif_bonus=2, WR禁用')

    print()
    print('【V14 固化版】')
    print(f'  总天数:    {len(results_v14)}')
    print(f'  胜率:     {v14_wins}/{len(results_v14)} = {v14_wins/len(results_v14)*100:.1f}%')
    print(f'  正收益比例: {v14_pos_days}/{len(results_v14)} = {v14_pos_days/len(results_v14)*100:.1f}%')
    print(f'  平均次日涨幅: {v14_avg_n:.2f}%')
    print(f'  最大次日涨幅: {v14_max_n:.2f}%')
    print(f'  参数: p_w=2.0, macd_w=0.5, dif_bonus=3, WR启用, HSL惩罚, 大阳+洗盘信号')

    print()
    diff_win = v14_wins - v9_wins
    print(f'【对比】')
    print(f'  胜率差(V14-V9): {diff_win} 天 ({diff_win/len(results_v9)*100:+.1f}%)')
    print(f'  平均次日涨幅差: {v14_avg_n - v9_avg_n:+.2f}%')
    print(f'  同日选同一股的次数: ', end='')

    same_count = 0
    same_win_both = 0
    for r9, r14 in zip(results_v9, results_v14):
        # Not necessarily same date order - find by date
        pass
    # Better comparison
    results_by_date = {}
    for r in results_v9:
        results_by_date[r['date']] = {'v9': r}
    for r in results_v14:
        if r['date'] in results_by_date:
            results_by_date[r['date']]['v14'] = r

    same_champ = sum(1 for k, v in results_by_date.items() if 'v9' in v and 'v14' in v and v['v9']['code'] == v['v14']['code'])
    print(f'{same_champ}')

    print()
    print('【逐日明细 — V9冠军 vs V14冠军】')
    print(f'{"日期":<12} {"V9冠军":<8} {"V9分":<6} {"V9次日%":<8} {"V14冠军":<8} {"V14分":<6} {"V14次日%":<8} {"胜出方":<6}')
    print('-'*70)
    for dt in sorted(results_by_date.keys()):
        v9 = results_by_date[dt].get('v9')
        v14 = results_by_date[dt].get('v14')
        if not v9 or not v14: continue
        winner = 'V14' if v14['n'] > v9['n'] else ('V9' if v9['n'] > v14['n'] else '平')
        print(f'{dt:<12} {v9["code"]:<8} {v9["score_v9"]:<6.1f} {v9["n"]:<+7.2f}%  {v14["code"]:<8} {v14["score_v14"]:<6.1f} {v14["n"]:<+7.2f}%  {winner:<6}')

    print()
    print('【明细 — V14择股一致性】')
    skip_first = True
    for dt in sorted(results_by_date.keys()):
        v9 = results_by_date[dt].get('v9')
        v14 = results_by_date[dt].get('v14')
        if not v9 or not v14: continue
        same = '✔ SAME' if v9['code'] == v14['code'] else '✗ DIFF'
        v9_label = f"V9_{v9['code']}_次日{v9['n']:+.1f}%"
        v14_label = f"V14_{v14['code']}_次日{v14['n']:+.1f}%"
        if skip_first:
            print(f'{"日期":<12} {"一致?":<10} {"V9冠军详情":<30} {"V14冠军详情":<30}')
            skip_first = False
        print(f'{dt:<12} {same:<10} {v9_label:<30} {v14_label:<30}')

    # 稳定性分析
    print()
    print('【稳定性】')
    from statistics import stdev
    v9_ns = [r['n'] for r in results_v9]
    v14_ns = [r['n'] for r in results_v14]
    if len(v9_ns) > 1:
        print(f'  V9 标准差:  {stdev(v9_ns):.2f}%')
        print(f'  V14 标准差: {stdev(v14_ns):.2f}%')
    v9_neg = sum(1 for r in results_v9 if r['n'] < 0)
    v14_neg = sum(1 for r in results_v14 if r['n'] < 0)
    print(f'  V9 亏损天数:  {v9_neg}/{len(results_v9)} = {v9_neg/len(results_v9)*100:.1f}%')
    print(f'  V14 亏损天数: {v14_neg}/{len(results_v14)} = {v14_neg/len(results_v14)*100:.1f}%')

if __name__ == '__main__':
    main()
