#!/usr/bin/env python3
"""重建 big_cache_full.pkl — 用活跃股票池3043.json 作为唯一股票列表"""
import os, sys, json, subprocess, time, pickle
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(SCRIPTS_DIR)

PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

# 从活跃股票池文件加载3043只
with open('活跃股票池_3043.json', 'r', encoding='utf-8') as f:
    pool = json.load(f)

codes = pool['codes']
stocks_info = pool['info']
print(f'📋 加载活跃股票池: {len(codes)}只', flush=True)
print(f'   沪主板: {pool["sh_count"]}只  深主板: {pool["sz_count"]}只', flush=True)

# 处理K线
def process_stock(code):
    mkt = PREFIX(code)
    fp = os.path.join(CACHE_DIR, f'{mkt}{code}.json')
    if not os.path.exists(fp):
        # 没有K线则从API拉
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt}{code},day,,,300,qfq'
        try:
            r = subprocess.run(['curl','-s','--max-time','10',url], capture_output=True, timeout=15)
            text = r.stdout.decode('gbk', errors='replace')
            d = json.loads(text) if text.strip().startswith('{') else {}
            sd = d.get('data',{}).get(f'{mkt}{code}',{})
            k = sd.get('qfqday',[])
            if not k:
                for key in sd:
                    if isinstance(sd[key],list) and sd[key] and isinstance(sd[key][0],list): k=sd[key]; break
            if not k or len(k) < 20: return None
            recs = [{'date':x[0],'open':float(x[1]),'close':float(x[2]),'high':float(x[3]),'low':float(x[4]),'volume':float(x[5])} for x in k]
            json.dump(recs, open(fp,'w'))
            kdata = recs
        except: return None
    else:
        try:
            with open(fp) as f: kdata = json.load(f)
        except: return None
    
    if not kdata or len(kdata) < 20: return None
    
    nm = stocks_info.get(code, {}).get('name', f'?{code}')
    results = {}
    for i in range(len(kdata)):
        dt = kdata[i]['date']
        if dt < '2024-01-02': continue
        if dt > '2026-05-28': continue
        df = kdata[:i+1]; n = len(df)
        close = [r['close'] for r in df]
        high = [r['high'] for r in df]
        low = [r['low'] for r in df]
        
        # n = 次日最高涨幅
        nh = 0
        if i+1 < len(kdata):
            nh = round((kdata[i+1]['high']/kdata[i]['close']-1)*100, 1)
        
        if n < 20: continue
        
        # 涨跌幅
        p = round((close[-1]/kdata[i-1]['close']-1)*100, 2) if i > 0 else 0
        vr = kdata[i]['volume']/max(kdata[i-1]['volume'],1) if i > 0 else 1
        
        # MA5
        ma5 = sum(close[-5:])/5 if n >= 5 else close[-1]
        a5 = 1 if close[-1] > ma5 else 0
        
        # MACD
        ema12 = close[-1]; ema26 = close[-1]
        for j in range(n-2, max(n-27, -1), -1):
            ema12 = close[j]*2/13+ema12*11/13
            ema26 = close[j]*2/27+ema26*25/27
        dfv = round(ema12-ema26,3); mg = 1 if dfv > 0 else 0
        
        # KDJ
        kv = dv = jv = 50; kdj_g = 0
        if n >= 9:
            h9 = max(high[-9:]); l9 = min(low[-9:])
            rsv = (close[-1]-l9)/(h9-l9+1e-10)*100
            kv = round(rsv*2/3+50/3,1); dv = round(kv*2/3+50/3,1); jv = round(3*kv-2*dv,1)
            kdj_g = 1 if kv > dv else 0
        
        # WR
        wr = 50
        if n >= 21:
            h21 = max(high[-21:]); l21 = min(low[-21:])
            wr = round(100*(h21-close[-1])/(h21-l21+1e-10),1)
        
        # CL
        cl = 50
        if n >= 20:
            h20 = max(high[-20:]); l20 = min(low[-20:])
            cl = round((close[-1]-l20)/(h20-l20+1e-10)*100,1)
        
        results[dt] = {
            'code': code, 'p': p, 'vol_ratio': vr, 'cl': cl,
            'dif_val': dfv, 'macd_golden': mg, 'above_ma5': a5,
            'wr_val': wr, 'k_val': kv, 'd_val': dv, 'j_val': jv,
            'kdj_golden': kdj_g, 'n': nh, 'close': close[-1], 'name': nm
        }
    return results

print("🔄 并行处理K线数据...", flush=True)
all_data = {}
real_info = {}
names_info = {}
done = 0
with ThreadPoolExecutor(max_workers=16) as pool:
    futs = {pool.submit(process_stock, c): c for c in codes}
    for fut in as_completed(futs):
        res = fut.result()
        if res:
            code = futs[fut]
            si = stocks_info.get(code, {})
            real_info[code] = {'hsl': si.get('hsl', 0), 'pe': si.get('pe', 0), 'shizhi': si.get('sz', 0)}
            names_info[code] = si.get('name', f'?{code}')
            for dt, item in res.items():
                if dt not in all_data: all_data[dt] = {}
                if code not in all_data[dt]:
                    all_data[dt][code] = item
        done += 1
        if done % 200 == 0: print(f"  {done}/{len(codes)}", flush=True)

# 整理成统一格式
data = {}
for dt in sorted(all_data.keys()):
    entries = []
    for code, item in all_data[dt].items():
        entries.append({
            'code': code, 'p': item['p'], 'vol_ratio': item['vol_ratio'],
            'cl': item['cl'], 'dif_val': item['dif_val'], 'macd_golden': item['macd_golden'],
            'above_ma5': item['above_ma5'], 'wr_val': item['wr_val'],
            'k_val': item['k_val'], 'd_val': item['d_val'], 'j_val': item['j_val'],
            'kdj_golden': item['kdj_golden'], 'n': item['n'], 'close': item['close'],
        })
    data[dt] = entries

pickle.dump({'data': data, 'real': real_info, 'names': names_info}, open('big_cache_full.pkl', 'wb'))
dates = sorted(data.keys())

print(f"\n✅ 缓存重建完成", flush=True)
print(f"日期: {dates[0]} ~ {dates[-1]}, 共{len(dates)}天", flush=True)
print(f"股票: {len(real_info)}只（= 活跃股票池3043只中的{len(real_info)}只有K线数据）", flush=True)
for dt in dates[-5:]:
    ss = data[dt]
    ps = [s['p'] for s in ss if abs(s['p']) < 15]
    ap = sum(ps)/len(ps) if ps else 0
    up = len([p for p in ps if p > 0])
    dn = len([p for p in ps if p < 0])
    print(f"  {dt}: {len(ss)}只 涨{up}/跌{dn} 均{ap:.2f}%", flush=True)
