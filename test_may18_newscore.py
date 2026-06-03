#!/usr/bin/env python3
"""
复测5月18日：新评分（MACD向上+KDJ触底反弹）
"""
import json, os, sys, pickle
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
ST_FILE = r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

BIG_CACHE = r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
with open(BIG_CACHE,'rb') as f:
    names_cache=pickle.load(f)['names']

def calc_ma(s, p):
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

# ═══ 新评分：MACD向上 + KDJ触底反弹 ═══
def calc_new_score(pct, atr_p, dif_v, dif_prev, ma5_5d, k_slope, d_slope, j_slope):
    sc = 0
    # 基础
    sc += pct * 1
    sc += atr_p * 1.5
    sc += dif_v * 0.5 if dif_v else 0
    
    # ① MACD向上（DIF今日>昨日）+3分
    if dif_v and dif_prev and dif_v > dif_prev:
        sc += 3
    
    # ② MA5斜率>8% +3分
    if ma5_5d and ma5_5d > 8:
        sc += 3
    
    # ③ J斜率 > K斜率 AND J斜率 > D斜率（J向上为正）+3分
    # J线领涨 → 股价还有动能
    if j_slope and j_slope > 0 and k_slope and d_slope:
        if j_slope > k_slope and j_slope > d_slope:
            sc += 3
    return sc

def test_date(target_date):
    """复测某一天"""
    all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and
               (f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2'))]
    
    cands_new=[]
    cands_old=[]
    loaded=0
    
    for fn in all_files:
        try:
            fp=os.path.join(CACHE_DIR,fn)
            with open(fp,'rb') as f: recs=json.loads(f.read().decode('utf-8'))
            if len(recs)<80: continue
            code=fn.replace('.json','')
            if code in ST: continue
            
            c=[r['close'] for r in recs]; h=[r['high'] for r in recs]
            l=[r['low'] for r in recs]; o=[r['open'] for r in recs]
            v=[r['volume'] for r in recs]
            mas=calc_ma(c,[5,10,20,60])
            dif,dea,macd=calc_macd(c)
            k,d,j=calc_kdj(h,l,c)
            pct=[0.0]
            for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
            atr=[None]*len(c)
            if len(c)>=15:
                for i in range(14,len(c)):
                    tr=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                    atr[i]=sum(tr)/14
            
            date_idx={r['date']:idx for idx,r in enumerate(recs)}
            di=date_idx.get(target_date)
            if di is None or di<80: continue
            
            cl=c[di]; op=o[di]
            m=mas
            
            # 硬过滤
            if cl>80: continue
            if not (m[5][di] and m[10][di] and m[20][di] and m[60][di]): continue
            if not (m[5][di]>m[10][di]>m[20][di]>m[60][di]): continue
            dv=dif[di]; dav=dea[di]
            if not (dv and dav and dv>0 and dv>dav): continue
            atrv=atr[di]
            if not (atrv and cl>0 and atrv/cl*100>3): continue
            if not (m[60][di] and cl>m[60][di]): continue
            if not (cl>op): continue
            if not (m[5][di] and cl>m[5][di]): continue
            pct_v=pct[di]
            if not (1<=pct_v<8): continue
            
            atr_p=atrv/cl*100 if atrv and cl>0 else 0
            dif_prev=dif[di-1] if di>0 and dif[di-1] else None
            ma5_5d=(m[5][di]/m[5][di-5]-1)*100 if di>=5 and m[5][di] and m[5][di-5] and m[5][di-5]>0 else 0
            j_v=j[di]; j_prev=j[di-1] if di>0 else None
            
            # 计算KDJ斜率
            k_slope = k[di] - k[di-1] if di>0 and k[di] and k[di-1] else None
            d_slope = d[di] - d[di-1] if di>0 and d[di] and d[di-1] else None
            j_slope = j[di] - j[di-1] if di>0 and j[di] and j[di-1] else None
            
            # 旧评分
            sc_old = pct_v + atr_p*1.5 + (dv*0.5 if dv else 0)
            # 新评分
            sc_new = calc_new_score(pct_v, atr_p, dv, dif_prev, ma5_5d, k_slope, d_slope, j_slope)
            
            cands_old.append((code, sc_old, pct_v, atr_p, dv, j_v))
            cands_new.append((code, sc_new, pct_v, atr_p, dv, ma5_5d, j_v, dif_prev, k[di], d[di]))
            loaded+=1
        except:
            continue
    
    print(f"📊 {target_date} 共{loaded}只通过过滤\n")
    
    # 旧评分排序
    cands_old.sort(key=lambda x:x[1], reverse=True)
    cands_new.sort(key=lambda x:x[1], reverse=True)
    
    names=names_cache
    
    print("="*90)
    print("🏆 【旧评分】Top5（p+a×1.5+dif×0.5）")
    print("="*90)
    print(f"{'#':<3} {'名称':<10} {'代码':<14} {'涨跌幅':>6} {'ATR':>5} {'DIF':>6} {'J值':>6} {'总分':>5}")
    print("-"*60)
    for i,(code,sc,pct_v,atr_p,dv,j_v) in enumerate(cands_old[:5],1):
        name=names.get(code,'?')
        print(f"{i:<3} {name:<10} {code:<14} {pct_v:>+5.1f}% {atr_p:>4.1f}% {dv:>5.2f} {j_v:>5.1f} {sc:>5.1f}")
    
    print(f"\n{'='*90}")
    print("🏆 【新评分】Top5（基础+MACD向上+MA5斜率+KDJ触底反弹）")
    print("="*90)
    print(f"{'#':<3} {'名称':<10} {'代码':<14} {'涨跌幅':>6} {'ATR':>5} {'DIF':>6} {'MA5斜率':>8} {'J值':>6} {'J↑':>4} {'总分':>5}")
    print("-"*80)
    for i,(code,sc,pct_v,atr_p,dv,ma5_5d,j_v,dif_p,k_v,d_v) in enumerate(cands_new[:5],1):
        name=names.get(code,'?')
        j_up="✅" if j_v<30 and dif_p and j_v>j_v else " "
        print(f"{i:<3} {name:<10} {code:<14} {pct_v:>+5.1f}% {atr_p:>4.1f}% {dv:>5.2f} {ma5_5d:>7.1f}% {j_v:>5.1f} {j_up:>4} {sc:>5.1f}")
    
    # 标注垃圾票（汇绿生态）
    for label, cands in [("旧", cands_old), ("新", cands_new)]:
        for i,c in enumerate(cands[:10],1):
            if 'sz001267' in c[0]:
                print(f"\n⚠️ {'旧' if label=='旧' else '新'}评分中 汇绿生态(sz001267) 排第{i}名")

test_date("2026-05-18")
