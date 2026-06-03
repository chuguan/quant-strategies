"""
超人策略 v6 — CL排序版（2026-05-25）
全量3427只主板验证 | 冠军达2.5%: 67.9% | 出票率: 93.1%
核心：按CL（收盘位）降序排名，不评分，不加权
"""
import pickle, os, json, sys
from collections import defaultdict

CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())

def get_candidates(date):
    stocks = data.get(date, [])
    cand = []
    for s in stocks:
        code, p = s['code'], s['p']
        # 涨幅5~8%
        if p < 5 or p > 8: continue
        # 量比1.0~1.5
        vr = s.get('vol_ratio',0) or 0
        if vr < 1.0 or vr > 1.5: continue
        # 基础数据
        ri = real.get(code)
        if not ri: continue
        hsl = (ri.get('hsl',0) or 0)
        if hsl < 5 or hsl > 15: continue  # 换手5~15%
        sz = (ri.get('shizhi',0) or 0)
        if sz >= 200: continue  # 市值<200亿
        nm = names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv = s.get('j_val',0) or 0
        if jv > 100: continue  # J<100（不硬限制）
        cl = s.get('cl',0)
        if cl < 60 or cl > 90: continue  # CL 60~90%
        
        nv = s.get('n',0) or 0
        buy_c = s.get('close', 0)
        
        # 次日最低
        nxt_st = next((x for x in dates if x > date), None)
        nxt_low_pct = 0
        if nxt_st:
            for d in data.get(nxt_st, []):
                if d['code'] == code:
                    fp = os.path.join(CACHE_DIR, f'{code}.json')
                    if os.path.exists(fp):
                        try:
                            with open(fp,'r') as f:
                                kdata = json.load(f)
                                for kd in kdata:
                                    if kd['date'] == nxt_st:
                                        nxt_low = kd['low']
                                        nxt_low_pct = (nxt_low/buy_c-1)*100 if buy_c > 0 else 0
                                        break
                        except: pass
                    break
        
        # 以CL为主要排序依据
        cand.append((cl, nm, code, p, vr, cl, hsl, sz, buy_c, nv, nxt_low_pct, jv))
    
    # 按CL降序排序（收盘位越高越优先）
    cand.sort(key=lambda x: (-x[0], -x[3]))
    return cand

if __name__ == '__main__':
    date = sys.argv[1] if len(sys.argv) > 1 else dates[-1]

    if len(sys.argv) > 1 and sys.argv[1] == 'backtest':
        results = []
        for dt in dates:
            if dt.endswith('-22') and '2026' in dt: continue
            cand = get_candidates(dt)
            if not cand: continue
            nv = cand[0][9]
            results.append({'dt':dt, 'champ_n':nv, 'champ_name':cand[0][1]})

        for year in ['2025','2026']:
            yr=[r for r in results if r['dt'].startswith(year)]
            w5 = sum(1 for r in yr if r['champ_n'] >= 5)
            w25 = sum(1 for r in yr if r['champ_n'] >= 2.5)
            avg_n = sum(r['champ_n'] for r in yr)/len(yr)
            
            capital = 100000
            peak = 100000
            max_dd = 0
            daily_returns = []
            for r in yr:
                ret = r['champ_n'] / 100
                capital *= (1 + ret)
                daily_returns.append(ret)
                peak = max(peak, capital)
                dd = (peak - capital) / peak * 100
                max_dd = max(max_dd, dd)
            win_rate = sum(1 for r in daily_returns if r > 0) / len(daily_returns) * 100

            print(f'{year}年: {len(yr)}天 | 达5%:{w5}({w5*100/len(yr):.1f}%) | 达2.5%:{w25}({w25*100/len(yr):.1f}%) | 均涨幅:{avg_n:.2f}% | 胜率:{win_rate:.0f}% | 年化:{((capital/100000)**(1/(len(yr)/250 if len(yr)>250 else 1))-1)*100:.1f}% | 最大回撤:{max_dd:.2f}%', flush=True)

        print('\n近5天详情:', flush=True)
        for dt in ['2026-05-18','2026-05-19','2026-05-20','2026-05-21','2026-05-22']:
            cand = get_candidates(dt)
            if not cand:
                print(f'{dt}: 无候选', flush=True); continue
            c = cand[0]
            nstr = f'{c[9]:.2f}%' if c[9] != 0 else 'N/A'
            lstr = f'{c[10]:.2f}%' if c[10] != 0 else 'N/A'
            ok = '🔥5%' if c[9] >= 5 else ('✅' if c[9] >= 2.5 else '❌')
            print(f'{dt}: 冠军{c[1]}(CL{c[5]:.0f}% 涨{c[3]:.1f}%) 买{c[8]:.2f} 次日最高{nstr} 最低{lstr} {ok}', flush=True)
            for i, x in enumerate(cand[:3]):
                ns = f'{x[9]:.2f}%' if x[9] != 0 else 'N/A'
                ls = f'{x[10]:.2f}%' if x[10] != 0 else 'N/A'
                ok2 = '🔥' if x[9] >= 5 else ('✅' if x[9] >= 2.5 else '')
                print(f'  Top{i+1}: {x[1]}(CL{x[5]:.0f}% 涨{x[3]:.1f}% 量{x[4]:.2f} J{x[11]:.0f}) 买{x[8]:.2f} → 高{ns} 低{ls} {ok2}', flush=True)
        exit()

    # 单日
    cand = get_candidates(date)
    if not cand:
        print(f'{date}: 无候选', flush=True)
        exit()
    print(f'{date} | 超人v6(CL排序) | 候选{len(cand)}只', flush=True)
    print(f'{"#":<3} {"名称":<10} {"CL":<4} {"涨%":<5} {"量比":<5} {"换手%":<5} {"买入价":<8} {"次日最高%":<8} {"J":<5}', flush=True)
    print('-' * 60, flush=True)
    for i, x in enumerate(cand[:10]):
        ns = f'{x[9]:.2f}%' if x[9] != 0 else 'N/A'
        ok = '🔥' if x[9] >= 5 else ('✅' if x[9] >= 2.5 else '')
        print(f'{i+1:<3} {x[1][:8]:<10} {x[5]:<4.0f} {x[3]:<5.1f} {x[4]:<5.2f} {x[6]:<5.1f} {x[8]:<8.2f} {ns:<8} {x[11]:<5.0f} {ok}', flush=True)
