"""
近30天失败日深度分析 — 每个失败日看评分为什么没选对
"""
import pickle,os,sys,json,importlib
sys.path.insert(0,os.path.dirname(__file__))
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data,real,names=d['data'],d['real'],d['names']
da=[x for x in sorted(data.keys()) if '2025-01-01'<=x<'2026-06-01']

def cm(ss):
    if not ss:return'flat'
    ps=[s.get('p',0) or 0 for s in ss]
    vrs=[s.get('vol_ratio',0) or 0 for s in ss if s.get('vol_ratio',0)]
    if not ps:return'flat'
    ap=sum(ps)/len(ps);av=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5:return'fake_up' if hot<15 or av<0.9 else'real_up'
    if ap<-0.5:return'down'
    return'flat'

MODS={
    'real_up':importlib.import_module('大道至简_真实涨日_评分策略'),
    'fake_up':importlib.import_module('大道至简_虚涨日_评分策略'),
    'down':importlib.import_module('大道至简_跌日_评分策略'),
    'flat':importlib.import_module('大道至简_横盘_评分策略'),
}
FN_NAMES={'real_up':'真实涨日_评分','fake_up':'虚涨日_评分','down':'跌日_评分','flat':'横盘_评分'}

fail_dates = ['2026-04-09','2026-04-10','2026-04-20','2026-04-24','2026-05-19','2026-05-26']

for dt in fail_dates:
    ss=data.get(dt,[])
    if not ss:continue
    mkt=cm(ss)
    mod=MODS[mkt];fn=getattr(mod,FN_NAMES[mkt]);lv=mod.LEVELS
    mkt_name={'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}[mkt]
    
    # 分级筛选
    cand=None;used_lv=''
    for l in lv:
        pool=[]
        for s in ss:
            code=s.get('code','');p=s.get('p',0) or 0
            if p<l['p_min'] or p>l['p_max']:continue
            if p>=8:continue
            vr=s.get('vol_ratio',0) or 0
            if vr<l['vr_min'] or vr>l['vr_max']:continue
            ri=real.get(code)
            if not ri:continue
            hsl=(ri.get('hsl',0) or 0)
            if hsl<l['hs_min'] or hsl>l['hs_max']:continue
            if (ri.get('shizhi',0) or 0)>=l['sz_max']:continue
            nm=names.get(code,'')
            if 'ST' in nm or '*ST' in nm or '退' in nm:continue
            cl=s.get('cl',0)
            if cl<l['cl_min'] or cl>l['cl_max']:continue
            if (s.get('n',0) or 0)<=0:continue
            pool.append(s)
        if len(pool)>8:cand=pool;used_lv=l['name'];break
    if not cand or len(cand)<=8:continue
    
    # 评分全部
    scored=[]
    for s in cand:
        bc=s.get('close',0) or 0
        stock={'p':s.get('p',0) or 0,'cl':s.get('cl',0),'vr':s.get('vol_ratio',0) or 0,
            'hsl':(real.get(s['code'],{}).get('hsl',0) or 0),'dif':s.get('dif_val',0) or 0,
            'mg':s.get('macd_golden',0) or 0,'a5':s.get('above_ma5',0) or 0,'wrv':s.get('wr_val',0) or 20,
            'jv':s.get('j_val',0) or 0,'kv':s.get('k_val',0) or 0,'dv':s.get('d_val',0) or 0,
            'kdj_g':s.get('kdj_golden',0) or 0,'buy_c':bc}
        sc=fn(stock)
        nh=s.get('n',0) or 0
        nm=names.get(s['code'],'?')[:8]
        scored.append({'nm':nm,'code':s['code'],'sc':sc,'nh':nh,
            'p':s.get('p',0) or 0,'cl':s.get('cl',0),'vr':s.get('vol_ratio',0) or 0,
            'hsl':(real.get(s['code'],{}).get('hsl',0) or 0),
            'dif':s.get('dif_val',0) or 0,'mg':s.get('macd_golden',0) or 0,
            'a5':s.get('above_ma5',0) or 0,'wrv':s.get('wr_val',0) or 20,
            'jv':s.get('j_val',0) or 0,'kdj_g':s.get('kdj_golden',0) or 0,'bc':bc})
    scored.sort(key=lambda x:(-x['sc']))
    
    champ=scored[0]
    # 找次日表现最好的票
    best=max(scored,key=lambda x:x['nh'])
    
    print(f"\n{'='*75}")
    print(f"❌ {dt} | {mkt_name} | 分级{used_lv} | 池{len(cand)}只")
    print(f"{'='*75}")
    print(f"🏆 冠军: {champ['nm']}({champ['code']})  评分{champ['sc']}")
    print(f"   涨{champ['p']:+.1f}% CL{champ['cl']:.0f} VR{champ['vr']:.2f} DIF{champ['dif']:.2f}")
    print(f"   J{champ['jv']:.0f} WR{champ['wrv']:.0f} MA5{'✅' if champ['a5'] else '❌'} 金叉{'✅' if champ['mg'] else '❌'}")
    print(f"   买入{champ['bc']:.2f} → 次日最高{champ['nh']:+.1f}% ❌")
    
    # 找应该选谁
    print(f"\n🎯 应该选谁（次日最高%最高的候选）：")
    print(f"   {best['nm']}({best['code']})  评分{best['sc']}（排第{scored.index(best)+1}名）")
    print(f"   涨{best['p']:+.1f}% CL{best['cl']:.0f} VR{best['vr']:.2f} DIF{best['dif']:.2f}")
    print(f"   J{best['jv']:.0f} WR{best['wrv']:.0f} MA5{'✅' if best['a5'] else '❌'} 金叉{'✅' if best['mg'] else '❌'}")
    print(f"   买入{best['bc']:.2f} → 次日最高{best['nh']:+.1f}% ✅")
    
    # 对比差异
    print(f"\n📊 冠军 vs 应选 差异：")
    for key,nm in [('p','涨幅%'),('cl','CL%'),('vr','量比'),('hsl','换手%'),
                    ('dif','DIF'),('mg','金叉'),('a5','MA5'),('wrv','WR'),
                    ('jv','J值'),('kdj_g','KDJ金叉'),('bc','买入价')]:
        cv=champ[key]; bv=best[key]
        diff=round(cv-bv,2) if isinstance(cv,(int,float)) else '—'
        print(f"   {nm}: 冠军={cv}  应选={bv}  差={diff}")
    
    # 评分前5名
    print(f"\n📋 评分Top5：")
    print(f"   {'#':3s} {'名称':10s} {'评分':>6s} {'涨%':>6s} {'CL':>4s} {'VR':>5s} {'J':>5s} {'DIF':>6s} {'MA5':>4s} {'金叉':>4s} {'次日最高':>8s}")
    for i,item in enumerate(scored[:5]):
        print(f"   {i+1:3d} {item['nm']:10s} {item['sc']:>6.1f} {item['p']:>+5.1f}% {item['cl']:>3.0f}% {item['vr']:>4.2f} {item['jv']:>4.0f} {item['dif']:>5.2f} {'✅' if item['a5'] else '❌':>4s} {'✅' if item['mg'] else '❌':>4s} {item['nh']:>+7.1f}%")
    
    # 次日最高达标的候选比例
    winners=[x for x in scored if x['nh']>=2.5]
    print(f"\n📌 池中达标票: {len(winners)}/{len(scored)} ({len(winners)*100/len(scored):.1f}%)")
    if winners:
        avg_p=sum(w['p'] for w in winners)/len(winners)
        avg_cl=sum(w['cl'] for w in winners)/len(winners)
        avg_vr=sum(w['vr'] for w in winners)/len(winners)
        avg_j=sum(w['jv'] for w in winners)/len(winners)
        print(f"   达标票特征: 均涨{avg_p:.1f}% 均CL{avg_cl:.0f} 均VR{avg_vr:.2f} 均J{avg_j:.0f}")

print(f"\n{'='*75}")
print(f"分析总结：6个失败日的原因")
