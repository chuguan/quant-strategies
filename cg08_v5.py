#!/usr/bin/env python3
"""
CG-08 V5：MACD金叉/死叉 + KDJ死叉评分
加分规则：
  MACD：DIF>>DEA(强劲金叉)+3, DIF≈DEA(将死叉)-5, DIF<DEA(死叉)-10
  KDJ：K<D(死叉)-10
"""
import json, os, sys, time
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)
CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
ST_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST = set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

MIN_CHG=1.0; MAX_CHG=8.0; TARGET=2.5

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
        pos20=[None]*len(c);j_v=j
        for i in range(19,len(c)):
            h20=max(h[i-19:i+1]);l20=min(l[i-19:i+1])
            pos20[i]=(c[i]-l20)/(h20-l20+0.001)*100
        all_data[code]={"recs":recs,"mas":mas,"dif":dif,"dea":dea,"pct":pct,"atr":atr,
                        "pos20":pos20,"j":j_v,"k":k,"d":d,
                        "date_idx":{r['date']:idx for idx,r in enumerate(recs)}}
        loaded+=1
        if loaded%500==0: print(f"  {loaded}/{len(all_files)}")
    except: pass
print(f"✅ {loaded}只 ({time.time()-t0:.0f}秒)")

# ═══ V5评分 ═══
def calc_score_v5(pct, atr_p, dif_v, dea_v, k_v, d_v, j_v):
    sc = pct + atr_p*1.5
    # DIF加分
    if dif_v: sc += dif_v*0.5
    
    # MACD金叉/死叉评分
    if dif_v and dea_v:
        gap = dif_v - dea_v
        if gap < 0:        # 死叉！直接减10分
            sc -= 10
        elif gap < 0.1:    # 即将死叉（差距极小）
            sc -= 5
        elif gap > 0.5:    # 强劲金叉
            sc += 3
    
    # KDJ死叉检测
    if k_v and d_v and k_v < d_v:  # K<D = 死叉
        sc -= 10
    
    return round(sc,2)

# ═══ 硬过滤 ═══
def pass_m1(sd, di):
    rec=sd["recs"][di]; cl=rec["close"]; op=rec["open"]
    m=sd["mas"]
    if cl>80: return False
    if not (m[5][di] and m[10][di] and m[20][di] and m[60][di]): return False
    if not (m[5][di]>m[10][di]>m[20][di]>m[60][di]): return False
    dv=sd["dif"][di]; dav=sd["dea"][di]
    if not (dv and dav and dv>0 and dv>dav): return False
    atrv=sd["atr"][di]
    if not (atrv and cl>0 and atrv/cl*100>3): return False
    if not (m[60][di] and cl>m[60][di]): return False
    if not (cl>op): return False
    if not (m[5][di] and cl>m[5][di]): return False
    pct_v=sd["pct"][di]
    if not (1<=pct_v<8): return False
    return True

# ═══ 回测 ═══
for yr in ['2025','2026']:
    by_date=defaultdict(list)
    for code,sd in all_data.items():
        if code in ST: continue
        for di in range(80, len(sd["recs"])):
            dt=sd["recs"][di]["date"]
            if not dt.startswith(yr): continue
            if not pass_m1(sd, di): continue
            if di+1>=len(sd["recs"]): continue
            cl=sd["recs"][di]["close"]
            atr_p=sd["atr"][di]/cl*100 if sd["atr"][di] and cl>0 else 0
            sc=calc_score_v5(sd["pct"][di], atr_p, sd["dif"][di], sd["dea"][di],
                            sd["k"][di], sd["d"][di], sd["j"][di])
            nxt_h=(sd["recs"][di+1]["high"]/cl-1)*100
            by_date[dt].append((code,sc,sd["pct"][di],atr_p,sd["dif"][di],sd["dea"][di],
                               sd["k"][di],sd["d"][di],sd["j"][di],nxt_h,cl))
    
    by_date={k:v for k,v in by_date.items() if len(v)>=5}
    w=t=0
    for dt in sorted(by_date.keys()):
        best=max(by_date[dt], key=lambda x:x[1])
        t+=1
        if best[9]>=TARGET: w+=1
    print(f"\n📊 {yr}: {t}天, 胜率{w/t*100:.1f}% ({w}/{t})")

# ═══ 1月9日-12日详细数据 ═══
print(f"\n{'='*130}")
print("📋 2026年1月9日-12日 详细评分对比")
print("="*130)

# 先找4个日期的数据
for target_dt in ['2026-01-09','2026-01-12','2026-01-13','2026-01-14']:
    code_data=[]
    for code,sd in all_data.items():
        if code in ST: continue
        di=sd["date_idx"].get(target_dt)
        if di is None or di<80: continue
        if not pass_m1(sd, di): continue
        if di+1>=len(sd["recs"]): continue
        cl=sd["recs"][di]["close"]
        atr_p=sd["atr"][di]/cl*100 if sd["atr"][di] and cl>0 else 0
        pct_v=sd["pct"][di]
        sc=calc_score_v5(pct_v, atr_p, sd["dif"][di], sd["dea"][di],
                        sd["k"][di], sd["d"][di], sd["j"][di])
        nxt=(sd["recs"][di+1]["high"]/cl-1)*100
        macd_gap=sd["dif"][di]-sd["dea"][di] if sd["dif"][di] and sd["dea"][di] else 0
        kdj_status="金叉" if sd["k"][di]>=sd["d"][di] else "🔴死叉"
        code_data.append((code, sc, pct_v, atr_p, sd["dif"][di], macd_gap,
                         sd["k"][di], sd["d"][di], kdj_status, nxt, cl, sd["recs"][di]["open"], recs := sd["recs"]))
    
    if not code_data: continue
    code_data.sort(key=lambda x:x[1], reverse=True)
    
    print(f"\n📅 {target_dt} (共{len(code_data)}只候选)")
    hdr=f"{'#':<3}{'代码':<14}{'名称':<8}{'买入价':>7}{'涨跌幅':>6}{'ATR':>5}{'DIF':>6}{'DEA':>6}{'D-D':>6}{'K':>5}{'D':>5}{'状态':<6}{'评分':>5}{'次日高':>7}"
    print(hdr)
    print("-"*len(hdr))
    for i,(code,sc,pct,atrp,difv,mgap,kv,dv,kdj_st,nxt,cl,op,*_) in enumerate(code_data[:5],1):
        name="—"
        res="✅" if nxt>=2.5 else "❌"
        print(f"{i:<3}{code:<14}{name:<8}{cl:>7.2f}{pct:>+5.1f}%{atrp:>4.1f}%{difv:>5.2f}{difv-mgap:>5.2f}{mgap:>5.2f}{kv:>4.0f}{dv:>4.0f}{kdj_st:<6}{sc:>5.1f}{nxt:>+5.1f}%{res}")
