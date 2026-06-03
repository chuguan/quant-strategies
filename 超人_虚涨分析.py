"""虚涨日：池子质量 vs 评分能力分析"""
import pickle, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

def cls(dt):
    st=data.get(dt,[]);
    if not st: return 'flat'
    ps=[s.get('p',0) or 0 for s in st]
    avg_p=sum(ps)/len(ps); avg_vr=sum(s.get('vol_ratio',0) or 0 for s in st)/len(st)
    hot=sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    elif avg_p<-0.5: return 'down'
    else: return 'flat'

fakes=[dt for dt in dates if cls(dt)=='fake_up']
print(f"虚涨日共{len(fakes)}天\n", flush=True)

overall=0; pool_bad=0; rank_bad=0; rank_fixable=0

for dt in fakes:
    # 标准条件（涨5~8%）
    std_cand=[]
    for s in data.get(dt,[]):
        code=s['code'];p=s['p']
        if p<5 or p>8: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<0.8 or vr>2.0: continue
        ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<5 or hsl>15: continue
        sz2=(ri.get('shizhi',0) or 0)
        if sz2>=300: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>100: continue
        cl=s.get('cl',0)
        if cl<60 or cl>90: continue
        nh=s.get('n',0) or 0
        if nh>0: std_cand.append((nh,code,p,cl,nm))
    
    # 宽松条件（涨0~8%）+ 反转信号
    wide_cand=[]
    for s in data.get(dt,[]):
        code=s['code'];p=s['p']
        if p<0 or p>8: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<0.6 or vr>3.0: continue
        ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<3 or hsl>20: continue
        sz2=(ri.get('shizhi',0) or 0)
        if sz2>=200: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>120: continue
        cl=s.get('cl',0)
        if cl<40 or cl>95: continue
        nh=s.get('n',0) or 0
        if nh>0: wide_cand.append((nh,code,p,cl,jv))
    
    # 标准池：有没好货？    
    std_good=sum(1 for c in std_cand if c[0]>=2.5)
    wide_good=sum(1 for c in wide_cand if c[0]>=2.5)
    
    # 标准池冠军是谁？
    if std_cand:
        std_best=max(std_cand, key=lambda x: x[0])
        std_champ=std_cand[0]  # 我们选的冠军（简化：涨幅排列）
    else:
        std_best=None
    
    # 宽池：我们选的冠军 vs 最好的
    wide_best_all=max(wide_cand, key=lambda x: x[0]) if wide_cand else None
    
    ok="✅" if std_cand and std_cand[0][0]>=2.5 else "❌"
    
    print(f"{dt}: std池{len(std_cand)}只(好{std_good}) 宽池{len(wide_cand)}只(好{wide_good}) 冠军{std_cand[0][0]:+.1f}%{ok} 宽池最好{wide_best_all[0]:+.1f}%", flush=True)
    
    overall+=1
    if std_good==0 and wide_good==0:
        pool_bad+=1  # 池子就没好货，怎么选都没用
        print(f"  → 池子本身没有好货！", flush=True)
    elif std_cand and std_cand[0][0]>=2.5:
        pass  # 选对了
    elif wide_good>0:
        rank_bad+=1
        rank_fixable+=1
        # 我们能选出来吗？
        if wide_best_all and wide_best_all[0]>=2.5:
            print(f"  → 拓宽后有好的({wide_best_all[3]}涨{wide_best_all[2]:+.1f}%→+{wide_best_all[0]:.1f}%)，宽池能选到！", flush=True)

print(f"\n{'='*60}", flush=True)
print(f"分析总结:", flush=True)
print(f"  池子就没好货（怎么选都没用）: {pool_bad}/{overall}天", flush=True)
print(f"  有货但标准池没选到: {rank_bad}/{overall}天", flush=True)
print(f"  拓宽后能选到的: {rank_fixable}/{overall}天", flush=True)
