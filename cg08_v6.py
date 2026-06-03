#!/usr/bin/env python3
"""
CG-08 V6：通达信共振评分版
MACD金叉/死叉评分 + KDJ金叉/死叉评分 + 基础评分
"""
import json, os, sys, time
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)
CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
ST_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST = set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

MIN=1.0; MAX=8.0; TARGET=2.5

def calc_ma(s,p):
    n=len(s);r={}
    for pd in p:
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

print("📡 加载数据..."); t0=time.time()
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and
           (f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2'))]
all_data={}; loaded=0

for fn in all_files:
    try:
        fp=os.path.join(CACHE_DIR,fn)
        with open(fp,'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<80: continue
        code=fn.replace('.json','')
        c=[r['close'] for r in recs];h=[r['high'] for r in recs];l=[r['low'] for r in recs]
        o=[r['open'] for r in recs];v=[r['volume'] for r in recs]
        mas=calc_ma(c,[5,10,20,60]);mas['v5']=calc_ma(v,[5])[5]
        dif,dea,macd=calc_macd(c)
        k,d,j=calc_kdj(h,l,c)
        pct=[0.0]
        for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr)/14
        pos20=[None]*len(c)
        for i in range(19,len(c)):
            h20=max(h[i-19:i+1]);l20=min(l[i-19:i+1])
            pos20[i]=(c[i]-l20)/(h20-l20+0.001)*100
        all_data[code]={"r":recs,"m":mas,"d":dif,"e":dea,"p":pct,"a":atr,
                        "pos20":pos20,"k":k,"d_":d,"j_":j,
                        "di":{r['date']:idx for idx,r in enumerate(recs)}}
        loaded+=1
        if loaded%500==0: print(f"  {loaded}/{len(all_files)}")
    except: pass
print(f"✅ {loaded}只 ({time.time()-t0:.0f}秒)")

# ═══ V6评分 ═══
def calc_score_v6(pct, atr_p, dif_v, dea_v, dif_1, dea_1, k_v, d_v, j_v, k_1, d_1, j_1):
    sc = pct + atr_p * 1.5
    if dif_v: sc += dif_v * 0.5
    
    # ═══ MACD评分 ═══
    # 今天金叉 CROSS(DIF,DEA)
    if dif_v and dea_v and dif_1 and dea_1 and dif_1 < dea_1 and dif_v > dea_v:
        sc += 5
    # 昨天金叉 REF(CROSS(DIF,DEA),1)
    elif dif_1 and dea_1 and k_1 is not None:
        # Check if previous day was golden cross (need 2 days before)
        sc += 2
    # DIF拐头向上 DIF>REF(DIF,1)
    if dif_v and dif_1 and dif_v > dif_1:
        sc += 1
    # 今天死叉 CROSS(DEA,DIF)
    if dif_v and dea_v and dif_1 and dea_1 and dif_1 > dea_1 and dif_v < dea_v:
        sc -= 5
    # 死叉向下 DEA>REF(DEA,1) AND DIF<DEA
    if dea_v and dea_1 and dea_v > dea_1 and dif_v and dea_v and dif_v < dea_v:
        sc -= 10
    
    # ═══ KDJ评分 ═══
    # KDJ金叉 CROSS(K,D) → +5
    if k_v and d_v and k_1 and d_1 and k_1 < d_1 and k_v > d_v:
        sc += 5
    # J拐头向上 J>REF(J,1) → +2
    if j_v and j_1 and j_v > j_1:
        sc += 2
    # J拐头向下 J<REF(J,1) → -5
    if j_v and j_1 and j_v < j_1:
        sc -= 5
    
    return round(sc, 2)

# ═══ 硬过滤 ═══
def pass_m1(sd, di):
    r=sd["r"][di]; cl=r["close"]; op=r["open"]
    m=sd["m"]
    if cl>80: return False
    if not (m[5][di] and m[10][di] and m[20][di] and m[60][di]): return False
    if not (m[5][di]>m[10][di]>m[20][di]>m[60][di]): return False
    dv=sd["d"][di]; ev=sd["e"][di]
    if not (dv and ev and dv>0 and dv>ev): return False
    atrv=sd["a"][di]
    if not (atrv and cl>0 and atrv/cl*100>3): return False
    if not (m[60][di] and cl>m[60][di]): return False
    if not (cl>op): return False
    if not (m[5][di] and cl>m[5][di]): return False
    pct_v=sd["p"][di]
    if not (1<=pct_v<8): return False
    return True

# ═══ 回测 ═══
for yr in ['2025','2026']:
    by_date=defaultdict(list)
    for code,sd in all_data.items():
        if code in ST: continue
        for di in range(80, len(sd["r"])):
            dt=sd["r"][di]["date"]
            if not dt.startswith(yr): continue
            if not pass_m1(sd, di): continue
            if di+1>=len(sd["r"]): continue
            cl=sd["r"][di]["close"]
            atr_p=sd["a"][di]/cl*100 if sd["a"][di] and cl>0 else 0
            sc=calc_score_v6(sd["p"][di], atr_p,
                            sd["d"][di], sd["e"][di],
                            sd["d"][di-1] if di-1>=0 else None,
                            sd["e"][di-1] if di-1>=0 else None,
                            sd["k"][di], sd["d_"][di], sd["j_"][di],
                            sd["k"][di-1] if di-1>=0 else None,
                            sd["d_"][di-1] if di-1>=0 else None,
                            sd["j_"][di-1] if di-1>=0 else None)
            nxt=(sd["r"][di+1]["high"]/cl-1)*100
            by_date[dt].append((code,sc,di))
    
    by_date={k:v for k,v in by_date.items() if len(v)>=5}
    w=t=0
    for dt in sorted(by_date.keys()):
        best=max(by_date[dt], key=lambda x:x[1])
        t+=1
        sd2=all_data[best[0]]
        nxt_val=(sd2["r"][best[2]+1]["high"]/sd2["r"][best[2]]["close"]-1)*100
        if nxt_val>=TARGET: w+=1
    print(f"📊 {yr}: {t}天, 胜率{w/t*100:.1f}% ({w}/{t})")

# 详细日期
print(f"\n{'='*140}")
for dt2 in ['2026-01-09','2026-01-12','2026-01-13','2026-01-14']:
    cs=[]
    for code,sd in all_data.items():
        if code in ST: continue
        di=sd["di"].get(dt2)
        if di is None or di<80: continue
        if not pass_m1(sd, di): continue
        if di+1>=len(sd["r"]): continue
        cl=sd["r"][di]["close"]
        atr_p=sd["a"][di]/cl*100 if sd["a"][di] and cl>0 else 0
        sc=calc_score_v6(sd["p"][di], atr_p,
                        sd["d"][di], sd["e"][di],
                        sd["d"][di-1] if di-1>=0 else None,
                        sd["e"][di-1] if di-1>=0 else None,
                        sd["k"][di], sd["d_"][di], sd["j_"][di],
                        sd["k"][di-1] if di-1>=0 else None,
                        sd["d_"][di-1] if di-1>=0 else None,
                        sd["j_"][di-1] if di-1>=0 else None)
        nxt=(sd["r"][di+1]["high"]/cl-1)*100
        cs.append((code,sc,sd["p"][di],atr_p,sd["d"][di],sd["e"][di],
                  sd["d"][di]-sd["e"][di] if sd["d"][di] and sd["e"][di] else 0,
                  sd["k"][di],sd["d_"][di],sd["j_"][di],
                  sd["k"][di-1] if di-1>=0 else 0,sd["d_"][di-1] if di-1>=0 else 0,
                  nxt,cl))
    if len(cs)<5: continue
    cs.sort(key=lambda x:x[1], reverse=True)
    print(f"\n📅 {dt2} 冠军详情:")
    c=cs[0]
    # 计算共振得分
    dif_v=c[4]; dea_v=c[5]; k_v=c[7]; d_v=c[8]; j_v=c[9]; k_1=c[10]; d_1=c[11]
    msc=0
    if dif_v and dea_v and k_1 and d_1: pass
    ksc=0
    kdj_golden="金叉✅" if k_v>=d_v else "死叉⚠️"
    res="✅" if c[12]>=2.5 else "❌"
    print(f"  评分{c[1]:.1f} 涨{c[2]:+.1f}% DIF{c[4]:.2f} DEA{c[5]:.2f} 差{c[6]:.2f}")
    print(f"  K={k_v:.0f} D={d_v:.0f} J={j_v:.0f} {kdj_golden}")
    print(f"  次日最高:{c[12]:+.1f}% {res}")
