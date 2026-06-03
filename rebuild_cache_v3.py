#!/usr/bin/env python3
"""
重建缓存V3 — 从最新JSON文件+腾讯API
包含：量比、换手率、PE、市值、所有技术指标
"""
import json, os, time, sys, urllib.request, re, pickle
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)
CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
OUTPUT = r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
TENCENT_URL = "http://qt.gtimg.cn/q="

def calc_ma(s, pd_list):
    n=len(s); r={}
    for pd in pd_list:
        ma=[None]*n
        for i in range(pd-1,n): ma[i]=sum(s[i-pd+1:i+1])/pd
        r[pd]=ma
    return r

def calc_macd(ps):
    n=len(ps); dif=[None]*n; dea=[None]*n; macd=[None]*n
    if n<26: return dif,dea,macd
    e12=[ps[0]]; e26=[ps[0]]
    for i in range(1,n):
        e12.append(e12[-1]*11/13+ps[i]*2/13); e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i]=e12[i]-e26[i]
    dea[0]=dif[0] if dif[0] else 0
    for i in range(1,n): dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    for i in range(n):
        if dif[i] and dea[i]: macd[i]=dif[i]-dea[i]
    return dif,dea,macd

def calc_kdj(h,l,c,n=9):
    L=len(c); k=[50.0]*L; d=[50.0]*L; j=[50.0]*L
    if L<n: return k,d,j
    for i in range(n-1,L):
        hh=max(h[i-n+1:i+1]); ll=min(l[i-n+1:i+1])
        rsv=50.0 if hh==ll else (c[i]-ll)/(hh-ll)*100
        if i>n-1:
            k[i]=2/3*k[i-1]+1/3*rsv; d[i]=2/3*d[i-1]+1/3*k[i]; j[i]=3*k[i]-2*d[i]
    return k,d,j

print("📡 扫描文件..."); t0=time.time()
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and
           (f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2'))]
print(f"📦 {len(all_files)}个JSON文件")

all_recs=defaultdict(list)

for idx, fn in enumerate(all_files):
    try:
        fp = os.path.join(CACHE_DIR, fn)
        with open(fp, 'rb') as f: recs = json.loads(f.read().decode('utf-8'))
        if len(recs) < 100: continue
        code = fn.replace('.json', '')
        c = [r['close'] for r in recs]; h = [r['high'] for r in recs]
        l = [r['low'] for r in recs]; o = [r['open'] for r in recs]
        v = [r['volume'] for r in recs]
        
        mas = calc_ma(c, [5,10,20,60])
        dif, dea, mcd = calc_macd(c)
        k, d, j = calc_kdj(h, l, c)
        pct = [0.0]
        for i in range(1, len(c)): pct.append((c[i]/c[i-1]-1)*100)
        atr = [None]*len(c)
        if len(c) >= 15:
            for i in range(14, len(c)):
                tr = [max(h[t]-l[t], abs(h[t]-c[t-1]), abs(l[t]-c[t-1])) for t in range(i-13, i+1)]
                atr[i] = sum(tr)/14
        ma5_v = calc_ma(v, [5])[5]
        
        for di in range(100, len(recs)):
            dt = recs[di]['date']
            if dt < '2025-01-01': continue
            cl = c[di]; op = o[di]; hi = h[di]; lo = l[di]
            if cl >= 80: continue
            m = mas
            
            # M1条件（严格版）
            if not (m[5][di] and m[10][di] and m[20][di] and m[60][di]): continue
            if not (m[5][di] > m[10][di] > m[20][di] > m[60][di]): continue
            if not (dif[di] and dea[di] and dif[di] > 0 and dif[di] > dea[di]): continue
            atrv = atr[di]
            if not (atrv and cl > 0 and atrv/cl*100 > 3): continue
            if not (m[60][di] and cl > m[60][di]): continue
            if not (cl > op): continue
            if not (m[5][di] and cl > m[5][di]): continue
            pct_v = round(pct[di], 2)
            if not (1 <= pct_v < 8): continue
            
            rng = hi-lo
            shadow = round((hi-max(cl,op))/(rng+0.001)*100, 1) if rng > 0 else 0
            body = round(abs(cl-op)/op*100, 2) if op > 0 else 0
            atr_p = round(atrv/cl*100, 2) if atrv and cl > 0 else 0
            pos20 = 0
            if di >= 20:
                h20 = max(h[di-19:di+1]); l20 = min(l[di-19:di+1])
                pos20 = round((cl-l20)/(h20-l20+0.001)*100, 1)
            
            # 量比（当日成交量/5日均量）
            vol_today = v[di]
            vol_ma5 = ma5_v[di] if ma5_v[di] else 1
            vol_ratio = round(vol_today/vol_ma5, 2) if vol_ma5 > 0 else 1.0
            
            macd_gap = round(dif[di]-dea[di], 3) if dif[di] and dea[di] else 0
            
            nxt_h = round((recs[di+1]["high"]/cl-1)*100, 2) if di+1 < len(recs) else None
            nxt_c = round((recs[di+1]["close"]/cl-1)*100, 2) if di+1 < len(recs) else None
            
            all_recs[dt].append({
                'code': code, 'p': pct_v, 'b': body, 's': shadow, 'a': atr_p,
                'cl': pos20, 'close': round(cl, 2),
                'is_yang': 1 if cl > op else 0,
                'above_ma5': 1 if (m[5][di] and cl > m[5][di]) else 0,
                'vol_ratio': vol_ratio,  # ✅ 量比
                'dif_val': round(dif[di], 3) if dif[di] else 0,
                'dea_val': round(dea[di], 3) if dea[di] else 0,
                'macd_gap': macd_gap,
                'macd_golden': 1 if dif[di] and dea[di] and dif[di] > dea[di] else 0,
                'k_val': round(k[di], 1) if k[di] else 0,
                'd_val': round(d[di], 1) if d[di] else 0,
                'j_val': round(j[di], 1) if j[di] else 0,
                'kdj_golden': 1 if k[di] and d[di] and k[di] >= d[di] else 0,
                'n': nxt_h,
                'next_close': nxt_c,
            })
    except:
        pass
    if (idx+1) % 500 == 0:
        print(f"  {idx+1}/{len(all_files)} -> {sum(len(v) for v in all_recs.values())}条")

print(f"\n✅ 缓存数据构建完成！{len(all_recs)}天，{sum(len(v) for v in all_recs.values())}条")
print(f"⏱ {time.time()-t0:.0f}秒")

# ═══ 用腾讯API批量获取实时数据（换手率、PE、市值） ═══
all_codes = list(set(r['code'] for v in all_recs.values() for r in v))
print(f"\n📡 获取{len(all_codes)}只股票实时数据（换手率/PE/市值）...")

tx_codes = [c for c in all_codes]
real_data = {}

for i in range(0, len(tx_codes), 50):
    batch = tx_codes[i:i+50]
    url = TENCENT_URL + ','.join(batch)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        txt = resp.read().decode('gbk')
        for line in txt.strip().split(';'):
            if not line.strip(): continue
            m = re.search(r'v_(sh\d+|sz\d+)="([^"]+)', line)
            if not m: continue
            ck = m.group(1); fields = m.group(2).split('~')
            if len(fields) < 60: continue
            try:
                hsl = float(fields[38]) if fields[38] and fields[38].replace('.','',1).lstrip('-').replace(' ','').isdigit() else 0
                pe = float(fields[39]) if fields[39] and fields[39].replace('.','',1).lstrip('-').replace(' ','').isdigit() else 0
                liutong_shizhi = float(fields[44]) if fields[44] and fields[44].replace('.','',1).lstrip('-').replace(' ','').isdigit() else 0
                liangbi = float(fields[56]) if fields[56] and fields[56].replace('.','',1).lstrip('-').replace(' ','').isdigit() else 1.0
                name = fields[1]
                orig = f"sh{ck[2:]}" if ck.startswith('sh') else f"sz{ck[2:]}"
                real_data[orig] = {
                    'name': name,
                    'liangbi': liangbi,
                    'hsl': hsl,
                    'pe': pe,
                    'shizhi': liutong_shizhi,
                }
            except:
                continue
    except:
        pass

print(f"✅ 获取名称/换手率/PE/市值: {len(real_data)}只")

# 名字补全
names = {}
for orig, rd in real_data.items():
    if rd['name']: names[orig] = rd['name']

cache = {
    'data': dict(all_recs),
    'names': names,
    'real': real_data,
    'build_time': time.time() - t0,
    'date': time.strftime('%Y-%m-%d %H:%M:%S'),
}

with open(OUTPUT, 'wb') as f:
    pickle.dump(cache, f)

print(f"\n✅ 缓存保存: {OUTPUT}")
print(f"📅 {len(all_recs)}天, {sum(len(v) for v in all_recs.values())}条, {len(real_data)}只实时数据")
print(f"⏱ 总耗时: {time.time()-t0:.0f}秒")
