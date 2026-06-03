#!/usr/bin/env python3
"""一次性建精确缓存 — 含代码+涨跌幅+名称"""
import json, os, time, sys, urllib.request, re, pickle
sys.stdout.reconfigure(line_buffering=True)

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
OUTPUT = r"C:\Users\12546\AppData\Local\hermes\scripts\precise_cache.pkl"

def calc_ma(s,p):
    n=len(s); r={}
    for pd in p:
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

print("📡 扫描文件..."); t0=time.time()
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
print(f"📦 {len(all_files)}个文件")

# 收集所有日期
all_recs_by_date={}  # {date: [{code, close/prev_close/body/shadow/atr/next_high}]}
code_names={}

for idx,fn in enumerate(all_files):
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<80: continue
        code=fn.replace('.json','')
        c=[r['close'] for r in recs]; h=[r['high'] for r in recs]; l=[r['low'] for r in recs]
        o=[r['open'] for r in recs]; v=[r['volume'] for r in recs]
        mas=calc_ma(c,[5,10,20,60])
        dif,dea=calc_macd(c)
        pct=[0.0]
        for i in range(1,len(c)): pct.append((c[i]/c[i-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr_l)/14
        
        # 对每个符合条件的日期记录
        for di in range(80, len(recs)):
            dt=recs[di]['date']
            if dt<'2025-01-01': continue
            cl=c[di]; op=o[di]; hi=h[di]; lo=l[di]
            if cl>=80: continue
            m=mas
            if not (m[5][di] and m[10][di] and m[20][di] and m[60][di] and
                    m[5][di]>m[10][di]>m[20][di]>m[60][di]): continue
            if not (dif[di] and dea[di] and dif[di]>0 and dif[di]>dea[di]): continue
            a_v=atr[di]
            if not (a_v and cl>0 and a_v/cl*100>3): continue
            if not (m[60][di] and cl>m[60][di]): continue
            if not (cl>op): continue
            if not (m[5][di] and cl>m[5][di]): continue
            
            rng=hi-lo
            shadow=(hi-max(cl,op))/(rng+0.001)*100 if rng>0 else 0
            body=abs(cl-op)/op*100
            atr_p=a_v/cl*100 if a_v and cl>0 else 0
            next_h=round((recs[di+1]["high"]/cl-1)*100,2) if di+1<len(recs) else None
            pct_v=round(pct[di],2)  # ✅ 真实涨跌幅！
            
            if dt not in all_recs_by_date:
                all_recs_by_date[dt]=[]
            all_recs_by_date[dt].append({
                'code':code,'p':pct_v,'b':round(body,2),'s':round(shadow,1),
                'a':round(atr_p,2),'n':next_h,'cl':round(cl,2)
            })
    except: pass
    if (idx+1)%500==0: print(f"  {idx+1}/{len(all_files)} -> 累计{sum(len(v) for v in all_recs_by_date.values())}条")

# 获取全部股票名称（去重）
all_codes=list(set(r['code'] for v in all_recs_by_date.values() for r in v))
print(f"📡 获取{len(all_codes)}只股票名称...")
for i in range(0,len(all_codes),50):
    batch=all_codes[i:i+50]
    sina_codes=[f"sh{c[2:]}" if c.startswith('sh') else f"sz{c[2:]}" for c in batch]
    try:
        req=urllib.request.Request(f"https://hq.sinajs.cn/list={','.join(sina_codes)}",
                                   headers={'Referer':'https://finance.sina.com.cn'})
        resp=urllib.request.urlopen(req,timeout=5)
        text=resp.read().decode('gbk')
        for line in text.strip().split('\n'):
            m=re.search(r'var hq_str_(sh\d+|sz\d+)="([^,]+)',line)
            if m:
                ck=m.group(1); orig=f"sh{ck[2:]}" if ck.startswith('sh') else f"sz{ck[2:]}"
                code_names[orig]=m.group(2)
    except: pass

# 保存
cache={'data':all_recs_by_date,'names':code_names,'build_time':time.time()-t0}
with open(OUTPUT,'wb') as f: pickle.dump(cache,f)
print(f"\n✅ 保存完成: {OUTPUT}")
print(f"📅 {len(all_recs_by_date)}个交易日")
print(f"📊 {sum(len(v) for v in all_recs_by_date.values())}条候选记录")
print(f"🏷️ {len(code_names)}只股票名称")
print(f"⏱ {time.time()-t0:.0f}秒")
