#!/usr/bin/env python3
"""快速版 — 带缓存的数据加载器"""
import json, os, time, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_DIR=r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
CACHE_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\.cand_cache.json"

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

# ── 缓存的key = 文件列表hash，确保数据变化时自动重建 ──
def get_cache_key():
    files=sorted([f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))])
    # 取前200只的修改时间+大小做hash
    h=hashlib.md5()
    for fn in files[:200]:
        fp=os.path.join(CACHE_DIR,fn)
        try: h.update(f"{fn}:{os.path.getmtime(fp)}:{os.path.getsize(fp)}".encode())
        except: pass
    return h.hexdigest()[:12]

def load_or_process():
    cache_key=get_cache_key()
    
    # 检查缓存
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE,'rb') as f:
                cached=json.loads(f.read().decode('utf-8'))
            if cached.get("_key")==cache_key:
                print(f"✅ 命中缓存! ({len(cached['cands_2025'])+len(cached['cands_2026'])}天)")
                return cached["cands_2025"],cached["cands_2026"]
    except: pass
    
    print("📡 首次加载，需处理3427只股票...")
    t0=time.time()
    
    # ═══ 多线程加载 ═══
    all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
    
    def load_one(fn):
        try:
            with open(os.path.join(CACHE_DIR,fn),'rb') as f:
                recs=json.loads(f.read().decode('utf-8'))
            if len(recs)<80: return None
            if recs[-1]["date"]<"2020": return None
            code=fn.replace('.json','')
            c=[r['close'] for r in recs]; h=[r['high'] for r in recs]; l=[r['low'] for r in recs]
            o=[r['open'] for r in recs]; v=[r['volume'] for r in recs]
            mas=calc_ma(c,[5,10,20,60])
            dif,dea=calc_macd(c)
            pct=[0.0]
            for idx in range(1,len(c)): pct.append((c[idx]/c[idx-1]-1)*100)
            atr=[None]*len(c)
            if len(c)>=15:
                for i in range(14,len(c)):
                    tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                    atr[i]=sum(tr_l)/14
            return (code,{"c":c,"h":h,"l":l,"o":o,"v":v,"mas":mas,"dif":dif,"dea":dea,"pct":pct,"recs":recs,"atr":atr})
        except: return None
    
    all_codes={}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs={ex.submit(load_one,fn):fn for fn in all_files}
        done=0
        for f in as_completed(futs):
            r=f.result()
            if r: all_codes[r[0]]=r[1]
            done+=1
            if done%500==0: print(f"  {done}/{len(all_files)}", flush=True)
    
    print(f"  ✅ {len(all_codes)}只活跃股, {time.time()-t0:.0f}秒")
    
    # ═══ M1条件 & 特征提取 ═══
    def pass_M1(c,s,d):
        if s["c"][d]>=80: return False
        m=s["mas"]
        if not (m[5][d] and m[10][d] and m[20][d] and m[60][d] and m[5][d]>m[10][d]>m[20][d]>m[60][d]): return False
        if not (s["dif"][d] and s["dea"][d] and s["dif"][d]>0 and s["dif"][d]>s["dea"][d]): return False
        a=s["atr"][d]; cl=s["c"][d]
        if not (a and cl>0 and a/cl*100>3): return False
        if not (m[60][d] and cl>m[60][d]): return False
        if s["c"][d]<=s["o"][d]: return False
        if not (m[5][d] and cl>m[5][d]): return False
        return True
    
    print("📝 提取候选特征...")
    cands_2025=[]; cands_2026=[]
    
    for code,sd in list(all_codes.items()):
        for di in range(80,len(sd["recs"])-1):
            if not pass_M1(code,sd,di): continue
            dt=sd["recs"][di]["date"]
            cl=sd["c"][di]; op=sd["o"][di]; hi=sd["h"][di]; lo=sd["l"][di]
            rng=hi-lo; shadow=(hi-max(cl,op))/(rng+0.001)*100 if rng>0 else 0
            body=abs(cl-op)/op*100
            atr_p=sd["atr"][di]/cl*100 if sd["atr"][di] and cl>0 else 0
            next_h=round((sd["recs"][di+1]["high"]/cl-1)*100,2)
            feat={"d":dt,"y":dt[:4],"s":round(shadow,1),"b":round(body,1),"a":round(atr_p,1),"n":next_h}
            if dt.startswith("2025"): cands_2025.append(feat)
            elif dt.startswith("2026"): cands_2026.append(feat)
    
    print(f"  ✅ 2025:{len(cands_2025)}条, 2026:{len(cands_2026)}条, {time.time()-t0:.0f}秒")
    
    # 保存缓存
    cache_data={"_key":cache_key,"cands_2025":cands_2025,"cands_2026":cands_2026}
    with open(CACHE_FILE,'w',encoding='utf-8') as f:
        json.dump(cache_data,f,ensure_ascii=False)
    print(f"  💾 缓存已保存: {CACHE_FILE}")
    
    return cands_2025, cands_2026

# ═══ 主入口 ═══
if __name__=="__main__":
    t0=time.time()
    cands_2025,cands_2026=load_or_process()
    print(f"⏱ 总用时: {time.time()-t0:.0f}秒")
    
    # 按天分组
    from collections import defaultdict
    by_day_2025=defaultdict(list)
    by_day_2026=defaultdict(list)
    for c in cands_2025: by_day_2025[c["d"]].append(c)
    for c in cands_2026: by_day_2026[c["d"]].append(c)
    
    # 过滤出≥5只的天
    days_2025=[c for c in by_day_2025.values() if len(c)>=5]
    days_2026=[c for c in by_day_2026.values() if len(c)>=5]
    print(f"📊 ≥5天: 2025={len(days_2025)}天, 2026={len(days_2026)}天")
    
    # 跑多权重测试
    schemes=[
        ("v14(35-1.2x)",lambda s: max(0,35-s*1.2) if s<30 else 0),
        ("A(40-2x)",lambda s: max(0,40-s*2) if s<20 else 0),
        ("B(30-1.5x)",lambda s: max(0,30-s*1.5) if s<20 else 0),
        ("C(50-2.5x)",lambda s: max(0,50-s*2.5) if s<20 else 0),
        ("D(25-1x)",lambda s: max(0,25-s) if s<20 else 0),
        ("E(20-0.8x)",lambda s: max(0,20-s*0.8) if s<25 else 0),
        ("F(分段30/20/10)",lambda s: 30 if s<5 else(20 if s<10 else(10 if s<15 else 0))),
        ("G(45-1.8x)",lambda s: max(0,45-s*1.8) if s<25 else 0),
        ("H(38-1.5x)",lambda s: max(0,38-s*1.5) if s<25 else 0),
        ("I(极严:15%上0)",lambda s: max(0,30-s*2) if s<15 else 0),
        ("J(55-2x)",lambda s: max(0,55-s*2) if s<27 else 0),
        ("K(上影<10%+20)",lambda s: 20 if s<10 else 0),
        ("L(100-4x)",lambda s: max(0,100-s*4) if s<25 else 0),
        ("M(60-3x)",lambda s: max(0,60-s*3) if s<20 else 0),
    ]
    
    def score(d,sfn): return sfn(d["s"])+min(d["b"]*3,25)+min(d["a"]*2,16)
    
    print(f"\n{'方案':<20} {'2025胜率':>14} {'2026胜率':>14} {'平均':>8}")
    print("-"*56)
    
    baseline=0
    for sname,sfn in schemes:
        res={}
        for yn,days in [("2025",days_2025),("2026",days_2026)]:
            wins=0
            for cand in days:
                champ=max(cand,key=lambda d:score(d,sfn))
                if champ["n"] and champ["n"]>=2.5: wins+=1
            res[yn]=(wins/len(days)*100,len(days))
        avg=(res["2025"][0]+res["2026"][0])/2
        if "v14" in sname: baseline=avg
        ch=avg-baseline
        mk="🔥" if ch>0.5 else("✅" if ch>=-0.5 else"")
        print(f"{sname:<20} {res['2025'][0]:>5.1f}%/{res['2025'][1]:>3}d {res['2026'][0]:>5.1f}%/{res['2026'][1]:>3}d {avg:>5.1f}% {mk}")
    
    print(f"\n🏆 比v14好的:")
    better=[(avg,sname) for sname,sfn in schemes 
            for avg in [sum([
                sum(1 for c in days_2025 if max(c,key=lambda d:score(d,sfn))["n"] and max(c,key=lambda d:score(d,sfn))["n"]>=2.5)/len(days_2025)*100,
                sum(1 for c in days_2026 if max(c,key=lambda d:score(d,sfn))["n"] and max(c,key=lambda d:score(d,sfn))["n"]>=2.5)/len(days_2026)*100
            ])/2]]
    # Actually let me just redo this properly
