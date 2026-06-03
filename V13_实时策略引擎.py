#!/usr/bin/env python3
"""V13 实时策略引擎 — 快准稳
流程: 新浪实时API(1.4s) → 计算p/cl/vr → 写入当天缓存 → 读库评分(0.1s) → 出结果
总耗时: ~3秒
"""
import subprocess, json, re, time, os, sys, importlib, sqlite3
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

def run_strategy():
    t0 = time.time()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # █ 第1步：实时行情（1.4秒）████████████
    with open(os.path.join(SCRIPTS_DIR, '活跃股票池_3043.json'), 'r') as f:
        pool = json.load(f)
    codes = [c for c in pool['codes'] if c.startswith(('600','601','603','605','000','001','002'))]
    
    realtime = {}
    BATCH = 300
    for i in range(0, len(codes), BATCH):
        batch = codes[i:i+BATCH]
        pref = ['sh'+c if c.startswith(('6','9')) else 'sz'+c for c in batch]
        url = 'https://hq.sinajs.cn/list=' + ','.join(pref)
        try:
            r = subprocess.run(['curl','-sL','--max-time','10',url,'-H','Referer: https://finance.sina.com.cn'], capture_output=True, timeout=15)
            for line in r.stdout.decode('gbk', errors='ignore').strip().split('\n'):
                m = re.search(r'var hq_str_(\w+)="(.+)"', line)
                if not m: continue
                parts = m.group(2).split(',')
                if len(parts) < 32: continue
                code = m.group(1)[2:]
                p = float(parts[3]) if parts[3] else 0
                pre = float(parts[2]) if parts[2] else 0
                hi = float(parts[4]) if parts[4] else 0
                lo = float(parts[5]) if parts[5] else 0
                vol = float(parts[8]) if parts[8] else 0
                amt = float(parts[9]) if parts[9] else 0
                realtime[code] = {
                    'name': parts[0],
                    'p': round((p-pre)/pre*100, 2) if pre>0 else 0,
                    'cl': round((p-lo)/(hi-lo)*100, 2) if (hi-lo)>0 else 50,
                    'vr': round(vol/(amt/100000000+0.01), 2) if amt>0 else 1.0,
                    'price': p, 'high': hi, 'low': lo, 'vol': vol,
                }
        except:
            pass
    
    t1 = time.time()
    
    # █ 第2步：技术指标（从最近交易日数据库读）██████
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT MAX(date) FROM data_cache')
    last_date = c.fetchone()[0]
    # 优先用当天已有数据
    c.execute('SELECT code, dif_val, wr_val, j_val, k_val, d_val, macd_golden, above_ma5, pos_in_day, close '
              'FROM data_cache WHERE date=?', (last_date,))
    tech = {r[0]: {'dif': r[1] or 0, 'wrv': r[2] or 50, 'jv': r[3] or 50, 'kv': r[4] or 50, 'dv': r[5] or 50,
                   'mg': r[6] or 0, 'a5': r[7] or 0, 'pos': r[8] or 50, 'close': r[9] or 0} for r in c.fetchall()}
    t2 = time.time()
    
    # █ 第3步：行情判定 + 写缓存 ████████████████
    ss = list(realtime.values())
    avg_p = sum(s['p'] for s in ss)/len(ss)
    avg_vr = sum(s['vr'] for s in ss if s['vr']>0)/max(sum(1 for s in ss if s['vr']>0), 1)
    hot = sum(1 for s in ss if 5<=s['p']<=8)
    if avg_p > 0.5: mk = 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    elif avg_p < -0.5: mk = 'down'
    else: mk = 'flat'
    mk_cn = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}[mk]
    
    # 写入当天缓存（只写库里没有的）
    if last_date != today:
        inserted = 0
        for code, s in realtime.items():
            t = tech.get(code, {})
            c.execute('''INSERT OR IGNORE INTO data_cache
                (date,code,name,p,cl,vr,n,dif_val,macd_golden,wr_val,j_val,k_val,d_val,
                 pos_in_day,above_ma5,kdj_golden,close,volume,original_source,cache_version)
                VALUES(?,?,?,?,?,?,0,?,?,?,?,?,?,?,?,0,?,?,?,?)''',
                (today, code, s['name'], round(s['p'],2), round(s['cl'],2), round(s['vr'],2),
                 round(t.get('dif',0),3), int(t.get('mg',0)), round(t.get('wrv',50),1),
                 round(t.get('jv',50),1), round(t.get('kv',50),1), round(t.get('dv',50),1),
                 round(t.get('pos',50),1), int(t.get('a5',0)),
                 round(s['price'],2), round(s['vol'],0),
                 'sina:realtime', today))
            inserted += 1
        conn.commit()
        t_cache = time.time()
        print(f'  写入缓存: {inserted}只, {t_cache-t2:.2f}s')
    t3 = time.time()
    
    # █ 第4步：加载评分策略 + 候选池筛选 █████████
    spec = importlib.util.spec_from_file_location('m',
        os.path.join(V13_DIR, '评分策略', f'分而治之_V10_{mk_cn}_评分策略.py'))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    LEVELS = mod.LEVELS
    LO = ['L0','L1','L2','L3','L4']
    lm = {l['name']: i for i,l in enumerate(LEVELS)}
    
    pool = None
    for ln in LO:
        if ln not in lm: continue
        lv = LEVELS[lm[ln]]; cand = []
        for code, s in realtime.items():
            if s['p'] < lv['p_min'] or s['p'] > min(lv.get('p_max',10),8): continue
            if s['vr'] < lv['vr_min'] or s['vr'] > lv['vr_max']: continue
            if s['cl'] < lv.get('cl_min',0) or s['cl'] > lv.get('cl_max',100): continue
            if 'ST' in s['name'] or '*ST' in s['name']: continue
            t = tech.get(code, {})
            hsl = 0; sz = 0
            if hsl < lv.get('hs_min',0) or hsl > lv.get('hs_max',99): pass
            if sz >= lv.get('sz_max',9999): pass
            cand.append((code, s, t))
        if len(cand) >= 10: pool = cand; break
    
    if not pool:
        print('❌ 候选池不足!')
        conn.close()
        return None
    
    # █ 第5步：评分 + 排名 █████████████████████
    scored = []
    for code, s, t in pool:
        st = {'p': s['p'], 'cl': s['cl'], 'vr': s['vr'],
              'dif': t.get('dif',0), 'mg': t.get('mg',0), 'a5': t.get('a5',0),
              'wrv': t.get('wrv',50), 'jv': t.get('jv',50), 'kv': t.get('kv',50),
              'dv': t.get('dv',50), 'nm': s['name'], 'pos_in_day': t.get('pos',50),
              'kdj_g': 0, 'hsl': 0, 't4_shadow': 0, 'slope5': 0, 'cons_up': 0,
              'd1': 0, 'd2': 0, 'd3': 0}
        sc = mod.score(st)
        scored.append((sc, code, s['name'], s['p'], s['cl']))
    scored.sort(key=lambda x: -x[0])
    
    total = time.time() - t0
    
    # █ 输出 █████████████████████████████████
    print(f'\n🔥 V13 实时策略结果  {today}  {total:.1f}s')
    print(f'{"="*42}')
    print(f'行情: {mk_cn}  |  候选池: {len(pool)}只')
    print(f'API: {t1-t0:.1f}s | 指标: {t2-t1:.1f}s | 评分: {t3-t2:.1f}s')
    print(f'{"-"*42}')
    print(f'{"排名":>3} {"名称":>10} {"代码":>8} {"涨幅":>6} {"评分":>5}')
    print(f'{"-"*42}')
    for rank, (sc, code, nm, p, cl) in enumerate(scored[:5], 1):
        print(f'{rank:>3} {nm:>10} {code:>8} {p:>+5.1f}% {sc:>5.0f}')
    
    conn.close()
    return scored[:3]

if __name__ == '__main__':
    result = run_strategy()
