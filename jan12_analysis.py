#!/usr/bin/env python3
"""2026-01-12 完整分析 — 股票名称+收盘价+涨幅"""
import json, os, time, sys, urllib.request, re
sys.stdout.reconfigure(line_buffering=True)

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
TARGET_DATE = "2026-01-12"

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

print("📡 加载数据..."); t0=time.time()
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
cands=[]
code_map={}  # 存价格数据用于获取名称

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
        # M1过滤
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
        
        cands.append({'code':code,'close':cl,'open':op,'high':hi,'low':lo,
                      'pct':today_pct,'shadow':round(shadow,1),'body':round(body,2),
                      'atr_pct':round(atr_p,2),'total':round(total,1),
                      'shadow_score':round(sc_shadow,1),'body_score':round(sc_body,1),
                      'atr_score':round(sc_atr,1),'next_high':next_h})
        
        code_map[code]={'close':cl,'open':op,'high':hi,'low':lo,'pct':today_pct,'volume':recs[di]['volume']}
    except: pass
    if (idx+1)%500==0: print(f"  {idx+1}/{len(all_files)} -> {len(cands)}只候选")

cands.sort(key=lambda x:x['total'], reverse=True)
print(f"✅ {len(cands)}只候选, {time.time()-t0:.0f}秒")

# ═══ 获取名称 ═══
print("📡 获取股票名称...")
codes_list=list(code_map.keys())
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
print(f"✅ {len(names)}只有名称")

# ═══ 输出 ═══
print(f"\n{'='*120}")
print(f"📅 {TARGET_DATE} — 全部候选（共{len(cands)}只）")
print(f"{'='*120}")
print(f"{'排名':<4} {'名称':<10} {'代码':<11} {'收盘':>7} {'涨跌幅':>8} {'实体%':>6} {'上影%':>6} {'ATR%':>6} {'上影分':>6} {'实体分':>6} {'ATR分':>5} {'总分':>5} {'次日高':>6}")
print("-"*90)

for rank,c in enumerate(cands[:30],1):
    name=names.get(c['code'],'—')
    nh=f"{c['next_high']:+.1f}%" if c['next_high'] else "N/A"
    mk="🏆" if rank==1 else ""
    print(f"{rank:<4} {name:<10} {c['code']:<11} {c['close']:>7.2f} {c['pct']:>+7.2f}% {c['body']:>5.2f}% {c['shadow']:>5.1f}% {c['atr_pct']:>5.2f}% {c['shadow_score']:>5.1f} {c['body_score']:>5.1f} {c['atr_score']:>4.1f} {c['total']:>5.1f} {nh:>6} {mk}")

# 冠军详情
if cands:
    c=cands[0]
    name=names.get(c['code'],'—')
    print(f"\n{'='*120}")
    print(f"🥇 冠军: {name}({c['code']})")
    print(f"   收盘价: {c['close']:.2f}  开盘: {c['open']:.2f}  最高: {c['high']:.2f}  最低: {c['low']:.2f}")
    print(f"   当日涨幅: {c['pct']:+.2f}%")
    print(f"   总分: {c['total']}")
    print(f"     上影线: {c['shadow']:.1f}% → {c['shadow_score']}分")
    print(f"     实体: {c['body']:.2f}% → {c['body_score']}分")
    print(f"     ATR: {c['atr_pct']:.2f}% → {c['atr_score']}分")
    print(f"   次日最高: {c['next_high']:+.1f}%" if c['next_high'] else "   次日: 无数据")

# 统计
high_pct=[c for c in cands if c['pct']>8.5]
print(f"\n📊 统计")
print(f"  总候选: {len(cands)}只")
print(f"  涨停(涨>8.5%): {len(high_pct)}只")
print(f"  非涨停: {len(cands)-len(high_pct)}只")

print(f"\n⏱ {time.time()-t0:.0f}秒")
