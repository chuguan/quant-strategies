"""检查4策略 — 涨幅<8% + 池≥10 + 沪深主板"""
import pickle, os, sys
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if '2025-01-01'<=x<'2026-06-01']

def is_main(code):
    return not (code.startswith('sz300') or code.startswith('sh688') or code.startswith('sh8'))

def cm(stocks):
    if not stocks: return 'flat'
    ps=[s.get('p',0) or 0 for s in stocks]
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    avg_p=sum(ps)/len(ps); avg_vr=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    if avg_p<-0.5: return 'down'
    return 'flat'

def md(dif,mg):
    if mg and dif>0.5: return 10
    if mg and dif>0.2: return 8
    if mg: return 6
    if dif>0.5: return 4
    if dif>0: return 2
    return 0

LV={
'real_up':[[3,7,0.6,2.5,5,15,200,60,90],[2,7,0.6,2.5,3,20,200,50,95],[1,7,0.5,3.0,2,25,300,40,95],[0,7,0.4,3.5,1,30,400,30,98],[-1,7,0.3,4.0,0.5,35,500,20,99]],
'fake_up':[[0,6,0.6,2.5,5,20,200,30,95],[-1,6,0.5,3.0,3,25,200,20,95],[-1,7,0.4,3.5,2,30,300,15,98],[-2,7,0.3,4.0,1,35,400,10,99],[-3,7,0.2,5.0,0.5,40,500,0,100]],
'down':[[-3,7,0.4,3.5,1,30,300,10,98],[-4,7,0.3,4.0,0.5,35,400,5,99],[-5,7,0.2,4.5,0.3,40,500,0,99],[-5,7,0.2,5.0,0.3,45,500,0,100],[-5,7,0.1,5.0,0.2,50,1000,0,100]],
'flat':[[0,7,0.6,2.5,3,20,200,40,95],[-1,7,0.5,3.0,2,25,200,30,95],[-2,7,0.4,3.5,1,30,300,20,98],[-3,7,0.3,4.0,0.5,35,400,10,99],[-5,7,0.2,5.0,0.3,40,500,0,100]],
}
W={
'real_up':{'pw':2.5,'cw':0.05,'mw':0.3,'m5':3,'vb':1,'hb':0.3,'wb':2,'jb':2,'jlb':2},
'fake_up':{'pw':1.0,'cw':0.05,'mw':0.5,'m5':0,'vb':0,'hb':0,'wb':0,'jb':0,'jlb':0},
'down':{'pw':1.5,'cw':0.05,'mw':0.3,'m5':2,'vb':0,'hb':0,'wb':0,'jb':0,'jlb':3},
'flat':{'pw':1.5,'cw':0.05,'mw':0.3,'m5':2,'vb':1,'hb':0.3,'wb':0,'jb':0,'jlb':2},
}
PE=[0,-1,-2,-3,-5]

def inspect(mk):
    lvs=LV[mk]; w=W[mk]
    results=[]
    for dt in dates:
        stocks=data.get(dt,[])
        if not stocks or cm(stocks)!=mk: continue
        used=0; cand=None
        for li,lv in enumerate(lvs):
            p1,p2,v1,v2,h1,h2,sz,c1,c2=lv; ca=[]
            for s in stocks:
                code=s['code']
                if not is_main(code): continue
                p=s.get('p',0) or 0
                if p<p1 or p>p2: continue
                if p>=8: continue
                vr=s.get('vol_ratio',0) or 0
                if vr<v1 or vr>v2: continue
                ri=real.get(code)
                if not ri: continue
                hsl=(ri.get('hsl',0) or 0)
                if hsl<h1 or hsl>h2: continue
                if (ri.get('shizhi',0) or 0)>=sz: continue
                nm=names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl=s.get('cl',0)
                if cl<c1 or cl>c2: continue
                nh=s.get('n',0) or 0
                if nh<=0: continue
                dif=s.get('dif_val',0) or 0; mg=s.get('macd_golden',0)
                buy=s.get('close',0) or 0; a5=s.get('above_ma5',0) or 0
                wrv=s.get('wr_val',0) or 0; jv=s.get('j_val',0) or 0
                ms=md(dif,mg); ps2=min(10,max(1,11-buy/10)) if buy else 0
                sc=p*w['pw']+cl*w['cw']+ps2*0.3+ms*w['mw']
                sc+=(w['m5'] if a5 else 0)+(w['vb']*1.5 if 1.0<=vr<=1.5 else 0)
                sc+=(w['hb']*2 if 5<=hsl<=7 else 0)+(w['wb'] if wrv<-80 else 0)
                sc+=(w['jb'] if jv>70 else 0)+(w['jlb'] if jv<20 else 0)
                ca.append({'s':sc,'n':nh,'p':p,'nm':nm[:12],'code':code})
            if len(ca)>=10: cand=ca; used=li; break
        if not cand: cand=ca; used=len(lvs)-1
        if not cand: continue
        if PE[used]:
            for c in cand: c['s']+=PE[used]
        cand.sort(key=lambda x:(-x['s'],-x['p']))
        results.append({'dt':dt,'used':used,'pool':len(cand),
                        'champ_p':cand[0]['p'],'champ_n':cand[0]['n'],
                        'champ_nm':cand[0]['nm'],'champ_cd':cand[0]['code'],
                        'top3':[c['p'] for c in cand[:3]]})
    return results

mn={'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
for mk in ['real_up','fake_up','down','flat']:
    rs=inspect(mk)
    nd=len(rs)
    max_p=max(r['champ_p'] for r in rs)
    min_pool=min(r['pool'] for r in rs)
    avg_pool=sum(r['pool'] for r in rs)/nd
    bad_days=[r for r in rs if r['champ_p']>=8]
    no_pool=[r for r in rs if r['pool']<10]
    lv_dist={}
    for r in rs: lv_dist[r['used']]=lv_dist.get(r['used'],0)+1
    wins=sum(1 for r in rs if r['champ_n']>=2.5)
    t3=sum(1 for r in rs if any(pn>=2.5 for pn in [rr['champ_n'] for rr in rs[:3]]))  # simplified
    t3_alt=sum(1 for r in rs if any(nh>=2.5 for nh in r['top3']))
    wins=sum(1 for r in rs if r['champ_n']>=2.5)
    # rebuild proper top3 check
    all_rs=inspect(mk)
    t3w=0
    for r in all_rs:
        top3=[c['n'] for c in []]  # need rebuild
    # simpler: just check from stored results
    t3_ok=0
    for r in rs:
        # rebuild
        pass
    
    print(f"\n{'='*55}")
    print(f" {mn[mk]} ({nd}天)")
    print(f"{'='*55}")
    print(f" 冠军涨幅: 最大{max_p:+.1f}% | {'✅ 全部<8%' if max_p<8 else '❌ 有≥8%的!'}")
    print(f" 候选池:   最小{min_pool}只 | 平均{avg_pool:.0f}只 | {'✅ 全部≥10' if min_pool>=10 else f'❌ {len(no_pool)}天<10只!'}")
    print(f" 放宽级:   ", end='')
    for i in range(5): 
        if i in lv_dist: print(f"L{i}{lv_dist[i]}天 ", end='')
    print()
    if bad_days:
        print(f" ⚠️ 冠军涨幅≥8%的天:")
        for r in bad_days: print(f"   {r['dt']}: {r['champ_nm']} 涨{r['champ_p']:.1f}%")

# 重新检查最严谨：针对每个策略每天出票的冠军涨幅
print(f"\n\n{'='*55}")
print(" 最终合规报告")
print(f"{'='*55}")
all_ok=True
for mk in ['real_up','fake_up','down','flat']:
    rs=inspect(mk)
    nd=len(rs)
    max_p=max(r['champ_p'] for r in rs)
    min_pool=min(r['pool'] for r in rs)
    win=sum(1 for r in rs if r['champ_n']>=2.5)
    t3_ok=0
    for r in rs:
        all_rs=inspect(mk)  # rebuild - slow but correct
        break
    # Use stored top3 values from earlier
    # Redo inline
    pass

# Let me just redo it cleanly
print("\n 重新验证...\n")
for mk in ['real_up','fake_up','down','flat']:
    lvs=LV[mk]; w=W[mk]
    wins=0; t3w=0; nd=0; maxp=-999; minpool=999; sumpool=0
    bad_days=[]
    for dt in dates:
        stocks=data.get(dt,[])
        if not stocks or cm(stocks)!=mk: continue
        used=0; cand=None
        for li,lv in enumerate(lvs):
            p1,p2,v1,v2,h1,h2,sz,c1,c2=lv; ca=[]
            for s in stocks:
                code=s['code']
                if not is_main(code): continue
                p=s.get('p',0) or 0
                if p<p1 or p>p2: continue
                if p>=8: continue
                vr=s.get('vol_ratio',0) or 0
                if vr<v1 or vr>v2: continue
                ri=real.get(code)
                if not ri: continue
                hsl=(ri.get('hsl',0) or 0)
                if hsl<h1 or hsl>h2: continue
                if (ri.get('shizhi',0) or 0)>=sz: continue
                nm=names.get(code,'')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl=s.get('cl',0)
                if cl<c1 or cl>c2: continue
                nh=s.get('n',0) or 0
                if nh<=0: continue
                dif=s.get('dif_val',0) or 0; mg=s.get('macd_golden',0)
                buy=s.get('close',0) or 0; a5=s.get('above_ma5',0) or 0
                wrv=s.get('wr_val',0) or 0; jv=s.get('j_val',0) or 0
                ms=md(dif,mg); ps2=min(10,max(1,11-buy/10)) if buy else 0
                sc=p*w['pw']+cl*w['cw']+ps2*0.3+ms*w['mw']
                sc+=(w['m5'] if a5 else 0)+(w['vb']*1.5 if 1.0<=vr<=1.5 else 0)
                sc+=(w['hb']*2 if 5<=hsl<=7 else 0)+(w['wb'] if wrv<-80 else 0)
                sc+=(w['jb'] if jv>70 else 0)+(w['jlb'] if jv<20 else 0)
                ca.append({'s':sc,'n':nh,'p':p,'nm':nm[:12],'code':code})
            if len(ca)>=10: cand=ca; used=li; break
        if not cand: cand=ca; used=len(lvs)-1
        if not cand: continue
        if PE[used]:
            for c in cand: c['s']+=PE[used]
        cand.sort(key=lambda x:(-x['s'],-x['p']))
        nd+=1; maxp=max(maxp,cand[0]['p']); minpool=min(minpool,len(cand)); sumpool+=len(cand)
        if cand[0]['p']>=8: bad_days.append((dt,cand[0]['nm'],cand[0]['p']))
        if cand[0]['n']>=2.5: wins+=1
        if any(c['n']>=2.5 for c in cand[:3]): t3w+=1
    
    avgp=sumpool/nd if nd else 0
    status_p='✅' if maxp<8 else '❌'
    status_po='✅' if minpool>=10 else '❌'
    print(f" {mn[mk]:<10}{nd:>4}d 冠军{maxp:>+5.1f}%{status_p} 池{minpool:>3d}~{avgp:>4.0f}只{status_po} 胜率{wins:>3d}/{nd}={wins*100/nd:>4.1f}% Top3{t3w:>3d}/{nd}={t3w*100/nd:>4.1f}%")
    if bad_days:
        for dt,nm1,p in bad_days:
            print(f"          ⚠️ {dt} {nm1} 涨{p:+.1f}%")
        all_ok=False

print(f"\n 总体: {'✅ 全部合规!' if all_ok else '❌ 有违规!'}")
