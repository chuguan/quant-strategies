#!/usr/bin/env python3
"""
通用数据刷新脚本 — 所有版本共用
逻辑：读取原版缓存(.bak) → 检测缺失天数 → 从K线JSON补充 → 保存
旧数据完全不动，只增量补充缺失天数
"""
import json, os, pickle, time, sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===== 路径配置 =====
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
PKL = os.path.join(SCRIPTS_DIR, 'big_cache_full.pkl')
BAK = PKL + '.bak'

# 同步到各版本归档目录
VERSION_COPIES = [
    os.path.join(SCRIPTS_DIR, 'release', 'V50', 'big_cache_full.pkl'),
    os.path.join(SCRIPTS_DIR, 'release', 'V42', 'big_cache_full.pkl'),
    os.path.join(SCRIPTS_DIR, 'release', 'V13', 'big_cache_full.pkl'),
]

sys.stdout.reconfigure(line_buffering=True)

# ===== 指标计算 =====
def calc_ma(s, pd_list):
    n=len(s); r={}
    for pd in pd_list:
        ma=[None]*n
        for i in range(pd-1,n): ma[i]=sum(s[i-pd+1:i+1])/pd
        r[pd]=ma
    return r

def calc_macd(ps):
    n=len(ps); dif=[None]*n; dea=[None]*n
    if n<26: return dif,dea
    e12=[ps[0]]; e26=[ps[0]]
    for i in range(1,n):
        e12.append(e12[-1]*11/13+ps[i]*2/13); e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i]=e12[i]-e26[i]
    dea[0]=dif[0] if dif[0] else 0
    for i in range(1,n): dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    return dif,dea

def calc_kdj(h,l,c,n=9):
    L=len(c); k=[50.0]*L; d=[50.0]*L; j=[50.0]*L
    if L<n: return k,d,j
    for i in range(n-1,L):
        hh=max(h[i-n+1:i+1]); ll=min(l[i-n+1:i+1])
        rsv=50.0 if hh==ll else (c[i]-ll)/(hh-ll)*100
        if i>n-1:
            k[i]=2/3*k[i-1]+1/3*rsv; d[i]=2/3*d[i-1]+1/3*k[i]; j[i]=3*k[i]-2*d[i]
    return k,d,j

def calc_wr(h,l,c,di):
    """WR指标(14日)"""
    if di < 14: return 50
    h14 = max(h[di-13:di+1]); l14 = min(l[di-13:di+1])
    return round((h14-c[di])/(h14-l14+0.001)*100, 1) if h14 != l14 else 50

def calc_atr(h,l,c,di):
    """ATR(14日)"""
    if di < 14: return 0
    trs = [max(h[t]-l[t], abs(h[t]-c[t-1]), abs(l[t]-c[t-1])) for t in range(di-13, di+1)]
    return sum(trs) / 14

def process_stock(fn, missing_dates_set):
    """处理单只股票，只返回缺失日期的数据"""
    try:
        with open(os.path.join(CACHE_DIR, fn), 'rb') as f:
            recs = json.loads(f.read().decode('utf-8'))
        if len(recs) < 100: return {}
        code = fn.replace('.json', '').lstrip('sh').lstrip('sz')  # 匹配原版格式（无前缀）
        
        file_dates = {r['date'] for r in recs}
        needed = file_dates & missing_dates_set
        if not needed:
            return {}
        
        c=[r['close'] for r in recs]; h=[r['high'] for r in recs]
        l=[r['low'] for r in recs]; o=[r['open'] for r in recs]; v=[r['volume'] for r in recs]
        
        mas = calc_ma(c, [5,10,20,60])
        dif, dea = calc_macd(c)
        k,d,j = calc_kdj(h,l,c)
        
        pct = [0.0]
        for i in range(1,len(c)): pct.append((c[i]/c[i-1]-1)*100)
        
        ma5_v = calc_ma(v, [5])[5]
        
        result = {}
        for di, rec in enumerate(recs):
            dt = rec['date']
            if dt not in needed: continue
            if di < 100 or dt < '2025-01-01': continue
            
            cl = c[di]; op = o[di]; hi = h[di]; lo = l[di]
            pct_v = round(pct[di], 2)
            rng = hi - lo
            
            a_v = calc_atr(h,l,c,di)
            atr_p = round(a_v/cl*100, 2) if a_v and cl > 0 else 0
            
            shadow = (hi - max(cl, op)) / (rng + 0.001) * 100 if rng > 0 else 0
            body = abs(cl - op) / op * 100 if op > 0 else 0
            
            pos20 = 0
            if di >= 20:
                h20 = max(h[di-19:di+1]); l20 = min(l[di-19:di+1])
                pos20 = round((cl - l20) / (h20 - l20 + 0.001) * 100, 1)
            
            vol_ratio = round(v[di] / ma5_v[di], 2) if ma5_v[di] and ma5_v[di] > 0 else 1.0
            j_val = round(j[di], 1) if j[di] is not None else 50.0
            k_val = round(k[di], 1) if k[di] is not None else 50.0
            d_val = round(d[di], 1) if d[di] is not None else 50.0
            kdj_g = 1 if di>=9 and k[di] and d[di] and k[di-1] and d[di-1] and k[di]>d[di] and k[di-1]<=d[di-1] else 0
            mg = 1 if di>=1 and dif[di] and dea[di] and dif[di-1] and dea[di-1] and dif[di]>dea[di] and dif[di-1]<=dea[di-1] else 0
            ma5_slope = round((mas[5][di]/mas[5][di-5]-1)*100, 2) if di>=5 and mas[5][di] and mas[5][di-5] and mas[5][di-5] > 0 else 0
            dif_val = round(dif[di], 3) if dif[di] is not None else 0
            amplitude = round((hi - lo) / op * 100, 2) if op > 0 else 0
            
            next_h = round((recs[di+1]['high']/cl-1)*100, 2) if di+1 < len(recs) else None
            next_c = round((recs[di+1]['close']/cl-1)*100, 2) if di+1 < len(recs) else None
            
            d_highs = {}
            for off in range(1, 6):
                d_highs[f'd{off}h'] = round((recs[di+off]['high']/cl-1)*100, 2) if di+off < len(recs) else None
            
            wr_val = calc_wr(h,l,c,di)
            
            result[dt] = {
                'code': code, 'p': pct_v, 'b': round(body,2), 's': round(shadow,1),
                'a': atr_p, 'cl': pos20, 'vol_ratio': vol_ratio, 'j_val': j_val,
                'ma5_slope': ma5_slope, 'dif_val': dif_val, 'amplitude': amplitude,
                'vol': v[di], 'close': round(cl,2), 'body_pct': round(body,2),
                'is_yang': 1 if cl>op else 0,
                'above_ma5': 1 if (mas[5][di] and cl>mas[5][di]) else 0,
                'above_ma10': 1 if (mas[10][di] and cl>mas[10][di]) else 0,
                'above_ma20': 1 if (mas[20][di] and cl>mas[20][di]) else 0,
                'n': next_h, 'next_close': next_c, 'next_high': next_h,
                'mg': mg, 'macd_golden': mg,
                'kv': k_val, 'k_val': k_val, 'dv': d_val, 'd_val': d_val,
                'wrv': wr_val, 'wr_val': wr_val,
                'kdj_g': kdj_g, 'kdj_golden': kdj_g,
                'pos_in_day': round((c[di]-l[di])/(h[di]-l[di]+0.001)*100, 1),
                **d_highs,
            }
        return result
    except:
        return {}

# ===== 公开入口 =====
def update_big_cache(version_label=''):
    """增量补充big_cache，所有版本共用。返回(天数, 总条数)"""
    t0 = time.time()
    
    # 加载原版
    src = BAK if os.path.exists(BAK) else PKL
    label = f'[{version_label}] ' if version_label else ''
    print(f'{label}📖 加载缓存...', flush=True)
    
    with open(src, 'rb') as f:
        cache = pickle.load(f)
    
    existing_dates = set(cache['data'].keys())
    print(f'{label}  现有: {len(existing_dates)}天, 最新={max(existing_dates) if existing_dates else "无"}', flush=True)
    
    # 扫描JSON文件找最新日期
    all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and 
               (f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2'))]
    
    latest_dates = set()
    for fn in all_files[:100]:
        try:
            with open(os.path.join(CACHE_DIR, fn), 'rb') as f:
                recs = json.loads(f.read().decode('utf-8'))
            for r in recs[-2:]:
                latest_dates.add(r['date'])
        except:
            pass
    
    missing = sorted(set(latest_dates) - existing_dates)
    # 过滤掉明显不合理的旧日期
    missing = [d for d in missing if d >= '2025-01-01']
    
    if not missing:
        total = sum(len(v) for v in cache['data'].values())
        print(f'{label}✅ 数据已最新（{len(existing_dates)}天/{total}条），进入指标重算', flush=True)
    else:
        print(f'{label}  缺失{len(missing)}天: {missing}', flush=True)
        
        # 多线程补充
        missing_set = set(missing)
        new_data = defaultdict(list)
        
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(process_stock, fn, missing_set): fn for fn in all_files}
            for i, fut in enumerate(as_completed(futures)):
                res = fut.result()
                for dt, rec in res.items():
                    new_data[dt].append(rec)
                if (i+1) % 500 == 0:
                    total = sum(len(v) for v in new_data.values())
                    print(f'{label}  {i+1}/{len(all_files)} -> +{total}条', flush=True)
        
        # 合并
        for dt in missing:
            if dt in new_data and new_data[dt]:
                cache['data'][dt] = new_data[dt]
                print(f'{label}  ✅ {dt}: +{len(new_data[dt])}条', flush=True)
    
    # ═══ 第二步：重算往前看字段（只处理可能受新数据影响的最后几天） ═══
    print(f'{label}  🔄 重算往前看字段...', flush=True)
    sorted_dates = sorted(cache['data'].keys())
    total_stale = 0
    
    # 只在最后10天里重算（更早的n/d1h~d5h已被原版固化，不会变）
    for di in range(max(0, len(sorted_dates)-10), len(sorted_dates)):
        dt = sorted_dates[di]
        stocks = cache['data'].get(dt, [])
        if not stocks: continue
        
        # 检查n填充率
        n_filled = sum(1 for s in stocks if s.get('n', 0) != 0 and s.get('n') is not None)
        fill_pct = n_filled * 100 // max(len(stocks), 1)
        is_last_day = (dt == sorted_dates[-1])
        if fill_pct >= 90 and not is_last_day:
            continue  # n已90%+填充且不是最后一天，说明数据完整
        
        # 构建未来5天映射
        future_maps = {}
        for off in range(1, 6):
            if di + off < len(sorted_dates):
                fd = sorted_dates[di + off]
                fut_stocks = cache['data'].get(fd, [])
                future_maps[off] = {s['code']: s['close'] for s in fut_stocks if s.get('close')}
            else:
                future_maps[off] = {}
        
        fixed = 0
        for s in stocks:
            close_d0 = s.get('close', 0)
            if not close_d0: continue
            
            d1_close = future_maps[1].get(s['code'])
            if d1_close:
                n_val = round((d1_close / close_d0 - 1) * 100, 2)
                s['n'] = n_val; s['next_close'] = n_val; s['next_high'] = n_val
            
            for off in range(1, 6):
                fclose = future_maps[off].get(s['code'])
                if fclose:
                    s[f'd{off}h'] = round((fclose / close_d0 - 1) * 100, 2)
            
            if d1_close:
                fixed += 1
        
        if fixed:
            total_stale += fixed
            print(f'{label}  🔧 {dt}: n填充{fill_pct}%→{n_filled+fixed}/{len(stocks)} ({fixed}条)', flush=True)
    
    if total_stale:
        print(f'{label}  🔧 共更新{total_stale}条', flush=True)
    
    with open(PKL, 'wb') as f:
        pickle.dump(cache, f)
    
    # 同步到各版本归档
    for vp in VERSION_COPIES:
        try:
            d = os.path.dirname(vp)
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
            with open(vp, 'wb') as f:
                pickle.dump(cache, f)
        except:
            pass
    
    total = sum(len(v) for v in cache['data'].values())
    print(f'{label}✅ 完成! {len(cache["data"])}天/{total}条 (⏱{time.time()-t0:.0f}秒)', flush=True)
    return len(cache['data']), total

if __name__ == '__main__':
    update_big_cache('通用')
