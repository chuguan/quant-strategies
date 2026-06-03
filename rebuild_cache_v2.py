#!/usr/bin/env python3
"""
重建big_cache V2 — 增加DEA、K值、D值、MACD/KDJ状态
一次构建（~2分钟），后续1秒出
"""
import json, os, time, sys, urllib.request, re, pickle
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)
CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
OUTPUT = r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"

def calc_ma(s,pd_list):
    n=len(s);r={}
    for pd in pd_list:
        ma=[None]*n
        for i in range(pd-1,n): ma[i]=sum(s[i-pd+1:i+1])/pd
        r[pd]=ma
    return r

def calc_macd(ps):
    n=len(ps);dif=[None]*n;dea=[None]*n;macd=[None]*n
    if n<26: return dif,dea,macd
    e12=[ps[0]];e26=[ps[0]]
    for i in range(1,n):
        e12.append(e12[-1]*11/13+ps[i]*2/13);e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i]=e12[i]-e26[i]
    dea[0]=dif[0] if dif[0] else 0
    for i in range(1,n): dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    for i in range(n):
        if dif[i] and dea[i]: macd[i]=dif[i]-dea[i]
    return dif,dea,macd

def calc_kdj(h,l,c,n=9):
    L=len(c);k=[50.0]*L;d=[50.0]*L;j=[50.0]*L
    if L<n: return k,d,j
    for i in range(n-1,L):
        hh=max(h[i-n+1:i+1]);ll=min(l[i-n+1:i+1])
        rsv=50.0 if hh==ll else (c[i]-ll)/(hh-ll)*100
        if i>n-1:
            k[i]=2/3*k[i-1]+1/3*rsv;d[i]=2/3*d[i-1]+1/3*k[i]
            j[i]=3*k[i]-2*d[i]
    return k,d,j

print("📡 扫描文件..."); t0=time.time()
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and
           (f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2'))]
print(f"📦 {len(all_files)}个文件")

all_recs=defaultdict(list)
code_names={}

for idx,fn in enumerate(all_files):
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<100: continue
        code=fn.replace('.json','')
        c=[r['close'] for r in recs];h=[r['high'] for r in recs];l=[r['low'] for r in recs]
        o=[r['open'] for r in recs];v=[r['volume'] for r in recs]
        mas=calc_ma(c,[5,10,20,60])
        dif,dea,mcd=calc_macd(c)
        k,d,j=calc_kdj(h,l,c)
        pct=[0.0]
        for i in range(1,len(c)): pct.append((c[i]/c[i-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr)/14
        ma5_v=calc_ma(v,[5])[5]
        
        for di in range(100,len(recs)):
            dt=recs[di]['date']
            if dt<'2025-01-01': continue
            cl=c[di];op=o[di];hi=h[di];lo=l[di]
            if cl>=80: continue
            m=mas
            # 放宽M1：MA5>MA60 + MACD零轴上 + ATR>2% + 站MA60
            if not (m[5][di] and m[60][di] and m[5][di]>m[60][di]): continue
            if not (dif[di] and dea[di] and dif[di]>0 and dif[di]>dea[di]): continue
            atrv=atr[di]
            if not (atrv and cl>0 and atrv/cl*100>2): continue
            if not (m[60][di] and cl>m[60][di]): continue
            pct_v=round(pct[di],2)
            if not (1<=pct_v<8): continue
            
            rng=hi-lo
            shadow=round((hi-max(cl,op))/(rng+0.001)*100,1) if rng>0 else 0
            body=round(abs(cl-op)/op*100,2) if op>0 else 0
            atr_p=round(atrv/cl*100,2) if atrv and cl>0 else 0
            pos20=0
            if di>=20:
                h20=max(h[di-19:di+1]);l20=min(l[di-19:di+1])
                pos20=round((cl-l20)/(h20-l20+0.001)*100,1)
            
            # 新增关键数据
            macd_gap=round(dif[di]-dea[di],3) if dif[di] and dea[di] else 0
            kdj_golden=1 if k[di] and d[di] and k[di]>=d[di] else 0  # 1=金叉
            macd_golden=1 if dif[di] and dea[di] and dif[di]>dea[di] else 0  # 1=金叉
            
            nxt_h=round((recs[di+1]["high"]/cl-1)*100,2) if di+1<len(recs) else None
            nxt_c=round((recs[di+1]["close"]/cl-1)*100,2) if di+1<len(recs) else None
            
            all_recs[dt].append({
                'code':code,
                'p':pct_v,  # 涨跌幅
                'b':body,   # 实体
                's':shadow, # 上影
                'a':atr_p,  # ATR
                'cl':pos20, # 收盘位
                'close':round(cl,2),
                'is_yang':1 if cl>op else 0,
                'above_ma5':1 if (m[5][di] and cl>m[5][di]) else 0,
                'above_ma10':1 if (m[10][di] and cl>m[10][di]) else 0,
                'above_ma20':1 if (m[20][di] and cl>m[20][di]) else 0,
                # V5新增：MACD+KDJ完整数据
                'dif_val':round(dif[di],3) if dif[di] else 0,
                'dea_val':round(dea[di],3) if dea[di] else 0,
                'macd_gap':macd_gap,           # DIF-DEA差值
                'macd_golden':macd_golden,      # MACD金叉标志
                'k_val':round(k[di],1) if k[di] else 0,
                'd_val':round(d[di],1) if d[di] else 0,
                'j_val':round(j[di],1) if j[di] else 0,
                'kdj_golden':kdj_golden,        # KDJ金叉标志
                # 次日数据
                'n':nxt_h,
                'next_close':nxt_c,
            })
    except: pass
    if (idx+1)%500==0: print(f"  {idx+1}/{len(all_files)} -> {sum(len(v) for v in all_recs.values())}条")

# 股票名称
all_codes=list(set(r['code'] for v in all_recs.values() for r in v))
print(f"📡 获取{len(all_codes)}只名称...")
for i in range(0,len(all_codes),50):
    batch=all_codes[i:i+50]
    scodes=[f"sh{c[2:]}" if c.startswith('sh') else f"sz{c[2:]}" for c in batch]
    try:
        req=urllib.request.Request(f"https://hq.sinajs.cn/list={','.join(scodes)}",
                                   headers={'Referer':'https://finance.sina.com.cn'})
        resp=urllib.request.urlopen(req,timeout=5)
        text=resp.read().decode('gbk')
        for line in text.strip().split('\n'):
            m=re.search(r'var hq_str_(sh\d+|sz\d+)="([^,]+)',line)
            if m:
                ck=m.group(1);orig=f"sh{ck[2:]}" if ck.startswith('sh') else f"sz{ck[2:]}"
                code_names[orig]=m.group(2)
    except: pass

cache={'data':dict(all_recs),'names':code_names,'build_time':time.time()-t0}
with open(OUTPUT,'wb') as f: pickle.dump(cache,f)
total=sum(len(v) for v in all_recs.values())
print(f"\n✅ 重建完成！{len(all_recs)}天, {total}条, {len(all_codes)}只, {time.time()-t0:.0f}秒")
print(f"新增字段: dea_val, macd_gap, macd_golden, k_val, d_val, kdj_golden")
print(f"以后查询: <1秒")
