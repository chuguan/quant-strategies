"""4类行情分型 + 虚涨日策略 全量回测 V2（修MACD bug）"""
import pickle, os, sys

os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
print("Loading...", flush=True)
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, real, names = d['data'], d['real'], d['names']
dates = [x for x in sorted(data.keys()) if '2025-01-01' <= x < '2026-06-01']
print(f"{len(dates)}天", flush=True)

def classify_market(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    if avg_p<-0.5: return 'down'
    return 'flat'

def calc_macd(dif, mg):
    if mg and dif > 0.5: return 10
    if mg and dif > 0.2: return 8
    if mg: return 6
    if dif > 0.5: return 4
    if dif > 0: return 2
    return 0

# 虚涨日参数
FAKE_PARAMS = {'p_min':0,'p_max':6,'vr_min':0.6,'vr_max':2.5,'hs_min':5,'hs_max':20,'sz_max':200,'cl_min':30,'cl_max':95}
# 主策略参数
MAIN_PARAMS = {'p_min':5,'p_max':8,'vr_min':0.8,'vr_max':2.0,'hs_min':5,'hs_max':15,'sz_max':300,'cl_min':60,'cl_max':90}

def filter_stock(s, p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz_max,cl_min,cl_max):
    code=s['code']; p=s.get('p',0) or 0
    if p<p_min or p>p_max: return None
    vr=s.get('vol_ratio',0) or 0
    if vr<vr_min or vr>vr_max: return None
    ri=real.get(code)
    if not ri: return None
    hsl=(ri.get('hsl',0) or 0)
    if hsl<hs_min or hsl>hs_max: return None
    if (ri.get('shizhi',0) or 0)>=sz_max: return None
    nm=names.get(code,'')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return None
    cl=s.get('cl',0)
    if cl<cl_min or cl>cl_max: return None
    nh=s.get('n',0) or 0
    if nh<=0: return None
    return {
        'nm':nm,'code':code,'p':p,'cl':cl,'vr':vr,'nh':nh,
        'buy':s.get('close',0) or 0,
        'dif':s.get('dif_val',0) or 0,'mg':s.get('macd_golden',0),
        'a5':s.get('above_ma5',0) or 0,'iy':s.get('is_yang',0) or 0,
        'hsl':hsl
    }

def fake_score(x):
    ms=calc_macd(x['dif'],x['mg'])
    ps2=min(10,max(1,11-x['buy']/10)) if x['buy'] else 0
    return x['p']*1.0 + x['cl']*0.05 + ps2*0.3 + ms*0.5

def real_score(x):
    ms=calc_macd(x['dif'],x['mg'])
    ps2=min(10,max(1,11-x['buy']/10)) if x['buy'] else 0
    return x['p']*3.0 + x['cl']*0.1 + ps2*0.3 + ms*0.3 + (3 if x['a5'] else 0)

def down_score(x):
    ms=calc_macd(x['dif'],x['mg'])
    ps2=min(10,max(1,11-x['buy']/10)) if x['buy'] else 0
    return x['p']*2.0 + x['cl']*0.05 + ps2*0.3 + ms*0.3

def flat_score(x):
    return down_score(x)

champ_wins={'real_up':0,'fake_up':0,'down':0,'flat':0}
champ_total={'real_up':0,'fake_up':0,'down':0,'flat':0}
top3_wins={'real_up':0,'fake_up':0,'down':0,'flat':0}
top3_total={'real_up':0,'fake_up':0,'down':0,'flat':0}
champ_all=0; total_all=0; top3_all=0; t3all=0

for dt in dates:
    stocks=data.get(dt,[])
    if not stocks: continue
    mkt=classify_market(stocks)
    
    cand=[]
    if mkt=='fake_up':
        for s in stocks:
            x=filter_stock(s,**FAKE_PARAMS)
            if not x: continue
            x['score']=fake_score(x)
            cand.append(x)
    else:
        for s in stocks:
            x=filter_stock(s,**MAIN_PARAMS)
            if not x: continue
            if mkt=='real_up': x['score']=real_score(x)
            elif mkt=='down': x['score']=down_score(x)
            else: x['score']=flat_score(x)
            cand.append(x)
    if not cand: continue
    
    cand.sort(key=lambda x:(-x['score'],-x['p']))
    total_all+=1; t3all+=1
    champ_total[mkt]+=1; top3_total[mkt]+=1
    
    if cand[0]['nh']>=2.5: champ_all+=1; champ_wins[mkt]+=1
    if any(c['nh']>=2.5 for c in cand[:3]): top3_all+=1; top3_wins[mkt]+=1

print(f"\n{'='*60}")
print("4行情分型+虚涨日策略 V2（修MACD）")
print(f"{'='*60}")
print(f"交易日: {total_all}")
print(f"\n【总胜率】")
print(f"  冠军达标: {champ_all}/{total_all}={champ_all*100/total_all:.1f}%")
print(f"  Top3达标: {top3_all}/{t3all}={top3_all*100/t3all:.1f}%")
print(f"\n【分行情】")
for mk,nm in [('real_up','真实涨日'),('fake_up','虚涨日'),('down','跌日'),('flat','横盘')]:
    if champ_total[mk]:
        cr=champ_wins[mk]*100/champ_total[mk]
        tr=top3_wins[mk]*100/top3_total[mk]
        print(f"  {nm}: {champ_total[mk]}天 | 冠军{cr:.1f}% | Top3{tr:.1f}%")

# 旧版对比
print(f"\n【旧版对比】")
old_c=0; old_t3=0
for dt in dates:
    stocks=data.get(dt,[])
    if not stocks: continue
    cand=[]
    for s in stocks:
        x=filter_stock(s,**MAIN_PARAMS)
        if not x: continue
        x['score']=real_score(x)  # 旧版不分行情全用涨日
        cand.append(x)
    if not cand: continue
    cand.sort(key=lambda x:(-x['score'],-x['p']))
    if cand[0]['nh']>=2.5: old_c+=1
    if any(c['nh']>=2.5 for c in cand[:3]): old_t3+=1
print(f"  旧版冠军: {old_c}/{total_all}={old_c*100/total_all:.1f}%")
print(f"  新版冠军: {champ_all}/{total_all}={champ_all*100/total_all:.1f}% (diff {champ_all-old_c:+d})")
print(f"  旧版Top3: {old_t3}/{t3all}={old_t3*100/t3all:.1f}%")
print(f"  新版Top3: {top3_all}/{t3all}={top3_all*100/t3all:.1f}% (diff {top3_all-old_t3:+d})")
