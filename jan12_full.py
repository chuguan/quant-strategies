#!/usr/bin/env python3
"""重新跑1月12日 — 输出保存到文件，展示全部数据"""
import json, os, time, sys, urllib.request, re
sys.stdout.reconfigure(line_buffering=True)

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
TARGET_DATE = "2026-01-12"
OUTPUT_FILE = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\jan12_full.txt"

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

lines=[]

print("📡 加载数据..."); t0=time.time()
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
cands=[]

for idx,fn in enumerate(all_files):
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<80: continue
        di=next((i for i,r in enumerate(recs) if r['date']==TARGET_DATE),None)
        if di is None: continue
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
        sc_shadow=max(0,35-shadow*1.2) if shadow<30 else 0
        sc_body=min(body*3,25)
        sc_atr=min(atr_p*2,16)
        total=sc_shadow+sc_body+sc_atr
        next_h=round((recs[di+1]["high"]/cl-1)*100,2) if di+1<len(recs) else None
        today_pct=round(pct[di],2)
        
        cands.append((code,cl,op,hi,lo,today_pct,body,shadow,atr_p,sc_shadow,sc_body,sc_atr,total,next_h))
    except: pass
    if (idx+1)%500==0: print(f"  {idx+1}/{len(all_files)} -> {len(cands)}只")

cands.sort(key=lambda x:x[12], reverse=True)
print(f"✅ {len(cands)}只候选")

# 获取名称
print("📡 获取名称...")
codes_list=[c[0] for c in cands]
names={}
for i in range(0,len(codes_list),50):
    batch=codes_list[i:i+50]
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
                names[orig]=m.group(2)
    except: pass

# 写到文件
with open(OUTPUT_FILE,'w',encoding='utf-8') as f:
    f.write(f"📅 {TARGET_DATE} CG-07 v14 全部候选（共{len(cands)}只）\n")
    f.write("="*120+"\n")
    hdr=f"{'排名':<4} {'名称':<10} {'代码':<12} {'收盘':>7} {'涨%':>7} {'实体%':>6} {'上影%':>6} {'ATR%':>6} {'上影分':>6} {'实体分':>6} {'ATR分':>5} {'总分':>5} {'次日':>6}\n"
    f.write(hdr)
    f.write("-"*90+"\n")
    for rank,c in enumerate(cands,1):
        code,cl,op,hi,lo,tpct,bd,shd,atrp,sh_sc,bd_sc,atr_sc,tot,nh=c
        name=names.get(code,'—')
        nh_s=f"{nh:+.1f}%" if nh else "N/A"
        mk="🏆" if rank==1 else ""
        f.write(f"{rank:<4} {name:<10} {code:<12} {cl:>7.2f} {tpct:>+6.2f}% {bd:>5.2f}% {shd:>5.1f}% {atrp:>5.2f}% {sh_sc:>5.1f} {bd_sc:>5.1f} {atr_sc:>4.1f} {tot:>5.1f} {nh_s:>6} {mk}\n")

# 统计
zt=[c for c in cands if c[5]>8.5]
nz=[c for c in cands if c[5]<=8.5]
with open(OUTPUT_FILE,'a',encoding='utf-8') as f:
    f.write(f"\n📊 统计\n")
    f.write(f"  总候选: {len(cands)}只\n")
    f.write(f"  涨停(>8.5%): {len(zt)}只\n")
    f.write(f"  非涨停: {len(nz)}只\n")
    f.write(f"\n⏱ {time.time()-t0:.0f}秒\n")

print(f"✅ 完整列表已保存到: {OUTPUT_FILE}")
print(f"📦 共{len(cands)}只")
print(f"⏱ {time.time()-t0:.0f}秒")
