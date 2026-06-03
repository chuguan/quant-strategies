"""横盘快速测试 — 已有策略+WR"""
import pickle, os
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if '2024-01-01'<=x<'2026-06-01']
def mb(c): return not (c.startswith('sz300') or c.startswith('sh688') or c.startswith('sh8'))
def cm(s):
    if not s: return 'flat'
    ps=[x.get('p',0) or 0 for x in s]
    vrs=[x.get('vol_ratio',0) or 0 for x in s if x.get('vol_ratio',0)]
    ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0; ht=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if ht<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'
fd=[]
for dt in dates:
    stocks=data.get(dt,[])
    if not stocks: continue
    if cm(stocks)=='flat': fd.append(dt)
print(f'横盘{len(fd)}天', flush=True)

def md(d,m):
    if m and d>0.5: return 10
    if m and d>0.2: return 8
    if m: return 6
    if d>0.5: return 4
    if d>0: return 2
    return 0

def test(name, p1,p2,v1,v2,h1,h2,sz,c1,c2,pw,cw,mw,m5,vb,hb,wb,jb,jlb):
    w=0; tc=0
    for dt in fd:
        ca=[]
        for s in data.get(dt,[]):
            code=s['code']
            if not mb(code): continue
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
            sc=p*pw+cl*cw+ps2*0.3+ms*mw
            sc+=(m5 if a5 else 0)+(vb*1.5 if 1.0<=vr<=1.5 else 0)+(hb*2 if 5<=hsl<=7 else 0)
            sc+=(wb if wrv<-80 else 0)+(jb if jv>70 else 0)+(jlb if jv<20 else 0)
            ca.append((sc,nh))
        if len(ca)<10: continue
        ca.sort(key=lambda x:-x[0]); tc+=1
        if ca[0][1]>=2.5: w+=1
    r=w*100/tc if tc else 0
    print(f'{w:3d}/{tc:3d}={r:5.1f}% | {name}', flush=True)

print(f'\n{"测试":<40} {"冠军":>8}', flush=True)
print('-'*50, flush=True)

# 当前横盘
test('当前横盘', 0,7,0.6,2.5,3,20,200,40,95, 1.5,0.05,0.3,2,1,0.3,0,0,2)

# 尝试加WR
test('横盘+WR+2', 0,7,0.6,2.5,3,20,200,40,95, 1.5,0.05,0.3,2,1,0.3,2,0,2)
test('横盘+WR+1', 0,7,0.6,2.5,3,20,200,40,95, 1.5,0.05,0.3,2,1,0.3,1,0,2)

# 降低涨幅权重+WR
test('涨x1.0+WR+2', 0,7,0.6,2.5,3,20,200,40,95, 1.0,0.05,0.3,2,1,0.3,2,0,2)
test('涨x1.0+WR+2无VR', 0,7,0.6,2.5,3,20,200,40,95, 1.0,0.05,0.3,2,0,0.3,2,0,2)
test('涨x2.0+WR+2', 0,7,0.6,2.5,3,20,200,40,95, 2.0,0.05,0.3,2,0,0,2,0,2)

# 放宽选股
test('宽池+WR+2', 0,7,0.6,2.5,3,25,300,30,95, 1.5,0.05,0.3,2,1,0.3,2,0,2)
test('更宽+WR+2', 0,7,0.5,3.0,2,25,300,30,95, 1.5,0.05,0.3,2,1,0.3,2,0,2)

# 纯WR反转（类似跌日J值反转的思路）
test('WR主导', 0,7,0.6,2.5,3,20,200,40,95, 1.5,0.05,0.3,2,0,0,3,0,0)
test('WR+J<20', 0,7,0.6,2.5,3,20,200,40,95, 1.5,0.05,0.3,2,0,0,2,0,3)
test('无MACD+WR', 0,7,0.6,2.5,3,20,200,40,95, 1.5,0.05,0,2,1,0.3,2,0,2)

# 尝试其他选股范围
test('窄涨0~6%+WR', 0,6,0.6,2.5,3,20,200,40,95, 1.5,0.05,0.3,2,1,0.3,2,0,2)
test('小市值+WR', 0,7,0.6,2.5,3,20,100,40,95, 1.5,0.05,0.3,2,1,0.3,2,0,2)
test('高CL+WR', 0,7,0.6,2.5,3,20,200,60,95, 1.5,0.05,0.3,2,1,0.3,2,0,2)
