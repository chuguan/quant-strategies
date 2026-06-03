"""跌日优化 — 沪深主板A股 + 涨<8% + 池≥10"""
import pickle, os, sys
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if '2025-01-01'<=x<'2026-06-01']

def cm(stocks):
    if not stocks: return 'flat'
    ps=[s.get('p',0) or 0 for s in stocks]
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    avg_p=sum(ps)/len(ps); avg_vr=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    if avg_p<-0.5: return 'down'
    return 'flat'

dd=[dt for dt in dates if cm(data.get(dt,[]))=='down']
print(f'跌日{len(dd)}天\n')

def is_main_board(code):
    """沪深主板A股：排除300/688/8开头"""
    return not (code.startswith('sz300') or code.startswith('sh688') or code.startswith('sh8'))

def md(dif,mg):
    if mg and dif>0.5: return 10
    if mg and dif>0.2: return 8
    if mg: return 6
    if dif>0.5: return 4
    if dif>0: return 2
    return 0

def run(p1,p2,v1,v2,h1,h2,sz,c1,c2,fn,req_pool=0,show_top=0):
    w=0; tc=0; pc=0
    for dt in dd:
        ca=[]
        for s in data.get(dt,[]):
            code=s['code']
            if not is_main_board(code): continue
            p=s.get('p',0) or 0
            if p<p1 or p>p2: continue
            if p>=8: continue  # 涨<8硬性
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
            fn_rs=fn(s,ri)
            if fn_rs is None: continue
            ca.append((fn_rs,nh,p))
        if len(ca)<10:
            pc+=1
            if req_pool: continue
        if not ca: continue
        ca.sort(key=lambda x:(-x[0],-x[2]))
        tc+=1
        if ca[0][1]>=2.5: w+=1
    return w,tc,pc

# ===== 各评分函数 =====
def s_cur(s,ri):
    """当前跌日评分"""
    p=s.get('p',0) or 0; cl=s.get('cl',0); dif=s.get('dif_val',0) or 0; mg=s.get('macd_golden',0)
    buy=s.get('close',0) or 0; a5=s.get('above_ma5',0) or 0
    ms=md(dif,mg); ps2=min(10,max(1,11-buy/10)) if buy else 0
    return p*2.0+cl*0.05+ps2*0.3+ms*0.3+(2 if a5 else 0)

def s_v20(s,ri):
    """虚涨日评分"""
    dif=s.get('dif_val',0) or 0; mg=s.get('macd_golden',0); buy=s.get('close',0) or 0
    p=s.get('p',0) or 0; cl=s.get('cl',0)
    ms=md(dif,mg); ps2=min(10,max(1,11-buy/10)) if buy else 0
    return p*1.0+cl*0.05+ps2*0.3+ms*0.5

def s_real(s,ri):
    """真实涨日评分(全)"""
    p=s.get('p',0) or 0; cl=s.get('cl',0); dif=s.get('dif_val',0) or 0; mg=s.get('macd_golden',0)
    buy=s.get('close',0) or 0; a5=s.get('above_ma5',0) or 0; wrv=s.get('wr_val',0) or 0
    jv=s.get('j_val',0) or 0; hsl=(ri.get('hsl',0) or 0); vr=s.get('vol_ratio',0) or 0
    ms=md(dif,mg); ps2=min(10,max(1,11-buy/10)) if buy else 0
    return p*2.5+cl*0.05+ps2*0.3+ms*0.3+(3 if a5 else 0)+(1.5 if 1.0<=vr<=1.5 else 0)+(0.6 if 5<=hsl<=7 else 0)+(2 if wrv<-80 else 0)+(2 if jv>70 else 0)+(2 if jv<20 else 0)

def s_flat(s,ri):
    """横盘评分"""
    p=s.get('p',0) or 0; cl=s.get('cl',0); dif=s.get('dif_val',0) or 0; mg=s.get('macd_golden',0)
    buy=s.get('close',0) or 0; a5=s.get('above_ma5',0) or 0; jv=s.get('j_val',0) or 0
    hsl=(ri.get('hsl',0) or 0); vr=s.get('vol_ratio',0) or 0
    ms=md(dif,mg); ps2=min(10,max(1,11-buy/10)) if buy else 0
    return p*1.5+cl*0.05+ps2*0.3+ms*0.3+(2 if a5 else 0)+(1.5 if 1.0<=vr<=1.5 else 0)+(0.6 if 5<=hsl<=7 else 0)+(2 if jv<20 else 0)

def s_v10(s,ri):
    """旧版v10涨日"""
    dif=s.get('dif_val',0) or 0; mg=s.get('macd_golden',0); buy=s.get('close',0) or 0
    a5=s.get('above_ma5',0) or 0; p=s.get('p',0) or 0; cl=s.get('cl',0)
    ms=md(dif,mg); ps2=min(10,max(1,11-buy/10)) if buy else 0
    return p*3.0+cl*0.1+ps2*0.3+ms*0.3+(3 if a5 else 0)

def s_lib(s,ri):
    """策略库评分"""
    p=s.get('p',0) or 0; cl=s.get('cl',0); dif=s.get('dif_val',0) or 0; mg=s.get('macd_golden',0)
    buy=s.get('close',0) or 0; a5=s.get('above_ma5',0) or 0; hsl=(ri.get('hsl',0) or 0)
    ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
    close=s.get('close',0) or 0
    ms=md(dif,mg); ps2=min(10,max(1,11-buy/10)) if buy else 0
    dt=0.9 if ma5>ma10>ma20 and ma5>close*0.98 else 0
    hslb=0.6 if 5<=hsl<=7 else 0
    return p*2.5+cl*0.1+ps2*0.3+ms*0.3+3*a5+hslb+dt

def s_jrev(s,ri):
    """J值反转"""
    p=s.get('p',0) or 0; cl=s.get('cl',0); dif=s.get('dif_val',0) or 0; mg=s.get('macd_golden',0)
    buy=s.get('close',0) or 0; jv=s.get('j_val',0) or 0; a5=s.get('above_ma5',0) or 0
    ms=md(dif,mg); ps2=min(10,max(1,11-buy/10)) if buy else 0
    return p*1.5+cl*0.05+ps2*0.3+ms*0.3+(2 if a5 else 0)+(3 if jv<20 else 0)

def s_wr(s,ri):
    """WR超卖"""
    p=s.get('p',0) or 0; cl=s.get('cl',0); dif=s.get('dif_val',0) or 0; mg=s.get('macd_golden',0)
    buy=s.get('close',0) or 0; a5=s.get('above_ma5',0) or 0; wrv=s.get('wr_val',0) or 0
    ms=md(dif,mg); ps2=min(10,max(1,11-buy/10)) if buy else 0
    return p*2.0+cl*0.05+ps2*0.3+ms*0.3+(2 if a5 else 0)+(2 if wrv<-80 else 0)

tests=[
    ("当前跌日-1~7", (-1,7,0.6,2.5,3,20,200,30,90), s_cur),
    ("虚涨日全套0~6", (0,6,0.6,2.5,5,20,200,30,95), s_v20),
    ("真实涨日全套3~7", (3,7,0.6,2.5,5,15,200,60,90), s_real),
    ("横盘全套0~7", (0,7,0.6,2.5,3,20,200,40,95), s_flat),
    ("旧版v10涨5~7", (5,7,0.8,2.0,5,15,300,60,90), s_v10),
    ("策略库4~7", (4,7,0.6,2.5,3,20,300,50,95), s_lib),
    ("J值反转-1~7", (-1,7,0.6,2.5,3,20,200,30,90), s_jrev),
    ("WR超卖-1~7", (-1,7,0.6,2.5,3,20,200,30,90), s_wr),
    ("放宽池+虚涨评分", (-2,7,0.5,3.0,2,25,200,20,95), s_v20),
    ("放宽池+横盘评分", (-2,7,0.5,3.0,2,25,200,20,95), s_flat),
    ("放宽池+J值反转", (-2,7,0.5,3.0,2,25,200,20,95), s_jrev),
    ("放宽池+WR超卖", (-2,7,0.5,3.0,2,25,200,20,95), s_wr),
    ("大放宽+J值反转", (-3,7,0.4,3.5,1,30,300,10,98), s_jrev),
    ("大放宽+WR超卖", (-3,7,0.4,3.5,1,30,300,10,98), s_wr),
]

print(f"{'冠军':>6} {'天':>3} {'缺池':>3} {'覆盖':>5} {'策略'}")
print(f"{'-'*6} {'-'*3} {'-'*3} {'-'*5} {'-'*50}")
for name,par,fn in tests:
    w,tc,pc=run(*par,fn,req_pool=0)
    r=w*100/tc if tc else 0
    cv=tc*100/(tc+pc) if tc+pc else 0
    print(f"{r:5.1f}% {tc:3d} {pc:3d} {cv:4.0f}% | {name}")

print(f"\n{'='*60}")
print("池≥10约束下最优:")
print(f"{'冠军':>6} {'天':>3} {'缺池':>3} {'策略'}")
print(f"{'-'*6} {'-'*3} {'-'*3} {'-'*50}")
best_r=0; best_name=None
for name,par,fn in tests:
    w,tc,pc=run(*par,fn,req_pool=10)
    r=w*100/tc if tc else 0
    print(f"{r:5.1f}% {tc:3d} {pc:3d} | {name}")
    if r>best_r: best_r=r; best_name=name
print(f"\n🏆 最优: {best_name} = {best_r:.1f}%")
